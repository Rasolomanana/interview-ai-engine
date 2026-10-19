"""Skill map comparison (CV vs job): job text sources + saved comparison history. The rule-based matching runs in the browser (free, instant)."""
import re
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

    def _plain(md) -> str:
        """Markdown -> readable plain text for the copilot fields (no #, ---, ** marks)."""
        if not isinstance(md, str):
            return ""
        out = []
        for line in md.splitlines():
            if re.fullmatch(r"\s*([-*_]\s*){3,}", line):
                continue
            line = re.sub(r"^\s*#{1,6}\s*", "", line)
            out.append(re.sub(r"\*\*(.+?)\*\*|__(.+?)__", lambda m: m.group(1) or m.group(2), line))
        return re.sub(r"\n{3,}", "\n\n", "\n".join(out)).strip()

    @router.get("/copilot")
    async def copilot(kind: str = Query(pattern="^(radar|pack|memoire)$"), id: str = Query(default="", max_length=80), user: dict = Depends(current_user)):
        """Interview copilot context prefilled from Career Memory + a pack or a Radar offer (nothing to retype)."""
        prof = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0, "cv_text": 1, "sectors": 1}) or {}
        out = {"title": "Entrevue", "cv": prof.get("cv_text") or "", "poste": "", "entreprise": "", "atsCv": "", "score": None, "missingKeywords": [], "gaps": [], "coverLetter": ""}
        if kind == "memoire":
            return out
        if kind == "pack":
            a = await db.applications.find_one({"id": id, "user_id": user["id"]}, {"_id": 0, "inputs": 1, "parts": 1, "ips": 1, "code": 1})
            if not a:
                raise HTTPException(status_code=404, detail="Pack introuvable")
            parts, d = a.get("parts") or {}, (a.get("parts") or {}).get("decision") or {}
            ats = d.get("ats") if isinstance(d.get("ats"), dict) else {}
            miss = next((v for k, v in ats.items() if ("manq" in k or "missing" in k) and isinstance(v, list)), [])
            return {**out, "title": f"Entrevue · {d.get('poste') or a.get('code', '')}"[:120], "cv": (a.get("inputs") or {}).get("cv_text") or out["cv"],
                    "poste": f"{d.get('poste') or ''}\n{(a.get('inputs') or {}).get('offer_text') or ''}".strip(), "entreprise": d.get("entreprise", ""),
                    "atsCv": _plain(parts.get("cv_ats")), "coverLetter": _plain(parts.get("letter")),
                    "score": (a.get("ips") or {}).get("score"), "missingKeywords": [str(x) for x in miss][:15],
                    "gaps": [str(x) for x in (d.get("reasons_avoid") or [])][:8] if isinstance(d.get("reasons_avoid"), list) else []}
        o = await db.radar_offers.find_one({"id": id, "user_id": user["id"]}, {"_id": 0, "title": 1, "company": 1, "description": 1, "ips": 1})
        if not o:
            raise HTTPException(status_code=404, detail="Offre introuvable")
        return {**out, "title": f"Entrevue · {o.get('title', '')}"[:120], "poste": f"{o.get('title', '')}\n{o.get('description') or ''}".strip(),
                "entreprise": o.get("company", ""), "score": (o.get("ips") or {}).get("score")}

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
