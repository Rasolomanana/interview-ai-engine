"""Radar auto-discovery (A+B+C+D): follow/notices/undo/suggestions/shared directory/_certain unit tests."""
import os
import time
import asyncio
import pytest
import requests
from pymongo import MongoClient

BASE_URL = os.environ["REACT_APP_BACKEND_URL"].rstrip("/")
MONGO_URL = os.environ["MONGO_URL"]
DB_NAME = os.environ["DB_NAME"]
EMAIL = "membre.test@careeros.dev"
PASSWORD = "CareerOS2026!"


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200, r.text
    s.headers.update({"Authorization": f"Bearer {r.json()['access_token']}"})
    return s


@pytest.fixture(scope="module")
def db():
    return MongoClient(MONGO_URL)[DB_NAME]


@pytest.fixture(scope="module")
def user_id(client):
    r = client.get(f"{BASE_URL}/api/auth/me")
    assert r.status_code == 200
    return r.json()["id"]


def _get_settings(client):
    r = client.get(f"{BASE_URL}/api/careeros/radar/settings")
    assert r.status_code == 200
    return r.json()


def _put_settings(client, st, **overrides):
    body = {k: st[k] for k in ("enabled", "keywords", "location", "companies", "sources", "expand") if k in st}
    body.update(overrides)
    # Strip server-only fields
    body["companies"] = [{k: v for k, v in c.items() if k not in ("checked_at", "updated_at")} for c in body["companies"]]
    r = client.put(f"{BASE_URL}/api/careeros/radar/settings", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def _remove_company(client, name: str):
    st = _get_settings(client)
    st["companies"] = [c for c in st["companies"] if c["name"].lower() != name.lower()]
    _put_settings(client, st)


# ---------------- Unit: _certain ----------------
def test_unit_certain_rejects_devinette_and_fragile():
    from careeros import radar_auto as AU
    base = {"ok": True, "count": 1, "quality": "fiable", "origin": "annuaire", "slug": "x", "portal_url": "https://x"}
    assert AU._certain(base, "X", None) is True
    assert AU._certain({**base, "origin": "devinette"}, "X", None) is False
    assert AU._certain({**base, "quality": "fragile"}, "X", None) is False
    assert AU._certain({**base, "count": 0}, "X", None) is False
    assert AU._certain({**base, "ok": False}, "X", None) is False


def test_unit_certain_annuaire_partage_named_or_two_members():
    from careeros import radar_auto as AU
    c = {"ok": True, "count": 1, "quality": "fiable", "origin": "annuaire partagé",
         "slug": "cascades", "portal_url": "https://jobs.cascades.com/services/rss/job/"}
    # named: company 'Cascades' token present in slug/url
    assert AU._certain(c, "Cascades", {"members": ["h1"]}) is True
    # not named + only 1 member -> not certain
    c2 = {**c, "slug": "x", "portal_url": "https://x"}
    assert AU._certain(c2, "Cascades", {"members": ["h1"]}) is False
    # not named + >=2 members -> certain
    assert AU._certain(c2, "Cascades", {"members": ["h1", "h2"]}) is True


def test_unit_same_company_tokens():
    from careeros import radar_auto as AU
    assert AU.same_company("Cascades inc.", "Cascades")
    assert AU.same_company("RONA Canada", "RONA inc.")
    assert not AU.same_company("RONA", "Coronado")


# ---------------- API: follow + notice + settings auto-flag ----------------
def test_follow_cascades_triggers_notice_and_auto_assoc(client, db, user_id):
    # Clean previous state for Cascades
    _remove_company(client, "Cascades")
    db.radar_notices.delete_many({"user_id": user_id, "company": "Cascades"})

    r = client.post(f"{BASE_URL}/api/careeros/radar/companies/follow", json={"name": "Cascades"})
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    # Poll up to 90s for background association
    notice = None
    for _ in range(45):
        time.sleep(2)
        rn = client.get(f"{BASE_URL}/api/careeros/radar/notices")
        if rn.status_code == 200:
            items = rn.json().get("items") or []
            notice = next((n for n in items if n["company"] == "Cascades"), None)
            if notice:
                break
    assert notice is not None, "No notice created for Cascades within 90s"
    assert notice["kind"] == "successfactors"
    assert notice["origin"] in ("annuaire", "annuaire partagé", "site")

    st = _get_settings(client)
    cascades = next((c for c in st["companies"] if c["name"] == "Cascades"), None)
    assert cascades is not None
    assert cascades["kind"] == "successfactors"
    assert cascades["auto"] is True
    assert "SuccessFactors" in (cascades.get("detected") or "")

    # Store notice id for next tests via module-level cache
    pytest.cascades_notice_id = notice["id"]


def test_shared_directory_populated_after_put_settings(client, db, user_id):
    """After PUT /settings with an associated company, portal_directory has a hashed-member doc (no PII)."""
    st = _get_settings(client)
    # Ensure Cascades is still present with its auto-detected kind
    cascades = next((c for c in st["companies"] if c["name"] == "Cascades"), None)
    if not cascades or not cascades.get("kind"):
        pytest.skip("Cascades not auto-associated (prior test prerequisite)")
    db.portal_directory.delete_many({"key": "cascades"})
    _put_settings(client, st)
    doc = db.portal_directory.find_one({"key": "cascades", "kind": "successfactors"})
    assert doc is not None, "portal_directory doc not created on PUT settings"
    assert "members" in doc and len(doc["members"]) >= 1
    assert "user_id" not in doc and "email" not in doc
    for m in doc["members"]:
        assert len(m) == 16
        assert user_id not in m


def test_undo_cascades_notice(client, db, user_id):
    nid = getattr(pytest, "cascades_notice_id", None)
    assert nid, "Prerequisite test must have created the notice"
    r = client.post(f"{BASE_URL}/api/careeros/radar/notices/{nid}/undo")
    assert r.status_code == 200, r.text

    st = _get_settings(client)
    cascades = next((c for c in st["companies"] if c["name"] == "Cascades"), None)
    assert cascades is not None
    assert cascades["kind"] == ""
    assert "successfactors" in (cascades.get("auto_block") or [])
    assert "annulée" in (cascades.get("detected") or "").lower()

    # Notice no longer in /notices (status: undone)
    items = client.get(f"{BASE_URL}/api/careeros/radar/notices").json().get("items") or []
    assert not any(n["id"] == nid for n in items)


def test_ack_hides_notice(client, db, user_id):
    # Create a dummy notice directly and ack it
    import uuid as _u
    nid = str(_u.uuid4())
    db.radar_notices.insert_one({"id": nid, "user_id": user_id, "status": "new", "company": "TEST_ACK",
                                 "kind": "workday", "kind_label": "Workday", "count": 1,
                                 "origin": "annuaire", "portal_url": "https://x", "at": "2026-01-01T00:00:00Z"})
    r = client.post(f"{BASE_URL}/api/careeros/radar/notices/{nid}/ack")
    assert r.status_code == 200
    items = client.get(f"{BASE_URL}/api/careeros/radar/notices").json().get("items") or []
    assert not any(n["id"] == nid for n in items)
    db.radar_notices.delete_one({"id": nid})


# ---------------- PUT settings: auto_detecting + auto_block on manual removal ----------------
def test_put_settings_new_company_returns_auto_detecting(client):
    _remove_company(client, "Dollarama")
    st = _get_settings(client)
    st["companies"].append({"name": "Dollarama", "enabled": True, "portal_url": "", "kind": "",
                            "slug": "", "website": "", "detected": "", "auto": False, "auto_block": []})
    r = client.put(
        f"{BASE_URL}/api/careeros/radar/settings",
        json={"enabled": st["enabled"], "keywords": st["keywords"], "location": st["location"],
              "sources": st["sources"], "expand": st["expand"],
              "companies": [{k: v for k, v in c.items() if k not in ("checked_at",)} for c in st["companies"]]})
    assert r.status_code == 200, r.text
    assert "Dollarama" in (r.json().get("auto_detecting") or [])


def test_put_settings_remove_kind_adds_to_auto_block(client, db, user_id):
    # Insert a company with a kind directly via PUT (sim an existing auto-association)
    st = _get_settings(client)
    comps = [c for c in st["companies"] if c["name"].lower() != "test_bmo"]
    comps.append({"name": "TEST_BMO", "enabled": True, "portal_url": "https://bmo.wd3.myworkdayjobs.com/External",
                  "kind": "workday", "slug": "bmo.wd3/External", "website": "", "detected": "",
                  "auto": True, "auto_block": []})
    _put_settings(client, st, companies=comps)

    # Now remove the kind manually (user "removes the portal")
    st2 = _get_settings(client)
    comps2 = []
    for c in st2["companies"]:
        if c["name"] == "TEST_BMO":
            c = {**c, "kind": "", "slug": "", "portal_url": ""}
        comps2.append(c)
    _put_settings(client, st2, companies=comps2)

    st3 = _get_settings(client)
    tb = next(c for c in st3["companies"] if c["name"] == "TEST_BMO")
    assert tb["kind"] == ""
    assert "workday" in (tb.get("auto_block") or []), f"auto_block missing workday: {tb.get('auto_block')}"

    # cleanup
    _remove_company(client, "TEST_BMO")


# ---------------- Suggestions endpoint ----------------
def test_suggestions_endpoint_shape(client):
    r = client.get(f"{BASE_URL}/api/careeros/radar/suggestions")
    assert r.status_code == 200
    data = r.json()
    assert "items" in data
    for g in data["items"]:
        for k in ("name", "offers", "a", "best_ips", "titles", "portal"):
            assert k in g, f"missing key {k} in suggestion"
        assert isinstance(g["titles"], list)
    # No followed companies in suggestions
    st = _get_settings(client)
    followed = {c["name"].lower() for c in st["companies"]}
    for g in data["items"]:
        assert g["name"].lower() not in followed


# ---------------- Cleanup ----------------
def test_cleanup_test_companies(client):
    for name in ("Cascades", "Dollarama", "TEST_BMO"):
        _remove_company(client, name)
    st = _get_settings(client)
    names = {c["name"] for c in st["companies"]}
    assert "Cascades" not in names
    assert "Dollarama" not in names
    assert "TEST_BMO" not in names
