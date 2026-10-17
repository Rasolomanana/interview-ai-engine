# Radar zones v2: custom radius, multiple zones (extra_zones), dashboard zone.zones + map_points
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
QC = "Québec, Québec"
DROP = ("configured", "daily_limit", "expanded", "user_id", "updated_at", "zone_for", "_id", "auto_detecting")


def _env(k):
    for ln in open("/app/backend/.env"):
        if ln.startswith(k + "="):
            return ln.split("=", 1)[1].strip().strip('"')


# ---------- Unit ----------
def test_unit_multi_zone():
    zs = [(MTL, "50"), (QC, "25")]
    assert not Z.check("Sherbrooke, QC", zs)[0]
    assert not Z.check("Drummondville, QC", zs)[0]
    assert Z.check("Lévis, QC", zs)[0]
    assert Z.check("Laval, QC", zs)[0]
    assert Z.check("Sherbrooke, QC", [(MTL, "province")])[0]
    assert not Z.check("Toronto, ON", [(MTL, "province")])[0]
    assert Z.check("Toronto, ON", [(MTL, "country")])[0]
    assert not Z.check("New York, NY", [(MTL, "country")])[0]
    assert not Z.check("Paris, France", [(MTL, "country")])[0]
    assert Z.zones_of({"location": MTL, "radius": "bogus", "extra_zones": [{"location": "a", "radius": "25"}] * 3}) == [(MTL, "100"), ("a", "25"), ("a", "25")]


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


def _body(s, **kw):
    st = s.get(f"{API}/radar/settings").json()
    b = {k: v for k, v in st.items() if k not in DROP}
    b.update(kw)
    return b


LOCS = {"sher": "Sherbrooke, QC", "drum": "Drummondville, QC", "levis": "Lévis, QC", "laval": "Laval, QC", "tor": "Toronto, ON", "ny": "New York, NY"}


@pytest.fixture(scope="module")
def seeded(s, db):
    me = s.get(f"{BASE_URL}/api/auth/me").json()
    uid = me.get("id") or me.get("user", {}).get("id")
    now = datetime.now(timezone.utc).isoformat()
    ids = {}
    docs = []
    for k, loc in LOCS.items():
        i = f"TEST_mz_{k}_{uuid.uuid4().hex[:6]}"
        ids[k] = i
        docs.append({"id": i, "user_id": uid, "dedupe_key": f"TEST_mz_{uuid.uuid4().hex}", "title": f"TEST_mz {loc}", "company": "TEST_Co", "location": loc,
                     "source": "jooble", "status": "nouvelle", "ips": {"score": 82, "priority": "A", "criteria": [], "knockout": False},
                     "first_seen": now, "last_seen": now, "run_id": None, "seen_runs": [], "analyzed_at": now})
    db.radar_offers.insert_many([dict(d) for d in docs])
    db.radar_settings.update_one({"user_id": uid}, {"$unset": {"zone_for": ""}})
    yield ids
    db.radar_offers.delete_many({"id": {"$regex": "^TEST_mz_"}})
    s.put(f"{API}/radar/settings", json=_body(s, location=MTL, radius="100", extra_zones=[]))
    s.get(f"{API}/radar/dashboard")


def _oz(d):
    return {o["id"] for o in d["out_zone"]}


def test_put_radius_validation(s, seeded):
    for r in Z.RADII:
        res = s.put(f"{API}/radar/settings", json=_body(s, radius=r))
        assert res.status_code == 200, res.text
        assert res.json()["radius"] == r
        assert s.get(f"{API}/radar/settings").json()["radius"] == r
    res = s.put(f"{API}/radar/settings", json=_body(s, radius="999"))
    assert res.status_code == 200 and res.json()["radius"] == "100"


def test_put_extra_zones_max2(s, seeded):
    ez = [{"location": "Québec, Québec", "radius": "25"}, {"location": "Gatineau", "radius": "bad"}]
    res = s.put(f"{API}/radar/settings", json=_body(s, radius="50", extra_zones=ez))
    assert res.status_code == 200, res.text
    g = s.get(f"{API}/radar/settings").json()
    assert g["extra_zones"] == [{"location": "Québec, Québec", "radius": "25"}, {"location": "Gatineau", "radius": "100"}]
    res3 = s.put(f"{API}/radar/settings", json=_body(s, extra_zones=ez + [{"location": "Laval", "radius": "25"}]))
    print("3 extra zones ->", res3.status_code, res3.text[:200])
    assert res3.status_code in (200, 422)
    if res3.status_code == 200:
        assert len(res3.json()["extra_zones"]) <= 2
    # empty location rows dropped
    res4 = s.put(f"{API}/radar/settings", json=_body(s, extra_zones=[{"location": "  ", "radius": "25"}]))
    assert res4.status_code == 200 and res4.json()["extra_zones"] == []


def test_dashboard_multi_zone(s, seeded):
    assert s.put(f"{API}/radar/settings", json=_body(s, location=MTL, radius="50", extra_zones=[{"location": QC, "radius": "25"}])).status_code == 200
    d = s.get(f"{API}/radar/dashboard").json()
    z = d["zone"]
    assert MTL in z["label"] and QC in z["label"] and "50 km" in z["label"] and "25 km" in z["label"]
    assert z["radius_km"] == 50
    assert len(z["zones"]) == 2 and all("lat" in x and "lon" in x for x in z["zones"])
    oz = _oz(d)
    for k in ("sher", "drum", "tor", "ny"):
        assert seeded[k] in oz, k
    for k in ("levis", "laval"):
        assert seeded[k] not in oz, k
    # map_points
    mp = {p["id"]: p for p in d["map_points"]}
    for k in ("levis", "laval"):
        p = mp[seeded[k]]
        for f in ("lat", "lon", "distance_km", "from", "priority", "score"):
            assert f in p, f
        assert p["priority"] == "A" and p["score"] == 82
    assert mp[seeded["levis"]]["from"] == "Québec" and mp[seeded["levis"]]["distance_km"] <= 5
    assert mp[seeded["laval"]]["from"] == "Montréal"
    assert seeded["sher"] not in mp


def test_dashboard_province(s, seeded):
    assert s.put(f"{API}/radar/settings", json=_body(s, radius="province", extra_zones=[])).status_code == 200
    d = s.get(f"{API}/radar/dashboard").json()
    assert d["zone"]["radius_km"] is None and "toute la province" in d["zone"]["label"]
    oz = _oz(d)
    for k in ("sher", "drum", "levis", "laval"):
        assert seeded[k] not in oz, k
    assert seeded["tor"] in oz and seeded["ny"] in oz


def test_dashboard_country(s, seeded, db):
    assert s.put(f"{API}/radar/settings", json=_body(s, radius="country", extra_zones=[])).status_code == 200
    d = s.get(f"{API}/radar/dashboard").json()
    assert "tout le pays" in d["zone"]["label"]
    oz = _oz(d)
    assert seeded["tor"] not in oz and seeded["ny"] in oz
    assert db.radar_offers.find_one({"id": seeded["tor"]})["status"] == "nouvelle"


def test_restore_default(s, seeded):
    assert s.put(f"{API}/radar/settings", json=_body(s, location=MTL, radius="100", extra_zones=[])).status_code == 200
    d = s.get(f"{API}/radar/dashboard").json()
    assert d["zone"]["radius_km"] == 100 and d["zone"]["label"] == f"{MTL} (100 km)"
    oz = _oz(d)
    assert seeded["drum"] not in oz and seeded["sher"] in oz and seeded["levis"] in oz
