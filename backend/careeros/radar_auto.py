"""CareerOS Radar — automatic portal discovery: shared anonymous directory, auto-association with undo, daily re-detection, company suggestions."""
import asyncio
import logging
import re
import uuid
from datetime import datetime, timedelta, timezone

from . import radar_discovery as D
from . import radar_rules as RR

logger = logging.getLogger(__name__)
CERTAIN = ("annuaire", "annuaire partagé", "site")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _tokens(x: str) -> set:
    x = re.sub(r"(?i)\b(inc|lt[ée]e|ltd|limited|canada|express|group|groupe|corporation|corp|the)\b\.?", "", x or "")
    return {w for w in re.findall(r"[a-z0-9]+", RR.norm(x)) if len(w) >= 2}


def same_company(a: str, b: str) -> bool:
    ta, tb = _tokens(a), _tokens(b)
    return bool(ta and tb and (ta <= tb or tb <= ta))


async def shared_lookup(db, name: str):
    from . import knowledge as KB
    return await KB.lookup(db, name)


async def _associate(db, user_id: str, c: dict, best: dict) -> dict:
    sel = {"user_id": user_id, "companies.name": c["name"]}
    via = " · Base commune" if best["origin"] == "base commune" else ""
    await db.radar_settings.update_one(sel, {"$set": {"companies.$.kind": best["kind"], "companies.$.slug": best["slug"], "companies.$.portal_url": best["portal_url"],
                                                      "companies.$.auto": True, "companies.$.checked_at": _now(),
                                                      "companies.$.detected": f"Associé automatiquement{via} · {best['kind_label']}"}})
    await db.radar_notices.update_one({"user_id": user_id, "company": c["name"], "kind": best["kind"], "status": "new"},
                                      {"$set": {"at": _now(), "kind_label": best["kind_label"], "count": best["count"], "origin": best["origin"], "portal_url": best["portal_url"]},
                                       "$setOnInsert": {"id": str(uuid.uuid4())}}, upsert=True)
    return {"name": c["name"], "associated": best["kind"], "origin": best["origin"]}


def _certain(cand: dict, name: str, shared) -> bool:
    if not (cand.get("ok") and cand.get("count") and cand.get("quality") == "fiable" and cand.get("origin") in CERTAIN):
        return False
    if cand["origin"] != "annuaire partagé":
        return True
    named = bool(_tokens(name) & set(re.findall(r"[a-z0-9]+", f"{cand['slug']} {cand['portal_url']}".lower())))
    return named or (shared or {}).get("validations", 0) >= 2  # single validation: the portal must carry the company name


async def detect_one(db, user_id: str, c: dict) -> dict:
    from . import knowledge as KB
    shared = await shared_lookup(db, c["name"])
    blocked = set(c.get("auto_block") or [])
    sel = {"user_id": user_id, "companies.name": c["name"]}
    if KB.usable(shared) and shared["kind"] not in blocked:  # collective knowledge: no network discovery needed
        return await _associate(db, user_id, c, {**KB.public(shared), "slug": shared["slug"], "origin": "base commune", "count": shared.get("recent_offers") or 0})
    week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
    if shared and shared.get("status") == "bloque" and (shared.get("last_validated") or "") >= week:
        label = f"Bloqué (anti-robot) : {KB.public(shared)['kind_label']}"
        await db.radar_settings.update_one(sel, {"$set": {"companies.$.detected": label[:160], "companies.$.checked_at": _now()}})
        return {"name": c["name"], "associated": ""}
    try:
        r = await asyncio.wait_for(D.discover(c["name"], c.get("website", ""), (shared or {}).get("portal_url", "")), timeout=50)
    except Exception:  # noqa: BLE001
        r = {"candidates": [], "message": "Détection interrompue : nouvel essai au prochain passage."}
    await learn(db, c["name"], r, shared)
    best = next((x for x in r["candidates"] if x["kind"] not in blocked and _certain(x, c["name"], shared)), None)
    if best:
        return await _associate(db, user_id, c, best)
    ok = [x for x in r["candidates"] if x.get("ok")]
    label = (f"Suggestion : {ok[0]['kind_label']} (à confirmer)" if ok else
             f"Bloqué (anti-robot) : {r['candidates'][0]['kind_label']}" if r["candidates"] and r["candidates"][0].get("blocked") else
             f"Non pris en charge : {', '.join(r['unsupported'])}" if r.get("unsupported") else "Aucun portail trouvé · suivi via Jooble")
    await db.radar_settings.update_one(sel, {"$set": {"companies.$.detected": label[:160], "companies.$.checked_at": _now()}})
    return {"name": c["name"], "associated": ""}


async def learn(db, name: str, r: dict, shared=None):
    """Feed the shared knowledge base with confirmed discoveries (official origin + successful read + offers) and 403 blocks."""
    from . import knowledge as KB
    for x in r.get("candidates") or []:
        if x.get("origin") not in CERTAIN:
            continue
        if x.get("blocked"):
            await KB.record(db, name, x["kind"], x["slug"], x["portal_url"], "bloque")
        elif _certain(x, name, shared) or (x.get("ok") and x.get("count") and x.get("quality") == "fragile" and x["origin"] in ("annuaire", "site")):
            await KB.record(db, name, x["kind"], x["slug"], x["portal_url"], x.get("quality") or "fiable", x["count"])


async def auto_detect(db, user_id: str, names: list = None, limit: int = 3) -> list:
    st = await db.radar_settings.find_one({"user_id": user_id}, {"_id": 0, "companies": 1}) or {}
    comps = [c for c in st.get("companies") or [] if isinstance(c, dict) and c.get("enabled", True) and not c.get("kind")]
    if names is not None:
        comps = [c for c in comps if c["name"] in names]
    else:  # daily re-detection: oldest checks first, at most once a week per company
        week = (datetime.now(timezone.utc) - timedelta(days=7)).isoformat()
        comps = sorted([c for c in comps if (c.get("checked_at") or "") < week], key=lambda c: c.get("checked_at") or "")
    out = []
    for c in comps[:limit]:
        try:
            out.append(await detect_one(db, user_id, c))
        except Exception:  # noqa: BLE001
            logger.exception("auto detect %s", c.get("name"))
    return out


async def undo(db, user_id: str, notice_id: str) -> bool:
    n = await db.radar_notices.find_one({"id": notice_id, "user_id": user_id}, {"_id": 0})
    if not n:
        return False
    await db.radar_settings.update_one({"user_id": user_id, "companies.name": n["company"]},
                                       {"$set": {"companies.$.kind": "", "companies.$.slug": "", "companies.$.portal_url": "", "companies.$.auto": False,
                                                 "companies.$.detected": "Association automatique annulée · suivi via Jooble"},
                                        "$addToSet": {"companies.$.auto_block": n["kind"]}})
    await db.radar_notices.update_one({"id": notice_id}, {"$set": {"status": "undone"}})
    return True


async def suggestions(db, user_id: str, roles: list, followed: list) -> list:
    since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
    groups = {}
    async for o in db.radar_offers.find({"user_id": user_id, "last_seen": {"$gte": since}, "source": {"$ne": "externe"}, "status": {"$ne": "hors_zone"}},
                                        {"_id": 0, "company": 1, "title": 1, "ips": 1, "source": 1}):
        pr = (o.get("ips") or {}).get("priority")
        rel = RR.title_relevance(o.get("title", ""), roles)
        if not o.get("company") or not (pr in ("A", "B") or rel >= 0.5) or any(same_company(o["company"], f) for f in followed):
            continue
        key = " ".join(sorted(_tokens(o["company"])))
        if not key:
            continue
        g = groups.setdefault(key, {"name": o["company"], "offers": 0, "a": 0, "best_ips": 0, "titles": []})
        g["offers"] += 1
        g["a"] += int(pr == "A")
        g["best_ips"] = max(g["best_ips"], (o.get("ips") or {}).get("score") or 0)
        if len(g["titles"]) < 3 and o["title"] not in g["titles"]:
            g["titles"].append(o["title"])
    rows = sorted([g for g in groups.values() if g["offers"] >= 2 or g["a"]], key=lambda g: (-g["a"], -g["offers"], -g["best_ips"]))[:8]
    for g in rows:
        d = D.directory_match(g["name"])
        sh = None if d and d[1] else await shared_lookup(db, g["name"])
        g["portal"] = D.KIND_LABEL.get(D.S.parse_portal(d[1])[0], "") if d and d[1] else D.KIND_LABEL.get(sh["kind"], "") if sh else ""
    return rows
