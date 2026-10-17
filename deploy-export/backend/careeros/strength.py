"""Indice de Force Professionnelle (IFP): profile-only score /100 by deterministic rules (no AI, no cost), with daily history."""
import re
import unicodedata
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException

MONTHS = {"jan": 1, "fev": 2, "feb": 2, "mar": 3, "avr": 4, "apr": 4, "mai": 5, "may": 5, "juin": 6, "jun": 6, "juil": 7, "jul": 7, "aou": 8, "aug": 8,
          "sep": 9, "oct": 10, "nov": 11, "dec": 12}
NOW_WORDS = r"(?:a ce jour|ce jour|aujourd hui|present|maintenant|actuel|now|current|today)"
LEAD = ["supervis", "encadr", "gestion d equipe", "gestion des equipes", "gestion de personnel", "chef d equipe", "leadership", "gestionnaire", "directeur",
        "directrice", "manager", "relations de travail", "syndic", "coordonnateur", "coordonnatrice", "mentor", "coach", "former les", "formation des employes", "responsable d equipe"]
CERTS = ["certif", "attestation", "premiers secours", "premier secours", "premiers soins", "cnesst", "sst", "chariot elevateur", "cariste", "sqf", "haccp", "pmp",
         "itil", "iso", "csst", "simdut", "whmis", "permis classe", "asp construction", "red seal", "cpa", "pl 300", "scrum master", "six sigma", "lean"]
TOOLS = ["excel", "word", "powerpoint", "outlook", "office 365", "microsoft 365", "power bi", "tableau", "sql", "python", "sap", "oracle", "dayforce", "horasphere",
         "geobus", "progression live", "jira", "wms", "erp", "salesforce", "sharepoint", "teams", "google workspace", "kronos", "ukg", "workday", "quickbooks",
         "autocad", "manhattan", "blue yonder", "netsuite", "dynamics", "looker", "zendesk"]
# domain -> (keywords, compatible roles, competitive sectors)
DOMAINS = {
    "Logistique et distribution": (["logisti", "reception", "expedition", "entrepos", "inventaire", "distribution", "chaine d approvisionnement", "supply", "flux", "manutention", "chariot"],
                                   ["Superviseur des opérations logistiques", "Coordonnateur logistique", "Superviseur d'entrepôt", "Gestionnaire de centre de distribution"],
                                   ["Entreposage et centres de distribution", "Commerce de détail et épicerie", "Commerce électronique"]),
    "Transport et livraison": (["transport", "livraison", "flotte", "camion", "dispatch", "repartition", "geobus", "dernier kilometre", "chauffeur"],
                               ["Répartiteur / dispatcher", "Superviseur transport", "Coordonnateur de la livraison"], ["Transport et messagerie", "Livraison du dernier kilomètre", "Transport scolaire et collectif"]),
    "Santé et sécurité au travail": (["sst", "cnesst", "securit", "secours", "prevention", "urgence", "incident", "risque", "ergonom"],
                                     ["Coordonnateur SST", "Agent de prévention", "Superviseur sécurité et conformité"], ["Manufacturier", "Construction", "Entreposage et centres de distribution"]),
    "Conformité et qualité": (["sqf", "conformit", "qualit", "norme", "iso", "haccp", "audit", "procedure", "politique"],
                              ["Coordonnateur qualité", "Superviseur conformité", "Technicien assurance qualité"], ["Agroalimentaire", "Manufacturier", "Pharmaceutique"]),
    "Leadership et gestion d'équipe": (["supervis", "encadr", "leadership", "equipe", "discipline", "gestion de personnel", "mentor", "coach", "multiculturel"],
                                       ["Superviseur des opérations", "Chef d'équipe", "Gestionnaire des opérations"], ["Services aux entreprises", "Manufacturier", "Commerce de détail et épicerie"]),
    "Gestion des opérations": (["operation", "quart", "priorit", "planif", "coordination", "production", "amelioration continue", "performance", "kpi", "imprevu"],
                               ["Gestionnaire des opérations", "Superviseur de production", "Coordonnateur des opérations"], ["Manufacturier", "Logistique tierce partie (3PL)", "Services publics"]),
    "Données et analyse": (["donnee", "data", "analyse", "power bi", "sql", "python", "tableau de bord", "dashboard", "reporting", "statisti"],
                           ["Analyste de données", "Analyste BI", "Analyste d'affaires"], ["Services financiers", "Technologies", "Secteur public"]),
    "Gestion de projet": (["projet", "partie prenante", "agile", "scrum", "pmp", "deploiement", "jalon"], ["Chargé de projet", "Coordonnateur de projets", "Gestionnaire de projet"],
                          ["Technologies", "Construction", "Services-conseils"]),
    "Finance et administration": (["budget", "financ", "comptab", "cout", "factur", "paie"], ["Technicien comptable", "Analyste financier", "Adjoint administratif"],
                                  ["Services financiers", "Secteur public", "Assurances"]),
    "Service à la clientèle": (["client", "service a la clientele", "relation client", "satisfaction"], ["Superviseur service à la clientèle", "Conseiller service client"],
                               ["Commerce de détail et épicerie", "Télécommunications", "Centres de contact"]),
    "Technologies": (["developp", "programm", "cloud", "azure", "aws", "java", "api", "devops", "reseau", "cyber"], ["Développeur", "Analyste TI", "Technicien en informatique"],
                     ["Technologies", "Services financiers", "Télécommunications"]),
}
WEIGHTS = {"experience": 25, "skills": 20, "leadership": 15, "certifications": 10, "tools": 15, "stability": 15}
LABELS = {"experience": "Expérience", "skills": "Compétences", "leadership": "Leadership", "certifications": "Certifications", "tools": "Outils maîtrisés",
          "stability": "Stabilité du parcours"}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _n(s: str) -> str:
    return re.sub(r"[^a-z0-9+#]+", " ", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()


def _date(tok: str, now: datetime) -> float:
    if re.fullmatch(NOW_WORDS, tok):
        return now.year + (now.month - 1) / 12
    m = re.fullmatch(r"(?:(\d{1,2})\s+|([a-z]{3,})\s+)?((?:19|20)\d{2})(?:\s+(\d{1,2}))?", tok)
    if not m:
        return 0
    month = int(m.group(1) or m.group(4) or 0) or MONTHS.get((m.group(2) or "")[:4], 0) or MONTHS.get((m.group(2) or "")[:3], 1)
    return int(m.group(3)) + (min(max(month, 1), 12) - 1) / 12


def _n_same_len(s: str) -> str:
    """Accent-free lowercase text with the same length as s (positions map back to the original CV)."""
    out = []
    for ch in s or "":
        c = unicodedata.normalize("NFKD", ch).encode("ascii", "ignore").decode().lower()[:1]
        out.append(c if c and re.match(r"[a-z0-9+#]", c) else " ")
    return "".join(out)


def periods(cv: str, now: datetime) -> list:
    """Job periods [(start, end, label)] from date ranges such as « 2023-11 à ce jour », « mars 2019 - juin 2022 », « 2015 – 2018 »."""
    t = _n_same_len(cv)
    mon = r"(?:janv?(?:ier)?|fevr?(?:ier)?|feb(?:ruary)?|mars?|march|avr(?:il)?|apr(?:il)?|mai|may|juin|june?|juil(?:let)?|july?|aout|aug(?:ust)?|sept?(?:embre|ember)?|oct(?:obre|ober)?|nov(?:embre|ember)?|dec(?:embre|ember)?)"
    d = rf"(?:(?:\d{{1,2}}\s+|{mon}\s+)?(?:19|20)\d{{2}}(?:\s+\d{{1,2}})?)"
    out, prev = [], 0
    for m in re.finditer(rf"({d})\s+(?:a|au|to|jusqu a)?\s*({d}|{NOW_WORDS})", t):
        g1, g2 = " ".join(m.group(1).split()), " ".join(m.group(2).split())
        a, b = _date(g1, now), _date(g2, now)
        if a and b and 0 < b - a <= 45 and b <= now.year + 1:
            snip = " ".join(cv[max(prev, m.start() - 45):m.end()].split())
            prev = m.end()
            out.append((round(a, 2), round(b + (1 / 12 if not re.fullmatch(NOW_WORDS, g2) else 0), 2), f"… {snip}"[-95:]))
    return out


def _merged_years(ps: list) -> float:
    total, cur = 0.0, None
    for a, b, _ in sorted(ps):
        if cur and a <= cur[1]:
            cur[1] = max(cur[1], b)
        else:
            total += (cur[1] - cur[0]) if cur else 0
            cur = [a, b]
    return round(total + ((cur[1] - cur[0]) if cur else 0), 1)


def _hits(text: str, words: list) -> list:
    return [w for w in words if f" {w}" in f" {text}"]


FIGURE = re.compile(r"\d[\d\s.,]*\s?(?:%|\$|k\$|m\$)|\$\s?\d[\d\s.,]*|\b\d{2,}\s+(?:employes|employés|personnes|agents|membres|chauffeurs|colis|commandes|camions|"
                    r"livraisons|clients|magasins|sites|quarts|palettes|associés|associes|collaborateurs|people|employees|staff)\b", re.I)


def quantified(text: str) -> list:
    return list(dict.fromkeys(m.group(0).strip() for m in FIGURE.finditer(text or "")))[:20]


def compute(p: dict, now: datetime = None) -> dict:
    now = now or datetime.now(timezone.utc)
    cv = p.get("cv_text") or ""
    corpus = _n(" ".join([cv, p.get("achievements") or "", p.get("headline") or "", " ".join(p.get("skills_detected") or []), " ".join(p.get("skills") or [])]))
    ps = periods(cv, now)
    years = _merged_years(ps)
    m = re.search(r"(?:plus de|over|more than)?\s*(\d{1,2})\s*(?:\+\s*)?(?:ans|annees|years)\s+d\s*experience|(\d{1,2})\s*(?:\+\s*)?(?:years|ans|annees) of experience", _n(cv))
    declared = int(m.group(1) or m.group(2)) if m else 0
    years_used = max(years, declared)
    crit = {}
    crit["experience"] = (min(1, years_used / 10), f"{years_used:g} an(s) d'expérience retenu(s)",
                          [f"Périodes détectées : {len(ps)} ({years:g} an(s) sans chevauchement)"] + ([f"Expérience déclarée : {declared} an(s)"] if declared else []) + [x[2] for x in ps[:8]],
                          "10 ans ou plus = note maximale (proportionnelle en dessous).")
    skills = list(dict.fromkeys([s.strip() for s in (p.get("skills_detected") or []) + (p.get("skills") or []) if str(s).strip()]))
    doms = {}
    for name, (keys, _r, _s) in DOMAINS.items():
        hit = [s for s in skills if any(k in _n(s) for k in keys)]
        mentions = sum(corpus.count(k) for k in keys)
        if hit or mentions >= 3:
            doms[name] = {"skills": hit, "mentions": mentions, "weight": len(hit) * 3 + mentions}
    breadth = len([d for d in doms.values() if d["skills"]])
    figures = quantified(cv + " " + (p.get("achievements") or ""))
    crit["skills"] = (min(1, len(skills) / 25 * 0.6 + min(breadth, 5) / 5 * 0.25 + min(len(figures), 5) / 5 * 0.15),
                      f"{len(skills)} compétence(s), {breadth} domaine(s), {len(figures)} résultat(s) chiffré(s)",
                      skills[:30] + [f"Résultat chiffré : « {f} »" for f in figures[:8]],
                      "25 compétences distinctes (60 %) + 5 domaines couverts (25 %) + 5 résultats chiffrés (15 %) = note maximale.")
    lead = _hits(corpus, LEAD)
    lead_n = sum(corpus.count(w) for w in lead)
    promos = int(p.get("promotions") or 0)
    crit["leadership"] = (min(1, lead_n / 10 * 0.8 + min(promos, 2) / 2 * 0.2), f"{lead_n} mention(s) de leadership, {promos} promotion(s)",
                          [f"« {w} »" for w in lead], "10 mentions d'encadrement (80 %) + 2 promotions (20 %) = note maximale.")
    certs = list(dict.fromkeys([c for c in p.get("certifications") or [] if str(c).strip()] + [f"« {w} » (dans le CV)" for w in _hits(corpus, CERTS)]))
    crit["certifications"] = (min(1, len(certs) / 4), f"{len(certs)} certification(s) ou attestation(s)", certs, "4 certifications ou attestations = note maximale.")
    tools = _hits(corpus, TOOLS)
    crit["tools"] = (min(1, len(tools) / 6), f"{len(tools)} outil(s) détecté(s)", tools, "6 outils ou logiciels distincts = note maximale.")
    if ps:
        tenure = round(sum(b - a for a, b, _ in ps) / len(ps), 1)
        crit["stability"] = (min(1, tenure / 3), f"{tenure:g} an(s) en moyenne par poste", [x[2] for x in ps[:8]], "3 ans en moyenne par poste = note maximale.")
    else:
        crit["stability"] = (0.5, "Dates de postes non détectées : note neutre", [], "Ajoutez les dates de vos postes (ex. « 2019-03 à 2022-06 ») dans le CV.")
    criteria = [{"key": k, "label": LABELS[k], "max": WEIGHTS[k], "score": round(v[0] * WEIGHTS[k], 1), "summary": v[1], "evidence": v[2][:30], "rule": v[3]}
                for k, v in crit.items()]
    raw = round(sum(v[0] * WEIGHTS[k] for k, v in crit.items()), 2)
    score = round(raw)
    top = sorted(doms.items(), key=lambda x: -x[1]["weight"])[:3]
    lead_level = crit["leadership"][0] >= 0.5
    roles, sectors = [], {}
    for name, d in top:
        _k, rs, ss = DOMAINS[name]
        roles += [r for r in rs if lead_level or not re.match(r"(Gestionnaire|Directeur)", r)][:2]
        for i, sct in enumerate(ss):
            sectors[sct] = sectors.get(sct, 0) + d["weight"] * (3 - i)
    for r in [x.strip() for x in re.split(r"[,;/\n]", p.get("target_roles") or "") if x.strip()][:2]:
        if r.lower() not in (x.lower() for x in roles):
            roles.insert(0, f"{r} (poste visé)")
    tw = sum(d["weight"] for _, d in top) or 1
    return {
        "score": score, "raw": raw, "level": "Très fort" if score >= 80 else "Fort" if score >= 65 else "Intermédiaire" if score >= 45 else "En développement",
        "criteria": criteria,
        "domains": [{"name": n, "share": round(d["weight"] * 100 / tw), "skills": d["skills"][:8], "mentions": d["mentions"]} for n, d in top],
        "roles": list(dict.fromkeys(roles))[:6],
        "sectors": [{"name": n, "score": round(v * 100 / max(sectors.values()))} for n, v in sorted(sectors.items(), key=lambda x: -x[1])[:5]],
        "note": "Indice calculé uniquement à partir de votre profil (CV maître et Career Memory), par règles CareerOS, sans IA. L'IPS reste la comparaison avec une offre précise.",
    }


def create_strength_router(db, current_user):
    router = APIRouter(prefix="/api/careeros")

    @router.get("/strength")
    async def strength(user: dict = Depends(current_user)):
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        res = compute(profile)
        day = datetime.now(timezone.utc).date().isoformat()
        last = await db.strength_history.find_one({"user_id": user["id"]}, {"_id": 0}, sort=[("day", -1)])
        if (profile.get("cv_text") or "").strip() and (not last or last["score"] != res["score"] or last["day"] == day):
            await db.strength_history.update_one({"user_id": user["id"], "day": day}, {"$set": {"score": res["score"], "criteria": {c["key"]: c["score"] for c in res["criteria"]}}}, upsert=True)
        hist = [h async for h in db.strength_history.find({"user_id": user["id"]}, {"_id": 0, "day": 1, "score": 1, "criteria": 1}).sort("day", 1).limit(365)]
        lv = levers(profile, res)
        ids = {it["id"] for it in lv["items"]}
        async for f in db.strength_follow.find({"user_id": user["id"], "done": False}, {"_id": 0}):
            if f["lever_id"] not in ids:  # followed lever no longer needed -> realised (anonymous aggregate)
                gain = round(res["raw"] - f["raw_at"], 1)
                await db.strength_follow.update_one({"user_id": user["id"], "lever_id": f["lever_id"]}, {"$set": {"done": True, "done_at": _now(), "gain": gain}})
                await db.lever_stats.update_one({"lever_id": f["lever_id"]}, {"$inc": {"done": 1, "gain_total": gain}}, upsert=True)
        followed = {f["lever_id"] async for f in db.strength_follow.find({"user_id": user["id"], "done": False}, {"_id": 0, "lever_id": 1})}
        for it in lv["items"]:
            it["followed"] = it["id"] in followed
        return {**res, "history": hist, "levers": lv}

    @router.post("/strength/levers/{lever_id}/follow")
    async def follow(lever_id: str, user: dict = Depends(current_user)):
        if not re.fullmatch(r"[a-z_]{2,20}", lever_id):
            raise HTTPException(status_code=422, detail="Levier inconnu")
        cur = await db.strength_follow.find_one({"user_id": user["id"], "lever_id": lever_id, "done": False})
        profile = await db.career_profiles.find_one({"user_id": user["id"]}, {"_id": 0}) or {}
        if not cur and lever_id not in {it["id"] for it in levers(profile, compute(profile))["items"]}:
            raise HTTPException(status_code=422, detail="Levier inconnu")
        if cur:
            await db.strength_follow.delete_one({"_id": cur["_id"]})
            await db.lever_stats.update_one({"lever_id": lever_id}, {"$inc": {"followed": -1}}, upsert=True)
            return {"followed": False}
        await db.strength_follow.update_one({"user_id": user["id"], "lever_id": lever_id},
                                            {"$set": {"done": False, "at": _now(), "raw_at": compute(profile)["raw"]}}, upsert=True)
        await db.lever_stats.update_one({"lever_id": lever_id}, {"$inc": {"followed": 1}}, upsert=True)
        return {"followed": True}

    return router


# ---------------- « Comment gagner des points ? » : rule-based levers, gain simulated by recomputing the index ----------------
def _plus(p: dict, cv: str = "", skills: list = (), certs: list = (), promotions: int = 0) -> dict:
    return {**p, "cv_text": f"{p.get('cv_text') or ''} {cv}", "skills": list(p.get("skills") or []) + list(skills),
            "certifications": list(p.get("certifications") or []) + list(certs), "promotions": int(p.get("promotions") or 0) + promotions}


def _has(corpus: str, *words) -> bool:
    return any(f" {w}" in f" {corpus}" for w in words)


def _catalog(p: dict, res: dict, corpus: str) -> list:
    """Candidate actions [(id, title, why, difficulty, effort label, effort hours, simulated profile, evidence)] adapted to the strongest domains."""
    doms = [d["name"] for d in res["domains"]]
    crit = {c["key"]: c for c in res["criteria"]}
    ops = any(d in doms for d in ("Logistique et distribution", "Gestion des opérations", "Conformité et qualité", "Transport et livraison", "Leadership et gestion d'équipe"))
    out = []
    figures = quantified((p.get("cv_text") or "") + " " + (p.get("achievements") or ""))
    if len(figures) < 5:
        out.append(("kpi", "Mettre en valeur vos KPI et résultats chiffrés dans le CV", "Les recruteurs retiennent d'abord les résultats mesurables (%, volumes, taille d'équipe, délais) : ils prouvent l'impact de votre expérience.",
                    "Facile", "30 min", 0.5, _plus(p, cv=" ".join(["12 %", "25 employés", "3000 colis", "98 %", "15 %"][: 5 - len(figures)])),
                    [f"Résultats chiffrés trouvés : {len(figures)}"] + [f"« {f} »" for f in figures]))
    if ops and not _has(corpus, "six sigma", "lean"):
        out.append(("cert_lean", "Obtenir une certification Lean Six Sigma (ceinture jaune ou verte)", "Certification reconnue en amélioration continue, très demandée pour les postes de supervision et de gestion des opérations.",
                    "Moyenne", "1 à 3 mois", 60, _plus(p, certs=["Lean Six Sigma Green Belt"]), [f"Certifications actuelles : {crit['certifications']['summary']}"] + crit["certifications"]["evidence"][:6]))
    if "Santé et sécurité au travail" in doms and not _has(corpus, "asp", "superviseur sst", "formation sst"):
        out.append(("cert_sst", "Suivre une formation SST pour superviseurs (ASP / CNESST)", "Votre profil est fort en SST : une attestation officielle transforme cette force en preuve vérifiable.",
                    "Facile", "1 à 3 jours", 16, _plus(p, certs=["Formation SST superviseur (ASP)"]), [f"Domaine SST : {next((d['share'] for d in res['domains'] if d['name'] == 'Santé et sécurité au travail'), 0)} % des domaines forts"]))
    if not _has(corpus, "pmp", "capm", "gestion de projet"):
        out.append(("cert_pm", "Obtenir une certification en gestion de projet (CAPM ou PMP)", "Montre votre capacité à piloter des changements et des projets transverses, un critère fréquent pour les postes de gestionnaire.",
                    "Élevée", "2 à 4 mois", 120, _plus(p, certs=["CAPM"], skills=["Gestion de projet"]), crit["certifications"]["evidence"][:6]))
    missing = [t for t in (["sap", "wms", "excel", "power bi"] if ops else ["excel", "power bi", "sql", "sharepoint"]) if not _has(corpus, t)][:2]
    if missing:
        out.append(("tools", f"Compléter vos outils : {', '.join(m.upper() if len(m) <= 4 else m.title() for m in missing)}", "Les offres de votre domaine exigent souvent ces logiciels ; une formation en ligne courte suffit pour les ajouter honnêtement au CV.",
                    "Moyenne", "2 à 4 semaines", 20, _plus(p, cv=" ".join(missing), skills=[m.title() for m in missing]), [f"Outils détectés : {', '.join(crit['tools']['evidence']) or 'aucun'}"]))
    if not _has(corpus, "budget", "budgetaire"):
        out.append(("budget", "Ajouter ou préciser votre expérience en gestion budgétaire", "La maîtrise des coûts et des budgets distingue un superviseur d'un gestionnaire : c'est un critère clé pour monter en responsabilité.",
                    "Facile", "15 min (si déjà pratiquée)", 0.5, _plus(p, cv="gestion budgétaire budget", skills=["Gestion budgétaire"]), ["Aucune mention de budget trouvée dans le CV ou la Career Memory"]))
    if ops and not _has(corpus, "syndic", "relations de travail", "convention collective"):
        out.append(("union", "Préciser votre expérience en relations de travail / milieu syndiqué", "Beaucoup d'employeurs logistiques et manufacturiers au Québec sont syndiqués : cette expérience rassure pour l'encadrement.",
                    "Facile", "15 min (si déjà vécue)", 0.5, _plus(p, cv="relations de travail convention collective", skills=["Relations de travail et gestion syndicale"]),
                    ["Aucune mention de syndicat ou de convention collective trouvée"]))
    lead = crit["leadership"]
    if lead["score"] < lead["max"] * 0.85:
        out.append(("lead", "Mettre davantage en valeur votre encadrement (taille d'équipe, coaching, formation)", "Le leadership pèse 15 points : décrire précisément qui vous encadrez et comment vous les faites progresser augmente fortement la valeur du profil.",
                    "Facile", "20 min", 0.3, _plus(p, cv="encadrement supervision coach mentor formation des employés"), [lead["summary"]] + lead["evidence"][:8]))
    if not int(p.get("promotions") or 0):
        out.append(("promo", "Renseigner vos promotions dans la Career Memory (si vous en avez eu)", "Une promotion est une preuve externe de performance : elle compte dans le critère leadership.",
                    "Facile", "2 min", 0.05, _plus(p, promotions=1), ["Promotions renseignées : 0"]))
    if len(crit["skills"]["evidence"]) < 25:
        out.append(("skills", "Ajouter 3 compétences clés de votre domaine principal", "Plus vos compétences sont nommées explicitement, plus elles sont reconnues par les filtres ATS et par CareerOS.",
                    "Facile", "15 min", 0.25, _plus(p, skills=["Planification des effectifs", "Amélioration continue", "Gestion des stocks"]), [crit["skills"]["summary"]]))
    if crit["stability"]["summary"].startswith("Dates de postes non"):
        out.append(("dates", "Indiquer les dates (mois et année) de chaque poste", "Sans dates, CareerOS ne peut pas mesurer votre expérience ni la stabilité de votre parcours.",
                    "Facile", "10 min", 0.2, _plus(p, cv="2016-01 à 2019-12 2020-01 à ce jour"), ["Aucune période de poste détectée dans le CV"]))
    return out


def _roi(gain: float, hours: float) -> str:
    r = gain / max(hours, 0.05)
    return "Excellent" if r >= 2 else "Très bon" if r >= 0.5 else "Bon" if r >= 0.08 else "Modéré"


def levers(p: dict, res: dict) -> dict:
    corpus = _n(" ".join([p.get("cv_text") or "", p.get("achievements") or "", " ".join(p.get("skills_detected") or []), " ".join(p.get("skills") or []),
                          " ".join(p.get("certifications") or [])]))
    raw, items = res["raw"], []
    for lid, title, why, diff, effort, hours, sim, ev in _catalog(p, res, corpus):
        new = compute(sim)
        gain = round(new["raw"] - raw, 1)
        if gain >= 0.3:
            moved = [f"{c['label']} : {o['score']} → {c['score']}/{c['max']}" for c, o in zip(new["criteria"], res["criteria"]) if c["score"] != o["score"]]
            items.append({"id": lid, "title": title, "gain": gain, "why": why, "difficulty": diff, "effort": effort, "effort_hours": hours,
                          "roi": _roi(gain, hours), "evidence": [e for e in ev if e][:10], "impact": moved, "_sim": sim})
    items.sort(key=lambda x: -x["gain"])
    targets = sorted({t for t in (85, 90, 95) if t > raw} | ({min(100, (int(raw) // 5 + 1) * 5)} if raw < 85 else set()))
    steps, cur, used = [], p, []
    for t in targets:
        picked = []
        for it in items:
            if it["id"] in used:
                continue
            if compute(cur)["raw"] >= t:
                break
            cur = it["_sim"] if not used else _merge(cur, it["_sim"], p)
            used.append(it["id"])
            picked.append(it["id"])
        reach = compute(cur)["raw"]
        steps.append({"target": t, "levers": picked, "reachable": reach >= t, "reach": round(reach, 1)})
    for it in items:
        it.pop("_sim")
    return {"items": items, "top3": [it["id"] for it in items[:3]], "milestones": steps}


def _merge(cur: dict, sim: dict, base: dict) -> dict:
    """Cumulate a lever's additions (sim minus base) on top of the current simulated profile."""
    extra_cv = (sim.get("cv_text") or "")[len(base.get("cv_text") or ""):]
    return {**cur, "cv_text": (cur.get("cv_text") or "") + extra_cv,
            "skills": list(cur.get("skills") or []) + list(sim.get("skills") or [])[len(base.get("skills") or []):],
            "certifications": list(cur.get("certifications") or []) + list(sim.get("certifications") or [])[len(base.get("certifications") or []):],
            "promotions": int(cur.get("promotions") or 0) + int(sim.get("promotions") or 0) - int(base.get("promotions") or 0)}
