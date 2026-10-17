"""Skill map comparison (CV vs job): job text sources + saved comparison history. The rule-based matching runs in the browser (free, instant)."""
import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field, field_validator


class HistoryIn(BaseModel):
    title: str = Field(default="", max_length=200)
    company: str = Field(default="", max_length=200)
    source_kind: str = Field(pattern="^(radar|pack|texte)$")
    source_id: Optional[str] = Field(default=None, max_length=80)
    score: int = Field(ge=0, le=100)
    result: dict
    texts: dict = Field(default={})

    @field_validator("result", "texts")
    @classmethod
    def _size(cls, v):
        if len(json.dumps(v, default=str)) > 200_000:
            raise ValueError("Contenu trop volumineux")
        return v


def create_skill_match_router(db, current_user):
    router = APIRouter(prefix="/api/careeros/skill-match")

    @router.get("/sources")
    async def sources(user: dict = Depends(current_user)):
        radar = [{"id": o["id"], "title": o.get("title", ""), "company": o.get("company", ""), "priority": (o.get("ips") or {}).get("priority"), "score": (o.get("ips") or {}).get("score")}
                 async for o in db.radar_offers.find({"user_id": user["id"], "ips.priority": {"$in": ["A", "B"]}, "status": {"$nin": ["hors_zone", "ignoree"]}},
                                                     {"_id": 0, "id": 1, "title": 1, "company": 1, "ips.priority": 1, "ips.score": 1}).sort("ips.score", -1).limit(40)]
        packs = [{"id": a["id"], "code": a.get("code"), "title": ((a.get("parts") or {}).get("decision") or {}).get("poste") or a.get("code"),
                  "company": ((a.get("parts") or {}).get("decision") or {}).get("entreprise", "")}
                 async for a in db.applications.find({"user_id": user["id"], "archived": {"$ne": True}}, {"_id": 0, "id": 1, "code": 1, "parts.decision.poste": 1, "parts.decision.entreprise": 1})
                 .sort("created_at", -1).limit(40)]
        return {"radar": radar, "packs": packs}

    @router.get("/source")
    async def source(kind: str = Query(pattern="^(radar|pack)$"), id: str = Query(max_length=80), user: dict = Depends(current_user)):
        if kind == "radar":
            o = await db.radar_offers.find_one({"id": id, "user_id": user["id"]}, {"_id": 0, "title": 1, "company": 1, "description": 1})
            if not o:
                raise HTTPException(status_code=404, detail="Offre introuvable")
            return {"title": o.get("title", ""), "company": o.get("company", ""), "text": f"{o.get('title', '')}\n{o.get('description') or ''}"}
        a = await db.applications.find_one({"id": id, "user_id": user["id"]}, {"_id": 0, "inputs.offer_text": 1, "parts.decision": 1, "code": 1})
        if not a:
            raise HTTPException(status_code=404, detail="Pack introuvable")
        d = (a.get("parts") or {}).get("decision") or {}
        return {"title": d.get("poste") or a.get("code", ""), "company": d.get("entreprise", ""), "text": f"{d.get('poste') or ''}\n{(a.get('inputs') or {}).get('offer_text') or ''}"}

    @router.post("/history")
    async def save(body: HistoryIn, user: dict = Depends(current_user)):
        doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "at": datetime.now(timezone.utc).isoformat(), **body.model_dump()}
        await db.skill_comparisons.insert_one(dict(doc))
        old = [h["id"] async for h in db.skill_comparisons.find({"user_id": user["id"]}, {"_id": 0, "id": 1}).sort("at", -1).skip(200)]
        if old:
            await db.skill_comparisons.delete_many({"id": {"$in": old}})
        return {"id": doc["id"], "at": doc["at"]}

    @router.get("/history")
    async def history(user: dict = Depends(current_user)):
        return [h async for h in db.skill_comparisons.find({"user_id": user["id"]}, {"_id": 0, "id": 1, "at": 1, "title": 1, "company": 1, "score": 1, "source_kind": 1})
                .sort("at", -1).limit(100)]

    @router.get("/history/{hid}")
    async def history_one(hid: str, user: dict = Depends(current_user)):
        h = await db.skill_comparisons.find_one({"id": hid, "user_id": user["id"]}, {"_id": 0, "user_id": 0})
        if not h:
            raise HTTPException(status_code=404, detail="Comparaison introuvable")
        return h

    @router.delete("/history/{hid}")
    async def history_delete(hid: str, user: dict = Depends(current_user)):
        r = await db.skill_comparisons.delete_one({"id": hid, "user_id": user["id"]})
        if not r.deleted_count:
            raise HTTPException(status_code=404, detail="Comparaison introuvable")
        return {"ok": True}

    return router
