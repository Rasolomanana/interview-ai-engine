"""CareerOS shared knowledge base: one anonymous card per employer (name, public portal, type, status, confidence). No member data."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header

from . import radar_auto as AU
from .radar_discovery import KIND_LABEL

STATUS = ("fiable", "fragile", "bloque")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def key(name: str) -> str:
    return " ".join(sorted(AU._tokens(name)))


def confidence(card: dict) -> str:
    if card.get("status") == "bloque" or not card.get("last_success"):
        return "faible"
    age = (_now() - datetime.fromisoformat(card["last_success"])).days
    offers = card.get("recent_offers") or 0
    if card.get("validations", 0) >= 3 and age <= 14 and offers:
        return "elevee"
    return "moyenne" if age <= 30 and offers else "faible"


def public(card: dict) -> dict:
    out = {k: card.get(k) for k in ("name", "portal_url", "kind", "status", "last_validated", "last_success", "validations", "recent_offers")}
    return {**out, "kind_label": KIND_LABEL.get(card.get("kind"), card.get("kind") or ""), "confidence": confidence(card)}


async def record(db, name: str, kind: str, slug: str, portal_url: str, status: str, offers: int = 0):
    """Merge one confirmed observation into the employer's single card; the most recent information wins."""
    k = key(name)
    if not (k and kind and slug and status in STATUS):
        return
    now = _now().isoformat()
    cur = await db.portal_knowledge.find_one({"key": k}, {"_id": 0})
    same = bool(cur and cur.get("kind") == kind and cur.get("slug") == slug)
    if status == "bloque":
        if cur and not same and cur.get("status") != "bloque":
            return  # a blocked alternative never hides a working portal
        upd = {"status": "bloque", "last_validated": now}
    else:
        today = now[:10]
        fresh = not same or (cur.get("last_success") or "")[:10] != today  # at most one validation per day
        upd = {"status": status, "last_validated": now, "last_success": now, "recent_offers": offers,
               "validations": ((cur or {}).get("validations", 0) if same else 0) + int(fresh)}
    base = {"key": k, "name": name.strip() if not same else cur["name"], "kind": kind, "slug": slug, "portal_url": portal_url or (cur or {}).get("portal_url", "")}
    if not same:
        upd.setdefault("validations", 0)
    await db.portal_knowledge.update_one({"key": k}, {"$set": {**base, **upd, "updated_at": now}, "$setOnInsert": {"created_at": now}}, upsert=True)


async def lookup(db, name: str):
    k = key(name)
    if not k:
        return None
    card = await db.portal_knowledge.find_one({"key": k}, {"_id": 0})
    if not card:
        async for c in db.portal_knowledge.find({}, {"_id": 0}):
            if AU.same_company(name, c["name"]):
                card = c
                break
    return card


def usable(card) -> bool:
    return bool(card and card.get("status") in ("fiable", "fragile") and confidence(card) in ("elevee", "moyenne"))


async def record_run(db, companies: list, portals: dict):
    by_name = {c["name"]: c for c in companies if c.get("kind") and c.get("slug")}
    for pname, pv in (portals or {}).items():
        c = by_name.get(pname)
        if not c or c["kind"] != pv.get("kind"):
            continue
        if pv.get("blocked"):
            await record(db, pname, c["kind"], c["slug"], c.get("portal_url", ""), "bloque")
        elif pv.get("ok") and pv.get("fetched"):
            await record(db, pname, c["kind"], c["slug"], c.get("portal_url", ""), "fragile" if pv.get("quality") == "fragile" else "fiable", pv["fetched"])


async def migrate(db):
    """One-time import of the former anonymous directory (members hash dropped)."""
    if await db.portal_knowledge.count_documents({}) or not await db.portal_directory.count_documents({}):
        return
    async for r in db.portal_directory.find({}, {"_id": 0}):
        k = key(r.get("name", ""))
        if k and not await db.portal_knowledge.find_one({"key": k}):
            await db.portal_knowledge.insert_one({"key": k, "name": r["name"], "kind": r["kind"], "slug": r["slug"], "portal_url": r.get("portal_url", ""),
                                                  "status": "fiable", "validations": len(r.get("members") or []), "last_validated": r.get("updated_at", ""),
                                                  "last_success": "", "recent_offers": 0, "updated_at": _now().isoformat()})


def create_knowledge_admin_router(db, check_admin):
    router = APIRouter(prefix="/api/admin")

    @router.get("/knowledge")
    async def knowledge(x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        rows = [public(c) async for c in db.portal_knowledge.find({}, {"_id": 0})]
        rows.sort(key=lambda r: (r["status"] == "bloque", {"elevee": 0, "moyenne": 1, "faible": 2}[r["confidence"]], r["name"].lower()))
        month = (_now() - timedelta(days=30)).isoformat()
        stats = {"total": len(rows), "fiable": sum(r["status"] == "fiable" for r in rows), "fragile": sum(r["status"] == "fragile" for r in rows),
                 "bloque": sum(r["status"] == "bloque" for r in rows), "elevee": sum(r["confidence"] == "elevee" for r in rows),
                 "recent": sum((r.get("last_validated") or "") >= month for r in rows)}
        return {"items": rows, "stats": stats}

    return router
