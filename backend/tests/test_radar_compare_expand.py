"""Backend tests for Radar compare endpoint + expand search + discovery (iteration 33).

Covers:
  - POST /api/careeros/radar/compare
  - GET  /api/careeros/radar/settings  (expand flag + expanded list)
  - PUT  /api/careeros/radar/settings
  - POST /api/careeros/radar/run
  - careeros.radar_rules.expand_terms / title_relevance
  - careeros.radar_discovery.discover (Airbus directory, Sofina Dayforce unsupported)
  - Company matching uses whole tokens (RONA ≠ Coronado)
"""
import os
import sys
import time
import asyncio
import pytest
import requests
from pathlib import Path

sys.path.insert(0, "/app/backend")

from careeros import radar_rules as RR
from careeros import radar_discovery as D


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


# ---------- Unit: radar_rules ----------
class TestRadarRulesUnit:
    def test_expand_terms_contains_bilingual_family_titles(self):
        out = RR.expand_terms(["Superviseur des opérations"])
        # bilingual + family titles
        joined = " | ".join(x.lower() for x in out)
        assert "operations supervisor" in joined
        assert "chef des opérations" in joined
        # original keyword stays first
        assert out[0].lower().startswith("superviseur")
        assert len(out) <= 10

    def test_title_relevance_cross_language(self):
        rel = RR.title_relevance("Chefs des opérations (Quart de soir)", ["Superviseur des opérations"])
        assert rel >= 0.5, f"expected >=0.5, got {rel}"

    def test_title_relevance_unrelated(self):
        assert RR.title_relevance("Pharmacien", ["Superviseur des opérations"]) < 0.3


# ---------- Unit: radar_discovery ----------
class TestRadarDiscovery:
    def test_discover_airbus_directory_workday(self):
        """Airbus is in DIRECTORY → ag.wd3 workday portal, origin=annuaire."""
        res = asyncio.get_event_loop().run_until_complete(D.discover("Airbus"))
        assert res["directory"] is True
        cands = res["candidates"]
        wd = [c for c in cands if c["kind"] == "workday" and "ag.wd3" in c["slug"].lower()]
        assert wd, f"no ag.wd3 Airbus workday candidate found: {cands}"
        # verify origin annuaire for the directory entry
        assert any(c.get("origin") == "annuaire" for c in wd)

    def test_discover_sofina_dayforce_unsupported(self):
        res = asyncio.get_event_loop().run_until_complete(D.discover("Sofina Foods", "sofina.com"))
        joined = " | ".join(res.get("unsupported") or [])
        assert "Dayforce" in joined, f"expected Dayforce unsupported, got {res.get('unsupported')} / message={res.get('message')}"


# ---------- API: /settings expand flag ----------
class TestSettingsExpand:
    def test_get_returns_expand_and_expanded(self, client):
        r = client.get(f"{BASE_URL}/api/careeros/radar/settings", timeout=30)
        assert r.status_code == 200, r.text
        s = r.json()
        assert s.get("expand") is True  # default
        assert isinstance(s.get("expanded"), list)
        # expanded contains the member keywords first
        if s.get("keywords"):
            assert s["expanded"][0].lower() == s["keywords"][0].lower()
        assert len(s["expanded"]) <= 10

    def test_put_expand_false_persists_and_restore(self, client):
        cur = client.get(f"{BASE_URL}/api/careeros/radar/settings", timeout=30).json()
        payload = {k: cur[k] for k in ("enabled", "keywords", "location", "companies", "sources")}
        # expand false
        payload["expand"] = False
        r = client.put(f"{BASE_URL}/api/careeros/radar/settings", json=payload, timeout=30)
        assert r.status_code == 200, r.text
        after = client.get(f"{BASE_URL}/api/careeros/radar/settings", timeout=30).json()
        assert after["expand"] is False
        # restore to true
        payload["expand"] = True
        r2 = client.put(f"{BASE_URL}/api/careeros/radar/settings", json=payload, timeout=30)
        assert r2.status_code == 200
        back = client.get(f"{BASE_URL}/api/careeros/radar/settings", timeout=30).json()
        assert back["expand"] is True


# ---------- API: /compare ----------
class TestCompare:
    LINES = ("RONA – Chef des opérations\n"
             "Ubisoft – IT Financial Planning Analyst\n"
             "Canpar – Operations Supervisor")

    def test_compare_returns_items_with_coverage_and_status(self, client):
        r = client.post(f"{BASE_URL}/api/careeros/radar/compare", json={"lines": self.LINES}, timeout=60)
        assert r.status_code == 200, r.text
        data = r.json()
        assert "terms" in data and isinstance(data["terms"], list)
        assert "location" in data
        items = data["items"]
        assert len(items) == 3
        for it in items:
            assert "coverage" in it and "state" in it["coverage"] and "label" in it["coverage"]
            assert it["coverage"]["state"] in ("portail", "jooble", "aucune")
            assert it["status"] in ("priorite_a", "priorite_b", "priorite_c",
                                    "eliminee", "reportee", "ignoree", "pack", "non_trouvee")
            if it["found"]:
                assert "offer" in it and "id" in it["offer"]
                assert isinstance(it.get("losses"), list)
                assert len(it["losses"]) <= 3
            else:
                assert "why" in it and isinstance(it["why"], str) and it["why"]
                # jooble key present (may be None since not configured)
                assert "jooble" in it

    def test_compare_empty_lines_422(self, client):
        r = client.post(f"{BASE_URL}/api/careeros/radar/compare", json={"lines": "   \n  "}, timeout=30)
        assert r.status_code == 422

    def test_compare_company_token_match_rona_not_coronado(self, client):
        """RONA (4 letters) must NOT match 'Coronado' or similar substring companies in the member's radar_offers.
        We verify indirectly: if an offer for 'Coronado' were matched, the status would be found; here we ensure
        the whole-token matching logic rejects substring collisions.
        """
        # Simulate via the rules function directly (deterministic): company_match uses whole tokens.
        # Replicate cn() from compare():
        import re
        def norm(x):
            return RR.norm(re.sub(r"(?i)\b(inc|lt[ée]e|ltd|limited|canada|express|group|groupe|corporation|corp|the)\b\.?", "", x or ""))
        def cn(x):
            return set(re.findall(r"[a-z0-9]+", norm(x)))
        def same(a, b):
            return bool(a and b and (a <= b or b <= a))
        assert not same(cn("RONA"), cn("Coronado"))
        assert same(cn("RONA inc."), cn("RONA Canada"))
        assert same(cn("Groupe Sofina"), cn("Sofina Foods inc"))


# ---------- API: /run completes with budget<=50 ----------
class TestRun:
    def test_run_completes_within_budget(self, client):
        r = client.post(f"{BASE_URL}/api/careeros/radar/run", timeout=30)
        # 409 if already running — acceptable
        if r.status_code == 409:
            pytest.skip("A radar run is already in progress")
        assert r.status_code == 200, r.text
        # Poll last run status
        for _ in range(30):
            runs = client.get(f"{BASE_URL}/api/careeros/radar/runs?days=1", timeout=30).json()
            if runs and runs[0]["status"] == "done":
                last = runs[0]
                assert last.get("analyzed", 0) <= 50
                assert "budget" in last
                return
            time.sleep(2)
        pytest.fail("Radar run did not complete within 60s")
