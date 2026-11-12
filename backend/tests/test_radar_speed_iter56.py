"""Radar speed fix (iter 56): fast 'done' status, AI phase after offers visible, data regression checks."""
import os
import time
from concurrent.futures import ThreadPoolExecutor

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api/careeros/radar"
STATE = {}


@pytest.fixture(scope="module")
def h():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "membre.test@careeros.dev", "password": "CareerOS2026!"}, timeout=20)
    if r.status_code != 200:
        pytest.skip("login failed")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def dash(h):
    r = requests.get(f"{API}/dashboard", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


def wait_idle(h, limit=600):
    t = time.time()
    while time.time() - t < limit:
        lr = dash(h).get("last_run") or {}
        if lr.get("status") != "running" and not lr.get("ai_pending"):
            return lr
        time.sleep(5)
    pytest.fail("radar never idle")


# Run: fast completion + timings + offers populated at 'done'
class TestRadarSpeed:
    def test_01_run_done_fast(self, h):
        before = wait_idle(h)
        STATE["prev_run_id"] = before.get("id")
        b = dash(h)
        STATE["ai_today_before"] = b["ai_today"]
        STATE["analyzed_before"] = b["analyzed_today"]
        # concurrent double POST: only one run must start
        with ThreadPoolExecutor(2) as ex:
            rs = list(ex.map(lambda _: requests.post(f"{API}/run", headers=h, timeout=30), range(2)))
        codes = sorted(r.status_code for r in rs)
        STATE["double_codes"] = codes
        print("concurrent POST codes", codes)
        t0 = time.time()
        r2 = requests.post(f"{API}/run", headers=h, timeout=30)
        print("3rd POST while running:", r2.status_code, r2.text[:120])
        STATE["third"] = r2.status_code
        d = None
        while time.time() - t0 < 120:
            d = dash(h)
            lr = d["last_run"]
            if lr["id"] != STATE["prev_run_id"] and lr["status"] == "done":
                break
            time.sleep(3)
        el = time.time() - t0
        print("elapsed to done", round(el, 1), "timings", d["last_run"].get("timings"))
        STATE["done_dash"] = d
        STATE["run"] = d["last_run"]
        assert d["last_run"]["status"] == "done", f"not done after {el}s"
        assert el < 120

    def test_02_timings_and_ai_pending(self, h):
        lr = STATE["run"]
        tm = lr.get("timings") or {}
        for k in ("sources_s", "store_rules_s", "total_s"):
            assert k in tm, tm
        print("ai_pending at done", lr.get("ai_pending"), "ai_analyzed", lr.get("ai_analyzed"))
        assert "ai_pending" in lr
        assert "errors" not in lr and "notices" in lr

    def test_03_offers_populated_rules(self, h):
        d = STATE["done_dash"]
        print("top_a", len(d["top_a"]), "top_b", len(d["top_b"]), "ignored", len(d["ignored"]),
              "new_today", len(d["new_today"]), "analyzed_today_list", len(d["analyzed_today_list"]), "run", {k: STATE["run"].get(k) for k in ("fetched", "new", "known", "analyzed", "skipped_limit", "out_zone", "budget")})
        assert len(d["top_a"]) + len(d["top_b"]) + len(d["ignored"]) > 0
        for o in d["analyzed_today_list"][:20]:
            assert o.get("ips") and o["ips"].get("method") in ("regles", "ia")
        if STATE["run"]["new"]:
            assert len(d["new_today"]) > 0

    def test_04_concurrent_post_only_one_run(self, h):
        codes = STATE["double_codes"]
        assert codes.count(200) == 1 and 409 in codes, codes
        assert STATE["third"] == 409

    def test_05_ai_phase_completes(self, h):
        t0 = time.time()
        lr = STATE["run"]
        while lr.get("ai_pending") and time.time() - t0 < 300:
            time.sleep(5)
            lr = dash(h)["last_run"]
        print("ai phase:", lr.get("ai_analyzed"), lr.get("timings"), "notices", lr.get("notices"))
        STATE["run"] = lr
        assert not lr.get("ai_pending")
        assert 0 <= lr.get("ai_analyzed", 0) <= 5
        if STATE["done_dash"]["last_run"].get("ai_pending"):
            assert "ai_s" in lr["timings"]

    def test_06_ai_marks_offers(self, h):
        d = dash(h)
        ia = [o for o in d["analyzed_today_list"] if o.get("method") == "ia"]
        print("ia offers today", len(ia), "ai_today", d["ai_today"], "before", STATE["ai_today_before"])
        for o in ia:
            assert o.get("ai_analyzed_at")
        assert d["ai_today"] <= 5 + 0 or d["ai_today"] <= d["deep_limit"]
        assert d["analyzed_today"] <= d["daily_limit"] or STATE["run"]["analyzed"] == 0


# Data regression: runs history, run offers kinds, dedupe, seen_runs
class TestRadarDataRegression:
    def test_runs_list(self, h):
        r = requests.get(f"{API}/runs", headers=h, timeout=30)
        assert r.status_code == 200
        runs = r.json()
        assert runs and runs[0]["id"] == STATE["run"]["id"]
        bs = runs[0]["by_source"]
        assert sum(v["fetched"] for v in bs.values()) == runs[0]["fetched"]
        assert sum(v["analyzed"] for v in bs.values()) == runs[0]["analyzed"]

    @pytest.mark.parametrize("kind", ["found", "new", "analyzed"])
    def test_run_offers_kind(self, h, kind):
        rid = STATE["run"]["id"]
        r = requests.get(f"{API}/runs/{rid}/offers", params={"kind": kind}, headers=h, timeout=30)
        assert r.status_code == 200, r.text
        offers = r.json()["offers"]
        print(kind, len(offers))
        if kind == "found":
            assert len(offers) >= STATE["run"]["fetched"] - STATE["run"].get("out_zone", 0) - 5 or len(offers) == 500
        if kind == "new":
            assert len(offers) == STATE["run"]["new"]
            assert all(o["status"] != "hors_zone" for o in offers)

    def test_known_offers_seen_runs(self, h):
        d = dash(h)
        kn = d["known_last_run"]
        print("known_last_run", len(kn), "run.known", STATE["run"]["known"])
        if STATE["run"]["known"]:
            assert len(kn) > 0
            assert all(o["last_seen"] >= STATE["run"]["at"] for o in kn)

    def test_dedupe_and_zone_in_db(self):
        from pymongo import MongoClient
        env = dict(l.strip().split("=", 1) for l in open("/app/backend/.env") if "=" in l and not l.startswith("#"))
        db = MongoClient(env["MONGO_URL"].strip('"'))[env["DB_NAME"].strip('"')]
        u = db.users.find_one({"email": "membre.test@careeros.dev"})
        uid = u["id"]
        dup = list(db.radar_offers.aggregate([{"$match": {"user_id": uid}}, {"$group": {"_id": "$dedupe_key", "n": {"$sum": 1}}}, {"$match": {"n": {"$gt": 1}}}]))
        assert not dup, dup[:3]
        rid = STATE["run"]["id"]
        seen = db.radar_offers.count_documents({"user_id": uid, "seen_runs": rid})
        print("offers with seen_runs=run", seen, "fetched", STATE["run"]["fetched"])
        assert seen == STATE["run"]["fetched"]
        hz = list(db.radar_offers.find({"user_id": uid, "run_id": rid, "status": "hors_zone"}, {"zone_reason": 1}))
        assert all(o.get("zone_reason") for o in hz)
        newin = list(db.radar_offers.find({"user_id": uid, "run_id": rid}, {"zone_reason": 1}))
        assert all("zone_reason" in o for o in newin)
        # duplicate AI: an offer AI-analysed twice would show ai_analyzed_at overwritten; count AI calls today vs cap
        n_ai = db.radar_offers.count_documents({"user_id": uid, "ai_analyzed_at": {"$gte": STATE["run"]["at"]}})
        print("AI analysed since run start", n_ai, "run ai_analyzed", STATE["run"].get("ai_analyzed"))
        assert n_ai >= STATE["run"].get("ai_analyzed", 0)
