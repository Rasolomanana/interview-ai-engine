"""Tests for CareerOS GPS de carrière: /api/careeros/journey + /api/auth/preferences."""
import os
import time
import uuid

import pytest
import requests

_env_url = os.environ.get("REACT_APP_BACKEND_URL")
if not _env_url:
    # Load from frontend .env
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    _env_url = line.split("=", 1)[1].strip()
                    break
    except Exception:
        pass
BASE = (_env_url or "").rstrip("/")
assert BASE, "REACT_APP_BACKEND_URL not set"


# ---------- helpers / fixtures ----------
@pytest.fixture(scope="module")
def fresh_member():
    email = f"TEST_journey_{uuid.uuid4().hex[:10]}@careeros.dev"
    password = "CareerOS2026!"
    r = requests.post(f"{BASE}/api/auth/register", json={"email": email, "password": password, "name": "Test Journey"})
    assert r.status_code == 200, r.text
    data = r.json()
    return {"email": email, "password": password, "token": data["access_token"], "user": data["user"]}


def _h(token):
    return {"Authorization": f"Bearer {token}"}


# ---------- /api/careeros/journey ----------
class TestJourney:
    def test_journey_requires_auth(self):
        r = requests.get(f"{BASE}/api/careeros/journey")
        assert r.status_code == 401

    def test_journey_fresh_member_shape_and_memory_next(self, fresh_member):
        r = requests.get(f"{BASE}/api/careeros/journey", headers=_h(fresh_member["token"]))
        assert r.status_code == 200, r.text
        j = r.json()

        # 5 steps
        assert len(j["steps"]) == 5
        keys = [s["key"] for s in j["steps"]]
        assert keys == ["memory", "radar", "pack", "interview", "followup"]
        for s in j["steps"]:
            assert set(s.keys()) >= {"key", "label", "to", "done"}
            assert isinstance(s["done"], bool)

        # 6 milestones
        assert len(j["milestones"]) == 6
        mkeys = [m["key"] for m in j["milestones"]]
        assert mkeys == ["profile", "radar", "offer", "pack", "sent", "interview"]
        assert j["total"] == 6
        assert isinstance(j["completed"], int)
        assert j["completed"] == 0  # fresh account

        # next = memory
        nxt = j["next"]
        assert nxt["step"] == "memory"
        assert nxt["to"] == "/careeros/memoire"
        assert set(nxt.keys()) >= {"step", "title", "text", "cta", "to", "time"}
        assert "Career Memory" in nxt["title"]

        assert "preferences" in j

    def test_journey_after_profile_moves_to_radar(self, fresh_member):
        cv = "Analyste BI avec 10 ans d'expérience en Power BI, SQL, Snowflake, Python. " * 10
        payload = {"cv_text": cv, "target_roles": "Analyste BI", "location": "Montréal, QC"}
        r = requests.put(f"{BASE}/api/careeros/profile", json=payload, headers=_h(fresh_member["token"]))
        assert r.status_code == 200, r.text

        r = requests.get(f"{BASE}/api/careeros/journey", headers=_h(fresh_member["token"]))
        assert r.status_code == 200
        j = r.json()
        # profile milestone done
        profile_m = next(m for m in j["milestones"] if m["key"] == "profile")
        assert profile_m["done"] is True
        # memory step done
        memory_step = next(s for s in j["steps"] if s["key"] == "memory")
        assert memory_step["done"] is True
        # next step should become radar (no radar offers yet)
        assert j["next"]["step"] == "radar"
        assert "Radar" in j["next"]["title"]
        assert j["next"]["to"] == "/careeros/radar"


# ---------- /api/auth/preferences ----------
class TestPreferences:
    def test_patch_requires_auth(self):
        r = requests.patch(f"{BASE}/api/auth/preferences", json={"guide_mode": "expert"})
        assert r.status_code == 401

    def test_empty_body_422(self, fresh_member):
        r = requests.patch(f"{BASE}/api/auth/preferences", json={}, headers=_h(fresh_member["token"]))
        assert r.status_code == 422

    def test_invalid_guide_mode_422(self, fresh_member):
        r = requests.patch(f"{BASE}/api/auth/preferences", json={"guide_mode": "bogus"}, headers=_h(fresh_member["token"]))
        assert r.status_code == 422

    def test_patch_guide_mode_persists(self, fresh_member):
        r = requests.patch(f"{BASE}/api/auth/preferences", json={"guide_mode": "expert"}, headers=_h(fresh_member["token"]))
        assert r.status_code == 200, r.text
        assert r.json()["preferences"]["guide_mode"] == "expert"

        me = requests.get(f"{BASE}/api/auth/me", headers=_h(fresh_member["token"]))
        assert me.status_code == 200
        assert me.json()["preferences"]["guide_mode"] == "expert"

    def test_patch_tour_done_partial(self, fresh_member):
        r = requests.patch(f"{BASE}/api/auth/preferences", json={"tour_done": True}, headers=_h(fresh_member["token"]))
        assert r.status_code == 200
        prefs = r.json()["preferences"]
        assert prefs["tour_done"] is True
        # expert from previous test must still be there (merged)
        assert prefs.get("guide_mode") == "expert"

        me = requests.get(f"{BASE}/api/auth/me", headers=_h(fresh_member["token"])).json()
        assert me["preferences"]["tour_done"] is True
        assert me["preferences"]["guide_mode"] == "expert"

    def test_patch_theme(self, fresh_member):
        r = requests.patch(f"{BASE}/api/auth/preferences", json={"theme": "dark"}, headers=_h(fresh_member["token"]))
        assert r.status_code == 200
        assert r.json()["preferences"]["theme"] == "dark"

    def test_invalid_theme_422(self, fresh_member):
        r = requests.patch(f"{BASE}/api/auth/preferences", json={"theme": "neon"}, headers=_h(fresh_member["token"]))
        assert r.status_code == 422
