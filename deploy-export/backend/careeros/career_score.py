"""CareerOS Career Score (0-100): global career health — strategy quality, profile
quality, progression and results. NOT a volume counter: 200 poor applications must
score below 20 targeted ones that produce 5 interviews."""

WEIGHTS = {"memoire": 20, "ips_moyen": 25, "activite": 15, "resultats": 25, "developpement": 15}
LABELS = {"memoire": "Career Memory", "ips_moyen": "IPS moyen des candidatures", "activite": "Qualité de l'activité carrière",
          "resultats": "Résultats obtenus", "developpement": "Développement du profil"}
LEVELS = [(90, "Profil d'élite"), (80, "Très compétitif"), (60, "Compétitif"), (40, "En développement"), (0, "À renforcer")]
APPLIED = {"postule", "entrevue", "offre", "refuse"}
MEMORY_FIELDS = ["cv_text", "headline", "location", "goals", "target_roles", "sectors", "salary_expectation", "achievements"]


def level_for(score: float) -> str:
    return next(label for floor, label in LEVELS if score >= floor)


def _filled(v):
    return bool(v.strip()) if isinstance(v, str) else bool(v)


def _memoire(p):
    done = [f for f in MEMORY_FIELDS if _filled(p.get(f))]
    missing = [f for f in MEMORY_FIELDS if f not in done]
    return len(done) / len(MEMORY_FIELDS), f"{len(done)}/{len(MEMORY_FIELDS)} rubriques complétées", (
        [f"Compléter la Career Memory : {', '.join(missing)}"] if missing else [])


def _ips_moyen(apps):
    applied = [a for a in apps if a.get("pipeline_status") in APPLIED and a.get("ips") is not None]
    pool = applied or [a for a in apps if a.get("ips") is not None]
    if not pool:
        return 0.0, "Aucune candidature analysée", ["Générer un premier pack candidature"]
    avg = sum(a["ips"] for a in pool) / len(pool)
    return avg / 100, f"IPS moyen {avg:.0f}/100 sur {len(pool)} candidature(s){' envoyées' if applied else ''}", (
        ["Cibler davantage d'offres de priorité A et appliquer les actions des Decision Reports"] if avg < 70 else [])


def _activite(apps):
    applied = [a for a in apps if a.get("pipeline_status") in APPLIED]
    if not applied:
        return 0.0, "Aucune candidature envoyée", ["Postuler aux opportunités de priorité A"]
    n = len(applied)
    targeted = sum(1 for a in applied if a.get("priority") in ("A", "B")) / n
    poor = sum(1 for a in applied if a.get("priority") == "C") / n
    regularity = min(n, 10) / 10  # saturates: volume beyond 10 adds nothing
    v = max(0.0, 0.3 * regularity + 0.7 * targeted - 0.4 * poor)
    acts = ["Éviter les candidatures de priorité C (elles dégradent ce score)"] if poor > 0.2 else []
    return min(v, 1.0), f"{n} envoyée(s), {targeted:.0%} ciblées (A/B), {poor:.0%} de priorité C", acts


def _resultats(apps, p):
    applied = [a for a in apps if a.get("pipeline_status") in APPLIED]
    n = len(applied)
    interviews = sum(1 for a in applied if a.get("pipeline_status") in ("entrevue", "offre") or a.get("had_interview"))
    offers = sum(1 for a in applied if a.get("pipeline_status") == "offre")
    promos = int(p.get("promotions") or 0)
    i_rate = interviews / n if n else 0
    o_rate = offers / n if n else 0
    v = 0.55 * min(i_rate / 0.25, 1) + 0.35 * min(o_rate / 0.10, 1) + 0.10 * min(promos, 1)
    acts = []
    if n and i_rate < 0.15:
        acts.append("Taux d'entrevue faible : prioriser la qualité (CV ATS + lettre + réseau) plutôt que le volume")
    if interviews and not offers:
        acts.append("Préparer les entrevues avec les réponses STAR et la simulation recruteur")
    return min(v, 1.0), f"{interviews} entrevue(s), {offers} offre(s) sur {n} candidature(s) ; {promos} promotion(s)", acts


def _developpement(p):
    skills = len(set((p.get("skills") or []) + (p.get("skills_detected") or [])))
    certs, edu, langs = len(p.get("certifications") or []), len(p.get("education") or []), len(p.get("languages") or [])
    v = 0.35 * min(skills / 12, 1) + 0.25 * min(certs / 3, 1) + 0.2 * min(edu / 1, 1) + 0.2 * min(langs / 2, 1)
    acts = []
    if certs < 1:
        acts.append("Ajouter ou obtenir une certification reconnue dans votre domaine")
    if skills < 8:
        acts.append("Documenter davantage de compétences dans la Career Memory")
    return v, f"{skills} compétences, {certs} certification(s), {edu} formation(s), {langs} langue(s)", acts


def compute_career_score(profile: dict, apps: list) -> dict:
    p = profile or {}
    parts = {
        "memoire": _memoire(p), "ips_moyen": _ips_moyen(apps), "activite": _activite(apps),
        "resultats": _resultats(apps, p), "developpement": _developpement(p),
    }
    comps = [{"key": k, "label": LABELS[k], "weight": WEIGHTS[k], "ratio": round(v, 3),
              "points": round(WEIGHTS[k] * v, 1), "raison": why, "actions": acts}
             for k, (v, why, acts) in parts.items()]
    score = round(sum(c["points"] for c in comps))
    weakest = sorted(comps, key=lambda c: c["ratio"])[:2]
    return {
        "score": score, "level": level_for(score), "components": comps,
        "explanation": f"Career Score {score}/100 ({level_for(score)}). Points faibles : " + ", ".join(c["label"].lower() for c in weakest) + ".",
        "actions": [a for c in weakest for a in c["actions"]][:4],
        "formula": "Σ poids × ratio : Career Memory 20, IPS moyen 25, qualité de l'activité 15, résultats 25, développement 15. "
                   "Niveaux : 0-39 À renforcer · 40-59 En développement · 60-79 Compétitif · 80-89 Très compétitif · 90-100 Profil d'élite.",
    }
