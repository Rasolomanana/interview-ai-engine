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
from fastapi import APIRouter, Depends, Header, HTTPException
from pydantic import BaseModel, Field, field_validator

from . import radar_sources as S
from .decision_report import build_decision_report
from .ips import compute_ips
from .prompts import SYSTEM

logger = logging.getLogger("careeros.radar")
DAILY_LIMIT = int(os.environ.get("RADAR_DAILY_LIMIT", "50"))
DEFAULT_SOURCES = ["jooble", "workday", "boards"]
JOOBLE_COMPANY_LIMIT = 20


def _now():
    return datetime.now(timezone.utc)


class Company(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    enabled: bool = True
    portal_url: str = Field(default="", max_length=400)
    kind: str = Field(default="", pattern="^(|workday|greenhouse|lever|ashby|amazon)$")
    slug: str = Field(default="", max_length=200)


class RadarSettings(BaseModel):
    enabled: bool = True
    keywords: List[str] = []
    location: str = "Québec"
    companies: List[Company] = Field(default=[], max_length=100)
    sources: List[str] = DEFAULT_SOURCES

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
 "ats": {{"keywords_missing": ["max 5"]}}}}
Ne donne AUCUN score global ni estimation chiffrée d'IPS : CareerOS calcule l'IPS officiel."""


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
        start = _now().replace(hour=0, minute=0, second=0, microsecond=0).isoformat()
        return await db.radar_offers.count_documents({"user_id": user_id, "analyzed_at": {"$gte": start}})

    async def _fetch(st: dict) -> tuple:
        offers, errors = [], {}
        kw = st.get("keywords") or []
        what = " ".join(kw[:2]) or "analyste"
        srcs, comps = _active_sources(st), [c for c in st["companies"] if c.get("enabled", True)]
        sem = asyncio.Semaphore(6)

        async def limited(coro):
            async with sem:
                return await coro
        async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as c:
            tasks = []  # (label, company filter or None, coroutine)
            for src, fn in (("adzuna", S.adzuna), ("jooble", S.jooble)):
                if src in srcs:
                    tasks += [(src, None, fn(c, what, st["location"]))]
                    tasks += [(f"{src}:{co['name']}", co["name"], fn(c, what, st["location"], co["name"])) for co in comps[:JOOBLE_COMPANY_LIMIT]]
            for co in comps:
                if co.get("kind") and co.get("slug") and ("workday" if co["kind"] == "workday" else "boards") in srcs:
                    tasks += [(f"{co['kind']}:{co['name']}", None, S.board(c, co["kind"], co["slug"], co["name"], kw))]
            res = await asyncio.gather(*(limited(t) for _, _, t in tasks), return_exceptions=True)
        for (name, company, _), r in zip(tasks, res):
            if isinstance(r, Exception):
                errors[name] = (str(r) or type(r).__name__)[:160]
                continue
            for o in r:
                if company and not S.company_match(o, company):
                    continue
                if o["source"] in ("greenhouse", "lever", "ashby") and not S.matches(o, kw):
                    continue
                offers.append(o)
        return offers, errors

    async def _analyze(doc: dict, cv: str, profile: dict):
        sysm, txt = radar_prompt(cv, doc, profile)
        d = parse_json((await generate_text(sysm, txt)).strip()) or {}
        if not d.get("ips_criteria"):
            raise ValueError("Réponse IA illisible")
        ips = compute_ips(d.get("ips_criteria"), d.get("knockout"), d.get("goal_fit"), doc.get("posted_at"), "aucun", False)
        report = build_decision_report(ips, d)
        await db.radar_offers.update_one({"id": doc["id"]}, {"$set": {
            "analyzed_at": _now().isoformat(), "ips": ips, "decision_report": report,
            "reasons_apply": (d.get("reasons_apply") or [])[:3], "reasons_avoid": (d.get("reasons_avoid") or [])[:3]}})

    async def run_for_user(user_id: str, trigger: str) -> dict:
        profile = await db.career_profiles.find_one({"user_id": user_id}, {"_id": 0}) or {}
        cv = (profile.get("cv_text") or "").strip()
        st = await _settings(user_id, profile)
        run = {"id": str(uuid.uuid4()), "user_id": user_id, "at": _now().isoformat(), "trigger": trigger,
               "fetched": 0, "new": 0, "known": 0, "analyzed": 0, "skipped_limit": 0, "errors": {}, "sources": S.configured(),
               "selected_sources": st["sources"], "by_source": {g: {"fetched": 0, "analyzed": 0} for g in ("jooble", "workday", "boards", "adzuna")},
               "status": "running"}
        await db.radar_runs.insert_one(dict(run))
        if len(cv) < 80:
            run["errors"]["cv"] = "Ajoutez votre CV dans la Career Memory pour activer le Radar."
        else:
            offers, run["errors"] = await _fetch(st)
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
                    await db.radar_offers.update_one({"id": existing["id"]}, {"$set": {"last_seen": _now().isoformat()}})
                    continue
                doc = {"id": str(uuid.uuid4()), "user_id": user_id, "dedupe_key": k, **o, "first_seen": _now().isoformat(),
                       "last_seen": _now().isoformat(), "run_id": run["id"], "status": "nouvelle", "ips": None, "decision_report": None,
                       "analyzed_at": None, "application_id": None}
                await db.radar_offers.insert_one(dict(doc))
                fresh.append(doc)
            run["fetched"], run["new"] = len(seen), len(fresh)
            budget = max(0, DAILY_LIMIT - await _analyzed_today(user_id))
            fresh_ids = {d["id"] for d in fresh}
            backlog = [d async for d in db.radar_offers.find({"user_id": user_id, "ips": None, "status": "nouvelle"}, {"_id": 0}).sort("first_seen", -1).limit(DAILY_LIMIT * 4)
                       if d["id"] not in fresh_ids]  # offers deferred by an earlier daily limit
            queue = fresh + backlog
            todo, run["skipped_limit"] = queue[:budget], max(0, len(queue) - budget)
            sem = asyncio.Semaphore(4)

            async def one(doc):
                async with sem:
                    try:
                        await _analyze(doc, cv, profile)
                        run["by_source"][S.group(doc["source"])]["analyzed"] += 1
                        return True
                    except Exception as e:  # noqa: BLE001
                        logger.warning("radar analyze %s failed: %s", doc["id"], e)
                        return False
            run["analyzed"] = sum(await asyncio.gather(*(one(d) for d in todo)))
        run["status"], run["finished_at"] = "done", _now().isoformat()
        await db.radar_runs.update_one({"id": run["id"]}, {"$set": run})
        return run

    # ---------------- Member endpoints ----------------
    @router.get("/settings")
    async def get_settings(user: dict = Depends(current_user)):
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        return {**await _settings(user["id"], profile), "configured": S.configured(), "daily_limit": DAILY_LIMIT}

    @router.put("/settings")
    async def put_settings(body: RadarSettings, user: dict = Depends(current_user)):
        data = body.model_dump()
        conf = S.configured()
        data["sources"] = [x for x in data["sources"] if x != "adzuna" or conf["adzuna"]]  # Adzuna needs a key
        seen, comps = set(), []
        for co in data["companies"]:
            co["name"] = co["name"].strip()
            if co["portal_url"] and not co["kind"]:
                co["kind"], co["slug"] = S.parse_portal(co["portal_url"])
            if co["name"] and co["name"].lower() not in seen:
                seen.add(co["name"].lower())
                comps.append(co)
        data["companies"] = comps
        await db.radar_settings.update_one({"user_id": user["id"]}, {"$set": {**data, "updated_at": _now().isoformat()}, "$unset": {"boards": ""}}, upsert=True)
        return await get_settings(user)

    class PortalBody(BaseModel):
        url: str = Field(min_length=8, max_length=400)
        name: str = Field(default="", max_length=80)

    @router.post("/portal/detect")
    async def detect_portal(body: PortalBody, user: dict = Depends(current_user)):
        kind, slug = S.parse_portal(body.url)
        if not kind:
            return {"kind": "", "slug": "", "ok": False, "count": 0,
                    "message": "Portail sans flux public pris en charge : cette entreprise sera suivie via Jooble."}
        try:
            async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as c:
                if kind == "workday":
                    offers = await S.workday(c, slug, body.name or slug, [], max_details=0)
                else:
                    offers = await S.board(c, kind, slug, body.name or slug, [])
            return {"kind": kind, "slug": slug, "ok": True, "count": len(offers), "message": f"Portail {kind} vérifié."}
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

    @router.get("/dashboard")
    async def dashboard(user: dict = Depends(current_user)):
        q = {"user_id": user["id"]}
        proj = {"_id": 0, "description": 0, "dedupe_key": 0, "user_id": 0}
        offers = [o async for o in db.radar_offers.find(q, proj).sort("first_seen", -1).limit(400)]
        last = await db.radar_runs.find_one(q, {"_id": 0, "user_id": 0}, sort=[("at", -1)])
        active = [o for o in offers if o["status"] not in ("ignoree", "pack") and o.get("ips")]
        top = lambda p: sorted([o for o in active if o["ips"]["priority"] == p], key=lambda o: -o["ips"]["score"])[:20]  # noqa: E731
        st = await _settings(user["id"], {})
        return {
            "sources_status": {"configured": S.configured(), "selected": st["sources"]},
            "last_run": last, "analyzed_today": await _analyzed_today(user["id"]), "daily_limit": DAILY_LIMIT,
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

    @router.post("/offers/{offer_id}/pack")
    async def pack(offer_id: str, user: dict = Depends(current_user)):
        o = await db.radar_offers.find_one({"id": offer_id, "user_id": user["id"]}, {"_id": 0})
        if not o:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        if o.get("application_id"):
            return {"id": o["application_id"], "already": True}
        from .router import PackBody
        text = f"{o['title']} — {o['company']} — {o['location']}\nSource : {o['source']} · {o['url']}\n\n{o['description']}"
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
        users = [s["user_id"] async for s in db.radar_settings.find({"enabled": True}, {"user_id": 1})]
        users += [p["user_id"] async for p in db.career_profiles.find({"cv_text": {"$nin": ["", None]}}, {"user_id": 1}) if p["user_id"] not in users]
        disabled = {s["user_id"] async for s in db.radar_settings.find({"enabled": False}, {"user_id": 1})}

        async def all_runs():
            for uid in users:
                if uid not in disabled:
                    try:
                        await run_for_user(uid, "quotidien")
                    except Exception:  # noqa: BLE001
                        logger.exception("radar cron user %s", uid)
        asyncio.create_task(all_runs())
        return {"started": True, "members": len([u for u in users if u not in disabled])}

    return router


async def ensure_radar_indexes(db):
    await db.radar_offers.create_index([("user_id", 1), ("dedupe_key", 1)], unique=True)
    await db.radar_offers.create_index([("user_id", 1), ("first_seen", -1)])
    await db.radar_offers.create_index("id", unique=True)
    await db.radar_runs.create_index([("user_id", 1), ("at", -1)])
    await db.radar_settings.create_index("user_id", unique=True)
    await db.radar_runs.update_many({"status": "running"}, {"$set": {"status": "interrompue"}})
