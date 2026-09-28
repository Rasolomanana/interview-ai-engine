"""Backend tests for /api/analyze-application (recruiter-grade analysis).

The endpoint uses a job + polling model: POST starts a background job and
returns {job_id, status}; GET /analyze-application/{job_id} is polled until
status is 'done' (result) or 'error'. This keeps requests short so corporate
proxies / gateways never truncate a 40s analysis.
"""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")

API = f"{BASE_URL}/api"

SAMPLE_CV = (
    "Jean Dupont — Superviseur logistique\n"
    "Expérience: 8 ans en supervision d'équipes (Intelcom, Pratt & Whitney).\n"
    "Compétences: gestion d'équipe, KPI, lean, sécurité, Excel, WMS.\n"
    "Formation: DEC en gestion des opérations."
)
SAMPLE_POSTE = (
    "Superviseur de production - aéronautique. Missions: encadrer 20 opérateurs, "
    "assurer la sécurité, respecter les délais, améliorer les KPI, appliquer le lean 5S. "
    "Exigences: 5+ ans en supervision, connaissance SAP, anglais fonctionnel."
)


def _run_job(cv, poste, url="", timeout=120):
    """Start a job and poll until it finishes. Returns (status, result, error)."""
    r = requests.post(
        f"{API}/analyze-application",
        json={"cv": cv, "poste": poste, "url": url},
        timeout=30,
    )
    assert r.status_code == 200, f"start failed: {r.status_code} {r.text[:300]}"
    job_id = r.json().get("job_id")
    assert job_id, f"no job_id: {r.text[:300]}"
    deadline = time.time() + timeout
    while time.time() < deadline:
        time.sleep(2)
        p = requests.get(f"{API}/analyze-application/{job_id}", timeout=30)
        assert p.status_code == 200, f"poll failed: {p.status_code} {p.text[:300]}"
        body = p.json()
        if body["status"] in ("done", "error"):
            return body["status"], body.get("result"), body.get("error")
    pytest.fail("analysis job timed out")


@pytest.fixture(scope="module")
def result():
    status, res, err = _run_job(SAMPLE_CV, SAMPLE_POSTE)
    assert status == "done", f"job errored: {err}"
    return res


def test_start_returns_job_id():
    r = requests.post(
        f"{API}/analyze-application",
        json={"cv": SAMPLE_CV, "poste": SAMPLE_POSTE, "url": ""},
        timeout=30,
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("job_id")
    assert body.get("status") == "pending"


def test_unknown_job_id_404():
    r = requests.get(f"{API}/analyze-application/does-not-exist-123", timeout=30)
    assert r.status_code == 404


def test_response_shape(result):
    for k in ["ats_cv", "score", "gaps", "missing_keywords", "red_flags", "company"]:
        assert k in result, f"missing key {k}: keys={list(result.keys())}"


def test_ats_cv_non_empty(result):
    assert isinstance(result["ats_cv"], str)
    assert len(result["ats_cv"]) > 200, f"ATS CV too short: {len(result['ats_cv'])}"


def test_score_is_integer_0_100(result):
    score = result["score"]
    assert isinstance(score, (int, float)), f"score type={type(score)} val={score}"
    assert 0 <= float(score) <= 100, f"score out of range: {score}"


def test_missing_keywords_list(result):
    mk = result["missing_keywords"]
    assert isinstance(mk, list)
    assert 3 <= len(mk) <= 7, f"missing_keywords count unexpected: {len(mk)}"


def test_gaps_and_red_flags_lists(result):
    assert isinstance(result["gaps"], list)
    assert isinstance(result["red_flags"], list)


def test_empty_cv_still_completes():
    """Edge case: empty CV — the job must finish (done or error), never crash."""
    status, res, err = _run_job("", SAMPLE_POSTE)
    assert status in ("done", "error"), f"unexpected status {status}"
