"""Lot B admin tests: gemini_calls / server_calls / simulations_detail / mixed badge.

Seeds via POST /api/track and verifies GET /api/admin/stats aggregation.
Cleans up seeded testsim_* events at end.
"""
import os
import uuid
import time
from datetime import datetime

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_PWD = os.environ.get("ADMIN_PASSWORD") or "admin2026"
TRACK = f"{BASE_URL}/api/track"
STATS = f"{BASE_URL}/api/admin/stats"


@pytest.fixture(scope="module")
def seeded_sessions():
    """Create 3 sessions: pure gemini, pure anthropic, mixed."""
    # Backend truncates session_id to [:8] for display. Keep "testsim" prefix
    # (per instructions) with unique 8th character so rows don't collide.
    uid = uuid.uuid4().hex[:6]
    sess = {
        "gem": f"testsimG_{uid}_" + uuid.uuid4().hex[:6],
        "ant": f"testsimA_{uid}_" + uuid.uuid4().hex[:6],
        "mix": f"testsimM_{uid}_" + uuid.uuid4().hex[:6],
    }

    def post(sid, provider, cost):
        r = requests.post(TRACK, json={
            "type": "llm_call",
            "session_id": sid,
            "meta": {"provider": provider, "mode": "server" if provider != "gemini" else "gemini", "cost": cost},
        }, timeout=15)
        assert r.status_code in (200, 201), f"track failed {r.status_code} {r.text}"

    post(sess["gem"], "gemini", 0.001)
    post(sess["gem"], "gemini", 0.002)
    post(sess["ant"], "anthropic", 0.004)
    post(sess["mix"], "gemini", 0.001)
    post(sess["mix"], "openrouter", 0.003)

    # Small delay to ensure order by first timestamp
    time.sleep(0.5)
    yield sess

    # Cleanup: delete seeded events directly from Mongo
    try:
        from pymongo import MongoClient
        mongo_url = os.environ.get("MONGO_URL") or "mongodb://localhost:27017"
        db_name = os.environ.get("DB_NAME") or "test_database"
        client = MongoClient(mongo_url)
        res = client[db_name].admin_events.delete_many(
            {"session_id": {"$in": list(sess.values())}}
        )
        print(f"[cleanup] deleted {res.deleted_count} seeded events")
    except Exception as e:
        print(f"[cleanup] skipped: {e}")


def _get_stats():
    r = requests.get(STATS, headers={"X-Admin-Password": ADMIN_PWD}, timeout=20)
    assert r.status_code == 200, f"{r.status_code} {r.text}"
    return r.json()


# --- Auth gate ---
def test_stats_requires_password():
    r = requests.get(STATS, timeout=10)
    assert r.status_code == 401


def test_stats_wrong_password():
    r = requests.get(STATS, headers={"X-Admin-Password": "nope"}, timeout=10)
    assert r.status_code == 401


# --- Shape ---
def test_stats_has_llm_split_and_simulations_detail(seeded_sessions):
    data = _get_stats()
    assert "llm" in data
    for k in ("gemini_calls", "server_calls", "gemini_cost", "server_cost"):
        assert k in data["llm"], f"missing llm.{k}"
    assert isinstance(data["llm"]["gemini_calls"], int)
    assert isinstance(data["llm"]["server_calls"], int)
    assert "simulations_detail" in data
    assert isinstance(data["simulations_detail"], list)
    assert len(data["simulations_detail"]) <= 100


# --- Aggregation correctness ---
def test_simulations_detail_contains_seeded(seeded_sessions):
    data = _get_stats()
    rows = {r["session_id"]: r for r in data["simulations_detail"]}
    gem_pref = seeded_sessions["gem"][:8]
    ant_pref = seeded_sessions["ant"][:8]
    mix_pref = seeded_sessions["mix"][:8]
    assert gem_pref in rows, f"gemini session missing. have {list(rows)[:10]}"
    assert ant_pref in rows, "anthropic session missing"
    assert mix_pref in rows, "mixed session missing"

    g = rows[gem_pref]
    assert g["gemini_calls"] == 2 and g["server_calls"] == 0
    assert g["main_provider"] == "gemini"
    assert g["mixed"] is False
    assert g["cost"] == pytest.approx(0.003, abs=1e-4)

    a = rows[ant_pref]
    assert a["gemini_calls"] == 0 and a["server_calls"] == 1
    assert a["main_provider"] == "anthropic"
    assert a["mixed"] is False

    m = rows[mix_pref]
    assert m["gemini_calls"] == 1 and m["server_calls"] == 1
    assert m["mixed"] is True
    assert m["providers"].get("gemini") == 1
    assert m["providers"].get("openrouter") == 1


def test_simulations_detail_sorted_newest_first(seeded_sessions):
    data = _get_stats()
    tss = [r["ts"] for r in data["simulations_detail"] if r["ts"]]
    assert tss == sorted(tss, reverse=True), "simulations_detail not sorted desc"


def test_llm_split_consistency(seeded_sessions):
    data = _get_stats()
    llm = data["llm"]
    assert llm["gemini_calls"] + llm["server_calls"] == llm["calls"]
    # Costs sum within rounding
    assert abs((llm["gemini_cost"] + llm["server_cost"]) - llm["cost"]) < 0.01
