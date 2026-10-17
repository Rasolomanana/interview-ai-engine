# Iteration 46: members never see technical errors (radar dashboard/runs), admin error journal categories,
# strength levers (« Comment gagner des points ? ») + follow, Radar save offer + learning, applications interviews_count
import asyncio
import os
import sys

import pytest
import requests
from dotenv import load_dotenv
from motor.motor_asyncio import AsyncIOMotorClient
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"X-Admin-Password": os.environ["ADMIN_PASSWORD"]}
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]

from careeros import portal_errors as PE  # noqa: E402

TEST_NAME = "TEST_Pack section iter46"


@pytest.fixture(scope="module")
def auth():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "membre.test@careeros.dev", "password": "CareerOS2026!"})
    if r.status_code != 200:
        pytest.skip("login failed")
    return {"Authorization": f"Bearer {r.json()['access_token']}"}, r.json()["user"]["id"]


# ---------- Radar: no technical errors for members ----------
class TestRadarNoErrors:
    def test_dashboard_last_run_no_errors(self, auth):
        r = requests.get(f"{BASE_URL}/api/careeros/radar/dashboard", headers=auth[0])
        assert r.status_code == 200
        d = r.json()
        lr = d.get("last_run")
        if lr:
            assert "errors" not in lr
            for n, pv in (lr.get("portals") or {}).items():
                assert "error" not in pv and "etype" not in pv, n
        assert "saved" in d and isinstance(d["saved"], list)
        assert {"pos", "neg", "liked", "disliked"} <= set(d["learning"])

    def test_runs_no_errors(self, auth):
        r = requests.get(f"{BASE_URL}/api/careeros/radar/runs", headers=auth[0])
        assert r.status_code == 200
        for run in r.json():
            assert "errors" not in run
            for pv in (run.get("portals") or {}).values():
                assert "error" not in pv and "etype" not in pv


# ---------- Admin error journal ----------
class TestAdminJournal:
    def test_list_categories_and_vdm_fixable(self):
        r = requests.get(f"{BASE_URL}/api/admin/portal-errors", headers=ADMIN)
        assert r.status_code == 200
        items = r.json()["items"]
        assert items
        for it in items:
            assert {"category", "category_label", "fixable"} <= set(it)
            assert "members" in it and isinstance(it["members"], int)
        vdm = [it for it in items if "Montréal" in (it["name"] or "") and it["kind"] == "oracle"]
        assert vdm and vdm[0]["fixable"] is True

    def test_log_error_non_portal_card(self, auth):
        async def go():
            db = AsyncIOMotorClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
            await PE.log_error(db, auth[1], "pack", TEST_NAME, "ia", "JSONDecodeError: Expecting value https://x.y/?token=abc")
        asyncio.run(go())
        try:
            items = requests.get(f"{BASE_URL}/api/admin/portal-errors", headers=ADMIN).json()["items"]
            card = next(it for it in items if it["name"] == TEST_NAME)
            assert card["category"] == "pack" and card["category_label"] == "Génération de pack"
            assert card["fixable"] is False
            assert "token=abc" not in card["message"]
            raw = DB.portal_errors.find_one({"name": TEST_NAME})
            assert auth[1] not in str(raw.get("members"))  # pseudonymised
        finally:
            DB.portal_errors.delete_many({"name": TEST_NAME})

    def test_no_admin_password_rejected(self):
        r = requests.get(f"{BASE_URL}/api/admin/portal-errors")
        assert r.status_code in (401, 403)


# ---------- Strength levers ----------
class TestLevers:
    def test_strength_levers_shape(self, auth):
        r = requests.get(f"{BASE_URL}/api/careeros/strength", headers=auth[0])
        assert r.status_code == 200
        lv = r.json()["levers"]
        assert set(lv) >= {"items", "top3", "milestones"}
        keys = {"id", "title", "gain", "why", "difficulty", "effort", "effort_hours", "roi", "evidence", "impact", "followed"}
        for it in lv["items"]:
            assert keys <= set(it)
            assert it["gain"] > 0
        gains = [it["gain"] for it in lv["items"]]
        assert gains == sorted(gains, reverse=True)
        assert lv["top3"] == [it["id"] for it in lv["items"][:3]]
        targets = [m["target"] for m in lv["milestones"]]
        score = r.json()["raw"]
        for t in (85, 90, 95):
            if t > score:
                assert t in targets
        for m in lv["milestones"]:
            assert {"target", "levers", "reachable", "reach"} <= set(m)

    def test_follow_toggle_and_stats(self, auth):
        lv = requests.get(f"{BASE_URL}/api/careeros/strength", headers=auth[0]).json()["levers"]
        if not lv["items"]:
            pytest.skip("no levers")
        it = next((x for x in lv["items"] if not x["followed"]), None)
        if not it:
            pytest.skip("all followed")
        lid = it["id"]
        before = (DB.lever_stats.find_one({"lever_id": lid}) or {}).get("followed", 0)
        r1 = requests.post(f"{BASE_URL}/api/careeros/strength/levers/{lid}/follow", headers=auth[0])
        assert r1.status_code == 200 and r1.json()["followed"] is True
        assert DB.lever_stats.find_one({"lever_id": lid})["followed"] == before + 1
        got = {x["id"]: x for x in requests.get(f"{BASE_URL}/api/careeros/strength", headers=auth[0]).json()["levers"]["items"]}
        assert got[lid]["followed"] is True
        r2 = requests.post(f"{BASE_URL}/api/careeros/strength/levers/{lid}/follow", headers=auth[0])
        assert r2.status_code == 200 and r2.json()["followed"] is False
        assert DB.lever_stats.find_one({"lever_id": lid})["followed"] == before
        got = {x["id"]: x for x in requests.get(f"{BASE_URL}/api/careeros/strength", headers=auth[0]).json()["levers"]["items"]}
        assert got[lid]["followed"] is False

    def test_follow_invalid_id(self, auth):
        r = requests.post(f"{BASE_URL}/api/careeros/strength/levers/X!/follow", headers=auth[0])
        assert r.status_code == 422


# ---------- Radar save + applications interviews_count ----------
class TestSaveAndApps:
    def test_save_toggle(self, auth):
        d = requests.get(f"{BASE_URL}/api/careeros/radar/dashboard", headers=auth[0]).json()
        cand = [o for o in (d.get("top_b") or []) + (d.get("top_a") or []) + (d.get("new_today") or []) if not o.get("saved")]
        if not cand:
            pytest.skip("no radar offer to save")
        oid = cand[0]["id"]
        try:
            r = requests.post(f"{BASE_URL}/api/careeros/radar/offers/{oid}/save", headers=auth[0])
            assert r.status_code == 200 and r.json()["saved"] is True
            d2 = requests.get(f"{BASE_URL}/api/careeros/radar/dashboard", headers=auth[0]).json()
            assert oid in [o["id"] for o in d2["saved"]]
            assert d2["learning"]["pos"] >= d["learning"]["pos"] + 1
        finally:
            r = requests.post(f"{BASE_URL}/api/careeros/radar/offers/{oid}/save", headers=auth[0])
            assert r.json()["saved"] is False
        d3 = requests.get(f"{BASE_URL}/api/careeros/radar/dashboard", headers=auth[0]).json()
        assert oid not in [o["id"] for o in d3["saved"]]

    def test_save_unknown_404(self, auth):
        r = requests.post(f"{BASE_URL}/api/careeros/radar/offers/nope-xyz/save", headers=auth[0])
        assert r.status_code == 404

    def test_applications_interviews_count(self, auth):
        r = requests.get(f"{BASE_URL}/api/careeros/applications", headers=auth[0])
        assert r.status_code == 200
        rows = r.json()
        assert rows
        for a in rows:
            assert isinstance(a.get("interviews_count"), int)
