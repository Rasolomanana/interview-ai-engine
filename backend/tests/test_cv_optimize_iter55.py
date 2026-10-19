# Iteration 55 regression: one-paragraph CV candidates, stricter validator, simulate short/long keys.
import json
import os
import sys

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from careeros.cv_optimize import JobSkill, _candidates, invented  # noqa: E402

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
ONE = ("Jean Tremblay — Analyste de données, Montréal. 6 ans d'expérience. Desjardins (2020-2025) : tableaux de bord Power BI pour 40 directeurs, "
       "automatisation SQL/Python réduisant le reporting de 30 %. Banque Nationale (2018-2020) : analyste junior, modèles Excel de prévision. "
       "Compétences : SQL, Python, Power BI, Excel, gestion de parties prenantes. Formation : B.Sc. Statistique, Université de Montréal. Langues : français, anglais.")
MULTI = """Marc Gagnon
Superviseur de production — Montréal
EXPÉRIENCE
Olymel, Saint-Hyacinthe (2019 - aujourd'hui) : Superviseur de production
- Supervision d'une équipe de production.
- Responsable de la planification des quarts de 25 employés.
- Optimisation des processus de la ligne d'emballage, réduction des pertes de 12 %.
- Suivi des indicateurs de rendement quotidiens et des rapports.
- Participer aux enquêtes d'accident avec le comité SST.
Lassonde (2015 - 2019) : Chef d'équipe
- Aider à la formation des nouveaux employés.
COMPÉTENCES : Excel, SAP, travail d'équipe, communication"""
BI = [JobSkill(label="Power BI", aliases=["power bi"], status="ok"), JobSkill(label="SQL", aliases=["sql"], status="ok"),
      JobSkill(label="Tableaux de bord", aliases=["tableaux de bord", "tableau de bord"], status="ok"),
      JobSkill(label="KPI", aliases=["kpi", "indicateurs de performance"], status="manquant")]
SUP = [JobSkill(label="Gestion du personnel", aliases=["gestion du personnel", "supervision"], status="ok"),
       JobSkill(label="Tableaux de bord", aliases=["tableaux de bord"], status="manquant"),
       JobSkill(label="KPI", aliases=["kpi", "indicateurs de performance"], status="partiel", domain_keys=["indicateurs"])]


# _candidates: one-paragraph CV keeps relevant sentences, only the name/title sentence excluded
def test_one_paragraph_cv_has_candidates():
    c = _candidates(ONE, BI)
    texts = [l for _, l in c]
    print(texts)
    assert c, "no candidate sentence for a one-paragraph CV"
    assert not any(t.startswith("Jean Tremblay") for t in texts)
    assert any("Power BI" in t and "Desjardins" in t for t in texts)


def test_multi_line_cv_skips_name_title_dates():
    texts = [l for _, l in _candidates(MULTI, SUP)]
    assert "Marc Gagnon" not in texts and not any(t.startswith("Superviseur de production —") for t in texts)
    assert not any(t.startswith("Olymel") or t.startswith("Lassonde") for t in texts)
    assert any("Supervision" in t for t in texts)


# invented(): stricter validator
@pytest.mark.parametrize("after,before", [
    ("- Supervision quotidienne d'une équipe de production performante.", "- Supervision d'une équipe de production."),
    ("- Supervision d'une équipe de production et tableaux de bord.", "- Supervision d'une équipe de production."),
    ("- Supervision d'une équipe de production de 40 employés.", "- Supervision d'une équipe de production."),
    ("- Supervision d'une équipe de production dans l'agroalimentaire.", "- Supervision d'une équipe de production."),
    ("- Supervision d'une équipe de production en anglais courant.", "- Supervision d'une équipe de production."),
    ("- Supervision d'une équipe de production, certification Lean.", "- Supervision d'une équipe de production."),
])
def test_invented_rejects_new_facts(after, before):
    assert invented(after, before, MULTI, SUP), after


@pytest.mark.parametrize("after,before", [
    ("- Gestion du personnel : supervision d'une équipe de production.", "- Supervision d'une équipe de production."),
    ("- Suivi des indicateurs de performance (KPI) de rendement quotidiens et des rapports.", "- Suivi des indicateurs de rendement quotidiens et des rapports."),
    ("- Planification des quarts de 25 employés.", "- Responsable de la planification des quarts de 25 employés."),
])
def test_invented_accepts_rewording(after, before):
    assert invented(after, before, MULTI, SUP) == "", after


# simulate: long keys preserved up to 120 chars, short keys work
@pytest.fixture(scope="module")
def h():
    r = requests.post(f"{API}/auth/login", json={"email": "optcv.0e28a9@careeros.dev", "password": "Optim2026!x"}, timeout=20)
    if r.status_code != 200:
        pytest.skip("login failed")
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_simulate_short_and_long_keys(h):
    long_k = "c:Diplôme d'études collégiales (DEC) en gestion industrielle ou domaine connexe"
    r = requests.post(f"{API}/careeros/cv-optimize/simulate", headers=h, json={"variants": {"base": MULTI, "i0": MULTI + "\nExcel", long_k: MULTI}}, timeout=20)
    assert r.status_code == 200
    d = r.json()
    assert {"base", "i0", long_k} <= set(d), list(d)
    assert isinstance(d["base"]["score"], (int, float)) and d["base"]["criteria"]


def test_simulate_too_many_variants(h):
    r = requests.post(f"{API}/careeros/cv-optimize/simulate", headers=h, json={"variants": {f"i{k}": MULTI for k in range(41)}}, timeout=20)
    assert r.status_code == 400
