"""Member-controlled sharing: nothing is shared unless the member explicitly authorises a person (advisor or relative), per scope, revocable."""
import uuid
from datetime import datetime, timezone
from typing import List, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr

from .router import _summary

SCOPES = {"cv": "CV", "memory": "Career Memory", "applications": "Candidatures"}
MEMORY_FIELDS = ("full_name", "headline", "location", "country", "province", "city", "goals", "target_roles", "sectors", "salary_expectation",
                 "skills", "certifications", "education", "languages", "achievements")


def _now():
    return datetime.now(timezone.utc).isoformat()


class GrantBody(BaseModel):
    email: EmailStr
    relation: Literal["conseiller", "proche"] = "conseiller"
    scopes: List[Literal["cv", "memory", "applications"]]


def create_sharing_router(db, current_user):
    router = APIRouter(prefix="/api/careeros/sharing")

    @router.get("")
    async def list_grants(user: dict = Depends(current_user)):
        given = [g async for g in db.share_grants.find({"owner_id": user["id"], "revoked_at": None}, {"_id": 0}).sort("created_at", -1)]
        received = [g async for g in db.share_grants.find({"grantee_email": user["email"].lower(), "revoked_at": None},
                                                         {"_id": 0, "id": 1, "owner_name": 1, "owner_email": 1, "relation": 1, "scopes": 1, "created_at": 1}).sort("created_at", -1)]
        return {"given": given, "received": received, "scopes": SCOPES}

    @router.post("")
    async def grant(body: GrantBody, user: dict = Depends(current_user)):
        email = body.email.lower()
        if email == user["email"].lower():
            raise HTTPException(status_code=400, detail="Vous ne pouvez pas partager avec votre propre compte.")
        if not body.scopes:
            raise HTTPException(status_code=400, detail="Cochez au moins une information à partager.")
        doc = {"id": str(uuid.uuid4()), "owner_id": user["id"], "owner_name": user.get("name") or "", "owner_email": user["email"], "grantee_email": email,
               "relation": body.relation, "scopes": sorted(set(body.scopes)), "created_at": _now(), "revoked_at": None, "views": 0, "last_viewed_at": None}
        await db.share_grants.update_many({"owner_id": user["id"], "grantee_email": email, "revoked_at": None}, {"$set": {"revoked_at": _now()}})
        await db.share_grants.insert_one(dict(doc))
        return doc

    @router.delete("/{grant_id}")
    async def revoke(grant_id: str, user: dict = Depends(current_user)):
        r = await db.share_grants.update_one({"id": grant_id, "owner_id": user["id"], "revoked_at": None}, {"$set": {"revoked_at": _now()}})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Autorisation introuvable")
        return {"ok": True}

    @router.get("/{grant_id}/view")
    async def view(grant_id: str, user: dict = Depends(current_user)):
        g = await db.share_grants.find_one({"id": grant_id, "grantee_email": user["email"].lower(), "revoked_at": None}, {"_id": 0})
        if not g:
            raise HTTPException(status_code=404, detail="Accès non autorisé ou révoqué par le membre.")
        p = await db.career_profiles.find_one({"user_id": g["owner_id"]}, {"_id": 0}) or {}
        out = {"owner_name": g["owner_name"], "owner_email": g["owner_email"], "scopes": g["scopes"], "relation": g["relation"]}
        if "cv" in g["scopes"]:
            out["cv_text"] = p.get("cv_text") or ""
        if "memory" in g["scopes"]:
            out["memory"] = {k: p.get(k) for k in MEMORY_FIELDS if p.get(k)}
        if "applications" in g["scopes"]:
            out["applications"] = [_summary(a) async for a in db.applications.find({"user_id": g["owner_id"]}, {"_id": 0}).sort("created_at", -1).limit(100)]
        await db.share_grants.update_one({"id": grant_id}, {"$inc": {"views": 1}, "$set": {"last_viewed_at": _now()}})
        return out

    return router
