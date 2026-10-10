"""Admin space tests: auth gating, stats, exports, tracking, consent-gated CV."""
import os
import time
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "https://interview-ai-engine.preview.emergentagent.com").rstrip("/")
ADMIN_PWD = "admin2026"


# --- Admin auth gate ---
class TestAdminAuth:
    def test_login_wrong_password(self):
        r = requests.post(f"{BASE_URL}/api/admin/login", json={"password": "nope"})
        assert r.status_code == 401

    def test_login_ok(self):
        r = requests.post(f"{BASE_URL}/api/admin/login", json={"password": ADMIN_PWD})
        assert r.status_code == 200
        assert r.json().get("success") is True

    def test_stats_requires_header(self):
        r = requests.get(f"{BASE_URL}/api/admin/stats")
        assert r.status_code == 401

    def test_stats_wrong_header(self):
        r = requests.get(f"{BASE_URL}/api/admin/stats", headers={"X-Admin-Password": "bad"})
        assert r.status_code == 401

    def test_stats_ok(self):
        r = requests.get(f"{BASE_URL}/api/admin/stats", headers={"X-Admin-Password": ADMIN_PWD})
        assert r.status_code == 200
        d = r.json()
        assert "totals" in d and "llm" in d and "submissions" in d
        for k in ("visitors", "simulations", "ats_analyses", "cvs_analyzed", "cover_letters"):
            assert k in d["totals"]
        assert "by_day" in d and "by_week" in d and "by_month" in d


# --- Exports ---
class TestAdminExports:
    def test_export_csv_requires_header(self):
        r = requests.get(f"{BASE_URL}/api/admin/export?fmt=csv")
        assert r.status_code == 401

    def test_export_csv_ok(self):
        r = requests.get(f"{BASE_URL}/api/admin/export?fmt=csv", headers={"X-Admin-Password": ADMIN_PWD})
        assert r.status_code == 200
        assert "text/csv" in r.headers.get("content-type", "")
        assert "date,score" in r.text or r.text.startswith("date,")

    def test_export_xlsx_ok(self):
        r = requests.get(f"{BASE_URL}/api/admin/export?fmt=xlsx", headers={"X-Admin-Password": ADMIN_PWD})
        assert r.status_code == 200
        # Starts with PK (zip magic bytes)
        assert r.content[:2] == b"PK"


# --- Tracking end-to-end ---
class TestTracking:
    def test_track_simulation_and_llm_increments_counters(self):
        before = requests.get(f"{BASE_URL}/api/admin/stats", headers={"X-Admin-Password": ADMIN_PWD}).json()
        sid = str(uuid.uuid4())
        r1 = requests.post(f"{BASE_URL}/api/track", json={"type": "simulation", "session_id": sid})
        r2 = requests.post(f"{BASE_URL}/api/track", json={
            "type": "llm_call", "session_id": sid,
            "meta": {"provider": "server", "tokens_in": 100, "tokens_out": 50, "cost": 0.001},
        })
        assert r1.status_code == 200 and r2.status_code == 200
        time.sleep(1)
        after = requests.get(f"{BASE_URL}/api/admin/stats", headers={"X-Admin-Password": ADMIN_PWD}).json()
        assert after["totals"]["simulations"] >= before["totals"]["simulations"] + 1
        assert after["llm"]["calls"] >= before["llm"]["calls"] + 1


# --- Consent-gated ATS submission storage ---
class TestConsentGatedCV:
    def _run_analysis(self, consent: bool, session_id: str, company_tag: str):
        payload = {
            "cv": f"TEST CV content for {company_tag} - Python engineer 5 years",
            "poste": f"Senior Engineer at {company_tag}",
            "url": "",
            "session_id": session_id,
            "consent": consent,
        }
        r = requests.post(f"{BASE_URL}/api/analyze-application", json=payload)
        assert r.status_code == 200
        job_id = r.json()["job_id"]
        for _ in range(16):
            time.sleep(5)
            s = requests.get(f"{BASE_URL}/api/analyze-application/{job_id}").json()
            if s["status"] != "pending":
                return s
        pytest.skip("LLM analysis timed out (>80s)")

    def test_noconsent_cv_not_stored(self):
        sid = f"TEST_noconsent_{uuid.uuid4()}"
        res = self._run_analysis(False, sid, "TEST_NoConsent")
        assert res["status"] == "done"
        stats = requests.get(f"{BASE_URL}/api/admin/stats", headers={"X-Admin-Password": ADMIN_PWD}).json()
        match = next((s for s in stats["submissions"] if s.get("ip_trunc") is not None and sid[:12] in (s.get("session_id") or "") or True and False), None)
        # Fallback: just check the most recent submission matches
        latest = stats["submissions"][0]
        assert latest["consent"] is False
        assert latest["has_cv"] is False

    def test_withconsent_cv_stored(self):
        sid = f"TEST_consent_{uuid.uuid4()}"
        res = self._run_analysis(True, sid, "TEST_WithConsent")
        assert res["status"] == "done"
        stats = requests.get(f"{BASE_URL}/api/admin/stats", headers={"X-Admin-Password": ADMIN_PWD}).json()
        latest = stats["submissions"][0]
        assert latest["consent"] is True
        assert latest["has_cv"] is True
