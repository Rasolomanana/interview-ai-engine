"""Radar fresh-member flow (iter 56): new offers inserted, rule scores visible at 'done', AI phase after, daily limit, no duplicate AI on re-run during ai_pending."""
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
A = f"{BASE_URL}/api"
R = f"{A}/careeros/radar"
S = {}


def login(email, pw):
    r = requests.post(f"{A}/auth/login", json={"email": email, "password": pw}, timeout=20)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


def dash(h):
    r = requests.get(f"{R}/dashboard", headers=h, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def fresh():
    src = login("membre.test@careeros.dev", "CareerOS2026!")
    prof = requests.get(f"{A}/careeros/profile", headers=src, timeout=20).json()
    sett = requests.get(f"{R}/settings", headers=src, timeout=20).json()
    email, pw = f"test_radar_speed_{uuid.uuid4().hex[:8]}@careeros.dev", "CareerOS2026!"
    r = requests.post(f"{A}/auth/register", json={"email": email, "password": pw, "name": "TEST_ Radar Speed"}, timeout=20)
    assert r.status_code in (200, 201), r.text
    h = login(email, pw)
    body = {k: v for k, v in prof.items() if k not in ("user_id", "skills_detected", "updated_at", "career_score")}
    r = requests.put(f"{A}/careeros/profile", json=body, headers=h, timeout=30)
    assert r.status_code == 200, r.text[:300]
    sbody = {k: sett.get(k) for k in ("keywords", "location", "radius", "zones", "companies", "sources", "expand") if k in sett}
    r = requests.put(f"{R}/settings", json=sbody, headers=h, timeout=30)
    print("settings put", r.status_code, r.text[:200])
    S["email"] = email
    print("fresh member", email)
    return h


class TestFreshMember:
    def test_01_first_run(self, fresh):
        t0 = time.time()
        r = requests.post(f"{R}/run", headers=fresh, timeout=30)
        assert r.status_code == 200, r.text
        d = None
        while time.time() - t0 < 150:
            d = dash(fresh)
            lr = d.get("last_run") or {}
            if lr.get("status") == "done":
                break
            time.sleep(3)
        el = round(time.time() - t0, 1)
        lr = d["last_run"]
        print("elapsed", el, "timings", lr.get("timings"), {k: lr.get(k) for k in ("fetched", "new", "known", "analyzed", "skipped_limit", "out_zone", "budget", "ai_pending", "ai_analyzed")})
        print("by_source", lr.get("by_source"), "notices", lr.get("notices"))
        print("top_a", len(d["top_a"]), "top_b", len(d["top_b"]), "ignored", len(d["ignored"]), "new_today", len(d["new_today"]), "analyzed_list", len(d["analyzed_today_list"]), "analyzed_today", d["analyzed_today"])
        S["run1"], S["d1"] = lr, d
        assert lr["status"] == "done" and el < 120
        assert lr["new"] > 0
        assert lr["analyzed"] == min(50, lr["new"]) or lr["analyzed"] <= 50
        assert d["analyzed_today"] <= 50
        if lr["new"] > 50:
            assert lr["skipped_limit"] == lr["new"] - 50
        assert len(d["new_today"]) > 0
        assert len(d["top_a"]) + len(d["top_b"]) + len(d["ignored"]) > 0
        assert all(o["ips"]["method"] == "regles" for o in d["analyzed_today_list"] if o.get("ips") and o.get("method") != "ia")
        assert lr.get("ai_pending") is True

    def test_02_rerun_during_ai_pending(self, fresh):
        lr = dash(fresh)["last_run"]
        S["ai_pending_at_rerun"] = lr.get("ai_pending")
        r = requests.post(f"{R}/run", headers=fresh, timeout=30)
        print("POST run during ai_pending:", lr.get("ai_pending"), r.status_code, r.text[:150])
        S["rerun_code"] = r.status_code

    def test_03_ai_phase(self, fresh):
        t0 = time.time()
        while time.time() - t0 < 280:
            runs = requests.get(f"{R}/runs", headers=fresh, timeout=30).json()
            if all(x.get("status") != "running" and not x.get("ai_pending") for x in runs):
                break
            time.sleep(5)
        for x in runs:
            print("run", x["id"][:8], x["status"], "ai_pending", x.get("ai_pending"), "ai_analyzed", x.get("ai_analyzed"), "timings", x.get("timings"), "analyzed", x.get("analyzed"), "new", x.get("new"), "known", x.get("known"))
        d = dash(fresh)
        ia = [o for o in d["analyzed_today_list"] if o.get("method") == "ia"]
        total_ai = sum(x.get("ai_analyzed") or 0 for x in runs)
        print("ai_today", d["ai_today"], "ia offers", len(ia), "sum ai_analyzed over runs", total_ai)
        S["total_ai"], S["ai_today"] = total_ai, d["ai_today"]
        first = [x for x in runs if x["id"] == S["run1"]["id"]][0]
        assert first["ai_pending"] is False
        assert 0 <= first["ai_analyzed"] <= 5
        assert "ai_s" in first["timings"]
        for o in ia:
            assert o.get("ai_analyzed_at")
        assert d["ai_today"] <= 5

    def test_04_no_duplicate_ai(self, fresh):
        print("sum ai_analyzed across runs", S["total_ai"], "distinct ai offers", S["ai_today"])
        assert S["total_ai"] == S["ai_today"], "same offer analysed by AI twice (rerun during ai_pending)"

    def test_05_second_run_known(self, fresh):
        runs = requests.get(f"{R}/runs", headers=fresh, timeout=30).json()
        if len(runs) < 2:
            pytest.skip("no second run")
        r2 = runs[0]
        assert r2["new"] == 0 or r2["known"] > 0
        assert r2["known"] >= S["run1"]["new"] - 5
        rid = r2["id"]
        f = requests.get(f"{R}/runs/{rid}/offers", params={"kind": "found"}, headers=fresh, timeout=30).json()["offers"]
        print("run2 found", len(f), "fetched", r2["fetched"])
        assert len(f) > 0
