"""CareerOS Radar — proactive opportunity detection.
Daily (or on demand): fetch legal sources → dedupe → 1 AI call per NEW offer (IPS Radar,
same official formula) → A/B/C + explanation. Full pack only when the member asks.
Collections: radar_settings, radar_offers (dedupe per member), radar_runs."""
import asyncio
import hashlib
import logging
import os
import re
import uuid
from datetime import datetime, timedelta, timezone
from typing import List

import httpx
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field, field_validator

from . import radar_rules as RR
from . import radar_sources as S
from . import radar_discovery as D
from . import radar_auto as AU
from .decision_report import build_decision_report
from .ips import compute_ips
from .prompts import SYSTEM

logger = logging.getLogger("careeros.radar")
DAILY_LIMIT = int(os.environ.get("RADAR_DAILY_LIMIT", "50"))
DEFAULT_SOURCES = ["jooble", "workday", "boards"]
AI_TOP = int(os.environ.get("RADAR_AI_TOP") or 5)  # AI confirmation of the best rule-scored offers, per member per day
DEEP_LIMIT = int(os.environ.get("RADAR_DEEP_LIMIT") or 20)  # extra on-demand AI analyses per member per day
ACTIVE_DAYS = 7
SOURCE_RANK = {"workday": 0, "successfactors": 0, "oracle": 1, "ukg": 1, "taleo": 1, "amazon": 1, "avature": 2, "phenom": 2, "schema": 1, "taleobe": 2, "smartrecruiters": 1, "icims": 2, "greenhouse": 2, "lever": 2, "ashby": 2,
               "jooble": 3, "adzuna": 4}


def _source_rank(o: dict) -> int:
    return SOURCE_RANK.get(o.get("source"), 3)
JOOBLE_COMPANY_LIMIT = 20


_BG = set()


def _day_start() -> str:
    """Midnight America/Toronto (the member's day), as a UTC ISO string."""
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Toronto")).replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat()


def _now():
    return datetime.now(timezone.utc)


class Company(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    portal_url: str = Field(default="", max_length=400)
    kind: str = Field(default="", pattern="^(|workday|successfactors|oracle|icims|ukg|taleo|avature|phenom|schema|taleobe|greenhouse|lever|ashby|smartrecruiters|amazon)$")
    slug: str = Field(default="", max_length=200)
    website: str = Field(default="", max_length=200)
    detected: str = Field(default="", max_length=160)
    auto: bool = False
    auto_block: List[str] = []
    checked_at: str = ""


class RadarSettings(BaseModel):
    enabled: bool = True
    keywords: List[str] = []
    location: str = "Québec"
    companies: List[Company] = Field(default=[], max_length=100)
    sources: List[str] = DEFAULT_SOURCES
    expand: bool = True  # recherche élargie : famille de titres FR/EN générée à partir des mots-clés

    @field_validator("companies", mode="before")
    @classmethod
    def _names(cls, v):
        return [{"name": c} if isinstance(c, str) else c for c in v or []]

    @field_validator("sources")
    @classmethod
    def _sources(cls, v):
        return [x for x in dict.fromkeys(v) if x in ("jooble", "workday", "boards", "adzuna")]


def _normalize(s: dict) -> dict:
    """Migrate V2.0 settings (string companies + separate boards) to configurable companies."""
    comps = [c if isinstance(c, dict) else {"name": c} for c in s.get("companies") or []]
    legacy = s.pop("boards", None)
    for b in legacy or []:
        hit = next((c for c in comps if c["name"].lower() == (b.get("company") or "").lower()), None)
        if hit:
            hit.update(kind=b["kind"], slug=b["slug"])
        else:
            comps.append({"name": b.get("company") or b["slug"], "kind": b["kind"], "slug": b["slug"]})
    srcs = [x for x in s.get("sources") or DEFAULT_SOURCES if x in ("jooble", "workday", "boards", "adzuna")]
    if legacy is not None and "workday" not in srcs:
        srcs.append("workday")
    return {**s, **RadarSettings(**{**s, "companies": comps, "sources": srcs}).model_dump()}


def _key(o: dict) -> str:
    norm = lambda x: re.sub(r"[^a-z0-9]", "", (x or "").lower())  # noqa: E731
    return hashlib.sha1(f"{norm(o['title'])}|{norm(o['company'])}|{norm(o['location'])[:20]}".encode()).hexdigest()


def radar_prompt(cv: str, offer: dict, profile: dict):
    goals = ", ".join(profile.get("goals") or []) or "non précisés"
    return SYSTEM, f"""OBJECTIFS DU MEMBRE : {goals} · POSTES VISÉS : {profile.get('target_roles') or 'non précisés'}
CV :
{cv[:4000]}

OFFRE : {offer['title']} — {offer['company']} — {offer['location']}
{offer['description'][:3000]}

Tu es le moteur IPS RADAR de CareerOS (tri rapide). Renvoie UNIQUEMENT un JSON valide :
{{"ips_criteria": {{"adequation_profil": {{"score": 0-10, "justification": "..."}}, "experience": {{...}}, "competences": {{...}},
 "certifications": {{...}}, "concurrence": {{"score": 0-10, "justification": "10 = faible concurrence"}}, "qualite_cv": {{...}}, "signaux_marche": {{...}}}},
 "knockout": {{"present": true/false, "detail": ""}}, "goal_fit": {{"score": 0-10, "justification": "5 si objectifs non précisés"}},
 "decision_summary": "1-2 phrases : postuler / optimiser / éviter et pourquoi", "reasons_apply": ["max 3"], "reasons_avoid": ["max 3"],
 "ats": {{"keywords_missing": ["max 5"]}},
 "requirements": [{{"label": "exigence explicite de l'offre (max 10)", "status": "ok|missing|unknown", "evidence": "preuve tirée du CV ou raison"}}]}}
Ne donne AUCUN score global ni estimation chiffrée d'IPS : CareerOS calcule l'IPS officiel.{EXCERPT_NOTE if is_excerpt(offer) else ""}"""


EXCERPT_NOTE = ("\nATTENTION : seul un EXTRAIT de l'offre est disponible (agrégateur). Ne pénalise pas une information absente de l'extrait : "
                "note 5 (neutre) un critère non vérifiable, et ne déclare une exigence éliminatoire que si elle est explicitement écrite.")


def is_excerpt(offer: dict) -> bool:
    return offer.get("source") == "jooble" or len(offer.get("description") or "") < 600


def rescore_radar(o: dict) -> tuple:
    """Recompute a stored V2.0 Radar IPS with the radar calibration, from the AI grades already stored (no AI call)."""
    old, rep = o["ips"], o.get("decision_report") or {}
    crit = {r["key"]: {"score": r["score"], "justification": r["justification"]} for r in old["criteria"] if r["source"] in ("ia",)}
    ips = compute_ips(crit, {"present": old.get("knockout"), "detail": old.get("knockout_detail", "")}, {"score": old.get("goal_fit")},
                      o.get("posted_at"), "aucun", False, stage="radar")
    rest = re.sub(r"^IPS officiel CareerOS : \d+/100 — priorité [ABC]\.\s*", "", rep.get("summary", ""))
    new = build_decision_report(ips, {"decision_summary": rest, "ats": {"keywords_missing": rep.get("keywords_to_add") or []}})
    new["actions"] = rep.get("actions") or new["actions"]
    return ips, new


def create_radar_router(db, current_user, generate_text, parse_json, careeros_router):
    router = APIRouter(prefix="/api/careeros/radar", tags=["radar"])

    async def _settings(user_id: str, profile: dict) -> dict:
        s = await db.radar_settings.find_one({"user_id": user_id}, {"_id": 0})
        if s:
            return _normalize(s)
        roles = [r.strip() for r in re.split(r"[,;/]", profile.get("target_roles") or "") if r.strip()]
        return {"user_id": user_id, **RadarSettings(keywords=roles[:5], location=profile.get("location") or "Québec").model_dump()}

    def _active_sources(st: dict) -> list:
        conf = S.configured()
        return [x for x in st["sources"] if conf.get(x)]

    async def _analyzed_today(user_id: str) -> int:
        start = _day_start()
        return await db.radar_offers.count_documents({"user_id": user_id, "analyzed_at": {"$gte": start}, "source": {"$ne": "externe"}})

    async def _fetch(st: dict) -> tuple:
        offers, errors = [], {}
        kw = st.get("keywords") or []
        terms = (RR.expand_terms(kw) if st.get("expand", True) else kw[:3]) or ["analyste"]  # one Jooble query per term (joined = AND search)
        srcs, comps = _active_sources(st), [c for c in st["companies"] if c.get("enabled", True)]
        comps.sort(key=lambda co: bool(co.get("kind") and co.get("slug")))  # Jooble fallback first for companies without a readable portal
        sem = asyncio.Semaphore(6)

        async def limited(coro):
            async with sem:
                return await coro
        async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as c:
            tasks = []  # (label, company filter or None, coroutine)
            if "adzuna" in srcs:
                tasks += [("adzuna", None, S.adzuna(c, " ".join(terms[:2]), st["location"]))]
                tasks += [(f"adzuna:{co['name']}", co["name"], S.adzuna(c, " ".join(terms[:2]), st["location"], co["name"])) for co in comps[:JOOBLE_COMPANY_LIMIT]]
            if "jooble" in srcs:
                tasks += [(f"jooble:{t}#{pg}", None, S.jooble(c, t, st["location"], page=pg)) for t in terms for pg in (1, 2)]
                tasks += [(f"jooble:{co['name']}", co["name"], S.jooble(c, "", st["location"], co["name"])) for co in comps[:JOOBLE_COMPANY_LIMIT]]
            for co in comps:
                if co.get("kind") and co.get("slug") and ("workday" if co["kind"] == "workday" else "boards") in srcs:
                    tasks += [(f"{co['kind']}:{co['name']}", None, S.board(c, co["kind"], co["slug"], co["name"], kw))]
            res = await asyncio.gather(*(limited(t) for _, _, t in tasks), return_exceptions=True)
        jooble_raw, jooble_ok = 0, 0
        portals = {}
        for (name, company, _), r in zip(tasks, res):
            kind = name.split(":", 1)[0]
            if kind in S.PORTAL_KINDS:
                portals[name.split(":", 1)[1]] = {"kind": kind, "ok": not isinstance(r, Exception), "fetched": 0 if isinstance(r, Exception) else len(r),
                                                  "error": (str(r) or type(r).__name__)[:160] if isinstance(r, Exception) else "",
                                                  "blocked": isinstance(r, Exception) and D.is_blocked(r)}
                pv = portals[name.split(":", 1)[1]]
                pv["quality"] = S.quality(kind, pv["ok"], pv["blocked"])
            if isinstance(r, Exception):
                errors[name] = (str(r) or type(r).__name__)[:160]
                continue
            if name.startswith("jooble"):
                jooble_raw, jooble_ok = jooble_raw + len(r), jooble_ok + 1
            for o in r:
                if company and not S.company_match(o, company):
                    continue
                if (company or o["source"] in ("greenhouse", "lever", "ashby", "icims", "taleo", "avature", "phenom", "schema", "taleobe")) and not S.matches(o, terms if st.get("expand", True) else kw):
                    continue
                offers.append(o)
        if jooble_ok and not jooble_raw:
            errors["jooble"] = (f"Jooble ({S.JOOBLE_HOST}) n'a renvoyé aucune offre pour « {st['location']} ». "
                                f"Vérifiez que la clé a été obtenue sur {S.JOOBLE_HOST}/api/about (les clés Jooble sont propres à chaque pays).")
        errors["_portals"] = portals
        return offers, errors

    async def _store(doc: dict, d: dict, method: str):
        ips = compute_ips(d.get("ips_criteria"), d.get("knockout"), d.get("goal_fit"), doc.get("posted_at"), "aucun", False, stage="radar")
        ips["method"] = method
        report = build_decision_report(ips, d)
        now = _now().isoformat()
        upd = {"ips": ips, "decision_report": report, "excerpt": is_excerpt(doc), "method": method,
               "reasons_apply": (d.get("reasons_apply") or [])[:3], "reasons_avoid": (d.get("reasons_avoid") or [])[:3]}
        reqs = [{"label": str(r.get("label", ""))[:120], "status": r.get("status") if r.get("status") in ("ok", "missing", "unknown") else "unknown",
                 "evidence": str(r.get("evidence", ""))[:200], "source": method} for r in (d.get("requirements") or []) if isinstance(r, dict) and r.get("label")][:16]
        upd["requirements_rules" if method == "regles" else "requirements_ai"] = reqs
        upd["analyzed_at" if method == "regles" else "ai_analyzed_at"] = now
        if not doc.get("analyzed_at"):
            upd["analyzed_at"] = now
        await db.radar_offers.update_one({"id": doc["id"]}, {"$set": upd})
        return ips

    async def _rules(doc: dict, cv: str, profile: dict, keywords: list):
        return await _store(doc, RR.score_offer(doc, cv, profile, keywords), "regles")

    async def _analyze(doc: dict, cv: str, profile: dict):
        sysm, txt = radar_prompt(cv, doc, profile)
        d = parse_json((await generate_text(sysm, txt)).strip()) or {}
        if not d.get("ips_criteria"):
            raise ValueError("Réponse IA illisible")
        return await _store(doc, d, "ia")

    async def _ai_today(user_id: str) -> int:
        start = _day_start()
        return await db.radar_offers.count_documents({"user_id": user_id, "ai_analyzed_at": {"$gte": start}})

    async def run_for_user(user_id: str, trigger: str) -> dict:
        profile = await db.career_profiles.find_one({"user_id": user_id}, {"_id": 0}) or {}
        cv = (profile.get("cv_text") or "").strip()
        st = await _settings(user_id, profile)
        run = {"id": str(uuid.uuid4()), "user_id": user_id, "at": _now().isoformat(), "trigger": trigger,
               "fetched": 0, "new": 0, "known": 0, "analyzed": 0, "skipped_limit": 0, "tracked": True, "errors": {}, "sources": S.configured(),
               "selected_sources": st["sources"], "by_source": {g: {"fetched": 0, "analyzed": 0} for g in ("jooble", "workday", "boards", "adzuna")},
               "status": "running"}
        await db.radar_runs.insert_one(dict(run))
        if len(cv) < 80:
            run["errors"]["cv"] = "Ajoutez votre CV dans la Career Memory pour activer le Radar."
        else:
            offers, run["errors"] = await _fetch(st)
            run["portals"] = run["errors"].pop("_portals", {})
            for pname, pv in run["portals"].items():
                pv["matched"] = sum(1 for o in offers if o["source"] == pv["kind"] and o.get("company") == pname)
            seen, fresh = set(), []
            for o in offers:
                k = _key(o)
                if k in seen:
                    continue
                seen.add(k)
                run["by_source"][S.group(o["source"])]["fetched"] += 1
                existing = await db.radar_offers.find_one({"user_id": user_id, "dedupe_key": k}, {"_id": 0, "id": 1})
                if existing:
                    run["known"] += 1
                    await db.radar_offers.update_one({"id": existing["id"]}, {"$set": {"last_seen": _now().isoformat()}, "$addToSet": {"seen_runs": run["id"]}})
                    continue
                doc = {"id": str(uuid.uuid4()), "user_id": user_id, "dedupe_key": k, **o, "first_seen": _now().isoformat(),
                       "last_seen": _now().isoformat(), "run_id": run["id"], "seen_runs": [run["id"]], "status": "nouvelle", "ips": None, "decision_report": None,
                       "analyzed_at": None, "application_id": None}
                await db.radar_offers.insert_one(dict(doc))
                fresh.append(doc)
            run["fetched"], run["new"] = len(seen), len(fresh)
            budget = max(0, DAILY_LIMIT - await _analyzed_today(user_id))
            fresh_ids = {d["id"] for d in fresh}
            backlog = [d async for d in db.radar_offers.find({"user_id": user_id, "ips": None, "status": "nouvelle"}, {"_id": 0}).sort("first_seen", -1).limit(DAILY_LIMIT * 4)
                       if d["id"] not in fresh_ids]  # offers deferred by an earlier daily limit
            roles = (st.get("keywords") or []) + [r for r in re.split(r"[,;/\n]", profile.get("target_roles") or "") if r.strip()]
            rank = lambda d: (-round(RR.title_relevance(d.get("title", ""), roles), 1), _source_rank(d))  # noqa: E731 - closest titles analysed first
            queue = sorted(fresh, key=rank) + sorted(backlog, key=rank)
            todo, run["skipped_limit"] = queue[:budget], max(0, len(queue) - budget)
            run["budget"] = budget
            if queue and not budget:
                run["errors"]["limite"] = (f"Limite de {DAILY_LIMIT} analyses par jour déjà atteinte depuis minuit (heure de Toronto) : "
                                           "les offres sont reportées au prochain passage.")
            scored = []
            for doc in todo:  # free deterministic pre-scoring
                scored.append((await _rules(doc, cv, profile, st.get("keywords") or []), doc))
                run["by_source"][S.group(doc["source"])]["analyzed"] += 1
            run["analyzed"] = len(scored)
            start = _day_start()
            pool = [d async for d in db.radar_offers.find({"user_id": user_id, "method": "regles", "analyzed_at": {"$gte": start},
                                                           "ips.knockout": False, "status": "nouvelle"}, {"_id": 0}).sort("ips.score", -1)]
            pool.sort(key=lambda d: (-d["ips"]["score"], _source_rank(d)))
            ai_todo = pool[:max(0, AI_TOP - await _ai_today(user_id))]
            fails, run["ai_analyzed"] = {"n": 0}, 0
            for doc in ai_todo:  # AI confirmation of the best offers of the day only
                if fails["n"] >= 3:  # AI service down: offers stay rule-scored
                    break
                try:
                    await _analyze(doc, cv, profile)
                    run["ai_analyzed"] += 1
                    fails["n"] = 0
                except Exception as e:  # noqa: BLE001
                    fails["n"] += 1
                    logger.warning("radar AI analyze %s failed: %s", doc["id"], e)
            if fails["n"] >= 3:
                run["errors"]["ia"] = ("Service IA du serveur indisponible : les meilleures offres restent pré-analysées par règles ; "
                                       "relancez l'analyse approfondie plus tard.")
        run["status"], run["finished_at"] = "done", _now().isoformat()
        await db.radar_runs.update_one({"id": run["id"]}, {"$set": run})
        return run

    # ---------------- Member endpoints ----------------
    @router.get("/settings")
    async def get_settings(user: dict = Depends(current_user)):
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        st = await _settings(user["id"], profile)
        return {**st, "configured": S.configured(), "daily_limit": DAILY_LIMIT, "expanded": RR.expand_terms(st.get("keywords") or [])}

    class CompareBody(BaseModel):
        lines: str = Field(max_length=4000)

    @router.post("/compare")
    async def compare(body: CompareBody, user: dict = Depends(current_user)):
        """Compare offers seen elsewhere (e.g. LinkedIn, typed by the member) with what the Radar found and scored."""
        items = []
        for ln in [x.strip() for x in body.lines.splitlines() if x.strip()][:12]:
            parts = [p.strip(" -–—|:•") for p in re.split(r"\s+[-–—|:]\s+|\t", ln, maxsplit=1)]
            items.append({"company": parts[0], "title": parts[1] if len(parts) > 1 else ""})
        if not items:
            raise HTTPException(status_code=422, detail="Indiquez une offre par ligne : « Entreprise – Titre ».")
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        st = await _settings(user["id"], profile)
        terms = RR.expand_terms(st.get("keywords") or []) if st.get("expand", True) else (st.get("keywords") or [])[:3]
        since = (_now() - timedelta(days=45)).isoformat()
        offers = [o async for o in db.radar_offers.find({"user_id": user["id"], "last_seen": {"$gte": since}}, {"_id": 0, "description": 0, "dedupe_key": 0, "user_id": 0})]
        def cn(x):
            return set(re.findall(r"[a-z0-9]+", RR.norm(re.sub(r"(?i)\b(inc|lt[ée]e|ltd|limited|canada|express|group|groupe|corporation|corp|the)\b\.?", "", x or ""))))

        def same(a, b):
            return bool(a and b and (a <= b or b <= a))

        async def one(it):
            co = cn(it["company"])
            follow = next((c for c in st["companies"] if same(co, cn(c["name"]))), None)
            cover = ({"state": "portail", "label": f"Suivie · portail {D.KIND_LABEL.get(follow['kind'], follow['kind'])}"} if follow and follow.get("kind")
                     else {"state": "jooble", "label": "Suivie · via Jooble" + (f" ({follow['detected']})" if follow.get("detected") else "")} if follow
                     else {"state": "aucune", "label": "Non suivie : couverte seulement par les recherches Jooble générales"})
            cands = [o for o in offers if same(co, cn(o.get("company")))]
            best = max(cands, key=lambda o: RR.title_relevance(o["title"], [it["title"]]) if it["title"] else 1, default=None)
            if best and it["title"] and RR.title_relevance(best["title"], [it["title"]]) < 0.4:
                best = None
            res = {**it, "coverage": cover, "in_terms": bool(it["title"]) and RR.title_relevance(it["title"], terms) >= 0.5}
            if best:
                ips = best.get("ips") or {}
                total = sum(r["weight"] for r in ips.get("criteria", [])) or 1
                lost = sorted(ips.get("criteria", []), key=lambda r: r["points"] - r["weight"])[:3]
                status = ("pack" if best["status"] == "pack" else "ignoree" if best["status"] == "ignoree" else "reportee" if not ips
                          else "eliminee" if ips.get("knockout") else f"priorite_{ips.get('priority', 'C').lower()}")
                return {**res, "found": True, "status": status, "offer": {k: best.get(k) for k in ("id", "title", "company", "location", "source", "method", "first_seen")},
                        "ips": ips.get("score"), "priority": ips.get("priority"), "knockout": ips.get("knockout_detail") if ips.get("knockout") else "",
                        "losses": [{"label": r["label"], "lost": round((r["weight"] - r["points"]) * 100 / total, 1), "why": r["justification"]} for r in lost]}
            jooble = None
            if S.configured()["jooble"] and it["title"]:
                try:
                    async with httpx.AsyncClient(timeout=S.TIMEOUT) as c:
                        hits = await S.jooble(c, it["title"], st["location"])
                    jooble = any(same(co, cn(h["company"])) for h in hits)
                except Exception:  # noqa: BLE001
                    jooble = None
            why = ("Présente sur Jooble pour ce titre, mais le titre n'est pas dans vos recherches Radar : ajoutez-le aux mots-clés ou activez la recherche élargie." if jooble and not res["in_terms"]
                   else "Présente sur Jooble et couverte par vos recherches : elle devrait apparaître au prochain passage (nouvelle offre ou au-delà des 100 premiers résultats)." if jooble
                   else "Absente de Jooble pour votre ville : seule la source employeur (ou LinkedIn) la publie. Suivez l'entreprise et cherchez son portail avec la loupe." if jooble is False
                   else "Jooble non vérifié (non configuré ou indisponible).")
            return {**res, "found": False, "status": "non_trouvee", "jooble": jooble, "why": why}
        return {"items": list(await asyncio.gather(*(one(it) for it in items))), "terms": terms, "location": st["location"]}

    @router.put("/settings")
    async def put_settings(body: RadarSettings, user: dict = Depends(current_user)):
        data = body.model_dump()
        conf = S.configured()
        data["sources"] = [x for x in data["sources"] if x != "adzuna" or conf["adzuna"]]  # Adzuna needs a key
        prev = {c["name"]: c for c in ((await db.radar_settings.find_one({"user_id": user["id"]}, {"_id": 0, "companies": 1})) or {}).get("companies") or [] if isinstance(c, dict)}
        seen, comps = set(), []
        for co in data["companies"]:
            co["name"] = co["name"].strip()
            old = prev.get(co["name"]) or {}
            if old.get("kind") and not co["kind"] and old["kind"] not in co["auto_block"]:
                co["auto_block"].append(old["kind"])  # portal removed by the member: never re-associate it automatically
            if co["portal_url"] and not co["kind"]:
                co["kind"], co["slug"] = S.parse_portal(co["portal_url"])
            if co["name"] and co["name"].lower() not in seen:
                seen.add(co["name"].lower())
                comps.append(co)
        data["companies"] = comps
        await db.radar_settings.update_one({"user_id": user["id"]}, {"$set": {**data, "updated_at": _now().isoformat()}, "$unset": {"boards": ""}}, upsert=True)
        await AU.share(db, user["id"], comps)
        todo = [c["name"] for c in comps if c["enabled"] and not c["kind"] and not c.get("checked_at")]
        if todo:  # new companies: automatic discovery in the background
            asyncio.create_task(AU.auto_detect(db, user["id"], todo, limit=10))
        return {**await get_settings(user), "auto_detecting": todo[:10]}

    class FollowBody(BaseModel):
        name: str = Field(min_length=1, max_length=80)

    @router.post("/companies/follow")
    async def follow(body: FollowBody, user: dict = Depends(current_user)):
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        st = await _settings(user["id"], profile)
        name = body.name.strip()
        if not any(AU.same_company(name, c["name"]) for c in st["companies"]):
            if len(st["companies"]) >= 100:
                raise HTTPException(status_code=400, detail="Maximum 100 entreprises suivies.")
            st["companies"].append(Company(name=name).model_dump())
            await db.radar_settings.update_one({"user_id": user["id"]}, {"$set": {k: v for k, v in st.items() if k != "user_id"}}, upsert=True)
        asyncio.create_task(AU.auto_detect(db, user["id"], [name], limit=1))
        return {"ok": True, "name": name}

    @router.get("/suggestions")
    async def company_suggestions(user: dict = Depends(current_user)):
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        st = await _settings(user["id"], profile)
        roles = (st.get("keywords") or []) + [r for r in re.split(r"[,;/\n]", profile.get("target_roles") or "") if r.strip()]
        return {"items": await AU.suggestions(db, user["id"], roles, [c["name"] for c in st["companies"]])}

    @router.get("/notices")
    async def notices(user: dict = Depends(current_user)):
        return {"items": [n async for n in db.radar_notices.find({"user_id": user["id"], "status": "new"}, {"_id": 0, "user_id": 0}).sort("at", -1).limit(20)]}

    @router.post("/notices/{notice_id}/ack")
    async def ack_notice(notice_id: str, user: dict = Depends(current_user)):
        await db.radar_notices.update_one({"id": notice_id, "user_id": user["id"]}, {"$set": {"status": "seen"}})
        return {"ok": True}

    @router.post("/notices/{notice_id}/undo")
    async def undo_notice(notice_id: str, user: dict = Depends(current_user)):
        if not await AU.undo(db, user["id"], notice_id):
            raise HTTPException(status_code=404, detail="Notification introuvable")
        return {"ok": True}

    class PortalBody(BaseModel):
        url: str = Field(min_length=8, max_length=400)
        name: str = Field(default="", max_length=80)

    class DiscoverBody(BaseModel):
        name: str = Field(min_length=1, max_length=80)
        website: str = Field(default="", max_length=200)

    @router.post("/portal/discover")
    async def discover_portal(body: DiscoverBody, user: dict = Depends(current_user)):
        try:
            return await asyncio.wait_for(D.discover(body.name.strip(), body.website.strip()), timeout=45)
        except asyncio.TimeoutError:
            return {"name": body.name, "candidates": [], "unsupported": [], "message": "Détection trop longue : réessayez ou collez l'URL du portail. Jooble reste utilisé en repli."}

    @router.get("/directory")
    async def employer_directory(user: dict = Depends(current_user)):
        return await D.directory()

    @router.post("/portal/detect")
    async def detect_portal(body: PortalBody, user: dict = Depends(current_user)):
        kind, slug = S.parse_portal(body.url)
        if not kind and S.host_of(body.url):
            async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as c:
                probe = await D.verify(c, "successfactors", S.host_of(body.url), body.name or "")
            if probe["ok"]:
                kind, slug = "successfactors", S.host_of(body.url)
        if not kind:
            return {"kind": "", "slug": "", "ok": False, "count": 0,
                    "message": "Portail sans flux public pris en charge : cette entreprise sera suivie via Jooble."}
        try:
            async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as c:
                if kind == "workday":
                    offers = await S.workday(c, slug, body.name or slug, [], max_details=0)
                else:
                    offers = await S.board(c, kind, slug, body.name or slug, [])
            return {"kind": kind, "slug": slug, "ok": True, "count": len(offers), "message": f"Portail {D.KIND_LABEL.get(kind, kind)} vérifié."}
        except Exception as e:  # noqa: BLE001
            return {"kind": kind, "slug": slug, "ok": False, "count": 0, "message": f"Portail {kind} injoignable ({(str(e) or type(e).__name__)[:80]})."}

    @router.post("/run")
    async def run_now(user: dict = Depends(current_user)):
        # Runs in background (can exceed proxy timeouts); the dashboard polls last_run.status.
        busy = await db.radar_runs.find_one({"user_id": user["id"], "status": "running", "at": {"$gte": (_now() - timedelta(minutes=15)).isoformat()}})
        if busy:
            raise HTTPException(status_code=409, detail="Une recherche Radar est déjà en cours.")
        asyncio.create_task(run_for_user(user["id"], "manuel"))
        return {"started": True}

    @router.get("/runs")
    async def runs(days: int = Query(30, ge=1, le=90), user: dict = Depends(current_user)):
        since = (_now() - timedelta(days=days)).isoformat()
        proj = {"_id": 0, "user_id": 0, "sources": 0, "selected_sources": 0}
        return [r async for r in db.radar_runs.find({"user_id": user["id"], "at": {"$gte": since}}, proj).sort("at", -1).limit(300)]

    @router.get("/runs/{run_id}/offers")
    async def run_offers(run_id: str, kind: str = Query("found", pattern="^(found|new)$"), user: dict = Depends(current_user)):
        run = await db.radar_runs.find_one({"id": run_id, "user_id": user["id"]}, {"_id": 0, "tracked": 1})
        if run is None:
            raise HTTPException(status_code=404, detail="Recherche introuvable")
        q = {"user_id": user["id"], "run_id": run_id} if kind == "new" else {"user_id": user["id"], "$or": [{"run_id": run_id}, {"seen_runs": run_id}]}
        proj = {"_id": 0, "description": 0, "dedupe_key": 0, "user_id": 0, "seen_runs": 0}
        offers = [o async for o in db.radar_offers.find(q, proj).sort("first_seen", -1).limit(300)]
        return {"offers": offers, "complete": kind == "new" or bool(run.get("tracked"))}

    @router.get("/dashboard")
    async def dashboard(user: dict = Depends(current_user)):
        q = {"user_id": user["id"]}
        proj = {"_id": 0, "description": 0, "dedupe_key": 0, "user_id": 0}
        offers = [o async for o in db.radar_offers.find(q, proj).sort("first_seen", -1).limit(400)]
        last = await db.radar_runs.find_one(q, {"_id": 0, "user_id": 0}, sort=[("at", -1)])
        active = [o for o in offers if o["status"] not in ("ignoree", "pack") and o.get("ips")]
        top = lambda p: sorted([o for o in active if o["ips"]["priority"] == p], key=lambda o: -o["ips"]["score"])[:20]  # noqa: E731
        st = await _settings(user["id"], {})
        day = _day_start()
        known = [o async for o in db.radar_offers.find({**q, "run_id": {"$ne": last["id"]}, "last_seen": {"$gte": last["at"]}}, proj).sort("last_seen", -1).limit(200)] if last else []
        analyzed = [o async for o in db.radar_offers.find({**q, "analyzed_at": {"$gte": day}}, proj).sort("analyzed_at", -1).limit(100)]
        return {
            "known_last_run": known, "analyzed_today_list": analyzed,
            "sources_status": {"configured": S.configured(), "selected": st["sources"], "portals": {
                "workday": sum(1 for c in st["companies"] if c.get("enabled", True) and c.get("kind") == "workday"),
                "boards": sum(1 for c in st["companies"] if c.get("enabled", True) and c.get("kind") and c.get("kind") != "workday")}},
            "last_run": last, "analyzed_today": await _analyzed_today(user["id"]), "daily_limit": DAILY_LIMIT,
            "ai_today": await _ai_today(user["id"]), "ai_top": AI_TOP, "deep_limit": AI_TOP + DEEP_LIMIT,
            "new_today": [o for o in offers if last and o.get("run_id") == last.get("id")][:50],
            "top_a": top("A"), "top_b": top("B"),
            "ignored": [o for o in offers if o["status"] == "ignoree" or (o.get("ips") and o["ips"]["priority"] == "C")][:40],
            "packed": [o for o in offers if o["status"] == "pack"][:40],
            "pending": len([o for o in offers if not o.get("ips")]),
        }

    @router.post("/offers/{offer_id}/ignore")
    async def ignore(offer_id: str, user: dict = Depends(current_user)):
        r = await db.radar_offers.update_one({"id": offer_id, "user_id": user["id"]}, {"$set": {"status": "ignoree"}})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        return {"ok": True}

    @router.post("/offers/{offer_id}/deep")
    async def deep(offer_id: str, user: dict = Depends(current_user)):
        o = await db.radar_offers.find_one({"id": offer_id, "user_id": user["id"]}, {"_id": 0})
        if not o:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        if o.get("method") == "ia":
            return o
        if await _ai_today(user["id"]) >= AI_TOP + DEEP_LIMIT:
            raise HTTPException(status_code=429, detail=f"Limite de {AI_TOP + DEEP_LIMIT} analyses approfondies par jour atteinte")
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        try:
            await _analyze(o, profile.get("cv_text") or "", profile)
        except Exception as e:  # noqa: BLE001
            logger.warning("radar deep %s failed: %s", offer_id, e)
            raise HTTPException(status_code=503, detail="Service IA temporairement indisponible : réessayez plus tard.")
        return await db.radar_offers.find_one({"id": offer_id}, {"_id": 0})

    @router.get("/offers/{offer_id}/explain")
    async def explain(offer_id: str, user: dict = Depends(current_user)):
        """Score detail. Rule-scored offers are re-evaluated with the current rules (free) so score and requirements stay consistent."""
        o = await db.radar_offers.find_one({"id": offer_id, "user_id": user["id"]}, {"_id": 0})
        if not o:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        cv = profile.get("cv_text") or ""
        if o.get("method") != "ia" and len(cv) >= 80:
            st = await _settings(user["id"], profile)
            await _rules(o, cv, profile, st.get("keywords") or [])
        elif not o.get("requirements_rules"):
            await db.radar_offers.update_one({"id": offer_id}, {"$set": {"requirements_rules": RR.requirements(o, cv, profile)}})
        o = await db.radar_offers.find_one({"id": offer_id}, {"_id": 0, "description": 0, "dedupe_key": 0, "user_id": 0})
        return o

    class ExternalBody(BaseModel):
        text: str = Field(default="", max_length=30000)
        url: str = Field(default="", max_length=1000)
        title: str = Field(default="", max_length=200)
        company: str = Field(default="", max_length=120)
        location: str = Field(default="", max_length=120)

    @router.post("/external")
    async def external(body: ExternalBody, user: dict = Depends(current_user)):
        """Score an offer the member pasted (LinkedIn, etc.). CareerOS never scrapes LinkedIn: the member provides the text."""
        o = {"title": body.title.strip(), "company": body.company.strip(), "location": body.location.strip(), "description": body.text.strip(), "posted_at": ""}
        if not o["description"] and body.url:
            try:
                async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as c:
                    jp = S._jobposting((await c.get(body.url, headers=S.UA)).text)
            except Exception:  # noqa: BLE001
                jp = None
            if not jp:
                raise HTTPException(status_code=422, detail="Lien illisible (ex. LinkedIn exige une connexion) : copiez-collez le texte de l'offre.")
            org = jp.get("hiringOrganization")
            o.update({"title": o["title"] or S._clean(jp.get("title")), "company": o["company"] or (org.get("name") if isinstance(org, dict) else "") or "",
                      "location": o["location"] or S._jp_location(jp), "description": S._clean(jp.get("description")), "posted_at": str(jp.get("datePosted") or "")[:10]})
        if len(o["description"]) < 80:
            raise HTTPException(status_code=422, detail="Collez le texte complet de l'offre (au moins quelques lignes).")
        if not o["title"]:
            o["title"] = next((x.strip() for x in o["description"].splitlines() if x.strip()), "Offre externe")[:120]
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        cv = profile.get("cv_text") or ""
        if len(cv) < 80:
            raise HTTPException(status_code=400, detail="Ajoutez votre CV dans la Career Memory pour analyser une offre.")
        o = {**o, "company": o["company"] or "Entreprise non précisée", "source": "externe", "url": body.url, "external_id": "", "salary": ""}
        k = _key(o)
        doc = await db.radar_offers.find_one({"user_id": user["id"], "dedupe_key": k}, {"_id": 0})
        if doc:
            await db.radar_offers.update_one({"id": doc["id"]}, {"$set": {"description": o["description"], "status": "nouvelle" if doc["status"] == "ignoree" else doc["status"]}})
            doc.update(description=o["description"])
        else:
            doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "dedupe_key": k, **o, "first_seen": _now().isoformat(), "last_seen": _now().isoformat(),
                   "run_id": None, "seen_runs": [], "status": "nouvelle", "ips": None, "decision_report": None, "analyzed_at": None, "application_id": None}
            await db.radar_offers.insert_one(dict(doc))
        if doc.get("method") != "ia":
            await _rules(doc, cv, profile, [])
        return await db.radar_offers.find_one({"id": doc["id"]}, {"_id": 0, "dedupe_key": 0, "user_id": 0})

    @router.post("/offers/{offer_id}/pack")
    async def pack(offer_id: str, user: dict = Depends(current_user)):
        o = await db.radar_offers.find_one({"id": offer_id, "user_id": user["id"]}, {"_id": 0})
        if not o:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        if o.get("application_id"):
            return {"id": o["application_id"], "already": True}
        from .router import PackBody
        text = f"{o['title']} — {o['company']} — {o['location']}\nSource : {o['source']} · {o['url']}\n\n{o['description']}"
        if o.get("method") == "ia" and o.get("ips"):  # reuse the Radar AI analysis for consistency
            notes = "; ".join(f"{c['label']} {c['score']}/10" for c in o["ips"]["criteria"])
            text += (f"\n\nANALYSE RADAR CAREEROS DÉJÀ RÉALISÉE (à réutiliser sauf contradiction avec l'offre) : {notes}. "
                     f"Exigence éliminatoire : {o['ips'].get('knockout_detail') or 'aucune'}.")
        body = PackBody(offer_text=text[:30000], offer_url="", posted_date=o.get("posted_at") or "", network="aucun")
        res = await careeros_router.create_pack_internal(body, user, {"type": "radar", "radar_offer_id": offer_id, "source": o["source"], "url": o["url"]})
        await db.radar_offers.update_one({"id": offer_id}, {"$set": {"status": "pack", "application_id": res["id"]}})
        return res

    # ---------------- Daily job (external scheduler) ----------------
    @router.post("/cron")
    async def cron(x_cron_secret: str = Header(None)):
        secret = os.environ.get("RADAR_CRON_SECRET")
        if not secret or x_cron_secret != secret:
            raise HTTPException(status_code=401, detail="Non autorisé")
        since = (_now() - timedelta(days=ACTIVE_DAYS)).isoformat()
        active = {u["id"]: u.get("last_seen_at") or "" async for u in db.users.find({"last_seen_at": {"$gte": since}}, {"id": 1, "last_seen_at": 1})}
        users = [s["user_id"] async for s in db.radar_settings.find({"enabled": True}, {"user_id": 1})]
        users += [p["user_id"] async for p in db.career_profiles.find({"cv_text": {"$nin": ["", None]}}, {"user_id": 1}) if p["user_id"] not in users]
        candidates = list(users)
        users = [u for u in users if u in active]  # only members active in the last 7 days
        disabled = {s["user_id"] async for s in db.radar_settings.find({"enabled": False}, {"user_id": 1})}
        todo = sorted(dict.fromkeys(u for u in users if u not in disabled), key=lambda u: active[u], reverse=True)  # most recently active first
        log = {"id": str(uuid.uuid4()), "at": _now().isoformat(), "status": "started", "members": len(todo), "inactive_skipped": len(set(candidates) - set(active)), "steps": []}
        await db.radar_cron_log.insert_one(dict(log))

        async def step(**kw):
            await db.radar_cron_log.update_one({"id": log["id"]}, {"$push": {"steps": {**kw, "at": _now().isoformat()}}})

        async def all_runs():
            for uid in todo:  # history first: the daily run never waits for portal discovery
                try:
                    r = await asyncio.wait_for(run_for_user(uid, "quotidien"), timeout=900)
                    await step(member=uid[:8], step="radar", ok=True, fetched=r.get("fetched"), new=r.get("new"), analyzed=r.get("analyzed"), run_id=r.get("id"))
                except Exception as e:  # noqa: BLE001
                    logger.exception("radar cron user %s", uid)
                    await step(member=uid[:8], step="radar", ok=False, error=f"{type(e).__name__}: {e}"[:300])
            for uid in todo:
                try:
                    res = await asyncio.wait_for(AU.auto_detect(db, uid, None, limit=3), timeout=240)
                    await step(member=uid[:8], step="detection", ok=True, associated=[x["name"] for x in res if x.get("associated")], checked=len(res))
                except Exception as e:  # noqa: BLE001
                    logger.exception("radar auto-detect user %s", uid)
                    await step(member=uid[:8], step="detection", ok=False, error=f"{type(e).__name__}: {e}"[:300])
            await db.radar_cron_log.update_one({"id": log["id"]}, {"$set": {"status": "done", "ended_at": _now().isoformat()}})

        task = asyncio.create_task(all_runs())
        _BG.add(task)  # keep a strong reference so the job is never garbage-collected mid-run
        task.add_done_callback(_BG.discard)
        from . import ai_credits as AC
        try:
            await AC.check_alert(db)  # daily low-credit check
        except Exception:  # noqa: BLE001
            logger.exception("credit alert check failed")
        logger.info("radar cron started: %s member(s), log %s", len(todo), log["id"])
        return {"started": True, "members": len(todo), "log_id": log["id"], "skipped_disabled": len(set(users) & disabled), "skipped_inactive": log["inactive_skipped"]}

    @router.get("/cron-status")
    async def cron_status(user: dict = Depends(current_user)):
        """Is this member included in the daily 06:00 run? (same rules as /cron)"""
        st = await db.radar_settings.find_one({"user_id": user["id"]}, {"_id": 0, "enabled": 1}) or {}
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "cv_text": 1}) or {}
        u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "last_seen_at": 1}) or {}
        since = (_now() - timedelta(days=ACTIVE_DAYS)).isoformat()
        last = await db.radar_runs.find_one({"user_id": user["id"], "trigger": "quotidien"}, {"_id": 0, "at": 1, "status": 1}, sort=[("at", -1)])
        reason = ("Désactivé : cochez « Recherche quotidienne automatique » dans les Réglages." if st.get("enabled") is False
                  else "Ajoutez votre CV dans la Career Memory." if len((profile.get("cv_text") or "").strip()) < 80
                  else f"Inactif depuis plus de {ACTIVE_DAYS} jours." if (u.get("last_seen_at") or "") < since else "")
        return {"included": not reason, "reason": reason, "last_auto": last}

    return router


async def ensure_radar_indexes(db):
    await db.radar_offers.create_index([("user_id", 1), ("dedupe_key", 1)], unique=True)
    await db.radar_offers.create_index([("user_id", 1), ("first_seen", -1)])
    await db.radar_offers.create_index("id", unique=True)
    await db.portal_directory.create_index("key")
    await db.radar_notices.create_index([("user_id", 1), ("status", 1), ("at", -1)])
    await db.radar_runs.create_index([("user_id", 1), ("at", -1)])
    await db.radar_cron_log.create_index("at")
    await db.radar_settings.create_index("user_id", unique=True)
    await db.radar_runs.update_many({"status": "running"}, {"$set": {"status": "interrompue"}})
    async for o in db.radar_offers.find({"ips": {"$ne": None}, "ips.stage": {"$ne": "radar"}}, {"_id": 0}):
        ips, report = rescore_radar(o)
        await db.radar_offers.update_one({"id": o["id"]}, {"$set": {"ips": ips, "decision_report": report, "excerpt": is_excerpt(o)}})
