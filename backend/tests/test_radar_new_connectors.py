"""Backend tests for new Radar connectors: Avature, Taleo, Phenom (UKG regression),
discover/detect endpoints, settings persistence with new kinds, employer directory,
and admin /connectors new fields."""
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_PWD = os.environ.get("ADMIN_PASSWORD", "admin2026")
MEMBER_EMAIL = "membre.test@careeros.dev"
MEMBER_PWD = "CareerOS2026!"


@pytest.fixture(scope="session")
def member_token():
    r = requests.post(f"{API}/auth/login", json={"email": MEMBER_EMAIL, "password": MEMBER_PWD}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


@pytest.fixture(scope="session")
def member_headers(member_token):
    return {"Authorization": f"Bearer {member_token}", "Content-Type": "application/json"}


# ----- Discovery tests -----
class TestDiscover:
    def test_bnc_avature_fragile(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Banque Nationale"}, headers=member_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        avature = [c for c in data["candidates"] if c["kind"] == "avature"]
        assert avature, f"No avature candidate found. Candidates: {data['candidates']}, unsupported: {data['unsupported']}"
        c = avature[0]
        assert c["ok"] is True
        assert c["count"] > 0
        assert c["quality"] == "fragile"
        assert "Avature" not in data["unsupported"]

    def test_bell_phenom_fragile(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Bell"}, headers=member_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        phenom = [c for c in data["candidates"] if c["kind"] == "phenom"]
        assert phenom, f"No phenom candidate. Candidates: {data['candidates']}"
        assert phenom[0]["ok"] is True
        assert phenom[0]["quality"] == "fragile"

    def test_air_canada_phenom_fragile(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Air Canada"}, headers=member_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        phenom = [c for c in data["candidates"] if c["kind"] == "phenom"]
        assert phenom, f"No phenom candidate. Candidates: {data['candidates']}"
        assert phenom[0]["ok"] is True
        assert phenom[0]["quality"] == "fragile"

    def test_hdr_taleo_fiable(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover",
                          json={"name": "HDR", "website": "https://hdr.taleo.net/careersection/ex/jobsearch.ftl"},
                          headers=member_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        taleo = [c for c in data["candidates"] if c["kind"] == "taleo"]
        assert taleo, f"No taleo candidate. Candidates: {data['candidates']}"
        assert taleo[0]["ok"] is True
        assert taleo[0]["quality"] == "fiable"

    def test_desjardins_workday_fiable_regression(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Desjardins"}, headers=member_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        wd = [c for c in data["candidates"] if c["kind"] == "workday"]
        assert wd, f"No workday candidate. Candidates: {data['candidates']}"
        assert wd[0]["ok"] is True
        assert wd[0]["quality"] == "fiable"


# ----- Detect tests -----
class TestDetect:
    def test_detect_taleo(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/detect",
                          json={"url": "https://hdr.taleo.net/careersection/ex/jobsearch.ftl"},
                          headers=member_headers, timeout=45)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["kind"] == "taleo", data
        assert data["ok"] is True

    def test_detect_avature(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/detect",
                          json={"url": "https://emplois.bnc.ca/fr_CA/careers/SearchJobs"},
                          headers=member_headers, timeout=45)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["kind"] == "avature", data

    def test_detect_phenom(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/detect",
                          json={"url": "https://jobs.bell.ca/ca/fr/search-results"},
                          headers=member_headers, timeout=45)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["kind"] == "phenom", data


# ----- Settings accepts new kinds -----
class TestSettingsNewKinds:
    def test_put_settings_accepts_taleo_avature_phenom(self, member_headers):
        # Snapshot
        got = requests.get(f"{API}/careeros/radar/settings", headers=member_headers, timeout=30)
        assert got.status_code == 200, got.text
        original = got.json()
        try:
            payload = {k: original[k] for k in ("sources", "location", "keywords", "companies", "exclude_keywords", "goal", "frequency")
                       if k in original}
            # Add 3 test companies
            payload["companies"] = (payload.get("companies") or []) + [
                {"name": "TEST_HDR_Taleo", "portal_url": "https://hdr.taleo.net/careersection/ex/", "kind": "taleo", "slug": "hdr.taleo.net/ex", "enabled": True},
                {"name": "TEST_BNC_Avature", "portal_url": "https://emplois.bnc.ca/fr_CA/careers/SearchJobs", "kind": "avature", "slug": "emplois.bnc.ca/fr_CA/careers", "enabled": True},
                {"name": "TEST_Bell_Phenom", "portal_url": "https://jobs.bell.ca/ca/fr/search-results", "kind": "phenom", "slug": "jobs.bell.ca/fr/ca", "enabled": True},
            ]
            r = requests.put(f"{API}/careeros/radar/settings", json=payload, headers=member_headers, timeout=30)
            assert r.status_code == 200, r.text
            persisted = r.json()
            names = {c["name"]: c for c in persisted.get("companies") or []}
            assert "TEST_HDR_Taleo" in names and names["TEST_HDR_Taleo"]["kind"] == "taleo"
            assert "TEST_BNC_Avature" in names and names["TEST_BNC_Avature"]["kind"] == "avature"
            assert "TEST_Bell_Phenom" in names and names["TEST_Bell_Phenom"]["kind"] == "phenom"
        finally:
            # Restore
            restore = {k: original[k] for k in ("sources", "location", "keywords", "companies", "exclude_keywords", "goal", "frequency")
                       if k in original}
            requests.put(f"{API}/careeros/radar/settings", json=restore, headers=member_headers, timeout=30)


# ----- Employer directory lists new entries -----
class TestDirectory:
    def test_directory_lists_new_employers(self, member_headers):
        r = requests.get(f"{API}/careeros/radar/directory", headers=member_headers, timeout=90)
        assert r.status_code == 200, r.text
        rows = {e["name"]: e for e in r.json()}
        for n in ("Banque Nationale", "Bell", "Air Canada"):
            assert n in rows, f"{n} missing in directory"
        assert rows["Banque Nationale"]["kind"] == "avature"
        assert rows["Bell"]["kind"] == "phenom"
        assert rows["Air Canada"]["kind"] == "phenom"
        # They should be ok (fetchable). Allow 'ok' or at least not blocked.
        for n in ("Banque Nationale", "Bell", "Air Canada"):
            assert rows[n]["ok"] is True, f"{n}: {rows[n]}"


# ----- Admin /connectors returns new fields -----
class TestAdminConnectors:
    def test_admin_connectors_has_new_fields(self):
        r = requests.get(f"{API}/admin/connectors", headers={"X-Admin-Password": ADMIN_PWD}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "redetect" in data and isinstance(data["redetect"], dict)
        for row in data["supported"]:
            for k in ("reliable", "fragile", "blocked", "fallback", "fragile_kind"):
                assert k in row, f"Missing {k} in supported row {row}"
            assert isinstance(row["fragile_kind"], bool)
        # Backlog must not contain modern ATS as unsupported (except as blocked prefix allowed)
        backlog_labels = {row["connector"] for row in data["backlog"]}
        for forbidden in ("UKG", "Avature", "Taleo", "Phenom"):
            # It's okay to appear with "(bloqué anti-robot)" suffix – only forbid the bare entries.
            assert forbidden not in backlog_labels, f"Bare backlog entry {forbidden} should have been removed: {backlog_labels}"
