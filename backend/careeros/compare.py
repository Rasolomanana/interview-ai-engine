"""Deterministic comparison of two versions of the same application."""


def _set(x):
    return {s.strip().lower(): s for s in (x or []) if isinstance(s, str)}


def compare_versions(a: dict, b: dict) -> dict:
    ia, ib = a.get("ips") or {}, b.get("ips") or {}
    ra = {r["key"]: r for r in ia.get("criteria") or []}
    rb = {r["key"]: r for r in ib.get("criteria") or []}
    deltas = []
    for k, r in rb.items():
        old = ra.get(k)
        if not old:
            continue
        d = round(r["points"] - old["points"], 1)
        if d:
            deltas.append({"critere": r["label"], "avant": old["score"], "apres": r["score"], "delta_points": d,
                           "raison_avant": old.get("justification", ""), "raison_apres": r.get("justification", "")})
    deltas.sort(key=lambda x: -abs(x["delta_points"]))
    ina, inb = a.get("inputs") or {}, b.get("inputs") or {}
    input_changes = []
    for key, label in [("cv_text", "CV"), ("offer_text", "Offre"), ("offer_url", "Lien de l'offre"), ("company_url", "Site entreprise"),
                       ("posted_date", "Date de publication"), ("network", "Réseau")]:
        if (ina.get(key) or "") != (inb.get(key) or ""):
            if key in ("cv_text", "offer_text"):
                input_changes.append(f"{label} modifié ({len(ina.get(key) or '')} → {len(inb.get(key) or '')} caractères)")
            else:
                input_changes.append(f"{label} : « {ina.get(key) or '—'} » → « {inb.get(key) or '—'} »")
    pa, pb = (a.get("profile_snapshot") or {}), (b.get("profile_snapshot") or {})
    for key, label in [("certifications", "Certifications"), ("skills", "Compétences"), ("goals", "Objectifs")]:
        added = sorted(set(pb.get(key) or []) - set(pa.get(key) or []))
        if added:
            input_changes.append(f"{label} — ajout(s) dans la Career Memory : {', '.join(added)}")
    ma = _set(((a.get("parts") or {}).get("decision") or {}).get("ats", {}).get("keywords_missing"))
    mb = _set(((b.get("parts") or {}).get("decision") or {}).get("ats", {}).get("keywords_missing"))
    ats_a = (((a.get("parts") or {}).get("decision") or {}).get("ats") or {}).get("score")
    ats_b = (((b.get("parts") or {}).get("decision") or {}).get("ats") or {}).get("score")
    delta = (ib.get("score") or 0) - (ia.get("score") or 0)
    trend = "amélioration" if delta > 0 else "dégradation" if delta < 0 else "stable"
    improved = [d for d in deltas if d["delta_points"] > 0]
    worsened = [d for d in deltas if d["delta_points"] < 0]
    return {
        "from_version": a.get("version"), "to_version": b.get("version"),
        "ips": {"avant": ia.get("score"), "apres": ib.get("score"), "delta": delta, "tendance": trend},
        "priority": {"avant": ia.get("priority"), "apres": ib.get("priority")},
        "ats": {"avant": ats_a, "apres": ats_b},
        "input_changes": input_changes or ["Aucune donnée d'entrée modifiée (variation due à la réévaluation IA)"],
        "improved": improved, "worsened": worsened,
        "keywords_now_covered": [mb_v for k, mb_v in ma.items() if k not in mb],
        "keywords_newly_missing": [v for k, v in mb.items() if k not in ma],
        "explanation": (
            f"IPS {ia.get('score')} → {ib.get('score')} ({'+' if delta > 0 else ''}{delta}, {trend}). "
            + (f"Principal gain : {improved[0]['critere']} (+{improved[0]['delta_points']} pts). " if improved else "")
            + (f"Principale perte : {worsened[0]['critere']} ({worsened[0]['delta_points']} pts)." if worsened else "")
        ).strip(),
    }
