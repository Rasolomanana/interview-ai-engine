"""CareerOS API: Career Memory (profile), one-click Application Pack, application history.

Data model (multi-user, built to host future engines):
- users              : member accounts (auth.py)
- career_profiles    : Career Memory — one living profile per member
- applications       : one per opportunity — inputs, pack documents, IPS, pipeline status,
                       plus reserved arrays for future engines (interviews, followups,
                       calendar_events, emails, timeline) used by Plan du Jour / Automation / Calendar.
"""
import asyncio
import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field

from . import prompts as PR
from .ips import compute_ips

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
    cv_text: str = Field(default="", max_length=60000)
    goals: List[str] = []
    target_roles: str = ""
    sectors: str = ""
    salary_expectation: str = ""
    skills: List[str] = []
    certifications: List[str] = []
    languages: List[str] = []
    achievements: str = ""


class PackBody(BaseModel):
    offer_text: str = Field(default="", max_length=30000)
    offer_url: str = ""
    company_url: str = ""
    cv_text: str = Field(default="", max_length=60000)
    posted_date: str = ""
    network: str = "aucun"
    save_cv_to_memory: bool = False


class StatusBody(BaseModel):
    pipeline_status: str
    note: Optional[str] = ""


def _summary(a: dict) -> dict:
    d = (a.get("parts") or {}).get("decision") or {}
    return {
        "id": a["id"], "created_at": a["created_at"], "status": a["status"],
        "pipeline_status": a.get("pipeline_status"), "poste": d.get("poste") or a.get("title", ""),
        "entreprise": d.get("entreprise", ""), "ips": (a.get("ips") or {}).get("score"),
        "priority": (a.get("ips") or {}).get("priority"), "ats": (d.get("ats") or {}).get("score"),
    }


def create_careeros_router(db, current_user, generate_text, fetch_page_text, parse_json):
    router = APIRouter(prefix="/api/careeros", tags=["careeros"])

    # ---------------- Career Memory ----------------
    @router.get("/meta")
    async def meta():
        return {"goals": GOALS, "pipeline": PIPELINE}

    @router.get("/profile")
    async def get_profile(user: dict = Depends(current_user)):
        p = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0})
        return p or {"user_id": user["id"], **ProfileBody().model_dump(), "skills_detected": [], "updated_at": None}

    @router.put("/profile")
    async def put_profile(body: ProfileBody, user: dict = Depends(current_user)):
        await db.career_profiles.update_one(
            {"user_id": user["id"]},
            {"$set": {**body.model_dump(), "updated_at": _now()}, "$setOnInsert": {"skills_detected": []}},
            upsert=True,
        )
        return await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0})

    # ---------------- Application Pack ----------------
    async def _set(app_id, field, value):
        await db.applications.update_one({"id": app_id}, {"$set": {field: value, "updated_at": _now()}})

    async def _json_part(app_id, name, prompt_fn, ctx):
        sysm, txt = prompt_fn(*ctx)
        data = parse_json((await generate_text(sysm, txt)).strip())
        if data is None:
            raise ValueError("Réponse illisible")
        await _set(app_id, f"parts.{name}", data)
        return data

    async def _text_part(app_id, name, prompt_fn, ctx):
        sysm, txt = prompt_fn(*ctx)
        out = (await generate_text(sysm, txt)).strip()
        if not out:
            raise ValueError("Réponse vide")
        await _set(app_id, f"parts.{name}", out)
        return out

    async def _run_pack(app_id, user_id, body: PackBody, cv: str, profile: dict):
        try:
            offer = body.offer_text.strip()
            if body.offer_url.strip():
                try:
                    fetched = await fetch_page_text(body.offer_url.strip())
                    offer = (offer + "\n\n" + fetched).strip()
                except Exception as e:  # noqa: BLE001
                    logger.warning("offer fetch failed: %s", e)
                    if not offer:
                        raise ValueError("Impossible de lire le lien de l'offre (site protégé ?). Collez le texte de l'offre.")
            company = ""
            if body.company_url.strip():
                try:
                    company = await fetch_page_text(body.company_url.strip())
                except Exception as e:  # noqa: BLE001
                    logger.warning("company fetch failed: %s", e)
            await _set(app_id, "inputs.offer_resolved", offer[:30000])
            ctx = (cv, offer, company, profile)
            jobs = {
                "decision": _json_part(app_id, "decision", PR.decision_prompt, ctx),
                "cv_ats": _text_part(app_id, "cv_ats", lambda *c: PR.cv_prompt("ats", *c), ctx),
                "cv_humain": _text_part(app_id, "cv_humain", lambda *c: PR.cv_prompt("humain", *c), ctx),
                "letter": _text_part(app_id, "letter", PR.letter_prompt, ctx),
                "questions": _json_part(app_id, "questions", PR.questions_prompt, ctx),
                "star": _json_part(app_id, "star", PR.star_prompt, ctx),
            }
            results = await asyncio.gather(*jobs.values(), return_exceptions=True)
            errors = {k: str(r)[:300] for k, r in zip(jobs, results) if isinstance(r, Exception)}
            out = dict(zip(jobs, results))
            decision = out["decision"] if not isinstance(out["decision"], Exception) else {}
            ips = compute_ips(decision.get("ips_criteria"), decision.get("knockout"), decision.get("goal_fit"),
                              body.posted_date, body.network, not isinstance(out["letter"], Exception))
            if decision:
                await _set(app_id, "ips", ips)
                skills = [s for s in (decision.get("skills_detected") or []) if isinstance(s, str)][:40]
                if skills:
                    await db.career_profiles.update_one(
                        {"user_id": user_id}, {"$addToSet": {"skills_detected": {"$each": skills}}, "$set": {"updated_at": _now()}}, upsert=True)
            status = "done" if not errors else ("error" if len(errors) == len(jobs) else "partial")
            await db.applications.update_one({"id": app_id}, {
                "$set": {"status": status, "errors": errors, "updated_at": _now()},
                "$push": {"timeline": {"at": _now(), "type": "pack_generated", "detail": status}},
            })
        except Exception as e:  # noqa: BLE001
            logger.exception("pack %s failed", app_id)
            await db.applications.update_one({"id": app_id}, {"$set": {"status": "error", "errors": {"pack": str(e)[:300]}, "updated_at": _now()}})

    @router.post("/packs")
    async def create_pack(body: PackBody, user: dict = Depends(current_user)):
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
        app_id = str(uuid.uuid4())
        await db.applications.insert_one({
            "id": app_id, "user_id": user["id"], "created_at": _now(), "updated_at": _now(),
            "status": "generating", "pipeline_status": "a_postuler",
            "inputs": {"offer_text": body.offer_text[:30000], "offer_url": body.offer_url, "company_url": body.company_url,
                       "cv_text": cv[:60000], "posted_date": body.posted_date, "network": body.network},
            "parts": {p: None for p in PARTS}, "errors": {}, "ips": None,
            "timeline": [{"at": _now(), "type": "created", "detail": ""}],
            "interviews": [], "followups": [], "calendar_events": [], "emails": [],
        })
        asyncio.create_task(_run_pack(app_id, user["id"], body, cv, profile))
        return {"id": app_id, "status": "generating"}

    # ---------------- History ----------------
    async def _own(app_id, user):
        a = await db.applications.find_one({"id": app_id, "user_id": user["id"]}, {"_id": 0})
        if not a:
            raise HTTPException(status_code=404, detail="Candidature introuvable")
        return a

    @router.get("/applications")
    async def list_apps(user: dict = Depends(current_user)):
        cur = db.applications.find({"user_id": user["id"]}, {"_id": 0, "inputs": 0}).sort("created_at", -1).limit(200)
        return [_summary(a) async for a in cur]

    @router.get("/applications/{app_id}")
    async def get_app(app_id: str, user: dict = Depends(current_user)):
        return await _own(app_id, user)

    @router.patch("/applications/{app_id}/status")
    async def set_status(app_id: str, body: StatusBody, user: dict = Depends(current_user)):
        if body.pipeline_status not in PIPELINE:
            raise HTTPException(status_code=400, detail="Statut invalide")
        await _own(app_id, user)
        await db.applications.update_one({"id": app_id}, {
            "$set": {"pipeline_status": body.pipeline_status, "updated_at": _now()},
            "$push": {"timeline": {"at": _now(), "type": "status", "detail": body.pipeline_status, "note": body.note or ""}},
        })
        return {"ok": True, "pipeline_status": body.pipeline_status}

    @router.delete("/applications/{app_id}")
    async def delete_app(app_id: str, user: dict = Depends(current_user)):
        await _own(app_id, user)
        await db.applications.delete_one({"id": app_id})
        return {"ok": True}

    return router


async def ensure_careeros_indexes(db):
    await db.career_profiles.create_index("user_id", unique=True)
    await db.applications.create_index([("user_id", 1), ("created_at", -1)])
    await db.applications.create_index("id", unique=True)
