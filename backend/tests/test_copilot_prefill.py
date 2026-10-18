# Option C: GET /api/careeros/skill-match/copilot (memoire/pack/radar) + Option A: POST /api/careeros/radar/external used by QuickVerdict
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api/careeros/skill-match"
OFFER = ("Analyste TI senior TEST_QV\nNous recherchons un analyste TI pour soutenir nos systèmes ERP SAP, "
         "Power BI, SQL et la gestion de projets. 5 ans d'expérience requis. Bilinguisme français anglais. "
         "Le candidat travaillera avec les équipes opérationnelles à Montréal.")


def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    d = r.json()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {d.get('access_token') or d.get('token')}"})
    return s


@pytest.fixture(scope="module")
def m1():
    return _login("membre.test@careeros.dev", "CareerOS2026!")


@pytest.fixture(scope="module")
def m2():
    return _login("conseiller.test@careeros.dev", "Conseil2026!")


@pytest.fixture(scope="module")
def sources(m1):
    r = m1.get(f"{API}/sources")
    assert r.status_code == 200
    return r.json()


KEYS = {"title", "cv", "poste", "entreprise", "atsCv", "score", "missingKeywords", "gaps", "coverLetter"}


def test_copilot_requires_auth():
    assert requests.get(f"{API}/copilot?kind=memoire").status_code in (401, 403)


def test_copilot_invalid_kind(m1):
    assert m1.get(f"{API}/copilot?kind=foo").status_code == 422
    assert m1.get(f"{API}/copilot").status_code == 422


def test_copilot_memoire(m1):
    r = m1.get(f"{API}/copilot?kind=memoire")
    assert r.status_code == 200
    d = r.json()
    assert KEYS <= set(d)
    assert d["title"] == "Entrevue"
    assert isinstance(d["cv"], str) and len(d["cv"]) > 80
    assert d["poste"] == "" and d["atsCv"] == "" and d["score"] is None


def test_copilot_pack(m1, sources):
    if not sources.get("packs"):
        pytest.skip("no packs")
    pid = sources["packs"][0]["id"]
    r = m1.get(f"{API}/copilot", params={"kind": "pack", "id": pid})
    assert r.status_code == 200
    d = r.json()
    print("PACK", d["title"], d["score"], len(d["missingKeywords"]), len(d["gaps"]), len(d["atsCv"]), len(d["coverLetter"]))
    assert d["title"].startswith("Entrevue · ")
    assert len(d["poste"]) > 50 and len(d["cv"]) > 80
    assert isinstance(d["missingKeywords"], list) and isinstance(d["gaps"], list)
    assert isinstance(d["atsCv"], str) and isinstance(d["coverLetter"], str)


def test_copilot_all_packs_no_500(m1, sources):
    bad = []
    for p in sources.get("packs", []):
        r = m1.get(f"{API}/copilot", params={"kind": "pack", "id": p["id"]})
        if r.status_code != 200:
            bad.append((p["id"], r.status_code))
    assert not bad, bad


def test_copilot_radar(m1, sources):
    if not sources.get("radar"):
        pytest.skip("no radar offers")
    oid = sources["radar"][0]["id"]
    r = m1.get(f"{API}/copilot", params={"kind": "radar", "id": oid})
    assert r.status_code == 200
    d = r.json()
    print("RADAR", d["title"], d["score"], d["entreprise"])
    assert d["title"].startswith("Entrevue · ")
    assert d["atsCv"] == "" and d["coverLetter"] == ""
    assert len(d["poste"]) > 10


def test_copilot_404(m1):
    assert m1.get(f"{API}/copilot", params={"kind": "pack", "id": "nope"}).status_code == 404
    assert m1.get(f"{API}/copilot", params={"kind": "radar", "id": "nope"}).status_code == 404
    assert m1.get(f"{API}/copilot", params={"kind": "pack"}).status_code == 404


def test_copilot_id_too_long(m1):
    assert m1.get(f"{API}/copilot", params={"kind": "pack", "id": "x" * 81}).status_code == 422


def test_copilot_isolation(m2, sources):
    if not sources.get("packs"):
        pytest.skip("no packs")
    assert m2.get(f"{API}/copilot", params={"kind": "pack", "id": sources["packs"][0]["id"]}).status_code == 404
    if sources.get("radar"):
        assert m2.get(f"{API}/copilot", params={"kind": "radar", "id": sources["radar"][0]["id"]}).status_code == 404


def test_external_quick_verdict_shape(m1):
    r = m1.post(f"{BASE_URL}/api/careeros/radar/external", json={"text": OFFER, "url": "", "title": "", "company": "", "location": ""})
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["id"] and o["source"] == "externe"
    assert o["ips"] and o["ips"]["priority"] in ("A", "B", "C") and isinstance(o["ips"]["score"], (int, float))
    rep = o.get("decision_report") or {}
    assert isinstance(rep.get("reasons_apply", []), list)
    assert o["company"] == "Entreprise non précisée"
    assert "TEST_QV" in o["title"]
    # idempotent (dedupe) - same id on resubmit
    r2 = m1.post(f"{BASE_URL}/api/careeros/radar/external", json={"text": OFFER})
    assert r2.status_code == 200 and r2.json()["id"] == o["id"]


def test_external_short_text_422(m1):
    r = m1.post(f"{BASE_URL}/api/careeros/radar/external", json={"text": "trop court"})
    assert r.status_code == 422
