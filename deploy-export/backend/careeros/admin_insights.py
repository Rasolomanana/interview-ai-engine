"""Admin insights: aggregated usage, funnel, geography and business analytics. No CV, Career Memory content or application content."""
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header

from admin import _check_admin
from . import knowledge as KB
from .admin_rbac import is_super
from .geo import member_geo
from .testaccounts import scope, uf
from .radar_discovery import KIND_LABEL

MIN_CELL = 3  # non-super roles: groups smaller than this are merged (no identifiable member)


def _now():
    return datetime.now(timezone.utc)


def _ago(days: int) -> str:
    return (_now() - timedelta(days=days)).isoformat()


def _pct(a, b):
    return round(100 * a / b, 1) if b else 0.0


def _top(counter: Counter, n=25, merge=False, other="Autres"):
    rows = counter.most_common()
    if merge:
        small = sum(c for _, c in rows if c < MIN_CELL)
        rows = [(k, c) for k, c in rows if c >= MIN_CELL] + ([(f"{other} (groupes de moins de {MIN_CELL})", small)] if small else [])
    return [{"label": k, "count": c} for k, c in rows[:n]]


def _title(s: str) -> str:
    s = re.sub(r"\s+", " ", s.strip(" .-·"))
    return s[:1].upper() + s[1:].lower() if s else ""


async def geo_labels(db) -> dict:
    """member id -> (country, province, city) display labels, as used by the Géographie tab."""
    locs = {s["user_id"]: s.get("location") or "" async for s in db.radar_settings.find(uf(), {"_id": 0, "user_id": 1, "location": 1})}
    profiles = {p["user_id"]: p async for p in db.career_profiles.find(uf(), {"_id": 0, "user_id": 1, "location": 1, "country": 1, "province": 1, "city": 1})}
    out = {}
    async for u in db.users.find(uf(field="id"), {"_id": 0, "id": 1}):
        g = member_geo(profiles.get(u["id"], {}), locs.get(u["id"], ""))
        out[u["id"]] = (g["country"] or "Non renseigné", f"{g['province']} ({g['country'] or '?'})" if g["province"] else "Non renseigné",
                        f"{g['city']}, {g['province'] or g['country'] or '?'}" if g["city"] else "Non renseigné")
    return out


def role_labels(target_roles: str, keywords=None) -> set:
    return {_title(x) for x in re.split(r"[,;/\n]", target_roles or "") if len(x.strip()) > 2} | {_title(x) for x in keywords or [] if len(x.strip()) > 2}


async def member_roles(db) -> dict:
    tr = {p["user_id"]: p.get("target_roles") or "" async for p in db.career_profiles.find(uf(), {"_id": 0, "user_id": 1, "target_roles": 1})}
    kw = {s["user_id"]: s.get("keywords") or [] async for s in db.radar_settings.find(uf(), {"_id": 0, "user_id": 1, "keywords": 1})}
    return {u: role_labels(tr.get(u, ""), kw.get(u)) for u in set(tr) | set(kw)}


def create_insights_router(db):
    router = APIRouter(prefix="/api/admin/insights")

    @router.get("/overview")
    async def overview(days: int = 30, include_test: bool = False, x_admin_password: str = Header(None)):
        _check_admin(x_admin_password)
        await scope(db, include_test)
        since = _ago(days) if days else ""
        users = [u async for u in db.users.find(uf(field="id"), {"_id": 0, "id": 1, "created_at": 1, "last_seen_at": 1, "paid": 1, "paid_since": 1})]
        a7, a30 = _ago(7), _ago(30)
        seen = lambda u, s: (u.get("last_seen_at") or "") >= s  # noqa: E731
        new_by_day = Counter((u.get("created_at") or "")[:10] for u in users if (u.get("created_at") or "") >= _ago(30))
        cohort = [u for u in users if (u.get("created_at") or "") >= since]
        sessions = await db.admin_events.distinct("session_id", {"type": {"$in": ["visit", "simulation"]}, **({"ts": {"$gte": _now() - timedelta(days=days)}} if days else {})})
        visitors = len([s for s in sessions if s])
        active = [u for u in cohort if seen(u, a30)]
        paid = [u for u in active if u.get("paid")]
        renewed = [u for u in paid if u.get("paid_since") and u["paid_since"] <= a30]
        reliable = visitors >= len(cohort)
        funnel = [{"step": "Visiteurs", "count": visitors, "rate": None, "note": "Sessions anonymes distinctes (visites et simulations)." +
                   ("" if reliable else " Suivi des visites récent : moins de visiteurs enregistrés que d'inscrits, taux d'inscription non significatif pour l'instant.")},
                  {"step": "Inscrits", "count": len(cohort), "rate": _pct(len(cohort), visitors) if reliable else None, "note": "Comptes créés sur la période."},
                  {"step": "Actifs", "count": len(active), "rate": _pct(len(active), len(cohort)), "note": "Inscrits connectés dans les 30 derniers jours."},
                  {"step": "Payants", "count": len(paid), "rate": _pct(len(paid), len(active)), "note": "Actifs marqués « payant » (Rentabilité)."},
                  {"step": "Renouvellement", "count": len(renewed), "rate": _pct(len(renewed), len(paid)),
                   "note": "Payants depuis plus de 30 jours (au moins un renouvellement). Date de début suivie depuis l'activation du suivi."}]
        st = [s async for s in db.radar_settings.find(uf(), {"_id": 0, "user_id": 1, "enabled": 1})]
        runs = [r async for r in db.radar_runs.find(uf({"at": {"$gte": a30}}), {"_id": 0, "user_id": 1, "trigger": 1, "at": 1})]
        runs_by_day = Counter(r["at"][:10] for r in runs)
        radar = {"enabled": sum(1 for s in st if s.get("enabled", True)), "configured": len(st),
                 "members_30d": len({r["user_id"] for r in runs} & {u["id"] for u in users}), "runs_30d": len(runs),
                 "runs_auto": sum(r.get("trigger") == "quotidien" for r in runs), "runs_manual": sum(r.get("trigger") != "quotidien" for r in runs),
                 "analyzed_30d": await db.radar_offers.count_documents(uf({"analyzed_at": {"$gte": a30}})),
                 "packs_30d": await db.applications.count_documents(uf({"created_at": {"$gte": a30}, "origin.type": "radar"})),
                 "runs_by_day": [{"day": d, "count": c} for d, c in sorted(runs_by_day.items())]}
        return {"members": {"total": len(users), "active_7d": sum(seen(u, a7) for u in users), "active_30d": sum(seen(u, a30) for u in users),
                            "new_7d": sum((u.get("created_at") or "") >= a7 for u in users), "new_30d": sum((u.get("created_at") or "") >= a30 for u in users),
                            "paid": sum(bool(u.get("paid")) for u in users),
                            "new_by_day": [{"day": d, "count": c} for d, c in sorted(new_by_day.items())],
                            "active_by_day": [{"day": d, "count": c} for d, c in sorted(Counter((u.get("last_seen_at") or "")[:10] for u in users if seen(u, a30)).items())]},
                "funnel": funnel, "period_days": days, "radar": radar}

    @router.get("/geo")
    async def geo(include_test: bool = False, x_admin_password: str = Header(None)):
        _check_admin(x_admin_password)
        await scope(db, include_test)
        countries, provinces, cities = Counter(), Counter(), Counter()
        for c, p, ci in (await geo_labels(db)).values():
            countries[c] += 1
            provinces[p] += 1
            cities[ci] += 1
        m = not is_super()
        return {"countries": _top(countries, merge=m), "provinces": _top(provinces, merge=m), "cities": _top(cities, 40, merge=m),
                "merged": m, "note": "Champs Pays / Province / Ville de la Career Memory, sinon déduits de la localisation (Career Memory ou Radar)."}

    @router.get("/business")
    async def business(include_test: bool = False, x_admin_password: str = Header(None)):
        _check_admin(x_admin_password)
        await scope(db, include_test)
        roles, companies, portals = Counter(), Counter(), Counter()
        names = {}
        for labels in (await member_roles(db)).values():
            roles.update(labels)  # one count per member and role
        async for s in db.radar_settings.find(uf(), {"_id": 0, "companies": 1}):
            for c in s.get("companies") or []:
                if isinstance(c, dict) and c.get("enabled", True) and c.get("name"):
                    k = KB.key(c["name"]) or c["name"].lower()
                    names.setdefault(k, c["name"])
                    companies[names[k]] += 1
                    portals[KIND_LABEL.get(c.get("kind"), c.get("kind")) if c.get("kind") else "Jooble (sans portail)"] += 1
        a30 = _ago(30)
        by_src, prio = Counter(), Counter()
        async for o in db.radar_offers.find(uf({"analyzed_at": {"$gte": a30}}), {"_id": 0, "source": 1, "ips.priority": 1}):
            by_src[o.get("source") or "?"] += 1
            prio[(o.get("ips") or {}).get("priority") or "—"] += 1
        app_prio = Counter()
        async for a in db.applications.find(uf(), {"_id": 0, "ips.priority": 1}):
            app_prio[(a.get("ips") or {}).get("priority") or "—"] += 1
        return {"roles": _top(roles), "companies": _top(companies), "portals": _top(portals),
                "offers": {"analyzed_30d": sum(by_src.values()), "analyzed_total": await db.radar_offers.count_documents(uf({"analyzed_at": {"$ne": None}})),
                           "by_source": _top(by_src)},
                "priorities": {"radar_30d": {k: prio.get(k, 0) for k in ("A", "B", "C")}, "applications": {k: app_prio.get(k, 0) for k in ("A", "B", "C")}},
                "note": "Agrégats uniquement : aucun CV, aucun contenu de Career Memory ni de candidature."}

    return router
