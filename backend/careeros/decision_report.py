"""Mandatory Decision Report: every IPS / priority is ALWAYS shipped with its reasons
and the actions that would improve it. Deterministic (built from the IPS rows),
enriched by the AI's own summary/actions when available — never empty."""

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
    ai_actions = [a for a in (decision.get("improvement_actions") or []) if isinstance(a, dict) and a.get("action")][:5]
    missing = (decision.get("ats") or {}).get("keywords_missing") or []

    summary = decision.get("decision_summary") or (
        f"IPS {score}/100 → priorité {priority}. Principal atout : {strengths[0]['label'].lower() if strengths else '—'}. "
        f"Principal frein : {weaknesses[0]['label'].lower() if weaknesses else '—'}."
    )
    return {
        "summary": summary,
        "why_priority": why_priority,
        "strengths": [{"critere": r["label"], "score": r["score"], "points": r["points"], "raison": r["justification"]} for r in strengths],
        "weaknesses": [{"critere": r["label"], "score": r["score"], "points": r["points"], "raison": r["justification"]} for r in weaknesses],
        "actions": ai_actions or [{"action": g["action"], "critere": g["critere"], "impact_estime": f"jusqu'à +{g['gain_potentiel']} pts IPS"} for g in gains],
        "potential_gains": gains,
        "keywords_to_add": missing[:8],
        "method": (ips or {}).get("formula", ""),
    }
