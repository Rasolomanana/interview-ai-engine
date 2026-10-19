"""CareerOS proprietary IPS (Interview Probability Score) — transparent formula.

The AI only grades criteria (0-10). The score and A/B/C priority are computed here,
deterministically, so the same inputs always give the same, explainable result."""
from datetime import date, datetime

WEIGHTS = {
    "adequation_profil": 20,
    "experience": 15,
    "competences": 15,
    "qualite_cv": 10,
    "concurrence": 10,
    "signaux_marche": 10,
    "certifications": 5,
    "fraicheur_offre": 5,
    "qualite_lettre": 5,
    "force_reseau": 5,
}
LABELS = {
    "adequation_profil": "Adéquation du profil",
    "experience": "Expérience",
    "competences": "Compétences",
    "qualite_cv": "Qualité du CV",
    "concurrence": "Concurrence (10 = faible)",
    "signaux_marche": "Signaux du marché",
    "certifications": "Certifications",
    "fraicheur_offre": "Fraîcheur de l'offre",
    "qualite_lettre": "Qualité de la lettre",
    "force_reseau": "Force du réseau",
}
NETWORK_SCORES = {"aucun": (2, "Aucun contact dans l'entreprise"), "contact": (6, "Un contact dans l'entreprise"), "recommandation": (10, "Recommandation interne")}
KNOCKOUT_CAP = 40
RADAR_EXCLUDED = ("qualite_lettre", "force_reseau")  # unknown before the member applies: evaluated in the pack
FORMULA_PACK = ("IPS = Σ (poids × note/10) ; plafonné à 40 si exigence éliminatoire. "
                "Priorité A : IPS ≥ 70 et objectifs ≥ 6/10 ; B : IPS ≥ 50 ; C : sinon.")
FORMULA_RADAR = ("IPS Radar = Σ (poids × note/10) sur les 8 critères évaluables avant candidature (90 points), ramené sur 100 ; "
                 "lettre et réseau sont évalués dans le pack. Plafonné à 40 si exigence éliminatoire. "
                 "Priorité A : IPS ≥ 70 et objectifs ≥ 6/10 ; B : IPS ≥ 50 ; C : sinon.")


def _clamp(v):
    try:
        return max(0.0, min(10.0, float(v)))
    except (TypeError, ValueError):
        return None


def freshness(posted_date: str):
    if not posted_date:
        return 5, "Date de publication inconnue (valeur neutre)"
    try:
        d = datetime.fromisoformat(posted_date[:10]).date()
    except ValueError:
        return 5, "Date de publication illisible (valeur neutre)"
    days = (date.today() - d).days
    score = 10 if days <= 3 else 8 if days <= 7 else 6 if days <= 14 else 4 if days <= 30 else 2
    return score, f"Publiée il y a {max(days, 0)} jour(s)"


def compute_ips(ai_criteria: dict, knockout: dict, goal_fit: dict, posted_date: str, network: str, letter_ready: bool, stage: str = "pack"):
    ai_criteria = ai_criteria or {}
    rows = []
    for key, weight in WEIGHTS.items():
        if stage == "radar" and key in RADAR_EXCLUDED:
            continue
        source, just = "ia", ""
        if key == "fraicheur_offre":
            score, just = freshness(posted_date)
            source = "formule"
        elif key == "force_reseau":
            score, just = NETWORK_SCORES.get(network or "aucun", NETWORK_SCORES["aucun"])
            source = "membre"
        elif key == "qualite_lettre":
            score, just = (8, "Lettre sur mesure générée par CareerOS") if letter_ready else (5, "Lettre non disponible (valeur neutre)")
            source = "formule"
        else:
            c = ai_criteria.get(key) or {}
            score = _clamp(c.get("score"))
            just = c.get("justification", "")
            if score is None:
                score, just, source = 5, "Non évalué (valeur neutre)", "neutre"
        rows.append({"key": key, "label": LABELS[key], "weight": weight, "score": round(score, 1),
                     "points": round(weight * score / 10, 1), "justification": just, "source": source})
    ips = round(sum(r["points"] for r in rows) * 100 / sum(r["weight"] for r in rows))
    ko = bool((knockout or {}).get("present"))
    if ko:
        ips = min(ips, KNOCKOUT_CAP)
    gf = _clamp((goal_fit or {}).get("score"))
    gf = 5 if gf is None else gf
    if ips >= 70 and gf >= 6 and not ko:
        priority = "A"
    elif ips >= 50 and not ko:
        priority = "B"
    else:
        priority = "C"
    return {
        "score": ips, "priority": priority, "criteria": rows,
        "knockout": ko, "knockout_detail": (knockout or {}).get("detail", ""),
        "goal_fit": gf, "stage": stage,
        "formula": FORMULA_RADAR if stage == "radar" else FORMULA_PACK,
    }
