"""Admin: connector usage (supported portals) and impact-ranked backlog of unsupported / blocked portals."""
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header

from . import radar_sources as S
from .radar_discovery import KIND_LABEL, norm

NOW_SUPPORTED = {"UKG", "Avature", "Taleo", "Phenom"}  # older detections to re-run (loupe / « Tout détecter »)

DIFFICULTY = {"UKG": ("Simple", 1.0), "Jobvite": ("Simple", 1.0), "Avature": ("Moyenne", 0.7), "Taleo": ("Moyenne", 0.7),
              "Njoyn": ("Moyenne", 0.7), "SilkRoad": ("Moyenne", 0.7), "Phenom": ("Difficile", 0.4), "portail propriétaire": ("Difficile", 0.3)}
BLOCKED_NOTE = ("Non recommandé (protection volontaire)", 0.0)


def _classify(detected: str):
    """('unsupported'|'blocked', [ATS…]) from the stored company.detected label."""
    d = detected or ""
    for prefix, kind in (("Non pris en charge : ", "unsupported"), ("Bloqué (anti-robot) : ", "blocked")):
        if d.startswith(prefix):
            return kind, [x.strip() for x in d[len(prefix):].split(",") if x.strip()]
    return None, []


def create_connectors_router(db, check_admin):
    router = APIRouter(prefix="/api/admin")

    @router.get("/connectors")
    async def connectors(x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        backlog, active, redetect = {}, {}, {}
        async for st in db.radar_settings.find({}, {"_id": 0, "user_id": 1, "companies": 1}):
            for c in st.get("companies") or []:
                if not c.get("enabled", True):
                    continue
                if c.get("kind"):
                    a = active.setdefault(c["kind"], {"companies": set(), "members": set()})
                    a["companies"].add(norm(c["name"])); a["members"].add(st["user_id"])
                    continue
                kind, ats = _classify(c.get("detected", ""))
                for name in ats:
                    if kind == "unsupported" and name in NOW_SUPPORTED:
                        redetect.setdefault(name, set()).add(norm(c["name"]))
                        continue
                    key = f"{name} (bloqué anti-robot)" if kind == "blocked" else name
                    b = backlog.setdefault(key, {"ats": name, "blocked": kind == "blocked", "companies": {}, "members": set()})
                    b["companies"].setdefault(norm(c["name"]), {"name": c["name"], "members": set()})["members"].add(st["user_id"])
                    b["members"].add(st["user_id"])
        since = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()
        jooble = {}
        async for o in db.radar_offers.find({"source": "jooble", "first_seen": {"$gte": since}}, {"_id": 0, "company": 1}):
            k = norm(o.get("company", ""))
            jooble[k] = jooble.get(k, 0) + 1
        rows = []
        for key, b in backlog.items():
            diff, factor = BLOCKED_NOTE if b["blocked"] else DIFFICULTY.get(b["ats"], ("À évaluer", 0.5))
            offers = sum(jooble.get(k, 0) for k in b["companies"])
            score = round((len(b["members"]) * 3 + len(b["companies"]) * 2 + offers / 10) * factor, 1)
            ex = sorted(b["companies"].values(), key=lambda x: -len(x["members"]))[:4]
            rows.append({"connector": key, "blocked": b["blocked"], "companies": len(b["companies"]), "members": len(b["members"]),
                         "examples": [x["name"] for x in ex], "offers_30d": offers, "difficulty": diff, "score": score})
        rows.sort(key=lambda r: -r["score"])
        top = rows[0]["score"] if rows and rows[0]["score"] else 0
        for r in rows:
            r["priority"] = "Aucune (protection)" if r["blocked"] else "Élevée" if top and r["score"] >= top * 0.66 else "Moyenne" if top and r["score"] >= top * 0.33 else "Faible"
        # Supported connectors: last run of each member.
        stats = {}
        async for run in db.radar_runs.aggregate([{"$match": {"portals": {"$exists": True}}}, {"$sort": {"at": -1}},
                                                  {"$group": {"_id": "$user_id", "portals": {"$first": "$portals"}}}]):
            for name, p in (run.get("portals") or {}).items():
                s = stats.setdefault(p["kind"], {"reads": 0, "ok": 0, "fetched": 0, "matched": 0, "fallback": 0, "blocked": 0, "fiable": 0, "fragile": 0})
                s["reads"] += 1; s["ok"] += int(bool(p.get("ok"))); s["fetched"] += p.get("fetched", 0); s["matched"] += p.get("matched", 0) or 0
                s["fallback"] += int(not p.get("ok")); s["blocked"] += int(bool(p.get("blocked")))
                q = p.get("quality") or S.quality(p["kind"], bool(p.get("ok")), bool(p.get("blocked")))
                if q in ("fiable", "fragile"):
                    s[q] += 1
        supported = []
        for kind, a in active.items():
            s = stats.get(kind, {})
            supported.append({"kind": kind, "label": KIND_LABEL.get(kind, kind), "companies": len(a["companies"]), "members": len(a["members"]),
                              "fetched": s.get("fetched", 0), "matched": s.get("matched", 0),
                              "success_pct": round(s["ok"] * 100 / s["reads"], 1) if s.get("reads") else None,
                              "fallback": s.get("fallback", 0), "blocked": s.get("blocked", 0), "reliable": s.get("fiable", 0), "fragile": s.get("fragile", 0),
                              "fragile_kind": kind in S.FRAGILE})
        supported.sort(key=lambda x: -x["companies"])
        return {"backlog": rows, "supported": supported, "redetect": {k: len(v) for k, v in redetect.items()}}

    return router
