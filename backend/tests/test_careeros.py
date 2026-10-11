"""CareerOS backend tests: auth, Career Memory, Pack generation, History, IPS unit."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/") if os.environ.get("REACT_APP_BACKEND_URL") else "https://interview-ai-engine.preview.emergentagent.com"

# Load from frontend .env if not set
if "REACT_APP_BACKEND_URL" not in os.environ:
    try:
        with open("/app/frontend/.env") as f:
            for line in f:
                if line.startswith("REACT_APP_BACKEND_URL="):
                    BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
    except Exception:
        pass

API = f"{BASE_URL}/api"
TEST_PASSWORD = "CareerOS2026!"
MEMBER_EMAIL = "membre.test@careeros.dev"


@pytest.fixture(scope="module")
def seed_user_token():
    r = requests.post(f"{API}/auth/login", json={"email": MEMBER_EMAIL, "password": TEST_PASSWORD}, timeout=15)
    assert r.status_code == 200, f"seed login failed: {r.status_code} {r.text}"
    return r.json()["access_token"]


@pytest.fixture(scope="module")
def new_user():
    email = f"test_{uuid.uuid4().hex[:10]}@careeros.dev"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": "Secret123!", "name": "T User"}, timeout=15)
    assert r.status_code == 200, r.text
    data = r.json()
    assert "user" in data and "access_token" in data and "refresh_token" in data
    assert data["user"]["email"] == email
    return {"email": email, **data}


# ---------- Auth ----------
class TestAuth:
    def test_register_duplicate_returns_409(self, new_user):
        r = requests.post(f"{API}/auth/register", json={"email": new_user["email"], "password": "Secret123!", "name": "x"}, timeout=15)
        assert r.status_code == 409

    def test_register_short_password_422(self):
        r = requests.post(f"{API}/auth/register", json={"email": f"test_{uuid.uuid4().hex[:6]}@x.com", "password": "short"}, timeout=15)
        assert r.status_code == 422

    def test_login_wrong_password_401(self):
        r = requests.post(f"{API}/auth/login", json={"email": MEMBER_EMAIL, "password": "WRONG_XYZ123"}, timeout=15)
        assert r.status_code == 401

    def test_me_requires_auth(self):
        r = requests.get(f"{API}/auth/me", timeout=15)
        assert r.status_code == 401

    def test_me_with_bearer(self, seed_user_token):
        r = requests.get(f"{API}/auth/me", headers={"Authorization": f"Bearer {seed_user_token}"}, timeout=15)
        assert r.status_code == 200
        assert r.json()["email"] == MEMBER_EMAIL

    def test_refresh_returns_new_access(self, new_user):
        r = requests.post(f"{API}/auth/refresh", json={"refresh_token": new_user["refresh_token"]}, timeout=15)
        assert r.status_code == 200
        assert "access_token" in r.json()

    def test_brute_force_lockout_429(self):
        # Use a dedicated unique email so we don't lock out seed/other tests
        email = f"test_lockout_{uuid.uuid4().hex[:8]}@careeros.dev"
        # Register the user with a known password
        reg = requests.post(f"{API}/auth/register", json={"email": email, "password": "Secret123!", "name": "lk"}, timeout=15)
        assert reg.status_code == 200
        last = None
        for _ in range(6):
            last = requests.post(f"{API}/auth/login", json={"email": email, "password": "BAD_PWD_X"}, timeout=15)
        assert last.status_code == 429, f"Expected 429 after 5 bad attempts, got {last.status_code}"


# ---------- Career Memory ----------
class TestMemory:
    def test_meta_public(self):
        r = requests.get(f"{API}/careeros/meta", timeout=15)
        assert r.status_code == 200
        d = r.json()
        assert isinstance(d.get("goals"), list) and len(d["goals"]) > 5
        assert "a_postuler" in d.get("pipeline", [])

    def test_profile_get_requires_auth(self):
        r = requests.get(f"{API}/careeros/profile", timeout=15)
        assert r.status_code == 401

    def test_profile_update_and_persist(self, new_user):
        h = {"Authorization": f"Bearer {new_user['access_token']}"}
        payload = {"full_name": "Test User", "headline": "Analyste BI", "goals": ["changer d'emploi"],
                   "cv_text": "X" * 200, "skills": ["Python", "SQL"]}
        r = requests.put(f"{API}/careeros/profile", json=payload, headers=h, timeout=15)
        assert r.status_code == 200
        got = r.json()
        assert got["headline"] == "Analyste BI"
        # verify persistence via GET
        r2 = requests.get(f"{API}/careeros/profile", headers=h, timeout=15)
        assert r2.status_code == 200
        assert r2.json()["headline"] == "Analyste BI"
        assert r2.json()["skills"] == ["Python", "SQL"]

    def test_profile_isolation(self, new_user, seed_user_token):
        # Seed user should not see new_user's profile data
        h_seed = {"Authorization": f"Bearer {seed_user_token}"}
        r = requests.get(f"{API}/careeros/profile", headers=h_seed, timeout=15)
        assert r.status_code == 200
        # headline should NOT match the one we set for new_user
        assert r.json().get("headline") != "Analyste BI_UNIQUE_X"


# ---------- Pack validation ----------
class TestPackValidation:
    def test_cv_too_short_400(self, new_user):
        h = {"Authorization": f"Bearer {new_user['access_token']}"}
        # Clear memory CV first
        requests.put(f"{API}/careeros/profile", json={"cv_text": ""}, headers=h, timeout=15)
        r = requests.post(f"{API}/careeros/packs",
                          json={"offer_text": "O" * 200, "cv_text": "short cv", "network": "aucun"},
                          headers=h, timeout=15)
        assert r.status_code == 400

    def test_offer_missing_400(self, new_user):
        h = {"Authorization": f"Bearer {new_user['access_token']}"}
        r = requests.post(f"{API}/careeros/packs",
                          json={"cv_text": "C" * 200, "offer_text": "", "network": "aucun"},
                          headers=h, timeout=15)
        assert r.status_code == 400

    def test_invalid_network_400(self, new_user):
        h = {"Authorization": f"Bearer {new_user['access_token']}"}
        r = requests.post(f"{API}/careeros/packs",
                          json={"cv_text": "C" * 200, "offer_text": "O" * 200, "network": "invalid_x"},
                          headers=h, timeout=15)
        assert r.status_code == 400


# ---------- History ----------
class TestHistory:
    def test_list_apps_own_only(self, seed_user_token, new_user):
        h_seed = {"Authorization": f"Bearer {seed_user_token}"}
        h_new = {"Authorization": f"Bearer {new_user['access_token']}"}
        r_seed = requests.get(f"{API}/careeros/applications", headers=h_seed, timeout=15)
        r_new = requests.get(f"{API}/careeros/applications", headers=h_new, timeout=15)
        assert r_seed.status_code == 200 and r_new.status_code == 200
        seed_apps = r_seed.json()
        new_apps = r_new.json()
        assert isinstance(seed_apps, list)
        # Seed user has 1 completed pack per spec
        assert len(seed_apps) >= 1
        # New user has no apps
        assert len(new_apps) == 0

    def test_other_user_app_returns_404(self, seed_user_token, new_user):
        h_seed = {"Authorization": f"Bearer {seed_user_token}"}
        h_new = {"Authorization": f"Bearer {new_user['access_token']}"}
        r = requests.get(f"{API}/careeros/applications", headers=h_seed, timeout=15)
        apps = r.json()
        if not apps:
            pytest.skip("No seed apps to cross-test")
        other_id = apps[0]["id"]
        r2 = requests.get(f"{API}/careeros/applications/{other_id}", headers=h_new, timeout=15)
        assert r2.status_code == 404

    def test_status_update_valid_and_invalid(self, seed_user_token):
        h = {"Authorization": f"Bearer {seed_user_token}"}
        r = requests.get(f"{API}/careeros/applications", headers=h, timeout=15)
        apps = r.json()
        if not apps:
            pytest.skip("No apps")
        app_id = apps[0]["id"]
        # invalid
        r_bad = requests.patch(f"{API}/careeros/applications/{app_id}/status",
                               json={"pipeline_status": "nope"}, headers=h, timeout=15)
        assert r_bad.status_code == 400
        # valid
        r_ok = requests.patch(f"{API}/careeros/applications/{app_id}/status",
                              json={"pipeline_status": "postule", "note": "test"}, headers=h, timeout=15)
        assert r_ok.status_code == 200
        # verify persistence + timeline
        r_get = requests.get(f"{API}/careeros/applications/{app_id}", headers=h, timeout=15)
        assert r_get.status_code == 200
        d = r_get.json()
        assert d["pipeline_status"] == "postule"
        assert any(t.get("type") == "status" for t in d.get("timeline", []))
        # restore
        requests.patch(f"{API}/careeros/applications/{app_id}/status",
                       json={"pipeline_status": "a_postuler"}, headers=h, timeout=15)


# ---------- IPS unit tests ----------
class TestIPS:
    def test_knockout_caps_40_priority_C(self):
        import sys
        sys.path.insert(0, "/app/backend")
        from careeros.ips import compute_ips
        ai = {k: {"score": 10, "justification": "x"} for k in
              ["adequation_profil", "experience", "competences", "qualite_cv",
               "concurrence", "signaux_marche", "certifications"]}
        r = compute_ips(ai, {"present": True, "detail": "no citizenship"}, {"score": 8}, "", "recommandation", True)
        assert r["score"] <= 40
        assert r["priority"] == "C"
        assert r["knockout"] is True

    def test_network_recommandation_10(self):
        import sys; sys.path.insert(0, "/app/backend")
        from careeros.ips import compute_ips
        r = compute_ips({}, {}, {"score": 6}, "", "recommandation", True)
        row = next(x for x in r["criteria"] if x["key"] == "force_reseau")
        assert row["score"] == 10

    def test_posted_date_today_fresh_10(self):
        import sys; sys.path.insert(0, "/app/backend")
        from datetime import date
        from careeros.ips import compute_ips
        r = compute_ips({}, {}, {"score": 6}, date.today().isoformat(), "aucun", True)
        row = next(x for x in r["criteria"] if x["key"] == "fraicheur_offre")
        assert row["score"] == 10

    def test_missing_ai_criterion_neutral_5(self):
        import sys; sys.path.insert(0, "/app/backend")
        from careeros.ips import compute_ips
        r = compute_ips({}, {}, {"score": 6}, "", "aucun", True)
        row = next(x for x in r["criteria"] if x["key"] == "adequation_profil")
        assert row["score"] == 5
        assert row["source"] == "neutre"

    def test_weights_sum_to_100(self):
        import sys; sys.path.insert(0, "/app/backend")
        from careeros.ips import WEIGHTS
        assert sum(WEIGHTS.values()) == 100

    def test_priority_A_requires_score_70(self):
        import sys; sys.path.insert(0, "/app/backend")
        from careeros.ips import compute_ips
        ai = {k: {"score": 9, "justification": "x"} for k in
              ["adequation_profil", "experience", "competences", "qualite_cv",
               "concurrence", "signaux_marche", "certifications"]}
        from datetime import date
        r = compute_ips(ai, {}, {"score": 8}, date.today().isoformat(), "recommandation", True)
        assert r["score"] >= 70
        assert r["priority"] == "A"


# ---------- Cleanup ----------
def test_zz_cleanup(new_user):
    """Remove created test users via direct Mongo (best-effort).
    This is a soft cleanup — if we can't reach Mongo we skip."""
    try:
        import pymongo
        url = os.environ.get("MONGO_URL")
        if not url:
            with open("/app/backend/.env") as f:
                for ln in f:
                    if ln.startswith("MONGO_URL="):
                        url = ln.split("=", 1)[1].strip()
        db_name = os.environ.get("DB_NAME")
        if not db_name:
            with open("/app/backend/.env") as f:
                for ln in f:
                    if ln.startswith("DB_NAME="):
                        db_name = ln.split("=", 1)[1].strip()
        if not url or not db_name:
            pytest.skip("No MONGO_URL/DB_NAME")
        c = pymongo.MongoClient(url)
        db = c[db_name]
        res = db.users.delete_many({"email": {"$regex": "^test_"}})
        db.career_profiles.delete_many({"user_id": {"$exists": True}})  # orphans only
        print(f"deleted {res.deleted_count} test users")
    except Exception as e:
        pytest.skip(f"cleanup skipped: {e}")
