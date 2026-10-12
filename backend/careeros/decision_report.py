"""Mandatory Decision Report: every IPS / priority is ALWAYS shipped with its reasons
and the actions that would improve it. Deterministic (built from the IPS rows),
enriched by the AI's own summary/actions when available — never empty."""

import re

# Score-like numbers the AI might invent (they could contradict the official IPS).
_SCORE_RE = re.compile(
    r"(\d{1,3}\s*/\s*(100|10)\b|\bIPS\b[^.;:]{0,25}?\d|[~≈]\s*\d|[+-]\s*\d{1,3}\s*(pts?|points?)\b|\d{1,3}\s*(pts?|points?)\b"
    r"|\d{1,3}\s*%\s*(de\s+)?(chances?|probabilit))", re.IGNORECASE)


def _no_ai_numbers(text: str) -> str:
    """Drop every sentence of AI text that carries a score-like estimate."""
    parts = re.split(r"(?<=[.!?])\s+", (text or "").strip())
    return " ".join(p for p in parts if p and not _SCORE_RE.search(p)).strip()


def _impact_word(gain: float) -> str:
    return "Impact élevé" if gain >= 4 else "Impact moyen" if gain >= 2 else "Impact faible"


ACTION_TEMPLATES = {
    "adequation_profil": "Repositionner le résumé et les 3 premières expériences sur les responsabilités clés de l'offre",
    "experience": "Mettre en avant les expériences les plus proches du poste (intitulés, périmètre, durée)",
    "competences": "Ajouter les compétences exigées réellement maîtrisées, avec un exemple concret pour chacune",
    "qualite_cv": "Utiliser le CV ATS généré et chiffrer chaque réalisation",
    "concurrence": "Postuler tôt et viser une recommandation interne pour sortir du lot",
    "signaux_marche": "Mettre en avant les compétences les plus demandées du marché pour ce rôle",
    "certifications": "Obtenir ou mentionner une certification attendue (ou en cours)",
    "fraicheur_offre": "Postuler rapidement : les offres récentes ont un meilleur taux de réponse",
    "qualite_lettre": "Envoyer la lettre personnalisée générée par CareerOS",
    "force_reseau": "Trouver un contact dans l'entreprise (LinkedIn, anciens collègues) ou demander une recommandation",
}

PRIORITY_RULES = {
    "A": "Priorité A : IPS ≥ 70, aucune exigence éliminatoire, et poste compatible avec vos objectifs (≥ 6/10). Postulez en premier.",
    "B": "Priorité B : IPS entre 50 et 69 (ou ≥ 70 mais peu aligné avec vos objectifs). Postulez après avoir appliqué les actions ci-dessous.",
    "C": "Priorité C : IPS < 50 ou exigence éliminatoire. Évitez, ou postulez en dernier après avoir comblé les écarts.",
}


def build_decision_report(ips: dict, decision: dict) -> dict:
    decision = decision or {}
    rows = (ips or {}).get("criteria") or []
    by_ratio = sorted(rows, key=lambda r: r["score"], reverse=True)
    strengths = [r for r in by_ratio if r["score"] >= 7][:3] or by_ratio[:2]
    weaknesses = sorted(rows, key=lambda r: (r["score"], -r["weight"]))
    weaknesses = [r for r in weaknesses if r["score"] < 6][:3] or weaknesses[:2]
    priority = (ips or {}).get("priority", "C")
    score = (ips or {}).get("score", 0)

    why_priority = [PRIORITY_RULES[priority]]
    if (ips or {}).get("knockout"):
        why_priority.append(f"Exigence éliminatoire détectée : {ips.get('knockout_detail') or 'voir analyse'} — IPS plafonné à 40.")
    if priority == "B" and score >= 70:
        why_priority.append(f"Compatibilité avec vos objectifs insuffisante ({ips.get('goal_fit')}/10) pour une priorité A.")

    gains = sorted(
        ({"critere": r["label"], "key": r["key"], "action": ACTION_TEMPLATES.get(r["key"], ""),
          "gain_potentiel": round(r["weight"] * (10 - r["score"]) / 10, 1)} for r in rows if r["score"] < 8),
        key=lambda x: -x["gain_potentiel"])[:4]
    ai_actions = []
    for a in (decision.get("improvement_actions") or [])[:5]:
        if isinstance(a, dict) and _no_ai_numbers(a.get("action", "")):
            impact = a.get("impact_estime", "")
            ai_actions.append({"action": _no_ai_numbers(a["action"]), "critere": a.get("critere", ""),
                               "impact_estime": impact if impact and not _SCORE_RE.search(impact) else ""})
    missing = (decision.get("ats") or {}).get("keywords_missing") or []

    official = f"IPS officiel CareerOS : {score}/100 — priorité {priority}."
    ai_summary = _no_ai_numbers(decision.get("decision_summary", ""))
    summary = official + " " + (ai_summary or (
        f"Principal atout : {strengths[0]['label'].lower() if strengths else '—'}. "
        f"Principal frein : {weaknesses[0]['label'].lower() if weaknesses else '—'}."
    ))
    return {
        "summary": summary,
        "why_priority": why_priority,
        "strengths": [{"critere": r["label"], "raison": _no_ai_numbers(r["justification"]) or r["label"]} for r in strengths],
        "weaknesses": [{"critere": r["label"], "raison": _no_ai_numbers(r["justification"]) or r["label"]} for r in weaknesses],
        "actions": ai_actions or [{"action": g["action"], "critere": g["critere"], "impact_estime": _impact_word(g["gain_potentiel"])} for g in gains],
        "potential_gains": [{"critere": g["critere"], "key": g["key"], "action": g["action"], "impact": _impact_word(g["gain_potentiel"])} for g in gains],
        "keywords_to_add": missing[:8],
        "method": (ips or {}).get("formula", ""),
        "official_ips": score, "version": 2,
    }
