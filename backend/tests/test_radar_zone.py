# Radar geographic zone: unit tests on careeros.zone.check + API tests (dashboard out_zone, reversible re-evaluation, run offers kind=out_zone)
import os
import sys
import uuid
from datetime import datetime, timezone

import pytest
import requests
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
from careeros import zone as Z  # noqa: E402

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    for ln in open("/app/frontend/.env"):
        if ln.startswith("REACT_APP_BACKEND_URL="):
            BASE_URL = ln.split("=", 1)[1].strip().strip('"').rstrip("/")
API = f"{BASE_URL}/api/careeros"
EMAIL, PWD = "membre.test@careeros.dev", "CareerOS2026!"
MTL = "Montréal, Québec"


def _env(k):
    for ln in open("/app/backend/.env"):
        if ln.startswith(k + "="):
            return ln.split("=", 1)[1].strip().strip('"')


# ---------- Unit: zone.check ----------
@pytest.mark.parametrize("loc", ["Toronto, ON", "Vancouver, BC", "Bucharest, Romania", "Chattanooga, TN, US", "Sherbrooke, QC", "Ottawa, ON", "Paris, France"])
def test_out_of_zone_for_montreal(loc):
    ok, why = Z.check(loc, MTL)
    assert ok is False, (loc, why)
    assert why


@pytest.mark.parametrize("loc", ["Laval, QC", "Candiac, QC", "Montreal, QC", "Montréal", "Canada", "", "Remote - Canada", "Longueuil, Québec", "Québec, Canada", "QC"])
def test_in_zone_for_montreal(loc):
    ok, why = Z.check(loc, MTL)
    assert ok is True, (loc, why)


def test_member_toronto():
    assert Z.check("Mississauga, ON", "Toronto")[0] is True
    assert Z.check("Montreal, QC", "Toronto")[0] is False
    assert Z.check("Vancouver, BC", "Toronto")[0] is False


def test_member_antananarivo():
    assert Z.check("Antananarivo, Madagascar", "Antananarivo")[0] is True
    assert Z.check("Montréal, QC", "Antananarivo")[0] is False
    assert Z.check("Paris, France", "Antananarivo")[0] is False


def test_sherbrooke_distance_reason():
    ok, why = Z.check("Sherbrooke, QC", MTL)
    assert not ok and "km" in why


# ---------- API ----------
@pytest.fixture(scope="module")
def s():
    ss = requests.Session()
    r = ss.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PWD})
    if r.status_code != 200:
        pytest.skip(f"login failed {r.status_code}")
    d = r.json()
    tok = d.get("access_token") or d.get("token")
    if tok:
        ss.headers["Authorization"] = f"Bearer {tok}"
    return ss


@pytest.fixture(scope="module")
def db():
    return MongoClient(_env("MONGO_URL"))[_env("DB_NAME")]


@pytest.fixture(scope="module")
def seeded(s, db):
    me = s.get(f"{BASE_URL}/api/auth/me").json()
    uid = me.get("id") or me.get("user", {}).get("id")
    now = datetime.now(timezone.utc).isoformat()
    ips = {"score": 80, "priority": "A", "criteria": [], "knockout": False}
    docs = []
    for loc, st in [("Toronto, ON", "nouvelle"), ("Laval, QC", "nouvelle"), ("Mississauga, ON", "ignoree")]:
        docs.append({"id": f"TEST_zone_{uuid.uuid4().hex[:8]}", "user_id": uid, "dedupe_key": f"TEST_zone_{uuid.uuid4().hex}", "title": f"TEST_zone {loc}",
                     "company": "TEST_Co", "location": loc, "source": "jooble", "status": st, "ips": ips, "first_seen": now, "last_seen": now,
                     "run_id": None, "seen_runs": [], "analyzed_at": now})
    db.radar_offers.insert_many([dict(d) for d in docs])
    # force re-evaluation
    db.radar_settings.update_one({"user_id": uid}, {"$unset": {"zone_for": ""}})
    yield {"uid": uid, "tor": docs[0]["id"], "lav": docs[1]["id"], "mis": docs[2]["id"]}
    db.radar_offers.delete_many({"id": {"$regex": "^TEST_zone_"}})
    st = s.get(f"{API}/radar/settings").json()
    if st.get("location") != MTL:
        body = {k: st[k] for k in st if k not in ("configured", "daily_limit", "expanded", "user_id", "updated_at", "zone_for", "_id")}
        body["location"] = MTL
        s.put(f"{API}/radar/settings", json=body)
    s.get(f"{API}/radar/dashboard")


def _ids(lst):
    return {o["id"] for o in lst}


def test_dashboard_out_zone(s, seeded):
    r = s.get(f"{API}/radar/dashboard")
    assert r.status_code == 200
    d = r.json()
    assert d["zone"]["location"] == MTL and d["zone"]["radius_km"] == 100
    assert isinstance(d["out_zone_count"], int) and d["out_zone_count"] >= 2
    oz = _ids(d["out_zone"])
    assert seeded["tor"] in oz and seeded["mis"] in oz and seeded["lav"] not in oz
    for k in ("top_a", "top_b", "ignored", "new_today", "known_last_run", "analyzed_today_list"):
        assert not (oz & _ids(d[k])), k
    assert seeded["lav"] in _ids(d["top_a"])
    tor = next(o for o in d["out_zone"] if o["id"] == seeded["tor"])
    assert tor["status"] == "hors_zone" and tor.get("zone_reason")


def test_location_change_reversible(s, seeded, db):
    st = s.get(f"{API}/radar/settings").json()
    body = {k: st[k] for k in st if k not in ("configured", "daily_limit", "expanded", "user_id", "updated_at", "zone_for", "_id")}
    body["location"] = "Toronto, Ontario"
    r = s.put(f"{API}/radar/settings", json=body)
    assert r.status_code == 200, r.text
    d = s.get(f"{API}/radar/dashboard").json()
    assert d["zone"]["location"] == "Toronto, Ontario"
    oz = _ids(d["out_zone"])
    assert seeded["lav"] in oz and seeded["tor"] not in oz and seeded["mis"] not in oz
    assert db.radar_offers.find_one({"id": seeded["tor"]})["status"] == "nouvelle"
    assert db.radar_offers.find_one({"id": seeded["mis"]})["status"] == "ignoree"
    # back to Montréal
    body["location"] = MTL
    assert s.put(f"{API}/radar/settings", json=body).status_code == 200
    d = s.get(f"{API}/radar/dashboard").json()
    oz = _ids(d["out_zone"])
    assert seeded["tor"] in oz and seeded["mis"] in oz and seeded["lav"] not in oz
    lav = db.radar_offers.find_one({"id": seeded["lav"]})
    assert lav["status"] == "nouvelle" and "status_before_zone" not in lav
    assert db.radar_offers.find_one({"id": seeded["mis"]})["status_before_zone"] == "ignoree"


def test_run_offers_out_zone(s):
    runs = s.get(f"{API}/radar/runs").json()
    if not runs:
        pytest.skip("no runs")
    rid = runs[0]["id"]
    r = s.get(f"{API}/radar/runs/{rid}/offers", params={"kind": "out_zone"})
    assert r.status_code == 200
    assert all(o["status"] == "hors_zone" for o in r.json()["offers"])
    r2 = s.get(f"{API}/radar/runs/{rid}/offers", params={"kind": "new"})
    assert r2.status_code == 200 and all(o["status"] != "hors_zone" for o in r2.json()["offers"])
    assert s.get(f"{API}/radar/runs/{rid}/offers", params={"kind": "bogus"}).status_code == 422
