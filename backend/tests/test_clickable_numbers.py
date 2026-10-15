# Clickable numbers: radar run offers drilldown + admin connectors names/portals
import os
import pytest
import requests
from dotenv import dotenv_values

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL") or dotenv_values("/app/frontend/.env")["REACT_APP_BACKEND_URL"]
BASE_URL = BASE_URL.rstrip("/")
ADMIN_PW = dotenv_values("/app/backend/.env")["ADMIN_PASSWORD"]
RUN_ID = "bd807f88-a485-4d61-8a78-1bf582b844b6"
KINDS = ["analyzed", "skipped", "src_jooble", "src_workday", "src_boards", "src_adzuna", "found", "new"]


@pytest.fixture(scope="module")
def s():
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": "membre.test@careeros.dev", "password": "CareerOS2026!"})
    if r.status_code != 200:
        pytest.skip("login failed")
    tok = r.json().get("access_token") or r.json().get("token")
    ss = requests.Session()
    ss.headers["Authorization"] = f"Bearer {tok}"
    return ss


# Radar run offers per kind
@pytest.mark.parametrize("kind", KINDS)
def test_run_offers_kinds(s, kind):
    r = s.get(f"{BASE_URL}/api/careeros/radar/runs/{RUN_ID}/offers", params={"kind": kind})
    assert r.status_code == 200, r.text
    d = r.json()
    assert isinstance(d["offers"], list) and isinstance(d["complete"], bool)
    for o in d["offers"]:
        assert "_id" not in o and "description" not in o
    print(kind, len(d["offers"]), d["complete"])


def test_analyzed_count_37(s):
    d = s.get(f"{BASE_URL}/api/careeros/radar/runs/{RUN_ID}/offers", params={"kind": "analyzed"}).json()
    assert len(d["offers"]) == 37
    assert d["complete"] is True


def test_boards_subset_of_found(s):
    f = {o["id"] for o in s.get(f"{BASE_URL}/api/careeros/radar/runs/{RUN_ID}/offers", params={"kind": "found"}).json()["offers"]}
    b = {o["id"] for o in s.get(f"{BASE_URL}/api/careeros/radar/runs/{RUN_ID}/offers", params={"kind": "src_boards"}).json()["offers"]}
    assert b <= f


def test_skipped_have_no_ips(s):
    d = s.get(f"{BASE_URL}/api/careeros/radar/runs/{RUN_ID}/offers", params={"kind": "skipped"}).json()
    assert all(o.get("ips") is None for o in d["offers"])


def test_invalid_kind_422(s):
    r = s.get(f"{BASE_URL}/api/careeros/radar/runs/{RUN_ID}/offers", params={"kind": "bogus"})
    assert r.status_code == 422


def test_unknown_run_404(s):
    r = s.get(f"{BASE_URL}/api/careeros/radar/runs/nope-xyz/offers", params={"kind": "found"})
    assert r.status_code == 404


def test_run_offers_requires_auth():
    r = requests.get(f"{BASE_URL}/api/careeros/radar/runs/{RUN_ID}/offers")
    assert r.status_code in (401, 403)


# Admin connectors names/portals
def test_admin_connectors_names_portals():
    r = requests.get(f"{BASE_URL}/api/admin/connectors", headers={"X-Admin-Password": ADMIN_PW})
    assert r.status_code == 200, r.text
    d = r.json()
    sup = d.get("supported") or []
    assert sup, d.keys()
    for row in sup:
        assert isinstance(row.get("names"), list), row
        assert isinstance(row.get("portals"), list), row
        for p in row["portals"]:
            for k in ("name", "quality", "fetched", "matched", "error"):
                assert k in p, (k, p)
    for row in d.get("backlog") or []:
        assert isinstance(row.get("names"), list)
    print("supported", [(r["kind"], len(r["names"]), len(r["portals"])) for r in sup])


def test_admin_connectors_bad_pw():
    r = requests.get(f"{BASE_URL}/api/admin/connectors", headers={"X-Admin-Password": "wrong"})
    assert r.status_code in (401, 403)
