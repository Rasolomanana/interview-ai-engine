"""CareerOS Radar — AI cost-reduction lot backend tests.
Covers: deterministic rules pre-score (method='regles'), AI confirmation of top-5
per day (method='ia'), /offers/{id}/deep endpoint, rule knockouts (foreign location,
mismatched profession family), cron with X-Cron-Secret filtering by active members,
admin credits/alert-settings/alert-test with password gating + validation.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

ENV = {}
with open("/app/backend/.env") as f:
    for line in f:
        if "=" in line and not line.startswith("#"):
            k, v = line.strip().split("=", 1)
            ENV[k] = v.strip('"')
RADAR_CRON_SECRET = ENV.get("RADAR_CRON_SECRET")
ADMIN_PASSWORD = ENV.get("ADMIN_PASSWORD")

ANALYST_CV = (
    "ANALYSTE D'AFFAIRES SENIOR — 10 ans d'expérience à Québec, Canada.\n"
    "Compétences : SQL, Python, Power BI, Tableau, Excel, DAX, Power Query, analyse de données, "
    "reporting, tableaux de bord, KPI, modélisation, forecasting, gestion de projet, agile, scrum.\n"
    "Certifications : CBAP, Scrum Master.\n"
    "Langues : français (langue maternelle), anglais professionnel.\n"
    "Formations : Baccalauréat en administration des affaires 2008-2012.\n"
    "Expérience : 2013-2024 analyste d'affaires chez Desjardins — livraison de 20 dashboards Power BI "
    "augmentant la productivité de 25 %. Pilotage d'un projet ERP de 5 M$.\n"
) * 2  # ensure cv_years detects >= some years and length > 80


# ---------------- Fixtures ----------------
@pytest.fixture(scope="module")
def fresh_member():
    email = f"test_costred_{uuid.uuid4().hex[:8]}@careeros.dev"
    pw = "CareerOS2026!"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "Test CostRed"}, timeout=15)
    assert r.status_code in (200, 201), r.text
    tok = r.json()["access_token"]
    h = {"Authorization": f"Bearer {tok}"}
    # Set CV + profile (analyst, Québec)
    pr = requests.put(f"{API}/careeros/profile", headers=h, json={
        "full_name": "Test CostRed", "headline": "Analyste senior", "location": "Québec",
        "cv_text": ANALYST_CV, "target_roles": "analyste, analyste d'affaires, data analyst",
        "goals": ["trouver un emploi"], "skills": ["SQL", "Python", "Power BI"],
        "languages": ["français", "anglais"], "sectors": "", "salary_expectation": "",
        "certifications": ["CBAP"], "education": [], "achievements": "", "promotions": 0,
    }, timeout=20)
    assert pr.status_code == 200, pr.text
    # Radar settings: 2 Workday + Amazon + analyst keywords
    rs = requests.put(f"{API}/careeros/radar/settings", headers=h, json={
        "enabled": True, "keywords": ["analyste", "analyst"], "location": "Québec",
        "sources": ["jooble", "workday", "boards"],
        "companies": [
            {"name": "Desjardins", "portal_url": "https://desjardins.wd10.myworkdayjobs.com/fr-CA/Desjardins"},
            {"name": "Amazon", "portal_url": "https://www.amazon.jobs/fr"},
        ],
    }, timeout=20)
    assert rs.status_code == 200, rs.text
    return {"h": h, "email": email}


def _wait_run_done(headers, timeout_s=300):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        d = requests.get(f"{API}/careeros/radar/dashboard", headers=headers, timeout=20).json()
        lr = d.get("last_run")
        if lr and lr.get("status") == "done":
            return d
        time.sleep(5)
    pytest.fail("Radar run did not finish in time")


# ---------------- Admin credits ----------------
class TestAdminCredits:
    def test_credits_requires_password(self):
        r = requests.get(f"{API}/admin/credits", timeout=15)
        assert r.status_code == 401

    def test_credits_shape_preview(self):
        assert ADMIN_PASSWORD
        r = requests.get(f"{API}/admin/credits", headers={"X-Admin-Password": ADMIN_PASSWORD}, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("openrouter", "anthropic", "links", "alert", "email_ready"):
            assert k in d, k
        # Preview: OPENROUTER_API_KEY not set → configured=False
        assert d["openrouter"]["configured"] is False
        assert d["links"]["openrouter"] == "https://openrouter.ai/settings/credits"
        assert d["links"]["anthropic"] == "https://console.anthropic.com/settings/billing"
        for k in ("email", "threshold"):
            assert k in d["alert"], k

    def test_alert_settings_invalid_email(self):
        r = requests.put(f"{API}/admin/alert-settings", headers={"X-Admin-Password": ADMIN_PASSWORD},
                         json={"email": "not-an-email", "threshold": 20}, timeout=15)
        assert r.status_code == 422, r.text

    def test_alert_settings_invalid_threshold(self):
        r = requests.put(f"{API}/admin/alert-settings", headers={"X-Admin-Password": ADMIN_PASSWORD},
                         json={"email": "delivered@resend.dev", "threshold": 3}, timeout=15)
        assert r.status_code == 422, r.text

    def test_alert_settings_valid_persists(self):
        r = requests.put(f"{API}/admin/alert-settings", headers={"X-Admin-Password": ADMIN_PASSWORD},
                         json={"email": "delivered@resend.dev", "threshold": 20}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["email"] == "delivered@resend.dev"
        assert d["threshold"] == 20
        # reload via GET
        r2 = requests.get(f"{API}/admin/credits", headers={"X-Admin-Password": ADMIN_PASSWORD}, timeout=15).json()
        assert r2["alert"]["email"] == "delivered@resend.dev"
        assert r2["alert"]["threshold"] == 20

    def test_alert_test_preview_not_configured(self):
        # Pre-save valid settings so the endpoint has something to work with
        requests.put(f"{API}/admin/alert-settings", headers={"X-Admin-Password": ADMIN_PASSWORD},
                     json={"email": "delivered@resend.dev", "threshold": 20}, timeout=15)
        r = requests.post(f"{API}/admin/alert-test", headers={"X-Admin-Password": ADMIN_PASSWORD}, timeout=20)
        # Preview: no OPENROUTER key → sent=False with reason, status 200
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["sent"] is False
        assert "OpenRouter" in (d.get("reason") or "")

    def test_llm_health_requires_password(self):
        r = requests.get(f"{API}/admin/llm-health", timeout=15)
        assert r.status_code == 401
        r2 = requests.get(f"{API}/admin/llm-health", headers={"X-Admin-Password": ADMIN_PASSWORD}, timeout=30)
        assert r2.status_code == 200
        assert "providers" in r2.json()


# ---------------- Deterministic rules (unit, no HTTP) ----------------
class TestRulesKnockouts:
    def test_knockout_india_location(self):
        from careeros import radar_rules as RR
        off = {"title": "Business Analyst", "description": "SQL Power BI dashboards reporting", "location": "Bangalore, India", "company": "Acme"}
        d = RR.score_offer(off, ANALYST_CV, {"location": "Québec", "target_roles": "analyste"}, ["analyste"])
        assert d["knockout"]["present"] is True
        assert "hors du Canada" in d["knockout"]["detail"]

    def test_knockout_usa_location(self):
        from careeros import radar_rules as RR
        off = {"title": "Analyst", "description": "SQL dashboards", "location": "New York, United States", "company": "Acme"}
        d = RR.score_offer(off, ANALYST_CV, {"location": "Québec", "target_roles": "analyste"}, ["analyste"])
        assert d["knockout"]["present"] is True

    def test_knockout_software_engineer_for_analyst(self):
        from careeros import radar_rules as RR
        off = {"title": "Software Engineer", "description": "Java Python backend microservices Kubernetes Docker",
               "location": "Montréal, QC", "company": "Acme"}
        d = RR.score_offer(off, ANALYST_CV, {"location": "Québec", "target_roles": "analyste, analyste d'affaires"}, ["analyste"])
        assert d["knockout"]["present"] is True
        # family mismatch message
        assert any("Métier différent" in x or "software" in x.lower() or "engineer" in x.lower() for x in d["knockout"]["detail"].split(";"))

    def test_decision_summary_rules_text(self):
        from careeros import radar_rules as RR
        off = {"title": "Analyste d'affaires", "description": "SQL Power BI dashboards reporting KPI tableau de bord",
               "location": "Québec, QC", "company": "Petit employeur"}
        d = RR.score_offer(off, ANALYST_CV, {"location": "Québec", "target_roles": "analyste d'affaires"}, ["analyste"])
        assert "Pré-analyse par règles" in d["decision_summary"]


# ---------------- Fresh member run → method 'regles' + at most 5 AI ----------------
class TestFreshRun:
    def test_run_and_dashboard_methods(self, fresh_member):
        h = fresh_member["h"]
        # start manual run
        r = requests.post(f"{API}/careeros/radar/run", headers=h, timeout=20)
        assert r.status_code == 200, r.text
        d = _wait_run_done(h, timeout_s=300)
        # dashboard contract
        assert d["ai_top"] == 5, d
        assert d["deep_limit"] == 25, d
        assert d["ai_today"] <= 5, d
        offers = d["top_a"] + d["top_b"] + d["ignored"] + d["new_today"]
        # de-dupe by id
        offers = {o["id"]: o for o in offers}.values()
        offers = [o for o in offers if o.get("ips")]
        if not offers:
            pytest.skip("No analyzed offers available (sources may have returned nothing in preview)")
        regles = [o for o in offers if o.get("method") == "regles"]
        ia = [o for o in offers if o.get("method") == "ia"]
        assert regles, "At least some offers must be rule-scored"
        # AI offers ≤ 5
        assert len(ia) <= 5
        # method stamped on ips too
        for o in regles[:3]:
            assert o["ips"].get("method") == "regles", o["ips"]
            sm = (o.get("decision_report") or {}).get("summary") or ""
            assert sm.startswith("IPS Radar CareerOS :"), sm[:100]

    def test_deep_rules_offer_becomes_ia(self, fresh_member):
        h = fresh_member["h"]
        d = requests.get(f"{API}/careeros/radar/dashboard", headers=h, timeout=15).json()
        all_offers = {o["id"]: o for o in d["top_a"] + d["top_b"] + d["ignored"]}.values()
        regles = [o for o in all_offers if o.get("method") == "regles" and o.get("status") == "nouvelle"]
        if not regles:
            pytest.skip("No 'regles' offer available for deep test")
        off = regles[0]
        r = requests.post(f"{API}/careeros/radar/offers/{off['id']}/deep", headers=h, timeout=120)
        if r.status_code == 503:
            pytest.skip("AI service momentarily unavailable")
        if r.status_code == 429:
            pytest.skip("Daily deep limit reached")
        assert r.status_code == 200, r.text
        res = r.json()
        assert res["method"] == "ia", res
        assert res["ips"].get("method") == "ia", res["ips"]
        pytest.deep_offer_id = off["id"]  # type: ignore

        # Repeat deep on an 'ia' offer: should return without new AI call (same shape)
        r2 = requests.post(f"{API}/careeros/radar/offers/{off['id']}/deep", headers=h, timeout=30)
        assert r2.status_code == 200
        assert r2.json()["method"] == "ia"

    def test_deep_cross_member_404(self, fresh_member):
        off_id = getattr(pytest, "deep_offer_id", None)
        if not off_id:
            pytest.skip("No offer id from previous test")
        # Register another member
        email = f"test_other_{uuid.uuid4().hex[:8]}@careeros.dev"
        r = requests.post(f"{API}/auth/register", json={"email": email, "password": "CareerOS2026!", "name": "Other"}, timeout=15)
        tok = r.json()["access_token"]
        h2 = {"Authorization": f"Bearer {tok}"}
        r2 = requests.post(f"{API}/careeros/radar/offers/{off_id}/deep", headers=h2, timeout=15)
        assert r2.status_code == 404


# ---------------- Cron auth + active member filter ----------------
class TestCron:
    def test_cron_no_secret(self):
        r = requests.post(f"{API}/careeros/radar/cron", timeout=15)
        assert r.status_code == 401

    def test_cron_wrong_secret(self):
        r = requests.post(f"{API}/careeros/radar/cron", headers={"X-Cron-Secret": "nope"}, timeout=15)
        assert r.status_code == 401

    def test_cron_correct_secret_returns_members(self, fresh_member):
        # fresh_member was just created (last_seen_at within 7 days by auth dep)
        # Trigger /me to make sure last_seen_at is set
        requests.get(f"{API}/auth/me", headers=fresh_member["h"], timeout=10)
        assert RADAR_CRON_SECRET
        r = requests.post(f"{API}/careeros/radar/cron", headers={"X-Cron-Secret": RADAR_CRON_SECRET}, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["started"] is True
        # Should be a non-negative integer count
        assert isinstance(d["members"], int) and d["members"] >= 1
