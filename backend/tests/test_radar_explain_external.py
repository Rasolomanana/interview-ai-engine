"""Backend tests for new Radar features: GET /explain and POST /external.

New endpoints (iteration 32):
  - GET  /api/careeros/radar/offers/{id}/explain
  - POST /api/careeros/radar/external
  - requirements_rules / requirements_ai persisted on offers
  - _analyzed_today excludes externe offers from daily quota
"""
import os
import pytest
import requests
from pathlib import Path


def _load_frontend_url() -> str:
    v = os.environ.get("REACT_APP_BACKEND_URL")
    if v:
        return v.rstrip("/")
    for ln in Path("/app/frontend/.env").read_text().splitlines():
        if ln.startswith("REACT_APP_BACKEND_URL="):
            return ln.split("=", 1)[1].strip().rstrip("/")
    raise RuntimeError("REACT_APP_BACKEND_URL not found")


BASE_URL = _load_frontend_url()
EMAIL = "membre.test@careeros.dev"
PASSWORD = "CareerOS2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD}, timeout=30)
    assert r.status_code == 200, r.text
    s.headers["Authorization"] = f"Bearer {r.json()['access_token']}"
    return s


@pytest.fixture(scope="module")
def dashboard(client):
    r = client.get(f"{BASE_URL}/api/careeros/radar/dashboard", timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


# ---- /explain ----
class TestExplain:
    def test_explain_rule_offer(self, client, dashboard):
        """GET /explain on a rule-scored offer returns IPS criteria + requirements_rules."""
        pool = (dashboard.get("top_a") or []) + (dashboard.get("top_b") or []) + (dashboard.get("ignored") or [])
        rule_offers = [o for o in pool if o.get("ips") and o.get("method") != "ia"]
        if not rule_offers:
            pytest.skip("No rule-scored offer available for this member")
        o = rule_offers[0]
        r = client.get(f"{BASE_URL}/api/careeros/radar/offers/{o['id']}/explain", timeout=30)
        assert r.status_code == 200, r.text
        data = r.json()
        assert data["id"] == o["id"]
        assert data["ips"]["score"] >= 0
        assert "criteria" in data["ips"] and len(data["ips"]["criteria"]) > 0
        # new field on the offer
        assert "requirements_rules" in data
        reqs = data["requirements_rules"]
        assert isinstance(reqs, list)
        for r_ in reqs:
            assert r_["status"] in ("ok", "missing", "unknown")
            assert r_["source"] == "regles"
            assert r_["label"]

    def test_explain_404(self, client):
        r = client.get(f"{BASE_URL}/api/careeros/radar/offers/does-not-exist/explain", timeout=15)
        assert r.status_code == 404


# ---- /external ----
class TestExternal:
    PAYLOAD = {
        "title": "Chef des opérations",
        "company": "TEST_RONA",
        "location": "Boucherville, QC",
        "url": "",
        "text": ("Chef des opérations — Centre de distribution. "
                 "Vous dirigerez une équipe en environnement syndiqué sur des quarts de soir et de nuit. "
                 "Baccalauréat ou DEC en logistique. Bilinguisme français / anglais requis. "
                 "5 ans d'expérience en gestion d'équipe, supervision, santé et sécurité (SST). "
                 "Compétences : Microsoft Office, Outlook, préparation de commandes, inventaire, "
                 "expedition, réception. Permis de conduire obligatoire. "
                 "Responsabilités : coordonner la réception et l'expédition, gérer une équipe de 20 personnes.") * 1,
    }

    def test_external_bad_short_text(self, client):
        r = client.post(f"{BASE_URL}/api/careeros/radar/external",
                        json={**self.PAYLOAD, "text": "trop court"}, timeout=30)
        assert r.status_code == 422

    def test_external_linkedin_url_rejected(self, client):
        r = client.post(f"{BASE_URL}/api/careeros/radar/external",
                        json={"title": "", "company": "", "location": "", "text": "",
                              "url": "https://www.linkedin.com/jobs/view/4001"}, timeout=30)
        # LinkedIn page has no public JobPosting JSON-LD → 422 with helpful message
        assert r.status_code == 422
        assert "Lien illisible" in r.json().get("detail", "") or "copie" in r.json().get("detail", "").lower()

    def test_external_create_and_persist(self, client):
        """Pastes an external offer → scored by rules → source=externe, ips present, requirements_rules present."""
        r = client.post(f"{BASE_URL}/api/careeros/radar/external", json=self.PAYLOAD, timeout=60)
        assert r.status_code == 200, r.text
        o = r.json()
        assert o["source"] == "externe"
        assert o["company"] == "TEST_RONA"
        assert o["title"] == "Chef des opérations"
        assert o["method"] == "regles"
        assert o["ips"]["score"] >= 0
        assert isinstance(o.get("requirements_rules"), list) and len(o["requirements_rules"]) > 0
        # Chef des opérations must NOT be flagged as 'senior' due to SENIOR regex update (chef removed)
        # Verify via explain the stored data
        explain = client.get(f"{BASE_URL}/api/careeros/radar/offers/{o['id']}/explain", timeout=30).json()
        labels = [r_["label"] for r_ in explain.get("requirements_rules", [])]
        # At least one explicit requirement must be present (languages/degrees/context detected from text)
        assert any("Bilinguisme" in l or "Baccalauréat" in l or "DEC" in l or "syndiqué" in l.lower()
                   or "équipe" in l.lower() or "quart" in l.lower() for l in labels), labels
        # Cleanup: ignore the offer (keeps DB clean-ish; no delete endpoint)
        client.post(f"{BASE_URL}/api/careeros/radar/offers/{o['id']}/ignore", timeout=15)

    def test_external_does_not_count_against_quota(self, client):
        """External offers must be excluded from the daily analyzed-today counter."""
        before = client.get(f"{BASE_URL}/api/careeros/radar/dashboard", timeout=20).json().get("analyzed_today", 0)
        r = client.post(f"{BASE_URL}/api/careeros/radar/external",
                        json={**self.PAYLOAD, "company": "TEST_RONA_QUOTA"}, timeout=60)
        assert r.status_code == 200, r.text
        after = client.get(f"{BASE_URL}/api/careeros/radar/dashboard", timeout=20).json().get("analyzed_today", 0)
        assert after == before, f"analyzed_today changed {before}→{after} after external analysis"
        client.post(f"{BASE_URL}/api/careeros/radar/offers/{r.json()['id']}/ignore", timeout=15)


# ---- rule changes: chef des opérations should not get 'senior' knockout ----
class TestRuleChanges:
    def test_requirements_module_detects_chef_as_lead(self):
        """Direct unit check: the rule module now recognises 'chef des opérations' as encadrement, not senior."""
        import sys
        sys.path.insert(0, "/app/backend")
        from careeros import radar_rules as RR  # noqa
        text = "Chef des opérations centre de distribution gestion d'équipe"
        # SENIOR no longer matches 'chef'
        assert not RR.SENIOR.search(RR.norm(text))
        # requirements() surfaces the supervision context
        offer = {"title": "Chef des opérations", "description": text + " environnement syndiqué quarts de soir SST permis de conduire"}
        profile = {"skills": ["Microsoft Office"]}
        cv = "Expérience 7 ans en supervision gestion d'équipe santé et sécurité SST Microsoft Office Outlook permis de conduire"
        reqs = RR.requirements(offer, cv, profile)
        labels = [r["label"] for r in reqs]
        assert any("Gestion d'équipe" in l or "supervision" in l.lower() for l in labels), labels
        assert any("Santé et sécurité" in l for l in labels), labels
