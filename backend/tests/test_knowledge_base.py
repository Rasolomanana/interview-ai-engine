# Shared knowledge base ("Base commune CareerOS"): admin list, match endpoint, radar run recording (max 1 validation/day)
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"X-Admin-Password": "admin2026"}
ALLOWED = {"name", "portal_url", "kind", "kind_label", "status", "last_validated", "last_success", "validations", "recent_offers", "confidence"}


@pytest.fixture(scope="module")
def token():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "membre.test@careeros.dev", "password": "CareerOS2026!"})
    if r.status_code != 200:
        pytest.skip("login failed")
    d = r.json()
    return d.get("access_token") or d.get("token")


def H(t):
    return {"Authorization": f"Bearer {t}"}


def kb():
    r = requests.get(f"{BASE_URL}/api/admin/knowledge", headers=ADMIN)
    assert r.status_code == 200
    return r.json()


def wait_run(t, timeout=180):
    end = time.time() + timeout
    while time.time() < end:
        last = requests.get(f"{BASE_URL}/api/careeros/radar/dashboard", headers=H(t)).json().get("last_run") or {}
        if last.get("status") != "running":
            return last
        time.sleep(8)
    return None


# Admin endpoint: auth + only anonymous fields + stats
class TestAdminKnowledge:
    def test_requires_admin(self):
        assert requests.get(f"{BASE_URL}/api/admin/knowledge").status_code in (401, 403)
        assert requests.get(f"{BASE_URL}/api/admin/knowledge", headers={"X-Admin-Password": "bad"}).status_code in (401, 403)

    def test_fields_and_stats(self):
        d = kb()
        assert isinstance(d["items"], list) and len(d["items"]) > 0
        for it in d["items"]:
            assert set(it.keys()) == ALLOWED, set(it.keys()) ^ ALLOWED
            assert it["status"] in ("fiable", "fragile", "bloque")
            assert it["confidence"] in ("elevee", "moyenne", "faible")
        for k in ("total", "fiable", "fragile", "bloque", "elevee", "recent"):
            assert k in d["stats"]
        assert d["stats"]["total"] == len(d["items"])
        assert d["stats"]["fiable"] + d["stats"]["fragile"] + d["stats"]["bloque"] == d["stats"]["total"]
        raw = str(d).lower()
        for bad in ("user_id", "members", "email", "@"):
            assert bad not in raw, bad

    def test_one_card_per_employer(self):
        names = [i["name"].lower() for i in kb()["items"]]
        assert len(names) == len(set(names))


# Member match endpoint
class TestMatch:
    def test_requires_auth(self):
        assert requests.post(f"{BASE_URL}/api/careeros/radar/knowledge/match", json={"names": ["Desjardins"]}).status_code == 401

    def test_variants(self, token):
        r = requests.post(f"{BASE_URL}/api/careeros/radar/knowledge/match", headers=H(token),
                          json={"names": ["Hydro-Québec", "Desjardins inc", "Inconnue XYZ", "Desjardins Groupe"]})
        assert r.status_code == 200
        items = r.json()["items"]
        assert "Inconnue XYZ" not in items
        assert items["Desjardins inc"]["name"] == "Desjardins"
        assert items["Desjardins inc"]["kind"] == "workday"
        assert items["Desjardins inc"]["usable"] is True
        assert items["Desjardins inc"]["slug"]
        assert items["Desjardins Groupe"]["name"] == "Desjardins"
        print("Hydro-Québec match:", items.get("Hydro-Québec"))
        for v in items.values():
            assert "user_id" not in v and "members" not in v


# Radar run feeds KB; second run same day must not increment validations
class TestRunRecording:
    def test_run_twice_no_double_validation(self, token):
        before = {i["name"]: i for i in kb()["items"]}
        r = requests.post(f"{BASE_URL}/api/careeros/radar/run", headers=H(token))
        if r.status_code == 409:
            wait_run(token)
            r = requests.post(f"{BASE_URL}/api/careeros/radar/run", headers=H(token))
        assert r.status_code == 200 and r.json().get("started")
        time.sleep(5)
        last = wait_run(token)
        assert last and last.get("status") != "running"
        mid = {i["name"]: i for i in kb()["items"]}
        print("after run1:", {n: (v["validations"], v["last_validated"][:19], v["status"]) for n, v in mid.items()})
        r2 = requests.post(f"{BASE_URL}/api/careeros/radar/run", headers=H(token))
        assert r2.status_code == 200
        time.sleep(5)
        assert wait_run(token)
        after = {i["name"]: i for i in kb()["items"]}
        for n, v in after.items():
            if n in mid and v["kind"] == mid[n]["kind"]:
                assert v["validations"] == mid[n]["validations"], f"{n}: {mid[n]['validations']} -> {v['validations']}"
        # at least one card got refreshed by the runs
        refreshed = [n for n, v in after.items() if n in before and v["last_validated"] > before[n]["last_validated"]]
        print("refreshed:", refreshed)
        assert refreshed
