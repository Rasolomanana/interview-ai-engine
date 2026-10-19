# CV optimisation (iteration 53): auth, validation, member isolation for versions/real, simulate limits, validator gaps.
import os
import uuid

import pytest
import requests

from careeros.cv_optimize import invented

API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
CV = """Marc Gagnon
Olymel (2019 - aujourd'hui) : Superviseur de production
- Supervision d'une équipe de production.
- Responsable de la planification des quarts de 25 employés.
Lassonde (2015 - 2019) : Chef d'équipe
COMPÉTENCES : Excel, SAP, français, anglais"""


def _member(cv=CV):
    em = f"TEST_cvopt.{uuid.uuid4().hex[:8]}@careeros.dev".lower()
    t = requests.post(f"{API}/auth/register", json={"email": em, "password": "Optim2026!x", "name": "T"}, timeout=20).json()
    h = {"Authorization": "Bearer " + (t.get("access_token") or t["tokens"]["access_token"])}
    if cv:
        assert requests.put(f"{API}/careeros/profile", headers=h, json={"cv_text": cv}, timeout=20).status_code == 200
    return h


@pytest.fixture(scope="module")
def two():
    return _member(), _member()


# Auth required on every endpoint
@pytest.mark.parametrize("method,path", [("post", "/propose"), ("post", "/simulate"), ("post", "/apply"), ("get", "/versions"), ("post", "/versions/x/restore"), ("post", "/versions/x/real")])
def test_auth_required(method, path):
    r = getattr(requests, method)(f"{API}/careeros/cv-optimize{path}", json={}, timeout=20)
    assert r.status_code in (401, 403)


def test_apply_validation(two):
    h, _ = two
    assert requests.post(f"{API}/careeros/cv-optimize/apply", headers=h, json={"cv_text": "court"}, timeout=20).status_code == 422


def test_simulate_variant_limit(two):
    h, _ = two
    r = requests.post(f"{API}/careeros/cv-optimize/simulate", headers=h, json={"variants": {str(i): CV for i in range(41)}}, timeout=30)
    assert r.status_code == 400


def test_simulate_shape(two):
    h, _ = two
    s = requests.post(f"{API}/careeros/cv-optimize/simulate", headers=h, json={"variants": {"base": CV}}, timeout=20).json()
    assert isinstance(s["base"]["score"], (int, float)) and isinstance(s["base"]["criteria"], dict) and s["base"]["labels"]


def test_versions_and_real_isolation(two):
    h, other = two
    v = requests.post(f"{API}/careeros/cv-optimize/apply", headers=h, json={"cv_text": CV + "\n- Ligne ajoutée test.", "offer": {"title": "TEST_offre"}}, timeout=20).json()
    assert all(x["id"] != v["id"] for x in requests.get(f"{API}/careeros/cv-optimize/versions", headers=other, timeout=20).json()["items"])
    assert requests.post(f"{API}/careeros/cv-optimize/versions/{v['id']}/real", headers=other, json={"match_after": 50}, timeout=20).status_code == 404
    assert requests.post(f"{API}/careeros/cv-optimize/versions/{v['id']}/real", headers=h, json={"match_after": 150}, timeout=20).status_code == 422
    mine = requests.get(f"{API}/careeros/cv-optimize/versions", headers=h, timeout=20).json()["items"]
    assert mine[0]["id"] == v["id"] and "_id" not in mine[0] and "user_id" not in mine[0]


# Known validator gaps observed with real AI output (report only): new sector / language level / added activities pass the validator.
def test_validator_sector_invention():
    b = "Lassonde (2015 - 2019) : Chef d'équipe"
    assert invented("Lassonde, secteur jus et boissons (2015 – 2019) : Chef d'équipe — Production agroalimentaire", b, CV, []) != ""


def test_validator_language_level_invention():
    b = "COMPÉTENCES : Excel, SAP, français, anglais"
    assert invented("COMPÉTENCES : Excel, SAP, bilinguisme professionnel français / anglais", b, CV, []) != ""


def test_validator_rejects_reported_inventions():
    b = "- Participer aux enquêtes d'accident avec le comité SST."
    for after in ["- Participer aux enquêtes d'accident avec le comité SST, analyses de causes et mesures préventives.",
                  "- Participer aux enquêtes d'accident avec le comité SST dans le respect des standards de qualité.",
                  "- Participer aux enquêtes d'accident avec le comité SST et obligations réglementaires."]:
        assert invented(after, b, CV, []) != "", after


def test_validator_rejects_line_swap():
    assert "origine" in invented("- Supervision des quarts de production.", "- Aider à la formation des nouveaux employés.", CV, [])


# Iteration 54: simulate must return every variant key the UI sends (ids like "c:<skill label>" can exceed 40 chars)
def test_simulate_keeps_long_variant_keys(two):
    k = "c:Diplôme d'études collégiales / universitaires"
    r = requests.post(f"{API}/careeros/cv-optimize/simulate", headers=two[0], json={"variants": {"base": CV, k: CV}}, timeout=20).json()
    assert k in r, list(r)


# Iteration 54: a CV pasted as one paragraph (> 320 chars, single line) must still yield candidate sentences
def test_candidates_single_paragraph_cv():
    from careeros.cv_optimize import _candidates
    cv = ("Jean Tremblay — Analyste de données, Montréal. Responsable de la production des rapports mensuels pour la direction. "
          "Participer aux réunions de suivi des projets avec les équipes. Aider les utilisateurs avec les tableaux de bord Excel. "
          "Compétences : SQL, Python, Excel. Formation : B.Sc. Statistique. Langues : français, anglais. Gestion des demandes des clients internes.")
    assert _candidates(cv, []), "single-line CV gives no candidate"


# Iteration 54: generic-prefix whitelist lets new activities/purposes through (observed in real AI output)
@pytest.mark.parametrize("after", ["- Superviser une équipe de production en assurant la coordination quotidienne des opérations.",
                                   "- Supervision d'une équipe de production dans le respect des objectifs de conformité.",
                                   "- Supervision d'une équipe de production et gestion des processus opérationnels."])
def test_validator_generic_loophole(after):
    assert invented(after, "- Supervision d'une équipe de production.", CV, []) != ""
