"""CareerOS API — career dossiers built on immutable, versioned analyses.

Collections (multi-user; nothing is ever overwritten, only appended/versioned):
- users / career_profiles (+ career_profile_versions snapshot on every save)
- applications            : the career dossier. `code` CO-YYYY-NNNNNN is THE reference
                            (plus technical `id`). Mirrors the latest version for fast reads.
- application_versions    : one immutable doc per (re)analysis: inputs, profile snapshot,
                            parts, IPS, Decision Report.
- interviews / calendar_events / recruiters / followups / emails : dossier entities
                            linked by application_id + application_code (models.py).
- career_score_history    : every Career Score change.
- counters                : yearly sequence for application codes.
"""
import re
import asyncio
import logging
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel, Field
from pymongo import ReturnDocument

from . import knowledge as KB
from . import radar_sources as S
from . import prompts as PR
from .ips import compute_ips
from .decision_report import build_decision_report
from .career_score import compute_career_score
from .compare import compare_versions
from .models import ENTITIES, EntityPatch

logger = logging.getLogger("careeros")

PIPELINE = ["a_postuler", "postule", "entrevue", "offre", "refuse", "abandonne"]
PARTS = ["decision", "cv_ats", "cv_humain", "letter", "questions", "star"]
GOALS = ["trouver un emploi", "changer d'emploi", "changer d'industrie", "obtenir une promotion",
         "augmenter mon salaire", "devenir gestionnaire", "devenir directeur", "devenir consultant",
         "acquérir de nouvelles compétences", "préparer une transition", "développer mon réseau",
         "améliorer ma qualité de vie professionnelle"]


def _now():
    return datetime.now(timezone.utc).isoformat()


class ProfileBody(BaseModel):
    full_name: str = ""
    headline: str = ""
    location: str = ""
    country: str = Field(default="", max_length=60)
    province: str = Field(default="", max_length=60)
    city: str = Field(default="", max_length=80)
    cv_text: str = Field(default="", max_length=60000)
    goals: List[str] = []
    target_roles: str = ""
    sectors: str = ""
    salary_expectation: str = ""
    skills: List[str] = []
    certifications: List[str] = []
    education: List[str] = []
    languages: List[str] = []
    achievements: str = ""
    promotions: int = Field(default=0, ge=0, le=50)


class PackBody(BaseModel):
    offer_text: str = Field(default="", max_length=30000)
    offer_url: str = ""
    company_url: str = ""
    cv_text: str = Field(default="", max_length=60000)
    posted_date: str = ""
    network: str = "aucun"
    save_cv_to_memory: bool = False


class ReanalyzeBody(BaseModel):
    offer_text: Optional[str] = Field(default=None, max_length=30000)
    cv_text: Optional[str] = Field(default=None, max_length=60000)
    use_memory_cv: bool = False
    posted_date: Optional[str] = None
    network: Optional[str] = None
    change_note: str = Field(default="", max_length=500)


class StatusBody(BaseModel):
    pipeline_status: str
    note: Optional[str] = ""


def _report(doc: dict):
    """Serve the Decision Report in its current official form (older stored reports are
    re-derived on read from the stored IPS + decision — storage is never rewritten)."""
    r = doc.get("decision_report")
    if r and r.get("version") != 2 and doc.get("ips"):
        r = build_decision_report(doc["ips"], (doc.get("parts") or {}).get("decision") or {})
    return r


URGENT_DAYS = 3  # A/B offers not applied to after this delay are flagged
_URL = re.compile(r"https?://[^\s<>\"')]+")


def _offer_link(a: dict) -> str:
    """Where to apply: link saved by the member, Radar offer URL, URL given at creation, or first URL of the offer text."""
    inp = a.get("inputs") or {}
    m = _URL.search(inp.get("offer_text") or "")
    return a.get("offer_link") or (a.get("origin") or {}).get("url") or (inp.get("offer_url") or "").strip() or (m.group(0).rstrip(".,;") if m else "")


def _summary(a: dict) -> dict:
    d = (a.get("parts") or {}).get("decision") or {}
    return {
        "id": a["id"], "code": a.get("code"), "created_at": a["created_at"], "status": a["status"],
        "pipeline_status": a.get("pipeline_status"), "poste": d.get("poste") or "",
        "apply_pending": bool(a.get("apply_opened_at")) and a.get("pipeline_status") == "a_postuler",
        "apply_urgent": a.get("pipeline_status") == "a_postuler" and (a.get("ips") or {}).get("priority") in ("A", "B")
                        and (a.get("created_at") or "9") < (datetime.now(timezone.utc) - timedelta(days=URGENT_DAYS)).isoformat(),
        "availability": (a.get("availability") or {}).get("status") or "",
        "entreprise": d.get("entreprise", ""), "ips": (a.get("ips") or {}).get("score"),
        "priority": (a.get("ips") or {}).get("priority"), "ats": (d.get("ats") or {}).get("score"),
        "version": a.get("current_version", 1), "ips_history": a.get("ips_history", []),
        "why": ((_report(a) or {}).get("summary") or "")[:220],
    }


async def next_application_code(db) -> str:
    year = datetime.now(timezone.utc).year
    c = await db.counters.find_one_and_update(
        {"_id": f"application_code_{year}"}, {"$inc": {"seq": 1}}, upsert=True, return_document=ReturnDocument.AFTER)
    return f"CO-{year}-{c['seq']:06d}"


def _version_summary(v: dict) -> dict:
    return {"version": v["version"], "created_at": v["created_at"], "status": v["status"], "change_note": v.get("change_note", ""),
            "ips": (v.get("ips") or {}).get("score"), "priority": (v.get("ips") or {}).get("priority"),
            "ats": (((v.get("parts") or {}).get("decision") or {}).get("ats") or {}).get("score")}


REQUIRED_KEYS = {"decision": ("ats", "ips_criteria", "recruiter_simulation")}
INVALID_CONTENT = "Le contenu généré par l'IA était incomplet ou mal formé."


class PartError(Exception):
    """Error whose message is safe to show to the member."""


AI_DOWN = ("Le service IA du serveur est temporairement indisponible (fournisseurs IA épuisés ou non configurés). "
           "Réessayez plus tard avec « Régénérer les sections manquantes ».")


def _friendly(e: Exception) -> str:
    if isinstance(e, PartError):
        return str(e)[:300]
    if getattr(e, "status_code", None) == 502:
        return AI_DOWN
    return "La génération a été interrompue (service IA indisponible ou réponse invalide)."


def create_careeros_router(db, current_user, generate_text, fetch_page_text, parse_json):
    router = APIRouter(prefix="/api/careeros", tags=["careeros"])

    # ---------------- Career Score (stored + historised; not displayed yet) ----------------
    async def recompute_career_score(user_id: str, trigger: str):
        try:
            profile = await db.career_profiles.find_one({"user_id": user_id}, {"_id": 0}) or {}
            apps = [_summary(a) | {"had_interview": a.get("had_interview", False)}
                    async for a in db.applications.find({"user_id": user_id, "archived": {"$ne": True}}, {"_id": 0})]
            cs = compute_career_score(profile, apps)
            prev = profile.get("career_score") or {}
            await db.career_profiles.update_one({"user_id": user_id}, {"$set": {"career_score": cs | {"updated_at": _now()}}}, upsert=True)
            if prev.get("score") != cs["score"] or prev.get("components") != cs["components"]:
                await db.career_score_history.insert_one({"user_id": user_id, "at": _now(), "trigger": trigger, **cs})
        except Exception:  # noqa: BLE001
            logger.exception("career score recompute failed")

    @router.get("/career-score")
    async def career_score(user: dict = Depends(current_user)):
        p = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "career_score": 1}) or {}
        hist = [h async for h in db.career_score_history.find({"user_id": user["id"]}, {"_id": 0, "user_id": 0}).sort("at", -1).limit(100)]
        return {"current": p.get("career_score"), "history": hist}

    # ---------------- Career Memory ----------------
    @router.get("/meta")
    async def meta():
        return {"goals": GOALS, "pipeline": PIPELINE, "entities": list(ENTITIES)}

    @router.get("/profile")
    async def get_profile(user: dict = Depends(current_user)):
        p = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "career_score": 0})
        out = {**ProfileBody().model_dump(), "skills_detected": [], **(p or {}), "user_id": user["id"]}
        if not (out["country"] or out["province"] or out["city"]):  # older profiles: pre-filled from the location, editable
            from .geo import member_geo
            out.update(member_geo(out))
        return out

    @router.put("/profile")
    async def put_profile(body: ProfileBody, user: dict = Depends(current_user)):
        data = body.model_dump()
        await db.career_profiles.update_one(
            {"user_id": user["id"]}, {"$set": {**data, "updated_at": _now()}, "$setOnInsert": {"skills_detected": []}}, upsert=True)
        await db.career_profile_versions.insert_one({"user_id": user["id"], "at": _now(), **data})
        await recompute_career_score(user["id"], "profile_saved")
        return await get_profile(user)

    # ---------------- Pack generation (writes into ONE immutable version) ----------------
    async def _write(app_id, version, field, value):
        await db.application_versions.update_one({"application_id": app_id, "version": version}, {"$set": {field: value}})
        await db.applications.update_one({"id": app_id, "current_version": version}, {"$set": {field: value, "updated_at": _now()}})

    async def _json_part(app_id, version, name, prompt_fn, ctx):
        sysm, txt = prompt_fn(*ctx)
        data = None
        for attempt in range(2):  # one retry when the AI returns malformed or truncated JSON
            data = parse_json((await generate_text(sysm, txt)).strip())
            if isinstance(data, dict) and all(isinstance(data.get(k), dict) for k in REQUIRED_KEYS.get(name, ())):
                break
            data = None
            logger.warning("pack %s v%s part %s: invalid JSON (attempt %s)", app_id, version, name, attempt + 1)
        if not isinstance(data, dict):
            raise PartError(INVALID_CONTENT)
        await _write(app_id, version, f"parts.{name}", data)
        return data

    async def _text_part(app_id, version, name, prompt_fn, ctx):
        sysm, txt = prompt_fn(*ctx)
        out = (await generate_text(sysm, txt, tier="premium" if name == "letter" else "eco")).strip()
        if not out:
            raise PartError("Le service IA a renvoyé une réponse vide.")
        await _write(app_id, version, f"parts.{name}", out)
        return out

    async def _run_pack(app_id, user_id, version, inputs: dict, profile: dict, only: Optional[list] = None):
        try:
            offer = (inputs.get("offer_text") or "").strip()
            if (inputs.get("offer_url") or "").strip():
                try:
                    offer = (offer + "\n\n" + await fetch_page_text(inputs["offer_url"].strip())).strip()
                except Exception as e:  # noqa: BLE001
                    logger.warning("offer fetch failed: %s", e)
                    if not offer:
                        raise PartError("Impossible de lire le lien de l'offre (site protégé ?). Collez le texte de l'offre.")
            company = ""
            if (inputs.get("company_url") or "").strip():
                try:
                    company = await fetch_page_text(inputs["company_url"].strip())
                except Exception as e:  # noqa: BLE001
                    logger.warning("company fetch failed: %s", e)
            await _write(app_id, version, "inputs.offer_resolved", offer[:30000])
            ctx = (inputs["cv_text"], offer, company, profile)
            jobs = {
                "decision": _json_part(app_id, version, "decision", PR.decision_prompt, ctx),
                "cv_ats": _text_part(app_id, version, "cv_ats", lambda *c: PR.cv_prompt("ats", *c), ctx),
                "cv_humain": _text_part(app_id, version, "cv_humain", lambda *c: PR.cv_prompt("humain", *c), ctx),
                "letter": _text_part(app_id, version, "letter", PR.letter_prompt, ctx),
                "questions": _json_part(app_id, version, "questions", PR.questions_prompt, ctx),
                "star": _json_part(app_id, version, "star", PR.star_prompt, ctx),
            }
            existing = {}
            if only:
                for k in [k for k in jobs if k not in only]:
                    jobs.pop(k).close()
                v = await db.application_versions.find_one({"application_id": app_id, "version": version}, {"_id": 0, "parts": 1, "errors": 1})
                existing = v or {}
            results = dict(zip(jobs, await asyncio.gather(*jobs.values(), return_exceptions=True)))
            for k, r in results.items():
                if isinstance(r, Exception) and not isinstance(r, PartError):
                    logger.error("pack %s v%s part %s failed: %r", app_id, version, k, r)
            errors = {**{k: e for k, e in (existing.get("errors") or {}).items() if k not in results},
                      **{k: _friendly(r) for k, r in results.items() if isinstance(r, Exception)}}
            done_parts = {**(existing.get("parts") or {}), **{k: r for k, r in results.items() if not isinstance(r, Exception)}}
            decision = done_parts.get("decision") if "decision" in results else None
            status = "done" if not errors else ("error" if not any(done_parts.get(p) for p in PARTS) else "partial")
            if decision:
                ips = compute_ips(decision.get("ips_criteria"), decision.get("knockout"), decision.get("goal_fit"),
                                  inputs.get("posted_date"), inputs.get("network"), bool(done_parts.get("letter")))
                await _write(app_id, version, "ips", ips)
                await _write(app_id, version, "decision_report", build_decision_report(ips, decision))
                await db.applications.update_one({"id": app_id}, {"$push": {"ips_history": {
                    "version": version, "score": ips["score"], "priority": ips["priority"],
                    "ats": (decision.get("ats") or {}).get("score"), "at": _now()}}})
                skills = [s for s in (decision.get("skills_detected") or []) if isinstance(s, str)][:40]
                if skills:
                    await db.career_profiles.update_one(
                        {"user_id": user_id}, {"$addToSet": {"skills_detected": {"$each": skills}}, "$set": {"updated_at": _now()}}, upsert=True)
            await _write(app_id, version, "errors", errors)
            await _write(app_id, version, "status", status)
            await db.applications.update_one({"id": app_id}, {"$push": {"timeline": {"at": _now(), "type": "pack_generated", "version": version, "detail": status}}})
            await recompute_career_score(user_id, f"pack_v{version}")
        except Exception as e:  # noqa: BLE001
            logger.exception("pack %s v%s failed", app_id, version)
            await _write(app_id, version, "errors", {"pack": _friendly(e)})
            await _write(app_id, version, "status", "error")

    async def _start_version(app: dict, version: int, inputs: dict, profile: dict, change_note: str):
        snapshot = {k: profile.get(k) for k in ("goals", "skills", "certifications", "education", "languages", "target_roles", "headline")}
        await db.application_versions.insert_one({
            "application_id": app["id"], "application_code": app["code"], "user_id": app["user_id"], "version": version,
            "created_at": _now(), "status": "generating", "change_note": change_note, "inputs": inputs,
            "profile_snapshot": snapshot, "parts": {p: None for p in PARTS}, "ips": None, "decision_report": None, "errors": {},
        })
        asyncio.create_task(_run_pack(app["id"], app["user_id"], version, inputs, profile))

    @router.post("/packs")
    async def create_pack(body: PackBody, user: dict = Depends(current_user)):
        return await _create_pack(body, user)

    async def _create_pack(body: PackBody, user: dict, origin: Optional[dict] = None):
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        cv = body.cv_text.strip() or (profile.get("cv_text") or "").strip()
        if len(cv) < 80:
            raise HTTPException(status_code=400, detail="CV manquant : collez votre CV ou enregistrez-le dans votre Career Memory.")
        if len(body.offer_text.strip()) < 80 and not body.offer_url.strip():
            raise HTTPException(status_code=400, detail="Offre manquante : collez le texte de l'offre ou son lien.")
        if body.network not in ("aucun", "contact", "recommandation"):
            raise HTTPException(status_code=400, detail="Valeur réseau invalide")
        if body.save_cv_to_memory and body.cv_text.strip():
            await db.career_profiles.update_one({"user_id": user["id"]}, {"$set": {"cv_text": cv, "updated_at": _now()}}, upsert=True)
        inputs = {"offer_text": body.offer_text[:30000], "offer_url": body.offer_url, "company_url": body.company_url,
                  "cv_text": cv[:60000], "posted_date": body.posted_date, "network": body.network}
        app = {
            "id": str(uuid.uuid4()), "code": await next_application_code(db), "user_id": user["id"],
            "created_at": _now(), "updated_at": _now(), "status": "generating", "pipeline_status": "a_postuler",
            "current_version": 1, "inputs": inputs, "parts": {p: None for p in PARTS}, "errors": {}, "ips": None,
            "decision_report": None, "ips_history": [], "had_interview": False, "archived": False,
            "timeline": [{"at": _now(), "type": "created", "version": 1, "detail": ""}],
            "origin": origin or {"type": "manual"},
        }
        await db.applications.insert_one(dict(app))
        await _start_version(app, 1, inputs, profile, "Analyse initiale")
        return {"id": app["id"], "code": app["code"], "version": 1, "status": "generating"}

    # ---------------- Dossier / history ----------------
    async def _own(app_id, user):
        a = await db.applications.find_one({"id": app_id, "user_id": user["id"], "archived": {"$ne": True}}, {"_id": 0})
        if not a:
            raise HTTPException(status_code=404, detail="Candidature introuvable")
        return a

    @router.get("/applications")
    async def list_apps(user: dict = Depends(current_user)):
        cur = db.applications.find({"user_id": user["id"], "archived": {"$ne": True}}, {"_id": 0, "inputs": 0}).sort("created_at", -1).limit(300)
        return [_summary(a) async for a in cur]

    @router.get("/applications/{app_id}")
    async def get_app(app_id: str, user: dict = Depends(current_user)):
        a = await _own(app_id, user)
        a["decision_report"] = _report(a)
        a["offer_link"] = _offer_link(a)
        a["offer_source"] = (a.get("offer_link_source") if a.get("offer_link") else "") or (a.get("origin") or {}).get("source") or ""
        from . import offer_check as OC
        title, company, loc = await _offer_meta(a)
        card = await KB.lookup(db, company) if company else None
        prof = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "location": 1, "country": 1, "province": 1, "city": 1}) or {}
        from .geo import member_geo
        a["search_links"] = OC.search_links(title, company, loc, (card or {}).get("portal_url") or (a.get("inputs") or {}).get("company_url") or "",
                                            member_geo(prof, loc)["province"])
        a["auto_sources"] = ["Portail officiel"] + [n for k, n in (("jooble", "Jooble"), ("adzuna", "Adzuna"), ("careerjet", "Careerjet")) if S.configured().get(k)]
        a["versions"] = [_version_summary(v) async for v in db.application_versions.find(
            {"application_id": app_id}, {"_id": 0, "inputs": 0}).sort("version", 1)]
        return a

    @router.post("/applications/{app_id}/reanalyze")
    async def reanalyze(app_id: str, body: ReanalyzeBody, user: dict = Depends(current_user)):
        a = await _own(app_id, user)
        if a["status"] == "generating":
            raise HTTPException(status_code=409, detail="Une analyse est déjà en cours pour cette candidature")
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        inputs = dict(a["inputs"])
        inputs.pop("offer_resolved", None)
        if body.use_memory_cv and (profile.get("cv_text") or "").strip():
            inputs["cv_text"] = profile["cv_text"][:60000]
        elif body.cv_text is not None and body.cv_text.strip():
            inputs["cv_text"] = body.cv_text.strip()[:60000]
        if body.offer_text is not None and body.offer_text.strip():
            inputs["offer_text"] = body.offer_text.strip()[:30000]
        if body.posted_date is not None:
            inputs["posted_date"] = body.posted_date
        if body.network is not None:
            if body.network not in ("aucun", "contact", "recommandation"):
                raise HTTPException(status_code=400, detail="Valeur réseau invalide")
            inputs["network"] = body.network
        version = a.get("current_version", 1) + 1
        await db.applications.update_one({"id": app_id}, {
            "$set": {"current_version": version, "status": "generating", "inputs": inputs, "parts": {p: None for p in PARTS},
                     "ips": None, "decision_report": None, "errors": {}, "updated_at": _now()},
            "$push": {"timeline": {"at": _now(), "type": "reanalyze", "version": version, "detail": body.change_note}},
        })
        await _start_version(a, version, inputs, profile, body.change_note or f"Réanalyse v{version}")
        return {"id": app_id, "code": a["code"], "version": version, "status": "generating"}

    @router.post("/applications/{app_id}/retry")
    async def retry_parts(app_id: str, user: dict = Depends(current_user)):
        """Regenerate only the failed sections of the current version (same inputs, nothing overwritten)."""
        a = await _own(app_id, user)
        if a["status"] == "generating":
            raise HTTPException(status_code=409, detail="Une analyse est déjà en cours pour cette candidature")
        missing = [p for p in PARTS if not (a.get("parts") or {}).get(p)]
        if not missing:
            raise HTTPException(status_code=400, detail="Toutes les sections sont déjà disponibles")
        version = a.get("current_version", 1)
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        await _write(app_id, version, "status", "generating")
        await db.applications.update_one({"id": app_id}, {"$push": {"timeline": {"at": _now(), "type": "retry", "version": version, "detail": ",".join(missing)}}})
        inputs = {k: v for k, v in a["inputs"].items() if k != "offer_resolved"}
        asyncio.create_task(_run_pack(app_id, a["user_id"], version, inputs, profile, only=missing))
        return {"id": app_id, "version": version, "retrying": missing}

    @router.get("/applications/{app_id}/versions/{version}")
    async def get_version(app_id: str, version: int, user: dict = Depends(current_user)):
        await _own(app_id, user)
        v = await db.application_versions.find_one({"application_id": app_id, "version": version}, {"_id": 0})
        if not v:
            raise HTTPException(status_code=404, detail="Version introuvable")
        v["decision_report"] = _report(v)
        return v

    @router.get("/applications/{app_id}/compare")
    async def compare(app_id: str, a: int, b: int, user: dict = Depends(current_user)):
        await _own(app_id, user)
        va = await db.application_versions.find_one({"application_id": app_id, "version": a}, {"_id": 0})
        vb = await db.application_versions.find_one({"application_id": app_id, "version": b}, {"_id": 0})
        if not va or not vb:
            raise HTTPException(status_code=404, detail="Version introuvable")
        return compare_versions(va, vb)

    @router.patch("/applications/{app_id}/status")
    async def set_status(app_id: str, body: StatusBody, user: dict = Depends(current_user)):
        if body.pipeline_status not in PIPELINE:
            raise HTTPException(status_code=400, detail="Statut invalide")
        await _own(app_id, user)
        upd = {"pipeline_status": body.pipeline_status, "updated_at": _now()}
        if body.pipeline_status in ("entrevue", "offre"):
            upd["had_interview"] = True
        cur = await _own(app_id, user)
        if body.pipeline_status == "postule" and not cur.get("applied_at"):
            upd["applied_at"] = _now()
        await db.applications.update_one({"id": app_id}, {
            "$unset": {"apply_opened_at": ""}, "$set": upd, "$push": {"timeline": {"at": _now(), "type": "status", "detail": body.pipeline_status, "note": body.note or ""}}})
        await recompute_career_score(user["id"], "status_changed")
        return {"ok": True, "pipeline_status": body.pipeline_status}

    class LinkBody(BaseModel):
        url: str = Field(max_length=2000)
        source: str = Field(default="", max_length=60)

    @router.put("/applications/{app_id}/offer-link")
    async def set_offer_link(app_id: str, body: LinkBody, user: dict = Depends(current_user)):
        await _own(app_id, user)
        url = body.url.strip()
        if not re.match(r"^https?://\S+\.\S+", url):
            raise HTTPException(status_code=400, detail="Lien invalide : collez l'adresse complète de l'offre (https://…).")
        from . import offer_check as OC
        a = await _own(app_id, user)
        av = await OC.check_url(url)
        alts = [x for x in a.get("alternatives") or [] if x.get("url") != url]
        await db.applications.update_one({"id": app_id}, {"$set": {"offer_link": url, "offer_link_source": body.source.strip(), "availability": av, "alternatives": alts, "updated_at": _now()}})
        return {"ok": True, "offer_link": url, "availability": av, "alternatives": alts}

    @router.post("/applications/{app_id}/apply-opened")
    async def apply_opened(app_id: str, user: dict = Depends(current_user)):
        a = await _own(app_id, user)
        if a.get("pipeline_status") == "a_postuler":
            await db.applications.update_one({"id": app_id}, {"$set": {"apply_opened_at": _now()},
                                                              "$push": {"timeline": {"at": _now(), "type": "apply_opened", "detail": "Offre ouverte pour postuler", "note": ""}}})
        return {"ok": True}

    @router.post("/applications/{app_id}/applied")
    async def applied(app_id: str, user: dict = Depends(current_user)):
        a = await _own(app_id, user)
        now = _now()
        if a.get("pipeline_status") != "a_postuler":  # never downgrade a later stage (interview, offer…)
            return {"ok": True, "pipeline_status": a.get("pipeline_status"), "applied_at": a.get("applied_at")}
        await db.applications.update_one({"id": app_id}, {"$set": {"pipeline_status": "postule", "applied_at": now, "updated_at": now}, "$unset": {"apply_opened_at": ""},
                                                          "$push": {"timeline": {"at": now, "type": "status", "detail": "postule", "note": "Candidature envoyée (confirmée par le membre)"}}})
        await recompute_career_score(user["id"], "status_changed")
        return {"ok": True, "pipeline_status": "postule", "applied_at": now}

    @router.post("/applications/{app_id}/apply-not-yet")
    async def apply_not_yet(app_id: str, user: dict = Depends(current_user)):
        await _own(app_id, user)
        await db.applications.update_one({"id": app_id}, {"$unset": {"apply_opened_at": ""}})
        return {"ok": True}

    @router.delete("/applications/{app_id}")
    async def archive_app(app_id: str, user: dict = Depends(current_user)):
        await _own(app_id, user)
        await db.applications.update_one({"id": app_id}, {"$set": {"archived": True, "archived_at": _now()},
                                                          "$push": {"timeline": {"at": _now(), "type": "archived", "detail": ""}}})
        await recompute_career_score(user["id"], "archived")
        return {"ok": True, "archived": True}

    # ---------------- Dossier entities (interviews, calendar, recruiters, followups, emails) ----------------
    @router.get("/applications/{app_id}/dossier")
    async def dossier(app_id: str, user: dict = Depends(current_user)):
        a = await _own(app_id, user)
        out = {"code": a["code"], "id": app_id}
        for name in ENTITIES:
            out[name] = [d async for d in db[name].find({"application_id": app_id}, {"_id": 0}).sort("created_at", 1)]
        return out

    def _entity_routes(name, model):
        @router.post(f"/applications/{{app_id}}/{name}", name=f"create_{name}")
        async def create_entity(app_id: str, body: model, user: dict = Depends(current_user)):
            a = await _own(app_id, user)
            doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "application_id": app_id, "application_code": a["code"],
                   "source": "member", "created_at": _now(), "updated_at": _now(), "revisions": [], **body.model_dump()}
            await db[name].insert_one(dict(doc))
            await db.applications.update_one({"id": app_id}, {"$push": {"timeline": {"at": _now(), "type": f"{name}_added", "detail": doc["id"]}}})
            return doc

        @router.patch(f"/applications/{{app_id}}/{name}/{{entity_id}}", name=f"update_{name}")
        async def update_entity(app_id: str, entity_id: str, body: EntityPatch, user: dict = Depends(current_user)):
            await _own(app_id, user)
            cur = await db[name].find_one({"id": entity_id, "application_id": app_id}, {"_id": 0, "revisions": 0})
            if not cur:
                raise HTTPException(status_code=404, detail="Élément introuvable")
            merged = model(**{**{k: cur.get(k) for k in model.model_fields if k in cur}, **body.changes}).model_dump()
            await db[name].update_one({"id": entity_id}, {"$set": {**merged, "updated_at": _now()},
                                                          "$push": {"revisions": {"at": _now(), "previous": {k: cur.get(k) for k in model.model_fields}}}})
            return await db[name].find_one({"id": entity_id}, {"_id": 0})

    for _name, _model in ENTITIES.items():
        _entity_routes(_name, _model)

    async def _offer_meta(a: dict) -> tuple:
        d = (a.get("parts") or {}).get("decision") or {}
        o = {}
        if (a.get("origin") or {}).get("radar_offer_id"):
            o = await db.radar_offers.find_one({"id": a["origin"]["radar_offer_id"]}, {"_id": 0, "title": 1, "company": 1, "location": 1}) or {}
        if not o.get("location"):
            st = await db.radar_settings.find_one({"user_id": a["user_id"]}, {"_id": 0, "location": 1}) or {}
            o["location"] = st.get("location") or ""
        return d.get("poste") or o.get("title") or "", d.get("entreprise") or o.get("company") or "", o.get("location") or ""

    async def check_application(a: dict, search: bool = False, client: dict = None) -> dict:
        """Availability of the offer link; when expired (or on demand) look for the same offer elsewhere."""
        from . import offer_check as OC
        link = _offer_link(a)
        av = await OC.check_url(link)
        title, company, loc = await _offer_meta(a)
        if av["status"] == "unknown" and "jooble." in link:
            listed = await OC.jooble_listed(title, company, loc, link)
            if listed is not None:
                av = {**av, "status": "available" if listed else "expired_likely",
                      "detail": "Toujours listée dans les résultats Jooble." if listed else "Ne figure plus dans les résultats Jooble : l'annonce a probablement été retirée."}
        upd = {"availability": av}
        if search or av["status"] in ("expired", "expired_likely"):
            upd["alternatives"] = await OC.find_elsewhere(db, a["user_id"], title, company, loc, link, client) if title else []
            upd["alternatives_at"] = _now()
        await db.applications.update_one({"id": a["id"]}, {"$set": upd})
        return {**{"alternatives": a.get("alternatives") or [], "alternatives_at": a.get("alternatives_at")}, **upd}

    @router.post("/applications/{app_id}/availability")
    async def availability(request: Request, app_id: str, search: bool = False, user: dict = Depends(current_user)):
        a = await _own(app_id, user)
        ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or (request.client.host if request.client else "")
        return await check_application(a, search, {"ip": ip, "ua": request.headers.get("user-agent", "")})

    router.create_pack_internal = _create_pack
    router.check_application = check_application
    router.own_application = _own
    return router


async def ensure_careeros_indexes(db):
    await db.career_profiles.create_index("user_id", unique=True)
    await db.career_profile_versions.create_index([("user_id", 1), ("at", -1)])
    await db.applications.create_index([("user_id", 1), ("created_at", -1)])
    await db.applications.create_index("id", unique=True)
    await db.applications.create_index("code", unique=True, sparse=True)
    await db.application_versions.create_index([("application_id", 1), ("version", 1)], unique=True)
    await db.application_versions.create_index("application_code")
    await db.career_score_history.create_index([("user_id", 1), ("at", -1)])
    for name in ENTITIES:
        await db[name].create_index([("application_id", 1), ("created_at", 1)])
        await db[name].create_index("application_code")
        await db[name].create_index("id", unique=True)
    await _migrate_legacy(db)
    await _recover_interrupted(db)


async def _recover_interrupted(db):
    """Background generations die with the process (deploy/restart): flag them so the
    member can relaunch — the partial results already written stay in the version."""
    msg = {"pack": "Génération interrompue (redémarrage du serveur). Relancez une réanalyse."}
    async for v in db.application_versions.find({"status": "generating"}, {"_id": 0, "application_id": 1, "version": 1}):
        await db.application_versions.update_one({"application_id": v["application_id"], "version": v["version"]},
                                                 {"$set": {"status": "error", "errors": msg}})
        await db.applications.update_one({"id": v["application_id"], "current_version": v["version"]},
                                         {"$set": {"status": "error", "errors": msg}})


async def _migrate_legacy(db):
    """Give pre-versioning applications a CO code + an immutable v1 version."""
    async for a in db.applications.find({"code": {"$exists": False}}, {"_id": 0}):
        code = await next_application_code(db)
        ips = a.get("ips")
        decision = (a.get("parts") or {}).get("decision") or {}
        report = build_decision_report(ips, decision) if ips else None
        hist = [{"version": 1, "score": ips["score"], "priority": ips["priority"], "ats": (decision.get("ats") or {}).get("score"), "at": a["created_at"]}] if ips else []
        await db.application_versions.update_one({"application_id": a["id"], "version": 1}, {"$setOnInsert": {
            "application_id": a["id"], "application_code": code, "user_id": a["user_id"], "version": 1, "created_at": a["created_at"],
            "status": a.get("status"), "change_note": "Analyse initiale", "inputs": a.get("inputs"), "profile_snapshot": {},
            "parts": a.get("parts"), "ips": ips, "decision_report": report, "errors": a.get("errors", {})}}, upsert=True)
        await db.applications.update_one({"id": a["id"]}, {
            "$set": {"code": code, "current_version": 1, "decision_report": report, "ips_history": hist,
                     "had_interview": a.get("pipeline_status") in ("entrevue", "offre"), "archived": False},
            "$unset": {"interviews": "", "followups": "", "calendar_events": "", "emails": ""}})
