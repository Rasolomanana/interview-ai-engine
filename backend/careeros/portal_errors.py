"""Admin error bin for employer portals: one anonymous card per (employer, error type); fix = tested URL applied to followers (undoable)."""
import hashlib
import re
import uuid
from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

from . import knowledge as KB
from . import radar_auto as AU
from . import radar_sources as S
from .radar_discovery import KIND_LABEL, is_blocked

TYPES = {"ia": "Service IA indisponible ou réponse invalide", "source": "Erreur de la source d'offres", "verification": "Vérification impossible", "redirection": "Redirection non lisible (3xx)", "bloque": "Bloqué par l'employeur (403 / anti-robot)", "introuvable": "Portail introuvable (404)",
         "serveur": "Erreur du serveur de l'employeur (5xx)", "http": "Refus HTTP (4xx)", "delai": "Délai dépassé", "lecture": "Réponse illisible"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def classify(e: Exception) -> str:
    if isinstance(e, S.PortalRedirect):
        return "redirection"
    if is_blocked(e):
        return "bloque"
    code = getattr(getattr(e, "response", None), "status_code", 0)
    if 300 <= code < 400:
        return "redirection"
    if code == 404:
        return "introuvable"
    if code >= 500:
        return "serveur"
    if code >= 400:
        return "http"
    return "delai" if isinstance(e, httpx.TimeoutException) else "lecture"


def member_message(e: Exception, jooble: bool) -> str:
    return f"{TYPES[classify(e)]}. {'Suivi via Jooble pour ce passage. ' if jooble else ''}L'équipe CareerOS est avertie et peut corriger le portail."


def _clean(msg: str) -> str:
    return re.sub(r"\?[^\s'\"]*", "", msg or "")[:220]  # no query strings in the bin


def _pseudo(user_id: str) -> str:
    return hashlib.sha256(f"careeros-portal-error|{user_id}".encode()).hexdigest()[:16]


SOURCE_LABEL = {"jooble": "Jooble", "adzuna": "Adzuna", "careerjet": "Careerjet", "serpapi": "Google Jobs (SerpApi)", "ia": "Service IA", "pack": "Pack"}
CATEGORY = {"portail": "Portail employeur", "source": "Source d'offres", "ia": "Service IA", "pack": "Génération de pack", "verification": "Vérification d'offre"}


async def log_error(db, user_id: str, category: str, name: str, etype: str, message: str, kind: str = ""):
    """Generic anonymous journal entry (one card per name + kind + type)."""
    k = f"{KB.key(name)}|{kind or category}|{etype}"
    now = _now()
    cur = await db.portal_errors.find_one({"key": k}, {"_id": 0, "status": 1})
    status = "ignore" if cur and cur.get("status") == "ignore" else "ouverte"
    await db.portal_errors.update_one({"key": k}, {"$set": {"name": name, "kind": kind or category, "category": category, "etype": etype, "message": _clean(message),
                                                            "last_seen": now, "status": status},
                                                   "$inc": {"occurrences": 1}, "$addToSet": {"members": _pseudo(user_id)},
                                                   "$setOnInsert": {"id": str(uuid.uuid4()), "first_seen": now, "history": []}}, upsert=True)


async def record_run(db, user_id: str, companies: list, portals: dict):
    by_name = {c["name"]: c for c in companies if c.get("kind")}
    now = _now()
    for name, pv in (portals or {}).items():
        c = by_name.get(name)
        if not c or pv.get("ok"):
            continue
        etype = pv.get("etype") or ("bloque" if pv.get("blocked") else "lecture")
        k = f"{KB.key(name)}|{pv['kind']}|{etype}"
        cur = await db.portal_errors.find_one({"key": k}, {"_id": 0, "status": 1})
        status = "ignore" if cur and cur.get("status") == "ignore" else "ouverte"
        await db.portal_errors.update_one({"key": k}, {"$set": {"name": name, "kind": pv["kind"], "category": "portail", "slug": c.get("slug", ""), "portal_url": _clean(c.get("portal_url", "")),
                                                                "etype": etype, "message": _clean(pv.get("error")), "last_seen": now, "status": status},
                                                       "$inc": {"occurrences": 1}, "$addToSet": {"members": _pseudo(user_id)},
                                                       "$setOnInsert": {"id": str(uuid.uuid4()), "first_seen": now, "history": []}}, upsert=True)


def _public(r: dict) -> dict:
    out = {k: r.get(k) for k in ("id", "name", "kind", "slug", "portal_url", "etype", "message", "first_seen", "last_seen", "occurrences", "status", "history", "fix")}
    cat = r.get("category") or "portail"
    return {**out, "category": cat, "category_label": CATEGORY.get(cat, cat), "fixable": cat == "portail" and r.get("kind") in S.PORTAL_KINDS, "members": len(r.get("members") or []), "type_label": TYPES.get(r.get("etype"), r.get("etype")), "kind_label": KIND_LABEL.get(r.get("kind")) or SOURCE_LABEL.get(r.get("kind"), CATEGORY.get(r.get("kind"), r.get("kind")))}


class StatusBody(BaseModel):
    status: str = Field(pattern="^(ouverte|resolue|ignore)$")


class FixBody(BaseModel):
    portal_url: str = Field(min_length=8, max_length=500)


def create_portal_errors_router(db, check_admin):
    router = APIRouter(prefix="/api/admin/portal-errors")

    async def _get(eid: str) -> dict:
        r = await db.portal_errors.find_one({"id": eid}, {"_id": 0})
        if not r:
            raise HTTPException(status_code=404, detail="Erreur introuvable")
        return r

    async def _log(eid: str, action: str, detail: str = ""):
        await db.portal_errors.update_one({"id": eid}, {"$push": {"history": {"at": _now(), "action": action, "detail": detail[:200]}}})

    @router.get("")
    async def list_errors(x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        rows = [_public(r) async for r in db.portal_errors.find({}, {"_id": 0}).sort("last_seen", -1).limit(500)]
        stats = {s: sum(r["status"] == s for r in rows) for s in ("ouverte", "resolue", "ignore")}
        stats["members"] = len({m async for r in db.portal_errors.find({"status": "ouverte"}, {"_id": 0, "members": 1}) for m in r.get("members") or []})
        return {"items": rows, "stats": {**stats, "total": len(rows)}, "types": TYPES}

    @router.post("/{eid}/status")
    async def set_status(eid: str, body: StatusBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        await _get(eid)
        await db.portal_errors.update_one({"id": eid}, {"$set": {"status": body.status}})
        await _log(eid, {"ouverte": "Rouverte", "resolue": "Marquée résolue", "ignore": "Ignorée"}[body.status])
        return {"ok": True}

    @router.post("/{eid}/fix")
    async def fix(eid: str, body: FixBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        r = await _get(eid)
        kind, slug = S.parse_portal(body.portal_url.strip())
        if not kind:
            raise HTTPException(status_code=422, detail="URL non reconnue : indiquez l'adresse publique du portail carrières (Workday, Oracle, SuccessFactors…).")
        try:
            async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as c:
                offers = await S.board(c, kind, slug, r["name"], [])
        except Exception as e:  # noqa: BLE001
            await _log(eid, "correction refusée (test en échec)", f"{kind} · {classify(e)}")
            raise HTTPException(status_code=422, detail=f"Test de lecture en échec : {TYPES[classify(e)]}. Rien n'a été modifié.") from e
        prev_card = await KB.lookup(db, r["name"])
        await KB.record(db, r["name"], kind, slug, body.portal_url.strip(), "fiable", len(offers))
        applied = []
        async for st in db.radar_settings.find({"companies.name": {"$exists": True}}, {"_id": 0, "user_id": 1, "companies": 1}):
            for co in st.get("companies") or []:
                if isinstance(co, dict) and AU.same_company(co.get("name", ""), r["name"]):
                    applied.append({"user_id": st["user_id"], "name": co["name"], "prev": {**{k: co.get(k, "") for k in ("kind", "slug", "portal_url", "detected")}, "auto_block": co.get("auto_block") or []}})
                    await db.radar_settings.update_one({"user_id": st["user_id"], "companies.name": co["name"]},
                                                       {"$set": {"companies.$.kind": kind, "companies.$.slug": slug, "companies.$.portal_url": body.portal_url.strip(),
                                                                 "companies.$.detected": "Portail corrigé par l'équipe CareerOS"},
                                                        "$pull": {"companies.$.auto_block": kind}})
        fix_id = str(uuid.uuid4())
        await db.portal_fix_undo.insert_one({"id": fix_id, "error_id": eid, "applied": applied, "prev_card": prev_card, "prev_status": r.get("status") or "ouverte", "at": _now()})
        fx = {"id": fix_id, "at": _now(), "kind": kind, "portal_url": body.portal_url.strip(), "offers": len(offers), "members": len(applied), "undone": False}
        await db.portal_errors.update_one({"id": eid}, {"$set": {"status": "resolue", "fix": fx}})
        await _log(eid, "portail corrigé", f"{KIND_LABEL.get(kind, kind)} · {len(offers)} offre(s) lue(s) · {len(applied)} membre(s)")
        return {"ok": True, "fix": fx}

    @router.post("/{eid}/undo")
    async def undo(eid: str, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        r = await _get(eid)
        fx = r.get("fix") or {}
        u = await db.portal_fix_undo.find_one({"id": fx.get("id")}, {"_id": 0}) if fx and not fx.get("undone") else None
        if not u:
            raise HTTPException(status_code=409, detail="Aucune correction à annuler")
        for a in u["applied"]:
            await db.radar_settings.update_one({"user_id": a["user_id"], "companies.name": a["name"]},
                                               {"$set": {f"companies.$.{k}": v for k, v in a["prev"].items()}})
        card = u.get("prev_card")
        if card:
            await db.portal_knowledge.update_one({"key": card["key"]}, {"$set": card}, upsert=True)
        else:
            await db.portal_knowledge.delete_one({"key": KB.key(r["name"])})
        await db.portal_errors.update_one({"id": eid}, {"$set": {"status": u.get("prev_status") or "ouverte", "fix.undone": True}})
        await db.portal_fix_undo.delete_one({"id": u["id"]})
        await _log(eid, "correction annulée", f"{len(u['applied'])} membre(s) restauré(s)")
        return {"ok": True}

    return router
