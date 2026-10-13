"""CareerOS Radar — deterministic pre-scoring (no AI). Compares Career Memory (CV, target roles, skills,
years, languages, location) with an offer and grades the 8 radar IPS criteria 0-10 with explanations.
The best offers of the day are then confirmed by AI; the rest stays rule-scored (free)."""
import re
import unicodedata
from datetime import datetime

SKILLS = [
    "sql", "python", "r", "excel", "power bi", "tableau", "looker", "sas", "spss", "vba", "dax", "power query", "etl", "dbt",
    "snowflake", "bigquery", "azure", "aws", "gcp", "databricks", "spark", "hadoop", "airflow", "git", "jira", "confluence",
    "sap", "oracle", "salesforce", "dynamics", "servicenow", "workday", "erp", "crm", "agile", "scrum", "kanban", "safe",
    "itil", "pmp", "lean", "six sigma", "uml", "bpmn", "api", "rest", "java", "javascript", "typescript", "c#", ".net",
    "html", "css", "react", "node", "docker", "kubernetes", "linux", "machine learning", "statistiques", "statistics",
    "modelisation", "modeling", "forecasting", "prevision", "budget", "comptabilite", "accounting", "finance", "audit",
    "conformite", "compliance", "risque", "risk", "kpi", "reporting", "tableaux de bord", "dashboards", "analyse de donnees",
    "data analysis", "visualisation", "data visualization", "gestion de projet", "project management", "change management",
    "gestion du changement", "processus", "process improvement", "amelioration continue", "continuous improvement",
    "logistique", "logistics", "supply chain", "chaine d'approvisionnement", "transport", "entrepot", "warehouse", "wms", "tms",
    "inventaire", "inventory", "approvisionnement", "procurement", "achats", "purchasing", "service a la clientele",
    "customer service", "ventes", "sales", "marketing", "communication", "ressources humaines", "human resources", "paie",
    "payroll", "recrutement", "recruiting", "formation", "training", "leadership", "gestion d'equipe", "team management",
    "negociation", "negotiation", "redaction", "writing", "exigences", "requirements", "analyse d'affaires", "business analysis",
    "cybersecurite", "cybersecurity", "reseau", "networking", "support technique", "technical support", "sante et securite",
    "health and safety", "permis de conduire", "chariot elevateur", "forklift", "cpa", "cfa", "pmi", "cbap", "ccba",
]
SYNONYMS = {
    "analyste": "analyst", "analyste d'affaires": "business analyst", "gestionnaire": "manager", "directeur": "director",
    "chef de projet": "project manager", "developpeur": "developer", "ingenieur": "engineer", "conseiller": "advisor",
    "coordonnateur": "coordinator", "coordinateur": "coordinator", "technicien": "technician", "adjoint": "assistant",
    "specialiste": "specialist", "agent": "agent", "comptable": "accountant", "superviseur": "supervisor", "donnees": "data",
    "affaires": "business", "logistique": "logistics", "approvisionnement": "supply", "ventes": "sales", "finances": "finance",
    "ressources humaines": "human resources", "service a la clientele": "customer service", "entrepot": "warehouse",
}
CERTS = ["pmp", "cpa", "cfa", "cbap", "ccba", "itil", "scrum master", "csm", "psm", "six sigma", "aws certified", "azure",
         "google certified", "cissp", "comptia", "prince2", "lean"]
SENIOR = re.compile(r"\b(senior|sr\.?|principal|lead|directeur|director|head|chef|vp|vice)\b")
JUNIOR = re.compile(r"\b(junior|jr\.?|stagiaire|intern|internship|stage|entry level|debutant|apprenti)\b")


def norm(t: str) -> str:
    t = unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"\s+", " ", t)


def _en(t: str) -> str:
    for fr, en in SYNONYMS.items():
        t = t.replace(fr, en)
    return t


def _words(t: str) -> set:
    return {w for w in re.findall(r"[a-z0-9#+.]{3,}", _en(norm(t))) if w not in {"and", "the", "des", "les", "pour", "avec", "une", "dans"}}


def skills_in(t: str) -> set:
    n = f" {norm(t)} "
    return {s for s in SKILLS if re.search(rf"(?<![a-z0-9]){re.escape(s)}(?![a-z0-9])", n)}


def cv_years(cv: str) -> int:
    n = norm(cv)
    m = [int(x) for x in re.findall(r"(\d{1,2})\s*\+?\s*(?:ans|annees|years?)\s+(?:d'|de |of )?(?:experience|exp)", n)]
    if m:
        return max(m)
    yrs = [int(y) for y in re.findall(r"\b(19[89]\d|20[0-3]\d)\b", n)]
    now = datetime.now().year
    return max(0, min(40, (min(now, max(yrs)) - min(yrs)))) if len(yrs) >= 2 else 0


def required_years(t: str) -> int:
    m = [int(x) for x in re.findall(r"(\d{1,2})\s*\+?\s*(?:a|-|to|à)?\s*\d{0,2}\s*(?:ans|annees|years?)\b", norm(t))]
    m = [x for x in m if 0 < x <= 20]
    return min(m) if m else 0


def _clip(x: float) -> int:
    return max(0, min(10, round(x)))


def _knockouts(offer_text: str, cv: str, profile: dict) -> list:
    o, c = norm(offer_text), norm(cv)
    out = []
    if re.search(r"bilingue|bilingual|french and english|francais et anglais", o) and not re.search(r"anglais|english|bilingue|bilingual", c):
        out.append("Bilinguisme exigé, anglais non mentionné dans le CV")
    if re.search(r"habilitation|security clearance|cote de securite|secret clearance", o) and not re.search(r"habilitation|clearance|cote de securite", c):
        out.append("Habilitation de sécurité exigée")
    if re.search(r"(must|doit) (be|etre) (a )?(us|american|u\.s\.) citizen|citoyennete americaine", o):
        out.append("Citoyenneté américaine exigée")
    for lic in ("permis de classe 1", "class 1 licen", "classe 1", "az licen", "dz licen"):
        if lic in o and lic not in c:
            out.append("Permis de conduire professionnel exigé")
            break
    for deg, pat in (("Doctorat exigé", r"(phd|doctorat) (required|requis|exige)"), ("Ingénieur (OIQ/PEng) exigé", r"\b(oiq|p\.? ?eng)\b")):
        if re.search(pat, o) and not re.search(pat.split(" ")[0], c):
            out.append(deg)
    return out


FOREIGN = re.compile(r"\b(india|bangalore|bengaluru|hyderabad|pune|united states|usa|u\.s\.|new york|california|texas|london|united kingdom|uk|"
                     r"germany|berlin|france|paris|spain|brazil|mexico|philippines|poland|ireland|dublin|singapore|japan|australia|netherlands|amsterdam)\b")
PROVINCES = {"quebec": r"quebec|qc|montreal|laval|gatineau|sherbrooke|levis|longueuil|trois-rivieres|saguenay",
             "ontario": r"ontario|\bon\b|toronto|ottawa|mississauga|hamilton|london, on|brampton|markham|st\. catharines",
             "alberta": r"alberta|\bab\b|calgary|edmonton", "british columbia": r"british columbia|\bbc\b|vancouver|victoria|burnaby"}
FAMILIES = [r"\bengineer\b", r"\bdeveloper\b", r"\bdeveloppeur", r"software", r"machine learning|\bml\b", r"scientist", r"accountant|comptable",
            r"nurse|infirmi", r"human resources|\bhr\b|\brh\b|payroll|\bpaie\b", r"recruiter|recruteur", r"mechanic|mecanicien", r"driver|chauffeur",
            r"electrician|electricien", r"lawyer|avocat|notaire", r"pharmac", r"cashier|caissier", r"cook|cuisinier"]


def _location_issue(offer: dict, profile: dict) -> tuple:
    loc = norm(f"{offer.get('location', '')}")
    remote = re.search(r"remote|teletravail|a distance|hybride|hybrid", norm(offer.get("location", "") + " " + offer.get("title", "")))
    if FOREIGN.search(loc) and not re.search(r"canada", loc):
        return "Poste situé hors du Canada", True
    home = norm(profile.get("location") or "quebec")
    mine = next((k for k, pat in PROVINCES.items() if re.search(pat, home)), None)
    theirs = next((k for k, pat in PROVINCES.items() if re.search(pat, loc)), None)
    if mine and theirs and mine != theirs and not remote:
        return f"Poste dans une autre province ({offer.get('location')})", False
    return "", False


def score_offer(offer: dict, cv: str, profile: dict, keywords: list = None) -> dict:
    """Return the same shape the AI produces: ips_criteria, knockout, goal_fit, reasons, decision_summary."""
    text = f"{offer.get('title', '')} {offer.get('description', '')}"
    title = offer.get("title", "")
    roles = [r for r in re.split(r"[,;/\n]", profile.get("target_roles") or "") if r.strip()] or list(keywords or [])
    goals = " ".join(profile.get("goals") or []) if isinstance(profile.get("goals"), list) else str(profile.get("goals") or "")
    extra = profile.get("skills") if isinstance(profile.get("skills"), list) else []
    cv_sk, off_sk = skills_in(cv + " " + " ".join(map(str, extra))), skills_in(text)
    common, missing = sorted(cv_sk & off_sk), sorted(off_sk - cv_sk)
    tw = _words(title)
    role_hit = max((len(tw & _words(r)) / max(1, len(_words(r))) for r in roles), default=0)
    cvw = _words(cv)
    overlap = len(_words(text) & cvw) / max(1, len(cvw))  # share of the CV vocabulary found in the offer
    have, need = cv_years(cv), required_years(text)
    ko = _knockouts(text, cv, profile)
    loc_msg, loc_ko = _location_issue(offer, profile)
    if loc_ko:
        ko.append(loc_msg)
    if need and have and need - have >= 4:
        ko.append(f"Expérience exigée ({need} ans) très supérieure à la vôtre ({have} ans)")
    t_en, cv_en, roles_en = _en(norm(title)), _en(norm(cv)), _en(norm(" ".join(roles)))
    fam = next((f for f in FAMILIES if re.search(f, t_en) and not re.search(f, cv_en) and not re.search(f, roles_en)), None)
    if fam:
        ko.append("Métier différent de votre parcours (" + offer.get("title", "")[:60] + ")")
    sk_ratio = min(1.0, len(common) / max(3, len(off_sk) * 0.5)) if off_sk else None
    short = len(offer.get("description") or "") < 600

    adequation = _clip(2 + role_hit * 4 + min(1.0, overlap * 2.5) * 4 - (2 if loc_msg and not loc_ko else 0))
    if len(off_sk) >= 6 and len(common) <= 1:
        ko.append("Compétences techniques clés de l'offre absentes du CV")
    if need and have:
        experience = _clip(10 - max(0, need - have) * 2.5) if have < need else _clip(8 + min(2, (have - need) / 3))
    else:
        experience = 5
    lvl = norm(title)
    if SENIOR.search(lvl) and have and have < 5:
        experience = min(experience, 4)
    if JUNIOR.search(lvl) and have >= 6:
        adequation = max(0, adequation - 2)
    competences = 5 if sk_ratio is None else _clip(3 + sk_ratio * 7)
    cv_len, cv_num = len(cv), len(re.findall(r"\d+\s*%|\$\s*\d|\d+\s*(?:k|m)\$", cv))
    qualite_cv = _clip(4 + min(3, cv_len / 2000) + min(3, cv_num))
    concurrence = 4 if re.search(r"amazon|google|desjardins|hydro|air canada|bombardier", norm(offer.get("company", ""))) else 6
    signaux = 6 if offer.get("salary") else 5
    certs_o = [c for c in CERTS if c in norm(text)]
    certifications = 5 if not certs_o else _clip(3 + 7 * len([c for c in certs_o if c in norm(cv)]) / len(certs_o))
    gf = _clip(3 + role_hit * 7) if roles else 5
    if goals and len(_words(goals) & tw):
        gf = min(10, gf + 1)

    j = "extrait de l'offre seulement — " if short else ""
    crit = {
        "adequation_profil": {"score": adequation, "justification": f"{j}Titre vs postes visés : {round(role_hit * 100)} % ; vocabulaire commun CV/offre : {round(overlap * 100)} %."},
        "experience": {"score": experience, "justification": f"Expérience estimée dans le CV : {have or 'non détectée'} an(s) ; exigée : {need or 'non précisée'}."},
        "competences": {"score": competences, "justification": (f"Compétences en commun : {', '.join(common[:8]) or 'aucune'} ; manquantes : {', '.join(missing[:6]) or 'aucune'}."
                                                                 if off_sk else f"{j}Aucune compétence identifiable dans l'offre : note neutre.")},
        "qualite_cv": {"score": qualite_cv, "justification": f"CV de {cv_len} caractères, {cv_num} résultat(s) chiffré(s)."},
        "concurrence": {"score": concurrence, "justification": "Employeur très attractif : concurrence probablement forte." if concurrence < 5 else "Concurrence estimée moyenne (règle par défaut)."},
        "signaux_marche": {"score": signaux, "justification": "Salaire affiché." if offer.get("salary") else "Aucun signal de marché particulier (note neutre)."},
        "certifications": {"score": certifications, "justification": f"Certifications demandées : {', '.join(certs_o)}." if certs_o else "Aucune certification demandée (note neutre)."},
    }
    reasons_apply = [x for x in (
        f"Correspond à vos postes visés ({round(role_hit * 100)} %)" if role_hit >= 0.5 else "",
        f"Compétences en commun : {', '.join(common[:4])}" if len(common) >= 2 else "",
        "Votre expérience couvre l'exigence" if need and have >= need else "") if x]
    reasons_avoid = [x for x in (
        *ko, f"Compétences manquantes : {', '.join(missing[:4])}" if len(missing) >= 3 else "",
        f"Expérience exigée ({need} ans) supérieure à la vôtre ({have} ans)" if need and have and have < need else "",
        "Titre éloigné de vos postes visés" if roles and role_hit < 0.25 else "") if x]
    return {
        "ips_criteria": crit,
        "knockout": {"present": bool(ko), "detail": " ; ".join(ko)},
        "goal_fit": {"score": gf},
        "reasons_apply": reasons_apply[:3], "reasons_avoid": reasons_avoid[:3],
        "decision_summary": ("Pré-analyse par règles CareerOS (sans IA) : correspondance entre votre Career Memory et l'offre. "
                             "Lancez l'analyse approfondie pour une évaluation IA."),
        "ats": {"keywords_missing": missing[:8]},
    }
