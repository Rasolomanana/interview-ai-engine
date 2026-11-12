"""Radar iter 57: no duplicate AI analyses on re-run during ai_pending (ai_claimed_at + busy_ai), speed + timings, cleanup of the fresh TEST_ member."""
import os
import time
import uuid

import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
A = f"{BASE_URL}/api"
R = f"{A}/careeros/radar"
S = {}


def _env():
    e = {}
    with open("/app/backend/.env") as f:
        for line in f:
            if "=" in line:
                k, v = line.strip().split("=", 1)
                e[k] = v.strip('"')
    return e


ENV = _env()
DB = MongoClient(ENV["MONGO_URL"])[ENV["DB_NAME"]]  # read-only checks


def login(email, pw):
    r = requests.post(f"{A}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def dash(h):
    r = requests.get(f"{R}/dashboard", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def wait_done(h, t0, limit=120):
    d = None
    while time.time() - t0 < limit:
        d = dash(h)
        lr = d.get("last_run") or {}
        if lr.get("status") in ("done", "error"):
            return d
        time.sleep(2)
    return d


@pytest.fixture(scope="module")
def fresh():
    src = login("membre.test@careeros.dev", "CareerOS2026!")
    prof = requests.get(f"{A}/careeros/profile", headers=src, timeout=20).json()
    sett = requests.get(f"{R}/settings", headers=src, timeout=20).json()
    email, pw = f"test_radar_dedupe_{uuid.uuid4().hex[:8]}@careeros.dev", "CareerOS2026!"
    r = requests.post(f"{A}/auth/register", json={"email": email, "password": pw, "name": "TEST_ Radar Dedupe"}, timeout=20)
    assert r.status_code in (200, 201), r.text
    h = login(email, pw)
    me = requests.get(f"{A}/auth/me", headers=h, timeout=20).json()
    S["uid"] = me.get("id") or (me.get("user") or {}).get("id")
    body = {k: v for k, v in prof.items() if k not in ("user_id", "skills_detected", "updated_at", "career_score")}
    assert requests.put(f"{A}/careeros/profile", json=body, headers=h, timeout=30).status_code == 200
    sbody = {k: sett.get(k) for k in ("keywords", "location", "radius", "zones", "companies", "sources", "expand") if k in sett}
    print("settings put", requests.put(f"{R}/settings", json=sbody, headers=h, timeout=30).status_code)
    print("fresh member", email, S["uid"])
    S["email"] = email
    return h


class TestNoDuplicateAI:
    def test_01_first_run_fast(self, fresh):
        t0 = time.time()
        r = requests.post(f"{R}/run", headers=fresh, timeout=30)
        assert r.status_code == 200, r.text
        d = wait_done(fresh, t0)
        S["el1"] = round(time.time() - t0, 1)
        lr = d["last_run"]
        S["run1"] = lr
        print("run1 elapsed", S["el1"], lr.get("status"), "timings", lr.get("timings"), "new", lr.get("new"), "analyzed", lr.get("analyzed"), "ai_pending", lr.get("ai_pending"))
        assert lr["status"] == "done"
        assert S["el1"] < 60
        for k in ("sources_s", "store_rules_s", "total_s"):
            assert k in lr["timings"]
        assert lr.get("ai_pending") is True

    def test_02_claimed_marked(self, fresh):
        claimed = list(DB.radar_offers.find({"user_id": S["uid"], "ai_claimed_at": {"$exists": True}}, {"_id": 0, "id": 1, "method": 1}))
        print("claimed after run1", len(claimed))
        S["claimed1"] = {c["id"] for c in claimed}
        assert 1 <= len(claimed) <= 5

    def test_03_rerun_during_ai_pending(self, fresh):
        lr = dash(fresh)["last_run"]
        S["pending_at_rerun"] = lr.get("ai_pending")
        t0 = time.time()
        r = requests.post(f"{R}/run", headers=fresh, timeout=30)
        print("rerun during ai_pending=", lr.get("ai_pending"), r.status_code, r.text[:150])
        assert r.status_code == 200
        time.sleep(2)
        d = wait_done(fresh, t0)
        lr2 = d["last_run"]
        S["run2"] = lr2
        print("run2 elapsed", round(time.time() - t0, 1), lr2.get("status"), "id differs", lr2["id"] != S["run1"]["id"], "ai_pending", lr2.get("ai_pending"), "timings", lr2.get("timings"))
        assert lr2["id"] != S["run1"]["id"]
        assert lr2["status"] == "done"

    def test_04_all_finish_no_duplicate(self, fresh):
        t0 = time.time()
        runs = []
        while time.time() - t0 < 280:
            runs = requests.get(f"{R}/runs", headers=fresh, timeout=30).json()
            if all(x.get("status") != "running" and not x.get("ai_pending") for x in runs):
                break
            time.sleep(5)
        for x in runs:
            print("run", x["id"][:8], x["status"], "ai_pending", x.get("ai_pending"), "ai_analyzed", x.get("ai_analyzed"), "timings", x.get("timings"))
        total = sum(x.get("ai_analyzed") or 0 for x in runs)
        ia = list(DB.radar_offers.find({"user_id": S["uid"], "ai_analyzed_at": {"$exists": True, "$ne": None}}, {"_id": 0, "id": 1, "ai_analyzed_at": 1, "method": 1}))
        claimed = list(DB.radar_offers.find({"user_id": S["uid"], "ai_claimed_at": {"$exists": True}}, {"_id": 0, "id": 1}))
        d = dash(fresh)
        print("sum ai_analyzed", total, "distinct ai offers", len(ia), "ai_today", d.get("ai_today"), "claimed total", len(claimed))
        assert all(not x.get("ai_pending") for x in runs)
        assert all("ai_s" in (x.get("timings") or {}) for x in runs if x.get("ai_analyzed") is not None and x.get("ai_pending") is False and x.get("budget") is not None and (x.get("ai_analyzed") or 0) > 0)
        assert total <= 5
        assert len(ia) <= 5
        assert total == len(ia), "same offer analysed twice by AI"
        assert d["ai_today"] <= 5


def teardown_module(module):
    uid = S.get("uid")
    if not uid:
        return
    print("cleanup user", uid)
    # authenticated self-delete if available, else report the id
    try:
        h = login(S["email"], "CareerOS2026!")
        for path in ("/auth/me", "/careeros/account"):
            r = requests.delete(f"{A}{path}", headers=h, timeout=30)
            print("delete", path, r.status_code)
            if r.status_code in (200, 204):
                break
    except Exception as e:  # noqa: BLE001
        print("cleanup failed", e)
