# Skill match (CV vs job comparison): sources, source, history CRUD + validation + isolation
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api/careeros/skill-match"


def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw})
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    d = r.json()
    tok = d.get("access_token") or d.get("token")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def m1():
    return _login("membre.test@careeros.dev", "CareerOS2026!")


@pytest.fixture(scope="module")
def m2():
    return _login("conseiller.test@careeros.dev", "Conseil2026!")


def test_requires_auth():
    assert requests.get(f"{API}/sources").status_code in (401, 403)
    assert requests.get(f"{API}/history").status_code in (401, 403)


def test_sources_shape(m1):
    r = m1.get(f"{API}/sources")
    assert r.status_code == 200
    d = r.json()
    assert isinstance(d["radar"], list) and isinstance(d["packs"], list)
    for o in d["radar"]:
        assert o["priority"] in ("A", "B")
        assert "id" in o and "title" in o
    for p in d["packs"]:
        assert "id" in p and "title" in p


def test_source_radar_and_pack(m1):
    d = m1.get(f"{API}/sources").json()
    if d["radar"]:
        r = m1.get(f"{API}/source", params={"kind": "radar", "id": d["radar"][0]["id"]})
        assert r.status_code == 200 and isinstance(r.json()["text"], str) and r.json()["text"].strip()
    if d["packs"]:
        r = m1.get(f"{API}/source", params={"kind": "pack", "id": d["packs"][0]["id"]})
        assert r.status_code == 200 and "text" in r.json() and "title" in r.json()


def test_source_unknown_404(m1):
    assert m1.get(f"{API}/source", params={"kind": "radar", "id": "nope-" + uuid.uuid4().hex}).status_code == 404
    assert m1.get(f"{API}/source", params={"kind": "pack", "id": "nope-" + uuid.uuid4().hex}).status_code == 404


def test_source_bad_kind_422(m1):
    assert m1.get(f"{API}/source", params={"kind": "texte", "id": "x"}).status_code == 422


@pytest.mark.parametrize("body", [
    {"title": "TEST_x", "source_kind": "foo", "score": 50, "result": {}},
    {"title": "TEST_x", "source_kind": "texte", "score": 101, "result": {}},
    {"title": "TEST_x", "source_kind": "texte", "score": -1, "result": {}},
    {"title": "TEST_x", "source_kind": "texte", "score": 50},
])
def test_history_validation(m1, body):
    assert m1.post(f"{API}/history", json=body).status_code == 422


def test_history_save_get_isolation(m1, m2):
    body = {"title": "TEST_Superviseur logistique", "company": "TEST_Co", "source_kind": "texte", "score": 42,
            "result": {"score": 42, "gaps": [], "domains": []}, "texts": {"offre": "abc"}}
    r = m1.post(f"{API}/history", json=body)
    assert r.status_code == 200
    hid = r.json()["id"]
    lst = m1.get(f"{API}/history").json()
    item = next((h for h in lst if h["id"] == hid), None)
    assert item and item["score"] == 42 and item["title"] == body["title"] and item["source_kind"] == "texte"
    assert "result" not in item and "_id" not in item
    one = m1.get(f"{API}/history/{hid}")
    assert one.status_code == 200
    j = one.json()
    assert j["result"]["score"] == 42 and j["texts"]["offre"] == "abc" and "user_id" not in j and "_id" not in j
    # isolation
    assert m2.get(f"{API}/history/{hid}").status_code == 404
    assert all(h["id"] != hid for h in m2.get(f"{API}/history").json())


def test_history_unknown_404(m1):
    assert m1.get(f"{API}/history/{uuid.uuid4()}").status_code == 404
