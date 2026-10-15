"""Admin: /api/admin/connectors — backlog of unsupported/blocked portals + active connectors stats."""
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_PWD = os.environ.get("ADMIN_PASSWORD", "admin2026")
EP = f"{BASE_URL}/api/admin/connectors"


class TestAdminConnectorsAuth:
    def test_missing_password_rejected(self):
        r = requests.get(EP)
        assert r.status_code in (401, 403), r.text

    def test_wrong_password_rejected(self):
        r = requests.get(EP, headers={"X-Admin-Password": "wrong"})
        assert r.status_code in (401, 403), r.text


class TestAdminConnectorsShape:
    @pytest.fixture(scope="class")
    def data(self):
        r = requests.get(EP, headers={"X-Admin-Password": ADMIN_PWD}, timeout=30)
        assert r.status_code == 200, r.text
        return r.json()

    def test_top_level_keys(self, data):
        assert "backlog" in data and isinstance(data["backlog"], list)
        assert "supported" in data and isinstance(data["supported"], list)

    def test_backlog_row_shape(self, data):
        for r in data["backlog"]:
            for k in ("connector", "blocked", "companies", "members", "examples",
                      "offers_30d", "difficulty", "score", "priority"):
                assert k in r, f"missing {k} in backlog row {r}"
            assert isinstance(r["blocked"], bool)
            assert isinstance(r["companies"], int) and r["companies"] >= 0
            assert isinstance(r["members"], int) and r["members"] >= 0
            assert isinstance(r["examples"], list)
            assert isinstance(r["offers_30d"], int) and r["offers_30d"] >= 0
            assert r["priority"] in ("Élevée", "Moyenne", "Faible", "Aucune (protection)")
            # blocked rows must have "Aucune (protection)" priority
            if r["blocked"]:
                assert r["priority"] == "Aucune (protection)"

    def test_supported_row_shape(self, data):
        for r in data["supported"]:
            for k in ("kind", "label", "companies", "members", "fetched",
                      "matched", "success_pct", "fallback", "blocked"):
                assert k in r, f"missing {k} in supported row {r}"
            assert isinstance(r["companies"], int) and r["companies"] >= 0
            assert isinstance(r["members"], int) and r["members"] >= 0
            assert r["success_pct"] is None or (0 <= r["success_pct"] <= 100)

    def test_backlog_sorted_by_score_desc(self, data):
        scores = [r["score"] for r in data["backlog"]]
        assert scores == sorted(scores, reverse=True), f"backlog not sorted desc: {scores}"

    def test_supported_sorted_by_companies_desc(self, data):
        comps = [r["companies"] for r in data["supported"]]
        assert comps == sorted(comps, reverse=True), f"supported not sorted desc: {comps}"
