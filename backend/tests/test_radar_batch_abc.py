"""Backend tests for Radar batch A+B+C:
A. Fix detection: Walmart (Workday Canada), Costco (Taleobe), Metro (schema.org sitemap),
   Loblaw (schema), Sobeys regression (SuccessFactors blocked).
B. Re-detect pattern: PUT /settings accepts kind='schema' and kind='taleobe'.
C. (Guides tested via Playwright - frontend)."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
ADMIN_PWD = os.environ.get("ADMIN_PASSWORD", "admin2026")
MEMBER_EMAIL = "membre.test@careeros.dev"
MEMBER_PWD = "CareerOS2026!"


@pytest.fixture(scope="session")
def member_headers():
    r = requests.post(f"{API}/auth/login", json={"email": MEMBER_EMAIL, "password": MEMBER_PWD}, timeout=30)
    assert r.status_code == 200, r.text
    tok = r.json()["access_token"]
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


# ---------- A. Discovery fixes ----------
class TestDiscoveryFixes:
    def test_walmart_workday_canada(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Walmart"},
                          headers=member_headers, timeout=90)
        assert r.status_code == 200, r.text
        data = r.json()
        wd = [c for c in data["candidates"] if c["kind"] == "workday"]
        assert wd, f"No workday candidate for Walmart. Got: {data['candidates']}"
        slugs = {c["slug"] for c in wd}
        assert any("walmart.wd504/walmartexternal" in s.lower() for s in slugs), f"slugs={slugs}"
        target = next(c for c in wd if "walmart.wd504/walmartexternal" in c["slug"].lower())
        assert target["ok"] is True
        assert target["quality"] == "fiable"

    def test_metro_schema_fiable(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Metro"},
                          headers=member_headers, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        schema = [c for c in data["candidates"] if c["kind"] == "schema"]
        assert schema, f"No schema candidate for Metro. Got: {data['candidates']}"
        c = schema[0]
        assert "talent.metro.ca" in c["slug"] and "sitemap" in c["slug"]
        assert c["ok"] is True
        assert c["count"] > 0
        assert c["quality"] == "fiable"

    def test_loblaw_schema_candidate(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Loblaw"},
                          headers=member_headers, timeout=120)
        assert r.status_code == 200, r.text
        data = r.json()
        schema = [c for c in data["candidates"] if c["kind"] == "schema"]
        assert schema, f"No schema candidate for Loblaw. Got: {data['candidates']} unsupported={data['unsupported']}"
        assert schema[0]["ok"] is True

    def test_costco_taleobe_no_icims_www(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Costco"},
                          headers=member_headers, timeout=90)
        assert r.status_code == 200, r.text
        data = r.json()
        # Must have Taleobe candidate (phf.tbe.taleo.net/phf02/COSTCO/41)
        taleobe = [c for c in data["candidates"] if c["kind"] == "taleobe"]
        assert taleobe, f"No taleobe candidate. Got: {data['candidates']} unsupported={data['unsupported']}"
        t = taleobe[0]
        assert "phf.tbe.taleo.net" in t["slug"]
        assert "COSTCO" in t["slug"].upper()
        assert "/41" in t["slug"] or t["slug"].endswith("/41")
        assert t["ok"] is True
        assert t["quality"] == "fragile"
        # No www.icims.com / cdn02.icims.com false positives
        icims_slugs = {c["slug"] for c in data["candidates"] if c["kind"] == "icims"}
        for s in icims_slugs:
            assert not s.startswith("www."), f"Unexpected www.icims slug: {s}"
            assert not s.startswith("cdn"), f"Unexpected cdn icims slug: {s}"
        # Taleo must not be in unsupported since Taleobe handles it
        assert "Taleo" not in data["unsupported"]

    def test_sobeys_successfactors_blocked_regression(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Sobeys"},
                          headers=member_headers, timeout=90)
        assert r.status_code == 200, r.text
        data = r.json()
        sf = [c for c in data["candidates"] if c["kind"] == "successfactors"]
        assert sf, f"Sobeys should still produce a SuccessFactors candidate. Got: {data['candidates']}"
        # It must remain blocked (Jooble fallback)
        assert sf[0].get("blocked") is True or sf[0]["ok"] is False, f"Sobeys SF should be blocked/unreadable: {sf[0]}"


# ---------- B. Detect endpoint ----------
class TestDetect:
    def test_detect_schema_sitemap(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/detect",
                          json={"url": "https://talent.metro.ca/sitemap.xml"},
                          headers=member_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["kind"] == "schema", data
        assert data["ok"] is True

    def test_detect_taleobe(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/detect",
                          json={"url": "https://phf.tbe.taleo.net/phf02/ats/careers/v2/jobSearch?act=redirectCwsV2&cws=41&org=COSTCO"},
                          headers=member_headers, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["kind"] == "taleobe", data


# ---------- B. Settings accepts schema + taleobe ----------
class TestSettingsNewKinds:
    def test_put_settings_accepts_schema_and_taleobe(self, member_headers):
        got = requests.get(f"{API}/careeros/radar/settings", headers=member_headers, timeout=30)
        assert got.status_code == 200, got.text
        original = got.json()
        keep = ("sources", "location", "keywords", "companies", "exclude_keywords", "goal", "frequency")
        try:
            payload = {k: original[k] for k in keep if k in original}
            payload["companies"] = (payload.get("companies") or []) + [
                {"name": "TEST_Metro_Schema", "portal_url": "https://talent.metro.ca/sitemap.xml",
                 "kind": "schema", "slug": "talent.metro.ca/sitemap.xml", "enabled": True},
                {"name": "TEST_Costco_Taleobe", "portal_url": "https://phf.tbe.taleo.net/phf02/ats/careers/v2/jobSearch?act=redirectCwsV2&cws=41&org=COSTCO",
                 "kind": "taleobe", "slug": "phf.tbe.taleo.net/phf02/COSTCO/41", "enabled": True},
            ]
            r = requests.put(f"{API}/careeros/radar/settings", json=payload, headers=member_headers, timeout=30)
            assert r.status_code == 200, r.text
            persisted = r.json()
            names = {c["name"]: c for c in persisted.get("companies") or []}
            assert "TEST_Metro_Schema" in names and names["TEST_Metro_Schema"]["kind"] == "schema"
            assert "TEST_Costco_Taleobe" in names and names["TEST_Costco_Taleobe"]["kind"] == "taleobe"
        finally:
            restore = {k: original[k] for k in keep if k in original}
            requests.put(f"{API}/careeros/radar/settings", json=restore, headers=member_headers, timeout=30)


# ---------- Directory contains Metro + Walmart Canada ----------
class TestDirectory:
    def test_directory_metro_walmart(self, member_headers):
        r = requests.get(f"{API}/careeros/radar/directory", headers=member_headers, timeout=180)
        assert r.status_code == 200, r.text
        rows = {e["name"]: e for e in r.json()}
        assert "Metro" in rows, "Metro missing in directory"
        assert rows["Metro"]["kind"] == "schema"
        assert rows["Metro"]["ok"] is True
        assert "Walmart Canada" in rows, "Walmart Canada missing in directory"
        assert rows["Walmart Canada"]["kind"] == "workday"
        assert rows["Walmart Canada"]["ok"] is True


# ---------- Regression on earlier connectors ----------
class TestRegressions:
    def test_bell_phenom(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Bell"},
                          headers=member_headers, timeout=90)
        assert r.status_code == 200, r.text
        cands = r.json()["candidates"]
        assert any(c["kind"] == "phenom" and c["ok"] for c in cands), cands

    def test_bnc_avature(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Banque Nationale"},
                          headers=member_headers, timeout=90)
        assert r.status_code == 200, r.text
        cands = r.json()["candidates"]
        assert any(c["kind"] == "avature" and c["ok"] for c in cands), cands

    def test_hdr_taleo(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover",
                          json={"name": "HDR", "website": "https://hdr.taleo.net/careersection/ex/jobsearch.ftl"},
                          headers=member_headers, timeout=90)
        assert r.status_code == 200, r.text
        cands = r.json()["candidates"]
        assert any(c["kind"] == "taleo" and c["ok"] for c in cands), cands

    def test_desjardins_workday(self, member_headers):
        r = requests.post(f"{API}/careeros/radar/portal/discover", json={"name": "Desjardins"},
                          headers=member_headers, timeout=90)
        assert r.status_code == 200, r.text
        cands = r.json()["candidates"]
        assert any(c["kind"] == "workday" and c["ok"] for c in cands), cands

    def test_admin_connectors_still_works(self):
        r = requests.get(f"{API}/admin/connectors", headers={"X-Admin-Password": ADMIN_PWD}, timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "supported" in data and "backlog" in data and "redetect" in data
