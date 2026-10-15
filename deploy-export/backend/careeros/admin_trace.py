"""Admin trace: every admin number opens the real records behind it. Super Admin sees member identity; other roles see a pseudonym."""
import hashlib
import re
from collections import Counter
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException

from admin import _check_admin
from . import knowledge as KB
from .admin_insights import MIN_CELL, geo_labels, member_roles
from .admin_rbac import is_super
from .radar_discovery import KIND_LABEL

LIMIT = 1000
MEMBER_COLS = [["member", "Membre"], ["created", "Inscription"], ["seen", "Dernière activité"], ["paid", "Payant"], ["radar", "Radar activé"], ["city", "Ville"]]
OFFER_COLS = [["date", "Analysée le"], ["title", "Poste"], ["company", "Entreprise"], ["source", "Source"], ["ips", "IPS"], ["priority", "Priorité"], ["member", "Membre"]]
RUN_COLS = [["date", "Date"], ["member", "Membre"], ["trigger", "Déclencheur"], ["fetched", "Trouvées"], ["new", "Nouvelles"], ["analyzed", "Analysées"],
            ["skipped", "Reportées"], ["status", "Statut"], ["alerts", "Alertes"]]


def _now():
    return datetime.now(timezone.utc)


def _ago(days):
    return (_now() - timedelta(days=days)).isoformat()


def _d(s) -> str:
    return str(s or "")[:16].replace("T", " ") or "—"


def pseudo(uid: str) -> str:
    return f"Membre #{hashlib.sha256((uid or '').encode()).hexdigest()[:6].upper()}"


class _Names(dict):
    def get(self, k, default=None):
        return super().get(k) or f"{pseudo(k)} (compte supprimé)"


def create_trace_router(db):
    router = APIRouter(prefix="/api/admin")

    async def who(super_: bool) -> dict:
        """uid -> display label; members deleted since are labelled as such."""
        users = {u["id"]: f"{u.get('name') or '—'} <{u.get('email')}>" async for u in db.users.find({}, {"_id": 0, "id": 1, "name": 1, "email": 1})}
        return _Names(users if super_ else {k: pseudo(k) for k in users})

    async def members(flt: dict, super_: bool, ids=None):
        if ids is not None:
            flt = {**flt, "id": {"$in": list(ids)}}
        radar = {s["user_id"]: s.get("enabled", True) async for s in db.radar_settings.find({}, {"_id": 0, "user_id": 1, "enabled": 1})}
        geo = await geo_labels(db)
        city_n = Counter(v[2] for v in geo.values())
        city = lambda uid: (lambda c: c if super_ or city_n[c] >= MIN_CELL or c == "Non renseigné" else f"Autres (groupe de moins de {MIN_CELL})")(geo.get(uid, ("", "", "—"))[2])  # noqa: E731
        rows = []
        async for u in db.users.find(flt, {"_id": 0, "id": 1, "name": 1, "email": 1, "created_at": 1, "last_seen_at": 1, "paid": 1}).sort("created_at", -1).limit(LIMIT):
            rows.append({"member": f"{u.get('name') or '—'} <{u['email']}>" if super_ else pseudo(u["id"]), "created": _d(u.get("created_at")),
                         "seen": _d(u.get("last_seen_at")), "paid": "oui" if u.get("paid") else "non",
                         "radar": "oui" if radar.get(u["id"]) else ("désactivé" if u["id"] in radar else "non configuré"), "city": city(u["id"])})
        return MEMBER_COLS, rows

    async def offers(flt: dict, super_: bool):
        names = await who(super_)
        rows = [{"date": _d(o.get("analyzed_at")), "title": o.get("title"), "company": o.get("company"), "source": o.get("source"),
                 "ips": (o.get("ips") or {}).get("score"), "priority": (o.get("ips") or {}).get("priority") or "—",
                 "member": names.get(o["user_id"]) or pseudo(o["user_id"])}
                async for o in db.radar_offers.find(flt, {"_id": 0, "user_id": 1, "analyzed_at": 1, "title": 1, "company": 1, "source": 1, "ips.score": 1, "ips.priority": 1})
                .sort("analyzed_at", -1).limit(LIMIT)]
        return OFFER_COLS, rows

    async def apps(flt: dict, super_: bool):
        names = await who(super_)
        rows = []
        async for a in db.applications.find(flt, {"_id": 0, "user_id": 1, "created_at": 1, "ips": 1, "origin": 1, "parts.decision.poste": 1, "parts.decision.entreprise": 1}).sort("created_at", -1).limit(LIMIT):
            r = {"date": _d(a.get("created_at")), "member": names.get(a["user_id"]) or pseudo(a["user_id"]), "priority": (a.get("ips") or {}).get("priority") or "—",
                 "ips": (a.get("ips") or {}).get("score"), "origin": "Radar" if (a.get("origin") or {}).get("type") == "radar" else "Manuel"}
            if super_:
                d = (a.get("parts") or {}).get("decision") or {}
                r.update(poste=d.get("poste") or "—", entreprise=d.get("entreprise") or "—")
            rows.append(r)
        cols = [["date", "Créé le"], ["member", "Membre"], ["origin", "Origine"], ["priority", "Priorité"], ["ips", "IPS"]] + ([["poste", "Poste"], ["entreprise", "Entreprise"]] if super_ else [])
        return cols, rows, None if super_ else "Rôle non Super Admin : poste et entreprise masqués (confidentialité des candidatures)."

    async def runs(flt: dict, super_: bool):
        names = await who(super_)
        rows = [{"date": _d(r.get("at")), "member": names.get(r["user_id"]) or pseudo(r["user_id"]), "trigger": "Automatique" if r.get("trigger") == "quotidien" else "Manuel",
                 "fetched": r.get("fetched", 0), "new": r.get("new", 0), "analyzed": r.get("analyzed", 0), "skipped": r.get("skipped_limit", 0), "status": r.get("status"),
                 "alerts": len([k for k in (r.get("errors") or {}) if not k.startswith("_")])}
                async for r in db.radar_runs.find(flt, {"_id": 0, "portals": 0, "by_source": 0}).sort("at", -1).limit(LIMIT)]
        return RUN_COLS, rows

    async def events(type_, days, key=""):
        flt = {"type": type_, **({"ts": {"$gte": _now() - timedelta(days=days)}} if days else {})}
        if key:
            flt["meta.provider"] = {"$ne": key[1:]} if key.startswith("!") else key
        rows = []
        async for e in db.admin_events.find(flt, {"_id": 0}).sort("ts", -1).limit(LIMIT):
            m = e.get("meta") or {}
            rows.append({"date": _d(e.get("ts").isoformat() if hasattr(e.get("ts"), "isoformat") else e.get("ts")), "session": (e.get("session_id") or "—")[:8],
                         "provider": m.get("provider") or "—", "tin": m.get("tokens_in"), "tout": m.get("tokens_out"), "cost": m.get("cost"), "ip": e.get("ip_trunc") or "—"})
        if type_ == "llm_call":
            return [["date", "Date"], ["session", "Session (anon.)"], ["provider", "Fournisseur"], ["tin", "Tokens entrée"], ["tout", "Tokens sortie"], ["cost", "Coût $"]], rows
        return [["date", "Date"], ["session", "Session (anon.)"], ["ip", "IP (anonymisée)"]], rows

    async def sessions(types, days):
        flt = {"type": {"$in": types}, "session_id": {"$nin": ["", None]}, **({"ts": {"$gte": _now() - timedelta(days=days)}} if days else {})}
        agg = db.admin_events.aggregate([{"$match": flt}, {"$group": {"_id": "$session_id", "first": {"$min": "$ts"}, "types": {"$addToSet": "$type"}, "n": {"$sum": 1}}},
                                         {"$sort": {"first": -1}}, {"$limit": LIMIT}])
        rows = [{"session": r["_id"][:8], "first": _d(r["first"].isoformat() if hasattr(r["first"], "isoformat") else r["first"]), "types": ", ".join(sorted(r["types"])), "n": r["n"]} async for r in agg]
        return [["session", "Session (anon.)"], ["first", "Première activité"], ["types", "Types"], ["n", "Événements"]], rows

    async def ats(cv_only: bool):
        flt = {"cv_text": {"$ne": None}} if cv_only else {}
        pipe = [{"$match": flt}, {"$sort": {"ts": -1}}, {"$limit": LIMIT},
                {"$project": {"_id": 0, "ts": 1, "score": 1, "company": 1, "consent": 1, "ip_trunc": 1, "has_cv": {"$cond": [{"$ifNull": ["$cv_text", False]}, True, False]}}}]
        rows = [{"date": _d(s.get("ts").isoformat() if hasattr(s.get("ts"), "isoformat") else s.get("ts")), "score": s.get("score"),
                 "company": re.sub(r"[#*⚠️\n]+", " ", s.get("company") or "")[:60].strip() or "—", "consent": "oui" if s.get("consent") else "non",
                 "cv": "oui" if s.get("has_cv") else "non", "ip": s.get("ip_trunc") or "—"}
                async for s in db.ats_submissions.aggregate(pipe)]
        return [["date", "Date"], ["score", "Score"], ["company", "Entreprise"], ["consent", "Consentement"], ["cv", "CV stocké"], ["ip", "IP (anon.)"]], rows

    @router.get("/trace")
    async def trace(metric: str, key: str = "", days: int = 30, x_admin_password: str = Header(None)):
        _check_admin(x_admin_password)
        sup = is_super()
        a7, a30 = _ago(7), _ago(30)
        since = _ago(days) if days else ""
        note = None
        title = metric
        if metric.startswith(("m_", "f_")):
            cohort = {"created_at": {"$gte": since}} if since and metric.startswith("f_") else {}
            spec = {"m_total": ("Membres au total", {}), "m_active7": ("Membres actifs (7 jours)", {"last_seen_at": {"$gte": a7}}),
                    "m_active30": ("Membres actifs (30 jours)", {"last_seen_at": {"$gte": a30}}), "m_new7": ("Nouveaux membres (7 jours)", {"created_at": {"$gte": a7}}),
                    "m_new30": ("Nouveaux membres (30 jours)", {"created_at": {"$gte": a30}}), "m_paid": ("Membres payants", {"paid": True}),
                    "f_inscrits": ("Entonnoir · Inscrits", cohort), "f_actifs": ("Entonnoir · Actifs", {**cohort, "last_seen_at": {"$gte": a30}}),
                    "f_payants": ("Entonnoir · Payants", {**cohort, "last_seen_at": {"$gte": a30}, "paid": True}),
                    "f_renouv": ("Entonnoir · Renouvellement", {**cohort, "last_seen_at": {"$gte": a30}, "paid": True, "paid_since": {"$lte": a30}})}
            if metric == "f_visitors":
                title, (cols, rows) = "Entonnoir · Visiteurs (sessions anonymes)", await sessions(["visit", "simulation"], days)
            elif metric in spec:
                title, flt = spec[metric]
                cols, rows = await members(flt, sup)
            else:
                raise HTTPException(status_code=422, detail="Indicateur inconnu")
        elif metric.startswith("r_"):
            if metric in ("r_enabled", "r_configured"):
                ids = {s["user_id"] async for s in db.radar_settings.find({"enabled": {"$ne": False}} if metric == "r_enabled" else {}, {"user_id": 1})}
                title, (cols, rows) = ("Radar activé" if metric == "r_enabled" else "Radar configuré"), await members({}, sup, ids)
            elif metric == "r_members":
                ids = set(await db.radar_runs.distinct("user_id", {"at": {"$gte": a30}}))
                title, (cols, rows) = "Membres ayant utilisé le Radar (30 j)", await members({}, sup, ids)
            elif metric in ("r_runs", "r_auto", "r_manual"):
                flt = {"at": {"$gte": a30}, **({"trigger": "quotidien"} if metric == "r_auto" else {"trigger": {"$ne": "quotidien"}} if metric == "r_manual" else {})}
                title, (cols, rows) = {"r_runs": "Passages Radar (30 j)", "r_auto": "Passages automatiques (30 j)", "r_manual": "Passages manuels (30 j)"}[metric], await runs(flt, sup)
            elif metric == "r_analyzed":
                title, (cols, rows) = "Offres analysées par le Radar (30 j)", await offers({"analyzed_at": {"$gte": a30}}, sup)
            elif metric == "r_packs":
                title = "Packs créés depuis le Radar (30 j)"
                cols, rows, note = await apps({"created_at": {"$gte": a30}, "origin.type": "radar"}, sup)
            else:
                raise HTTPException(status_code=422, detail="Indicateur inconnu")
        elif metric in ("g_country", "g_province", "g_city"):
            i = {"g_country": 0, "g_province": 1, "g_city": 2}[metric]
            labels = await geo_labels(db)
            counts = Counter(v[i] for v in labels.values())
            small = key.startswith("Autres (")
            ids = {u for u, v in labels.items() if (counts[v[i]] < MIN_CELL if small else v[i] == key)}
            title = f"{['Pays', 'Province / région', 'Ville'][i]} · {key}"
            cols, rows = await members({}, sup, ids)
        elif metric == "b_role":
            ids = {u for u, labels in (await member_roles(db)).items() if key in labels}
            title, (cols, rows) = f"Poste recherché · {key}", await members({}, sup, ids)
        elif metric in ("b_company", "b_portal"):
            names = await who(sup)
            rows = []
            async for s in db.radar_settings.find({}, {"_id": 0, "user_id": 1, "companies": 1}):
                for c in s.get("companies") or []:
                    if not (isinstance(c, dict) and c.get("enabled", True) and c.get("name")):
                        continue
                    portal = KIND_LABEL.get(c.get("kind"), c.get("kind")) if c.get("kind") else "Jooble (sans portail)"
                    if (metric == "b_company" and (KB.key(c["name"]) or c["name"].lower()) == (KB.key(key) or key.lower())) or (metric == "b_portal" and portal == key):
                        rows.append({"company": c["name"], "portal": portal, "url": c.get("portal_url") or "—", "auto": "oui" if c.get("auto") else "non",
                                     "member": names.get(s["user_id"]) or pseudo(s["user_id"])})
            title = f"{'Entreprise suivie' if metric == 'b_company' else 'Portail'} · {key}"
            cols = [["company", "Entreprise"], ["portal", "Portail"], ["url", "URL du portail"], ["auto", "Associé auto"], ["member", "Membre"]]
        elif metric in ("b_offers30", "b_offers_total", "b_source", "b_prio_radar"):
            flt = {"analyzed_at": {"$gte": a30}} if metric != "b_offers_total" else {"analyzed_at": {"$ne": None}}
            if metric == "b_source":
                flt["source"] = key
            if metric == "b_prio_radar":
                flt["ips.priority"] = key
            title = {"b_offers30": "Offres analysées (30 j)", "b_offers_total": "Offres analysées (total, 1000 plus récentes)",
                     "b_source": f"Offres analysées (30 j) · source {key}", "b_prio_radar": f"Offres Radar (30 j) · priorité {key}"}[metric]
            cols, rows = await offers(flt, sup)
        elif metric == "b_prio_apps":
            title = f"Candidatures · priorité {key}"
            cols, rows, note = await apps({"ips.priority": key}, sup)
        elif metric.startswith("a_"):
            if metric == "a_visitors":
                title, (cols, rows) = "Visiteurs (sessions de simulation distinctes)", await sessions(["simulation"], 0)
            elif metric in ("a_simulations", "a_letters", "a_llm"):
                title = {"a_simulations": "Simulations", "a_letters": "Lettres", "a_llm": f"Appels LLM{f' · {key}' if key and not key.startswith('!') else ' · serveur (hors Gemini)' if key else ''}"}[metric]
                cols, rows = await events({"a_simulations": "simulation", "a_letters": "cover_letter", "a_llm": "llm_call"}[metric], 0, key)
            elif metric in ("a_ats", "a_cvs"):
                title, (cols, rows) = ("Analyses ATS" if metric == "a_ats" else "CV analysés (stockés avec consentement)"), await ats(metric == "a_cvs")
            else:
                raise HTTPException(status_code=422, detail="Indicateur inconnu")
        elif metric in ("fin_active", "fin_paid", "fin_active_paid"):
            month = key or _now().strftime("%Y-%m")
            act = set(await db.member_activity.distinct("user_id", {"month": month}))
            if month == _now().strftime("%Y-%m"):  # same rule as Rentabilité: activity log + connections this month
                act |= set(await db.users.distinct("id", {"last_seen_at": {"$gte": f"{month}-01"}}))
            doc = await db.finance_months.find_one({"month": month}, {"_id": 0, "paid_override": 1}) or {}
            if doc.get("paid_override") is not None:
                note = f"Nombre de payants saisi manuellement pour {month} : {doc['paid_override']}. La liste ci-dessous montre les membres cochés « payant »."
            if metric == "fin_active":
                title, (cols, rows) = f"Membres actifs · {month}", await members({}, sup, act)
            elif metric == "fin_paid":
                title, (cols, rows) = "Membres payants", await members({"paid": True}, sup)
            else:
                title, (cols, rows) = f"Membres actifs payants · {month}", await members({"paid": True}, sup, act)
        elif metric == "fin_ai_calls":
            month = key or _now().strftime("%Y-%m")
            rows = [{"date": _d(r.get("at")), "provider": r.get("provider"), "model": r.get("model"), "feature": r.get("feature") or "—",
                     "tin": r.get("tokens_in"), "tout": r.get("tokens_out")}
                    async for r in db.ai_usage.find({"month": month}, {"_id": 0}).sort("at", -1).limit(LIMIT)]
            title = f"Appels IA journalisés · {month}"
            cols = [["date", "Date"], ["provider", "Fournisseur"], ["model", "Modèle"], ["feature", "Fonctionnalité"], ["tin", "Jetons entrée"], ["tout", "Jetons sortie"]]
        else:
            raise HTTPException(status_code=422, detail="Indicateur inconnu")
        return {"title": title, "cols": cols, "rows": rows, "total": len(rows), "truncated": len(rows) >= LIMIT,
                "note": note or (None if sup else "Membres pseudonymisés pour votre rôle (aucun e-mail, aucun CV ni contenu de Career Memory).")}

    return router
