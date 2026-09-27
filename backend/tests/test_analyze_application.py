"""Backend tests for /api/analyze-application (new recruiter-grade analysis)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # fallback for local exec
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


@pytest.fixture(scope="module")
def analysis():
    """Call the endpoint once — LLM call can take 15-40s."""
    r = requests.post(
        f"{API}/analyze-application",
        json={"cv": SAMPLE_CV, "poste": SAMPLE_POSTE, "url": ""},
        timeout=90,
    )
    return r


def test_status_ok(analysis):
    assert analysis.status_code == 200, f"body={analysis.text[:500]}"


def test_response_shape(analysis):
    data = analysis.json()
    for k in ["ats_cv", "score", "gaps", "missing_keywords", "red_flags", "company"]:
        assert k in data, f"missing key {k}: keys={list(data.keys())}"


def test_ats_cv_non_empty(analysis):
    data = analysis.json()
    assert isinstance(data["ats_cv"], str)
    assert len(data["ats_cv"]) > 200, f"ATS CV too short: {len(data['ats_cv'])}"


def test_score_is_integer_0_100(analysis):
    data = analysis.json()
    score = data["score"]
    # Prompt asks for 0-100 integer; spec allows tolerance if LLM returns 4-tuple but ideally int.
    assert isinstance(score, (int, float)), f"score type={type(score)} val={score}"
    assert 0 <= float(score) <= 100, f"score out of range: {score}"


def test_missing_keywords_list(analysis):
    data = analysis.json()
    mk = data["missing_keywords"]
    assert isinstance(mk, list)
    # Prompt requires exactly 5 but per user "pas bloquant si l'IA renvoie 4"
    assert 3 <= len(mk) <= 7, f"missing_keywords count unexpected: {len(mk)}"


def test_gaps_and_red_flags_lists(analysis):
    data = analysis.json()
    assert isinstance(data["gaps"], list)
    assert isinstance(data["red_flags"], list)


def test_empty_cv_still_returns_structured():
    """Edge case: empty CV — endpoint should not 500."""
    r = requests.post(
        f"{API}/analyze-application",
        json={"cv": "", "poste": SAMPLE_POSTE, "url": ""},
        timeout=90,
    )
    # Accept 200 or 502 (illisible) but NOT 500
    assert r.status_code in (200, 502), f"unexpected status {r.status_code}: {r.text[:300]}"
