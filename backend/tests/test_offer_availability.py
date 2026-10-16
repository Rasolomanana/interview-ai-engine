# Offer availability check (A), search elsewhere (B), prefilled search links (C), apply urgency (D), cron 'disponibilite' step
import os
import time
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
APP_ID = "a793f26d-ecb6-465c-b3f3-5ca25a1d78f1"
ORIG = "https://example.com/jobs/TEST_123"


def _env(k):
    for line in open("/app/backend/.env"):
        if line.startswith(k + "="):
            return line.split("=", 1)[1].strip().strip('"')


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    d = r.json()
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {d.get('access_token') or d.get('token')}"})
    return s


@pytest.fixture(scope="module")
def member():
    s = _login("membre.test@careeros.dev", "CareerOS2026!")
    s.put(f"{API}/careeros/applications/{APP_ID}/offer-link", json={"url": ORIG}, timeout=30)
    yield s
    s.put(f"{API}/careeros/applications/{APP_ID}/offer-link", json={"url": ORIG}, timeout=30)


@pytest.fixture(scope="module")
def other():
    return _login("conseiller.test@careeros.dev", "Conseil2026!")


# A + B: expired link -> expired + alternatives auto-searched
def test_expired_link_auto_search(member):
    r = member.post(f"{API}/careeros/applications/{APP_ID}/availability", timeout=120)
    assert r.status_code == 200, r.text
    d = r.json()
    av = d["availability"]
    assert av["status"] == "expired"
    assert "404" in av["detail"]
    assert av["checked_at"]
    assert isinstance(d["alternatives"], list)
    print("alternatives:", d["alternatives"])
    assert any(x["official"] and "analyste" in (x["title"] or "").lower() for x in d["alternatives"]), d["alternatives"]
    for x in d["alternatives"]:
        for k in ("title", "company", "url", "source", "match", "official"):
            assert k in x
        assert isinstance(x["match"], int) and 50 <= x["match"] <= 100


def test_search_true_returns_alternatives(member):
    r = member.post(f"{API}/careeros/applications/{APP_ID}/availability?search=true", timeout=120)
    assert r.status_code == 200
    d = r.json()
    assert d["alternatives_at"]
    assert isinstance(d["alternatives"], list) and d["alternatives"]


def test_persisted_on_get_and_search_links(member):
    r = member.get(f"{API}/careeros/applications/{APP_ID}", timeout=30)
    assert r.status_code == 200
    a = r.json()
    assert a["availability"]["status"] == "expired"
    assert a.get("alternatives")
    labels = [l["label"] for l in a["search_links"]]
    print("search_links:", a["search_links"])
    for l in ("Indeed", "LinkedIn", "Guichet-Emplois", "Google Emplois"):
        assert l in labels
    assert all(l["url"].startswith("https://") for l in a["search_links"])


def test_list_has_urgent_and_availability(member):
    r = member.get(f"{API}/careeros/applications", timeout=30)
    assert r.status_code == 200
    lst = r.json()
    for a in lst:
        assert "apply_urgent" in a and "availability" in a
    me = next(a for a in lst if a["id"] == APP_ID)
    assert me["availability"] == "expired"
    print([(a["id"][:8], a["priority"], a["pipeline_status"], a["created_at"][:10], a["apply_urgent"], a["availability"]) for a in lst])


def test_use_alternative_then_restore(member):
    a = member.get(f"{API}/careeros/applications/{APP_ID}", timeout=30).json()
    alt = a["alternatives"][0]["url"]
    r = member.put(f"{API}/careeros/applications/{APP_ID}/offer-link", json={"url": alt}, timeout=30)
    assert r.status_code == 200 and r.json()["offer_link"] == alt
    assert member.get(f"{API}/careeros/applications/{APP_ID}", timeout=30).json()["offer_link"] == alt
    r = member.put(f"{API}/careeros/applications/{APP_ID}/offer-link", json={"url": ORIG}, timeout=30)
    assert r.json()["offer_link"] == ORIG


def test_cross_member_404(other):
    r = other.post(f"{API}/careeros/applications/{APP_ID}/availability?search=true", timeout=30)
    assert r.status_code == 404


def test_unauth_401():
    r = requests.post(f"{API}/careeros/applications/{APP_ID}/availability", timeout=30)
    assert r.status_code in (401, 403)


def test_unknown_app_404(member):
    r = member.post(f"{API}/careeros/applications/does-not-exist/availability", timeout=30)
    assert r.status_code == 404


# Workday JSON API unit checks
def test_workday_api_url():
    import sys
    sys.path.insert(0, "/app/backend")
    from careeros.offer_check import _workday_api, similarity, search_links
    u = _workday_api("https://acme.wd3.myworkdayjobs.com/fr-CA/External/job/Montreal/Analyste-TI_R123")
    assert u == "https://acme.wd3.myworkdayjobs.com/wday/cxs/acme/External/job/Montreal/Analyste-TI_R123"
    assert _workday_api("https://example.com/x") == ""
    assert similarity("Analyste TI", "Analyste TI senior") >= 0.5
    links = search_links("Analyste", "Ville", "Montréal", "https://career.example")
    assert links[0]["url"] == "https://career.example" and len(links) == 5


def test_workday_check_live():
    import sys, asyncio
    sys.path.insert(0, "/app/backend")
    from careeros.offer_check import check_url
    r = asyncio.run(check_url("https://acme.wd3.myworkdayjobs.com/fr-CA/External/job/Montreal/Nope_R000000"))
    print("workday nonexistent:", r)
    assert r["status"] in ("expired", "unknown")


# Cron 'disponibilite' step
def test_cron_logs_disponibilite():
    sec, adm = _env("RADAR_CRON_SECRET"), _env("ADMIN_PASSWORD")
    r = requests.post(f"{API}/careeros/radar/cron", headers={"X-Cron-Secret": sec}, timeout=60)
    assert r.status_code == 200, r.text
    d = r.json()
    print("cron:", d)
    if not d.get("started"):
        pytest.skip(f"cron not started: {d}")
    log_id = d["log_id"]
    for _ in range(50):
        time.sleep(5)
        lg = requests.get(f"{API}/admin/radar-cron-log", headers={"X-Admin-Password": adm}, timeout=30).json()
        items = lg if isinstance(lg, list) else (lg.get("items") or lg.get("logs") or [])
        mine = next((x for x in items if x.get("id") == log_id), None)
        if mine and any(s.get("step") == "disponibilite" for s in mine.get("steps", [])):
            print("disponibilite steps:", [s for s in mine["steps"] if s.get("step") == "disponibilite"])
            assert all(s.get("ok") for s in mine["steps"] if s.get("step") == "disponibilite")
            return
    pytest.fail("no 'disponibilite' step logged in 250s")
