# CV optimisation: no-invention validator, candidate selection, simulate/apply/versions/restore endpoints (no AI call needed).
import os
import uuid

import requests

from careeros.cv_optimize import JobSkill, _candidates, invented

API = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/") + "/api"
CV = """Marc Gagnon
Olymel (2019 - aujourd'hui) : Superviseur de production
- Supervision d'une équipe de production.
- Responsable de la planification des quarts de 25 employés.
- Optimisation des processus de la ligne d'emballage, réduction des pertes de 12 %.
COMPÉTENCES : Excel, SAP"""
SK = [JobSkill(label="Indicateurs de performance (KPI)", aliases=["kpi", "indicateurs"], status="partiel", domain_keys=["production", "planif", "performance"]),
      JobSkill(label="Lean Six Sigma", aliases=["lean", "six sigma"], status="manquant", domain_keys=[])]


def test_validator_rejects_inventions():
    b = "- Supervision d'une équipe de production."
    assert invented("- Supervision d'une équipe de production de 25 employés.", b, CV, SK) == ""  # 25 is in the CV
    assert "chiffre" in invented("- Supervision d'une équipe de 40 employés.", b, CV, SK)
    assert "années" in invented("- 12 ans d'expérience en supervision de production.", b, CV, SK)
    assert "intitulé" in invented("- Directeur de la production.", b, CV, SK)
    assert "certification" in invented("- Supervision d'une équipe de production, certifié PMP.", b, CV, SK)
    assert "lean" in invented("- Supervision d'une équipe de production selon le Lean.", b, CV, SK).lower()
    assert invented("- Supervision d'une équipe de production et suivi des KPI.", b, CV, SK) == ""  # partial skill proven by the line (production)


def test_candidates_split_long_lines():
    long = "Résumé : " + " ".join(["Responsable de la coordination des équipes de production et des horaires."] * 6)
    c = _candidates(CV + "\n" + long, SK)
    assert c and all(len(line) <= 320 for _, line in c)


def _member():
    em = f"cvopt.{uuid.uuid4().hex[:8]}@careeros.dev"
    t = requests.post(f"{API}/auth/register", json={"email": em, "password": "Optim2026!x", "name": "T"}, timeout=20).json()
    h = {"Authorization": "Bearer " + (t.get("access_token") or t["tokens"]["access_token"])}
    assert requests.put(f"{API}/careeros/profile", headers=h, json={"cv_text": CV}, timeout=20).status_code == 200
    return h


def test_simulate_apply_versions_restore():
    h = _member()
    s = requests.post(f"{API}/careeros/cv-optimize/simulate", headers=h, json={"variants": {"base": CV, "x": CV + "\n- Encadrement et coaching de l'équipe."}}, timeout=20).json()
    assert s["x"]["criteria"]["leadership"] >= s["base"]["criteria"]["leadership"]
    new = CV.replace("- Supervision d'une équipe de production.", "- Supervision d'une équipe de production de 25 employés.")
    v = requests.post(f"{API}/careeros/cv-optimize/apply", headers=h, json={"cv_text": new, "offer": {"title": "Superviseur", "kind": "texte"}, "accepted": ["r2-0"],
                                                                         "estimated": {"match_before": 60, "match_after": 70, "ifp_before": 50, "ifp_after": 52}}, timeout=20).json()
    assert v["real"]["ifp_after"] >= v["real"]["ifp_before"]
    assert requests.get(f"{API}/careeros/profile", headers=h, timeout=20).json()["cv_text"] == new
    assert requests.post(f"{API}/careeros/cv-optimize/versions/{v['id']}/real", headers=h, json={"match_after": 71}, timeout=20).status_code == 200
    items = requests.get(f"{API}/careeros/cv-optimize/versions", headers=h, timeout=20).json()["items"]
    assert items[0]["cv_before"] == CV and items[0]["cv_after"] == new and items[0]["real"]["match_after"] == 71 and items[0]["estimated"]["match_after"] == 70
    assert requests.post(f"{API}/careeros/cv-optimize/versions/{v['id']}/restore", headers=h, timeout=20).status_code == 200
    assert requests.get(f"{API}/careeros/profile", headers=h, timeout=20).json()["cv_text"] == CV
    assert requests.get(f"{API}/careeros/cv-optimize/versions", headers=h, timeout=20).json()["items"][0]["kind"] == "restauration"


def test_isolation_and_empty_cv():
    h, other = _member(), _member()
    v = requests.post(f"{API}/careeros/cv-optimize/apply", headers=h, json={"cv_text": CV + "\nx", "offer": {}}, timeout=20).json()
    assert requests.post(f"{API}/careeros/cv-optimize/versions/{v['id']}/restore", headers=other, timeout=20).status_code == 404
    em = f"cvopt.{uuid.uuid4().hex[:8]}@careeros.dev"
    t = requests.post(f"{API}/auth/register", json={"email": em, "password": "Optim2026!x"}, timeout=20).json()
    e = {"Authorization": "Bearer " + (t.get("access_token") or t["tokens"]["access_token"])}
    r = requests.post(f"{API}/careeros/cv-optimize/propose", headers=e, json={"title": "x", "skills": []}, timeout=20)
    assert r.status_code == 400 and "CV maître" in r.json()["detail"]
