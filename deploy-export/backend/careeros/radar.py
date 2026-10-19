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
from . import knowledge as KB
from . import zone as Z
from . import portal_errors as PE
from . import ai_budget as AB
from .decision_report import build_decision_report
from .ips import compute_ips
from .prompts import SYSTEM

logger = logging.getLogger("careeros.radar")
MAX_COMPANIES = 100
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
_STATE = {}  # in-memory: Toronto day already claimed (avoids a DB hit per request)
DAILY_HOUR = 6


def _toronto_now():
    from zoneinfo import ZoneInfo
    return datetime.now(ZoneInfo("America/Toronto"))


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
    companies: List[Company] = Field(default=[], max_length=MAX_COMPANIES)
    sources: List[str] = DEFAULT_SOURCES
    expand: bool = True  # recherche élargie : famille de titres FR/EN générée à partir des mots-clés
    radius: str = "100"  # 25/50/100/200 km, province or country around the main location
    extra_zones: List[dict] = Field(default=[], max_length=2)  # up to 2 more cities [{location, radius}]

    @field_validator("radius", mode="before")
    @classmethod
    def _radius(cls, v):
        return str(v) if str(v) in Z.RADII else "100"

    @field_validator("extra_zones", mode="before")
    @classmethod
    def _zones(cls, v):
        return [{"location": str(z.get("location") or "").strip()[:120], "radius": str(z.get("radius")) if str(z.get("radius")) in Z.RADII else "100"}
                for z in (v or [])[:2] if isinstance(z, dict) and str(z.get("location") or "").strip()]

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
        return {"user_id": user_id, **RadarSettings(keywords=roles[:5], location=profile.get("location") or profile.get("city") or profile.get("province") or "Québec").model_dump()}

    async def _apply_zone(user_id: str, st: dict) -> None:
        """Re-evaluate the member's stored offers when the zone rules or the Radar zones change (reversible)."""
        location = Z.zones_of(st)
        sig = Z.signature(location)
        mark = await db.radar_settings.find_one({"user_id": user_id}, {"_id": 0, "zone_for": 1}) or {}
        if mark.get("zone_for") == sig:
            return
        async for o in db.radar_offers.find({"user_id": user_id, "status": {"$ne": "pack"}, "source": {"$ne": "externe"}}, {"_id": 0, "id": 1, "location": 1, "status": 1, "status_before_zone": 1}):
            ok, why = Z.check(o.get("location"), location)
            if not ok and o["status"] != "hors_zone":
                await db.radar_offers.update_one({"id": o["id"]}, {"$set": {"status": "hors_zone", "status_before_zone": o["status"], "zone_reason": why}})
            elif not ok:
                await db.radar_offers.update_one({"id": o["id"]}, {"$set": {"zone_reason": why}})
            elif o["status"] == "hors_zone":
                await db.radar_offers.update_one({"id": o["id"]}, {"$set": {"status": o.get("status_before_zone") or "nouvelle", "zone_reason": why}, "$unset": {"status_before_zone": ""}})
        await db.radar_settings.update_one({"user_id": user_id}, {"$set": {"zone_for": sig}}, upsert=True)

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
                tasks += [(f"jooble:{t}#{pg}" + (f"@{loc}" if i else ""), None, S.jooble(c, t, loc, page=pg))
                          for i, (loc, _r) in enumerate(Z.zones_of(st) or [(st["location"], "100")]) for t in terms for pg in (1, 2)]
                tasks += [(f"jooble:{co['name']}", co["name"], S.jooble(c, "", st["location"], co["name"])) for co in comps[:JOOBLE_COMPANY_LIMIT]]
            for co in comps:
                if co.get("kind") and co.get("slug") and ("workday" if co["kind"] == "workday" else "boards") in srcs:
                    tasks += [(f"{co['kind']}:{co['name']}", None, S.board(c, co["kind"], co["slug"], co["name"], kw))]
            res = await asyncio.gather(*(limited(t) for _, _, t in tasks), return_exceptions=True)
            asked = {n.split(":", 1)[1] for n, _, _ in tasks if n.startswith("jooble:")}
            failed = [n.split(":", 1)[1] for (n, _, _), r in zip(tasks, res) if n.split(":", 1)[0] in S.PORTAL_KINDS and isinstance(r, Exception)]
            if S.configured().get("jooble"):  # unreadable portal -> Jooble for this company during this run
                extra = [(f"jooble:{n}", n, S.jooble(c, "", st["location"], n)) for n in failed if n not in asked]
                tasks += extra
                res = list(res) + list(await asyncio.gather(*(limited(t) for _, _, t in extra), return_exceptions=True))
        moved = {}
        for co in comps:
            new = S.MOVED.get((co.get("kind"), co.get("slug")))
            if new:
                moved[co["name"]] = {"kind": co["kind"], "old": co["slug"], "new": new}
        jooble_raw, jooble_ok = 0, 0
        portals = {}
        for (name, company, _), r in zip(tasks, res):
            kind = name.split(":", 1)[0]
            if kind in S.PORTAL_KINDS:
                portals[name.split(":", 1)[1]] = {"kind": kind, "ok": not isinstance(r, Exception), "fetched": 0 if isinstance(r, Exception) else len(r),
                                                  "error": (str(r) or type(r).__name__)[:160] if isinstance(r, Exception) else "",
                                                  "blocked": isinstance(r, Exception) and D.is_blocked(r), "etype": PE.classify(r) if isinstance(r, Exception) else ""}
                pv = portals[name.split(":", 1)[1]]
                pv["quality"] = S.quality(kind, pv["ok"], pv["blocked"])
            if isinstance(r, Exception):
                errors[name] = PE.member_message(r, kind in S.PORTAL_KINDS and S.configured().get("jooble")) if kind in S.PORTAL_KINDS else (str(r) or type(r).__name__)[:160]
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
        errors["_portals"], errors["_moved"] = portals, moved
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
            moved = run["errors"].pop("_moved", {})
            for cname, mv in moved.items():  # portal moved (redirect): remember the new address for the member and the shared base
                host = mv["new"].split("/", 1)[0]
                co = next(c for c in st["companies"] if c["name"] == cname)
                url = re.sub(r"^https://[^/]+", f"https://{host}", co.get("portal_url") or "")
                await db.radar_settings.update_one({"user_id": user_id, "companies.name": cname},
                                                   {"$set": {"companies.$.slug": mv["new"], "companies.$.portal_url": url}})
                co["slug"], co["portal_url"] = mv["new"], url
                run["errors"][f"info:{cname}"] = f"Portail déplacé par l'employeur : nouvelle adresse {host} enregistrée, lecture poursuivie."
            try:
                await PE.record_run(db, user_id, st["companies"], run["portals"])
                for k, v in run["errors"].items():
                    src = k.split(":", 1)[0]
                    if src in S.PORTAL_KINDS or src in ("limite", "info"):
                        continue
                    await PE.log_error(db, user_id, "source", f"{src} · {k.split(':', 1)[-1].split('#')[0][:60]}" if ":" in k else src, "source", str(v), kind=src)
            except Exception:  # noqa: BLE001
                logger.exception("portal errors record_run")
            for pname, pv in run["portals"].items():
                pv["matched"] = sum(1 for o in offers if o["source"] == pv["kind"] and o.get("company") == pname)
            try:
                await KB.record_run(db, st["companies"], run["portals"])
            except Exception:  # noqa: BLE001
                logger.exception("knowledge record_run")
            await _apply_zone(user_id, st)
            seen, fresh = set(), []
            run["out_zone"] = 0
            for o in offers:
                k = _key(o)
                if k in seen:
                    continue
                seen.add(k)
                run["by_source"][S.group(o["source"])]["fetched"] += 1
                existing = await db.radar_offers.find_one({"user_id": user_id, "dedupe_key": k}, {"_id": 0, "id": 1, "status": 1})
                if existing:
                    run["known"] += 1
                    run["out_zone"] += existing.get("status") == "hors_zone"
                    await db.radar_offers.update_one({"id": existing["id"]}, {"$set": {"last_seen": _now().isoformat()}, "$addToSet": {"seen_runs": run["id"]}})
                    continue
                doc = {"id": str(uuid.uuid4()), "user_id": user_id, "dedupe_key": k, **o, "first_seen": _now().isoformat(),
                       "last_seen": _now().isoformat(), "run_id": run["id"], "seen_runs": [run["id"]], "status": "nouvelle", "ips": None, "decision_report": None,
                       "analyzed_at": None, "application_id": None}
                ok, why = Z.check(o.get("location"), Z.zones_of(st))
                doc["zone_reason"] = why
                if not ok:
                    doc["status"], doc["status_before_zone"] = "hors_zone", "nouvelle"
                    run["out_zone"] += 1
                await db.radar_offers.insert_one(dict(doc))
                if ok:
                    fresh.append(doc)
            run["fetched"], run["new"] = len(seen), len(fresh)
            budget = max(0, DAILY_LIMIT - await _analyzed_today(user_id))
            fresh_ids = {d["id"] for d in fresh}
            backlog = [d async for d in db.radar_offers.find({"user_id": user_id, "ips": None, "status": "nouvelle"}, {"_id": 0}).sort("first_seen", -1).limit(DAILY_LIMIT * 4)
                       if d["id"] not in fresh_ids]  # offers deferred by an earlier daily limit
            roles = (st.get("keywords") or []) + [r for r in re.split(r"[,;/\n]", profile.get("target_roles") or "") if r.strip()]
            learned = await _learned(user_id)  # member's own feedback: closer to the offers they kept, away from the ones they ignored
            rank = lambda d: (-round(RR.title_relevance(d.get("title", ""), roles) + _learn_bonus(d.get("title", ""), learned), 1), _source_rank(d))  # noqa: E731
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
            pool.sort(key=lambda d: (-(d["ips"]["score"] + 10 * _learn_bonus(d.get("title", ""), learned)), _source_rank(d)))
            ai_todo = pool[:max(0, AI_TOP - await _ai_today(user_id))]
            fails, run["ai_analyzed"] = {"n": 0}, 0
            for doc in ai_todo:  # AI confirmation of the best offers of the day only
                if fails["n"] >= 3:  # AI service down: offers stay rule-scored
                    break
                try:
                    await _analyze(doc, cv, profile)
                    run["ai_analyzed"] += 1
                    fails["n"] = 0
                except AB.QuotaReached:  # budget / rules-only mode: not an error, offers stay rule-scored
                    run["ai_rules_only"] = True
                    break
                except Exception as e:  # noqa: BLE001
                    fails["n"] += 1
                    logger.warning("radar AI analyze %s failed: %s", doc["id"], e)
            if fails["n"] >= 3:
                await PE.log_error(db, user_id, "ia", "Radar · analyse IA du top 5", "ia", "3 échecs consécutifs de l'analyse IA (voir logs serveur)")
                run["errors"]["ia"] = ("Service IA du serveur indisponible : les meilleures offres restent pré-analysées par règles ; "
                                       "relancez l'analyse approfondie plus tard.")
        run["status"], run["finished_at"] = "done", _now().isoformat()
        await db.radar_runs.update_one({"id": run["id"]}, {"$set": run})
        return run

    async def _learned(user_id: str) -> dict:
        """Title-word weights learned from the member's own actions: pack / saved / applied / interview (+), ignored (-)."""
        apps = {a["id"]: a.get("pipeline_status") async for a in db.applications.find({"user_id": user_id}, {"_id": 0, "id": 1, "pipeline_status": 1})}
        pos, neg, n = {}, {}, {"pos": 0, "neg": 0}
        async for o in db.radar_offers.find({"user_id": user_id, "$or": [{"status": {"$in": ["pack", "ignoree"]}}, {"saved": True}]},
                                            {"_id": 0, "title": 1, "status": 1, "saved": 1, "application_id": 1, "ips.priority": 1}):
            good = o.get("saved") or o["status"] == "pack"
            w = 1 + (apps.get(o.get("application_id")) in ("postule", "entrevue", "offre")) + (apps.get(o.get("application_id")) in ("entrevue", "offre")) + ((o.get("ips") or {}).get("priority") == "A")
            bucket = pos if good else neg
            n["pos" if good else "neg"] += 1
            for t in RR._words(o.get("title", "")):
                bucket[t] = bucket.get(t, 0) + (w if good else 1)
        weights = {t: round((pos.get(t, 0) - 0.7 * neg.get(t, 0)) / (1 + pos.get(t, 0) + neg.get(t, 0)) * min(1, (pos.get(t, 0) + neg.get(t, 0)) / 2), 3)
                   for t in set(pos) | set(neg)}
        return {"weights": {t: w for t, w in weights.items() if abs(w) >= 0.1}, "signals": n}

    def _learn_bonus(title: str, learned: dict) -> float:
        ws = [learned["weights"].get(t, 0) for t in RR._words(title)]
        return max(-0.5, min(0.5, sum(ws) / max(3, len(ws)))) if ws else 0

    def _member_run(r):
        """Members never see technical errors (they go to the Admin error journal)."""
        if not r:
            return r
        r = {**{k: v for k, v in r.items() if k != "errors"},
             "notices": {k: v for k, v in (r.get("errors") or {}).items() if k in ("cv", "limite")}}
        r["portals"] = {n: {k: v for k, v in pv.items() if k not in ("error", "etype")} for n, pv in (r.get("portals") or {}).items()}
        return r

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
            if len(st["companies"]) >= MAX_COMPANIES:
                raise HTTPException(status_code=409, detail=f"LIMIT:Limite atteinte ({MAX_COMPANIES}/{MAX_COMPANIES})")
            await db.radar_removed.delete_one({"user_id": user["id"], "name": name})
            st["companies"].append(Company(name=name).model_dump())
            await db.radar_settings.update_one({"user_id": user["id"]}, {"$set": {k: v for k, v in st.items() if k != "user_id"}}, upsert=True)
        asyncio.create_task(AU.auto_detect(db, user["id"], [name], limit=1))
        return {"ok": True, "name": name}

    @router.get("/suggestions")
    async def company_suggestions(user: dict = Depends(current_user)):
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        st = await _settings(user["id"], profile)
        roles = (st.get("keywords") or []) + [r for r in re.split(r"[,;/\n]", profile.get("target_roles") or "") if r.strip()]
        removed = [r["name"] async for r in db.radar_removed.find({"user_id": user["id"]}, {"_id": 0, "name": 1})]
        return {"items": await AU.suggestions(db, user["id"], roles, [c["name"] for c in st["companies"]] + removed)}

    async def _activity(user_id: str, companies: list) -> dict:
        """Per followed company: last offer seen and last relevant (A/B) offer, from the member's own Radar history."""
        rows = [r async for r in db.radar_offers.aggregate([{"$match": {"user_id": user_id}}, {"$group": {
            "_id": "$company", "last": {"$max": "$last_seen"},
            "last_rel": {"$max": {"$cond": [{"$in": ["$ips.priority", ["A", "B"]]}, "$last_seen", None]}}, "n": {"$sum": 1}}}])]
        now = _now()
        out = {}
        for c in companies:
            hit = [r for r in rows if r["_id"] and AU.same_company(r["_id"], c["name"])]
            last = max((r["last"] for r in hit if r.get("last")), default=None)
            rel = max((r["last_rel"] for r in hit if r.get("last_rel")), default=None)
            days = (now - datetime.fromisoformat(last)).days if last else None
            rdays = (now - datetime.fromisoformat(rel)).days if rel else None
            out[c["name"]] = {"last": last, "last_relevant": rel, "days": days, "relevant_days": rdays, "offers": sum(r["n"] for r in hit),
                              "status": "active" if days is not None and days <= 30 else "low" if days is not None and days < 90 else "inactive"}
        return out

    @router.get("/companies/activity")
    async def companies_activity(user: dict = Depends(current_user)):
        st = await _settings(user["id"], {})
        act = await _activity(user["id"], st["companies"])
        counts = {k: sum(a["status"] == k for a in act.values()) for k in ("active", "low", "inactive")}
        counts["no_relevant_30"] = sum(a["relevant_days"] is None or a["relevant_days"] > 30 for a in act.values())
        return {"items": act, "counts": counts, "total": len(st["companies"]), "limit": MAX_COMPANIES}

    class RemoveBody(BaseModel):
        names: List[str] = Field(min_length=1, max_length=MAX_COMPANIES)
        mode: str = Field(default="retire", pattern="^(retire|bloque)$")
        reason: str = Field(default="", max_length=200)

    @router.post("/companies/remove")
    async def companies_remove(body: RemoveBody, user: dict = Depends(current_user)):
        """Unfollow in bulk: offers already found are kept; removed companies leave the suggestions (restorable)."""
        st = await _settings(user["id"], {})
        names = {n.strip() for n in body.names if n.strip()}
        keep = [c for c in st["companies"] if c["name"] not in names]
        await db.radar_settings.update_one({"user_id": user["id"]}, {"$set": {"companies": keep}}, upsert=True)
        at = _now().isoformat()
        for n in names:
            await db.radar_removed.update_one({"user_id": user["id"], "name": n}, {"$set": {"mode": body.mode, "reason": body.reason.strip(), "at": at}}, upsert=True)
        return {"removed": len(st["companies"]) - len(keep), "total": len(keep), "companies": keep}

    @router.get("/companies/removed")
    async def companies_removed(user: dict = Depends(current_user)):
        return {"items": [r async for r in db.radar_removed.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).sort("at", -1).limit(500)]}

    class RestoreBody(BaseModel):
        name: str = Field(min_length=1, max_length=80)
        follow: bool = True

    @router.post("/companies/restore")
    async def companies_restore(body: RestoreBody, user: dict = Depends(current_user)):
        await db.radar_removed.delete_one({"user_id": user["id"], "name": body.name})
        if body.follow:
            return await follow(FollowBody(name=body.name), user)
        return {"ok": True}

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
            shared = await KB.lookup(db, body.name)
            r = await asyncio.wait_for(D.discover(body.name.strip(), body.website.strip(), (shared or {}).get("portal_url", "")), timeout=45)
            await AU.learn(db, body.name.strip(), r, shared)
            return {**r, "knowledge": KB.public(shared) if shared else None}
        except asyncio.TimeoutError:
            return {"name": body.name, "candidates": [], "unsupported": [], "message": "Détection trop longue : réessayez ou collez l'URL du portail. Jooble reste utilisé en repli."}

    class MatchBody(BaseModel):
        names: List[str] = Field(default=[], max_length=150)

    @router.post("/knowledge/match")
    async def knowledge_match(body: MatchBody, user: dict = Depends(current_user)):
        out = {}
        for n in body.names[:150]:
            card = await KB.lookup(db, n)
            if card and (KB.usable(card) or card.get("status") == "bloque"):
                out[n] = {**KB.public(card), "slug": card["slug"], "usable": KB.usable(card)}
        return {"items": out}

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
            return {"kind": kind, "slug": slug, "ok": False, "count": 0, "message": f"Portail {D.KIND_LABEL.get(kind, kind)} momentanément illisible : l'entreprise reste suivie via Jooble."}

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
        return [_member_run(r) async for r in db.radar_runs.find({"user_id": user["id"], "at": {"$gte": since}}, proj).sort("at", -1).limit(300)]

    @router.get("/runs/{run_id}/offers")
    async def run_offers(run_id: str, kind: str = Query("found", pattern="^(found|new|analyzed|skipped|out_zone|src_jooble|src_workday|src_boards|src_adzuna)$"),
                         user: dict = Depends(current_user)):
        run = await db.radar_runs.find_one({"id": run_id, "user_id": user["id"]}, {"_id": 0, "tracked": 1, "at": 1, "finished_at": 1})
        if run is None:
            raise HTTPException(status_code=404, detail="Recherche introuvable")
        in_run = {"$or": [{"run_id": run_id}, {"seen_runs": run_id}]}
        q = {"user_id": user["id"], **({"run_id": run_id} if kind == "new" else in_run)}
        if kind == "analyzed":  # analysed during this run (rules or AI)
            end = run.get("finished_at") or (datetime.fromisoformat(run["at"]) + timedelta(minutes=30)).isoformat()
            q = {"user_id": user["id"], "analyzed_at": {"$gte": run["at"], "$lte": end}, "source": {"$ne": "externe"}}
        elif kind == "skipped":  # deferred by the daily limit, including those analysed by a later run
            q = {"user_id": user["id"], "$and": [in_run, {"$or": [{"ips": None}, {"analyzed_at": {"$gt": run.get("finished_at") or run["at"]}}]}]}
        elif kind == "out_zone":
            q = {**q, "status": "hors_zone"}
        if kind == "new":
            q = {**q, "status": {"$ne": "hors_zone"}}
        proj = {"_id": 0, "description": 0, "dedupe_key": 0, "user_id": 0, "seen_runs": 0}
        offers = [o async for o in db.radar_offers.find(q, proj).sort("first_seen", -1).limit(500)]
        if kind.startswith("src_"):
            offers = [o for o in offers if S.group(o["source"]) == kind[4:]]
        return {"offers": offers, "complete": kind in ("new", "analyzed") or bool(run.get("tracked"))}

    @router.get("/dashboard")
    async def dashboard(user: dict = Depends(current_user)):
        q = {"user_id": user["id"]}
        st = await _settings(user["id"], {})
        await _apply_zone(user["id"], st)
        proj = {"_id": 0, "description": 0, "dedupe_key": 0, "user_id": 0}
        out_zone = [o async for o in db.radar_offers.find({**q, "status": "hors_zone"}, proj).sort("first_seen", -1).limit(300)]
        q = {**q, "status": {"$ne": "hors_zone"}}
        offers = [o async for o in db.radar_offers.find(q, proj).sort("first_seen", -1).limit(400)]
        last = await db.radar_runs.find_one({"user_id": user["id"]}, {"_id": 0, "user_id": 0}, sort=[("at", -1)])
        active = [o for o in offers if o["status"] not in ("ignoree", "pack") and o.get("ips")]
        top = lambda p: sorted([o for o in active if o["ips"]["priority"] == p], key=lambda o: -o["ips"]["score"])[:20]  # noqa: E731
        zones = Z.zones_of(st)
        day = _day_start()
        known = [o async for o in db.radar_offers.find({**q, "run_id": {"$ne": last["id"]}, "last_seen": {"$gte": last["at"]}}, proj).sort("last_seen", -1).limit(200)] if last else []
        analyzed = [o async for o in db.radar_offers.find({**q, "analyzed_at": {"$gte": day}}, proj).sort("analyzed_at", -1).limit(100)]
        return {
            "known_last_run": known, "analyzed_today_list": analyzed,
            "saved": [o for o in offers if o.get("saved") and o["status"] not in ("pack", "ignoree")],
            "radar_a": [o for o in active if o["ips"]["priority"] == "A"],
            "learning": {**(lr := await _learned(user["id"]))["signals"],
                         "liked": [t for t, w in sorted(lr["weights"].items(), key=lambda x: -x[1]) if w > 0][:8],
                         "disliked": [t for t, w in sorted(lr["weights"].items(), key=lambda x: x[1]) if w < 0][:8]},
            "out_zone": out_zone, "out_zone_count": await db.radar_offers.count_documents({"user_id": user["id"], "status": "hors_zone"}),
            "zone": {"location": st["location"], "radius_km": int(st["radius"]) if st["radius"].isdigit() else None,
                     "label": " · ".join(f"{loc} ({Z.label(r)})" for loc, r in zones),
                     "zones": [{"location": loc, "radius": r, "label": Z.label(r), **({"lat": c[0], "lon": c[1]} if (c := Z.place(loc)["coords"]) else {})} for loc, r in zones]},
            "map_points": [{"id": o["id"], "title": o["title"], "company": o.get("company", ""), "location": o.get("location", ""), "url": o.get("url", ""),
                            "priority": o["ips"]["priority"], "score": o["ips"]["score"], **pt}
                           for o in offers if o.get("ips") and o["status"] != "ignoree" and (pt := Z.nearest(o.get("location"), zones))][:300],
            "sources_status": {"configured": S.configured(), "selected": st["sources"], "portals": {
                "workday": sum(1 for c in st["companies"] if c.get("enabled", True) and c.get("kind") == "workday"),
                "boards": sum(1 for c in st["companies"] if c.get("enabled", True) and c.get("kind") and c.get("kind") != "workday")}},
            "last_run": _member_run(last), "analyzed_today": await _analyzed_today(user["id"]), "daily_limit": DAILY_LIMIT,
            "ai_today": await _ai_today(user["id"]), "ai_top": AI_TOP, "deep_limit": AI_TOP + DEEP_LIMIT,
            "new_today": [o for o in offers if last and o.get("run_id") == last.get("id")][:50],
            "top_a": top("A"), "top_b": top("B"),
            "ignored": [o for o in offers if o["status"] == "ignoree" or (o.get("ips") and o["ips"]["priority"] == "C")][:40],
            "packed": [o for o in offers if o["status"] == "pack"][:40],
            "pending": len([o for o in offers if not o.get("ips")]),
        }

    @router.post("/offers/{offer_id}/ignore")
    async def ignore(offer_id: str, user: dict = Depends(current_user)):
        r = await db.radar_offers.update_one({"id": offer_id, "user_id": user["id"]}, {"$set": {"status": "ignoree"}, "$unset": {"status_before_zone": ""}})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        return {"ok": True}

    @router.post("/offers/{offer_id}/save")
    async def save_offer(offer_id: str, user: dict = Depends(current_user)):
        o = await db.radar_offers.find_one({"id": offer_id, "user_id": user["id"]}, {"_id": 0, "id": 1, "saved": 1})
        if not o:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        await db.radar_offers.update_one({"id": offer_id}, {"$set": {"saved": not o.get("saved"), "saved_at": _now().isoformat()}})
        return {"saved": not o.get("saved")}

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

    # ---------------- Daily job: self-scheduled at 06:00 Toronto, external cron only wakes the server ----------------
    async def start_daily(trigger: str, force: bool = False) -> dict:
        """Start today's automatic run once (atomic claim per Toronto day). force=True: manual relaunch."""
        today = _toronto_now().strftime("%Y-%m-%d")
        if not force:
            try:
                await db.radar_daily.insert_one({"_id": today, "at": _now().isoformat(), "trigger": trigger})
            except Exception:  # noqa: BLE001  (already claimed today)
                return {"started": False, "already": True, "day": today}
        since = (_now() - timedelta(days=ACTIVE_DAYS)).isoformat()
        active = {u["id"]: u.get("last_seen_at") or "" async for u in db.users.find({"last_seen_at": {"$gte": since}}, {"id": 1, "last_seen_at": 1})}
        users = [s["user_id"] async for s in db.radar_settings.find({"enabled": True}, {"user_id": 1})]
        users += [p["user_id"] async for p in db.career_profiles.find({"cv_text": {"$nin": ["", None]}}, {"user_id": 1}) if p["user_id"] not in users]
        candidates = list(users)
        users = [u for u in users if u in active]  # only members active in the last 7 days
        disabled = {s["user_id"] async for s in db.radar_settings.find({"enabled": False}, {"user_id": 1})}
        todo = sorted(dict.fromkeys(u for u in users if u not in disabled), key=lambda u: active[u], reverse=True)  # most recently active first
        log = {"id": str(uuid.uuid4()), "at": _now().isoformat(), "status": "started", "trigger": trigger, "day": today, "members": len(todo), "inactive_skipped": len(set(candidates) - set(active)), "steps": []}
        await db.radar_cron_log.insert_one(dict(log))

        async def step(**kw):
            await db.radar_cron_log.update_one({"id": log["id"]}, {"$push": {"steps": {**kw, "at": _now().isoformat()}}})

        async def keepalive():
            """Render free instances sleep after 15 min without inbound traffic: ping our public URL during the run."""
            url = os.environ.get("RENDER_EXTERNAL_URL")
            if not url:
                return
            async with httpx.AsyncClient(timeout=10) as c:
                while True:
                    await asyncio.sleep(240)
                    try:
                        await c.get(f"{url}/api/ping")
                    except Exception:  # noqa: BLE001
                        pass

        async def all_runs():
            ka = asyncio.create_task(keepalive())
            try:
                await _all_runs()
            except Exception as e:  # noqa: BLE001
                logger.exception("radar daily run")
                await db.radar_cron_log.update_one({"id": log["id"]}, {"$set": {"status": "error", "error": f"{type(e).__name__}: {e}"[:300]}})
            finally:
                ka.cancel()

        async def _all_runs():
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
            from . import offer_check as OC
            for uid in todo:  # are the offers still open? expired ones are searched elsewhere
                try:
                    apps = [a async for a in db.applications.find({"user_id": uid, "pipeline_status": "a_postuler", "archived": {"$ne": True}}, {"_id": 0}).sort("created_at", -1).limit(30)]
                    stale = sorted([x for x in apps if OC.is_stale(x)], key=lambda x: {"A": 0, "B": 1}.get((x.get("ips") or {}).get("priority"), 2))[:15]
                    checked = [await asyncio.wait_for(careeros_router.check_application(a, search=(a.get("ips") or {}).get("priority") == "A"), timeout=90) for a in stale]
                    await step(member=uid[:8], step="disponibilite", ok=True, checked=len(checked),
                               expired=sum(c["availability"]["status"] in ("expired", "expired_likely") for c in checked), found_elsewhere=sum(bool(c.get("alternatives")) for c in checked))
                except Exception as e:  # noqa: BLE001
                    logger.exception("offer availability user %s", uid)
                    await step(member=uid[:8], step="disponibilite", ok=False, error=f"{type(e).__name__}: {e}"[:300])
            await db.radar_cron_log.update_one({"id": log["id"]}, {"$set": {"status": "done", "ended_at": _now().isoformat()}})

        task = asyncio.create_task(all_runs())
        _BG.add(task)  # keep a strong reference so the job is never garbage-collected mid-run
        task.add_done_callback(_BG.discard)
        from . import ai_credits as AC
        try:
            await AC.check_alert(db)  # daily low-credit check
        except Exception:  # noqa: BLE001
            logger.exception("credit alert check failed")
        logger.info("radar daily started (%s): %s member(s), log %s", trigger, len(todo), log["id"])
        return {"started": True, "members": len(todo), "log_id": log["id"], "skipped_disabled": len(set(users) & disabled), "skipped_inactive": log["inactive_skipped"]}

    async def maybe_start(trigger: str):
        """Called by the internal loop and by any incoming request: start today's run once it is past 06:00 Toronto."""
        now = _toronto_now()
        day = now.strftime("%Y-%m-%d")
        if now.hour < DAILY_HOUR or _STATE.get("day") == day:
            return
        r = await start_daily(trigger)
        _STATE["day"] = day
        if r.get("started"):
            logger.info("daily radar auto-started by %s", trigger)

    async def scheduler_loop():
        while True:
            try:
                await maybe_start("planificateur interne")
            except Exception:  # noqa: BLE001
                logger.exception("radar scheduler")
            await asyncio.sleep(300)

    router.maybe_start = maybe_start
    router.scheduler_loop = scheduler_loop

    @router.post("/cron")
    async def cron(force: bool = False, x_cron_secret: str = Header(None)):
        secret = os.environ.get("RADAR_CRON_SECRET")
        if not secret or x_cron_secret != secret:
            raise HTTPException(status_code=401, detail="Non autorisé")
        if not force and _toronto_now().hour < DAILY_HOUR:
            return {"started": False, "reason": f"avant {DAILY_HOUR} h (heure de Toronto) : serveur réveillé, le passage démarrera à {DAILY_HOUR} h"}
        r = await start_daily("cron-job.org" if not force else "relance manuelle", force=force)
        _STATE["day"] = _toronto_now().strftime("%Y-%m-%d")
        return r

    @router.get("/cron-status")
    async def cron_status(user: dict = Depends(current_user)):
        """Is this member included in the daily 06:00 run? (same rules as /cron)"""
        st = await db.radar_settings.find_one({"user_id": user["id"]}, {"_id": 0, "enabled": 1}) or {}
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "cv_text": 1}) or {}
        u = await db.users.find_one({"id": user["id"]}, {"_id": 0, "last_seen_at": 1}) or {}
        since = (_now() - timedelta(days=ACTIVE_DAYS)).isoformat()
        last = await db.radar_runs.find_one({"user_id": user["id"], "trigger": "quotidien"}, {"_id": 0, "at": 1, "status": 1}, sort=[("at", -1)])
        log = await db.radar_cron_log.find_one({}, {"_id": 0, "at": 1, "status": 1, "trigger": 1, "members": 1}, sort=[("at", -1)])
        reason = ("Désactivé : cochez « Recherche quotidienne automatique » dans les Réglages." if st.get("enabled") is False
                  else "Ajoutez votre CV dans la Career Memory." if len((profile.get("cv_text") or "").strip()) < 80
                  else f"Inactif depuis plus de {ACTIVE_DAYS} jours." if (u.get("last_seen_at") or "") < since else "")
        return {"included": not reason, "reason": reason, "last_auto": last, "last_daily": log, "hour": DAILY_HOUR}

    return router


async def ensure_radar_indexes(db):
    await db.radar_offers.create_index([("user_id", 1), ("dedupe_key", 1)], unique=True)
    await db.radar_offers.create_index([("user_id", 1), ("first_seen", -1)])
    await db.radar_offers.create_index("id", unique=True)
    await db.portal_directory.create_index("key")
    await db.portal_knowledge.create_index("key", unique=True)
    await KB.migrate(db)
    await db.radar_notices.create_index([("user_id", 1), ("status", 1), ("at", -1)])
    await db.radar_runs.create_index([("user_id", 1), ("at", -1)])
    await db.radar_cron_log.create_index("at")
    await db.radar_settings.create_index("user_id", unique=True)
    await db.radar_runs.update_many({"status": "running"}, {"$set": {"status": "interrompue"}})
    task = asyncio.create_task(_rescore_all(db))  # in background: never delays the server start (cold start on Render)
    _BG.add(task)
    task.add_done_callback(_BG.discard)


async def _rescore_all(db):
    async for o in db.radar_offers.find({"ips": {"$ne": None}, "ips.stage": {"$ne": "radar"}}, {"_id": 0}):
        ips, report = rescore_radar(o)
        await db.radar_offers.update_one({"id": o["id"]}, {"$set": {"ips": ips, "decision_report": report, "excerpt": is_excerpt(o)}})
