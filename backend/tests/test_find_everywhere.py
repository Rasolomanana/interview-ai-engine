# 'Trouver l'offre partout': google_jobs budget in responses, auto/manual search, 12h cache fields, SerpApi 99 cap + _google_ok rules (unit)
import os
import asyncio
from datetime import datetime, timezone, timedelta
import pytest
import requests
import httpx

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
APP_ID = "a793f26d-ecb6-465c-b3f3-5ca25a1d78f1"
ORIG = "https://example.com/jobs/TEST_123"


@pytest.fixture(scope="module")
def s():
    r = requests.post(f"{API}/auth/login", json={"email": "membre.test@careeros.dev", "password": "CareerOS2026!"}, timeout=30)
    if r.status_code != 200:
        pytest.skip("login failed")
    d = r.json()
    ss = requests.Session()
    ss.headers.update({"Authorization": f"Bearer {d.get('access_token') or d.get('token')}"})
    ss.put(f"{API}/careeros/applications/{APP_ID}/offer-link", json={"url": ORIG}, timeout=30)
    yield ss
    ss.put(f"{API}/careeros/applications/{APP_ID}/offer-link", json={"url": ORIG}, timeout=30)


def _gj(g):
    assert set(["month", "used", "cap", "enabled", "last"]) <= set(g), g
    assert g["cap"] == 99
    assert g["enabled"] is False
    assert g["month"] == datetime.now(timezone.utc).strftime("%Y-%m")
    assert isinstance(g["used"], int)


# GET application includes google_jobs + auto_sources
def test_get_app_google_jobs_and_auto_sources(s):
    r = s.get(f"{API}/careeros/applications/{APP_ID}", timeout=60)
    assert r.status_code == 200
    a = r.json()
    _gj(a["google_jobs"])
    assert a["auto_sources"][0] == "Portail officiel"
    assert "Google Jobs" not in a["auto_sources"]
    assert a["pipeline_status"] == "a_postuler"
    print("auto_sources", a["auto_sources"], "prio", (a.get("ips") or {}).get("priority"))


# automatic search (auto=true) -> alternatives + alternatives_at + google_jobs
def test_auto_search(s):
    r = s.post(f"{API}/careeros/applications/{APP_ID}/availability?search=true&auto=true", timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    _gj(d["google_jobs"])
    assert isinstance(d["alternatives"], list)
    at = d["alternatives_at"]
    assert at and abs((datetime.now(timezone.utc) - datetime.fromisoformat(at.replace("Z", "+00:00"))).total_seconds()) < 300
    g = s.get(f"{API}/careeros/applications/{APP_ID}", timeout=60).json()
    assert g["alternatives_at"] == at


# manual search (auto=false) also refreshes alternatives_at
def test_manual_search(s):
    before = s.get(f"{API}/careeros/applications/{APP_ID}", timeout=60).json()["alternatives_at"]
    r = s.post(f"{API}/careeros/applications/{APP_ID}/availability?search=true", timeout=120)
    assert r.status_code == 200
    d = r.json()
    _gj(d["google_jobs"])
    assert d["alternatives_at"] >= before


# check-only (search=false) keeps cached alternatives_at
def test_check_only_keeps_cache(s):
    before = s.get(f"{API}/careeros/applications/{APP_ID}", timeout=60).json()
    r = s.post(f"{API}/careeros/applications/{APP_ID}/availability", timeout=120)
    assert r.status_code == 200
    d = r.json()
    _gj(d["google_jobs"])
    assert "alternatives_at" in d
    # link is expired -> alternatives re-searched anyway (expected), else must keep cached value
    if d["availability"]["status"] not in ("expired", "expired_likely"):
        assert d["alternatives_at"] == before["alternatives_at"]


# ---------- unit: SerpApi hard cap ----------
class FakeColl:
    def __init__(self):
        self.docs = {}

    async def find_one(self, q):
        return self.docs.get(q["_id"])

    async def find_one_and_update(self, q, u, upsert=False):
        d = self.docs.get(q["_id"])
        if d is not None:
            if d["count"] < q["count"]["$lt"]:
                d["count"] += u["$inc"]["count"]
                return d
            raise Exception("E11000 duplicate key")
        self.docs[q["_id"]] = {"_id": q["_id"], "count": 1}
        return None


class FakeDB:
    def __init__(self):
        self.serpapi_usage = FakeColl()


def test_google_jobs_cap_99(monkeypatch):
    import sys
    sys.path.insert(0, "/app/backend")
    from careeros import radar_sources as S
    monkeypatch.setenv("SERPAPI_API_KEY", "x")
    calls = []

    def handler(req):
        calls.append(1)
        return httpx.Response(200, json={"jobs_results": [{"title": "Analyste BI", "company_name": "Hydro", "apply_options": [{"title": "Indeed", "link": f"https://indeed/{len(calls)}"}]}]})

    async def run():
        db = FakeDB()
        async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as cl:
            outs = [await S.google_jobs(cl, db, "Analyste BI", "Hydro", "Montréal") for _ in range(105)]
        return db, outs

    db, outs = asyncio.run(run())
    assert len(calls) == 99
    assert sum(1 for o in outs if o) == 99
    assert outs[0][0]["source"] == "Indeed" and outs[0][0]["via_google"]
    assert asyncio.run(S.google_jobs_budget(db))["used"] == 99


def test_google_jobs_disabled_without_key(monkeypatch):
    import sys
    sys.path.insert(0, "/app/backend")
    from careeros import radar_sources as S
    monkeypatch.delenv("SERPAPI_API_KEY", raising=False)
    assert asyncio.run(S.google_jobs(None, FakeDB(), "a", "b", "c")) == []
