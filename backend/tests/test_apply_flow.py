# Apply flow (offer link, apply-opened / applied / apply-not-yet) for CareerOS application packs
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"


def _login(email, pw):
    r = requests.post(f"{API}/auth/login", json={"email": email, "password": pw}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed {email}: {r.status_code}")
    d = r.json()
    tok = d.get("access_token") or d.get("token")
    s = requests.Session()
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def member():
    return _login("membre.test@careeros.dev", "CareerOS2026!")


@pytest.fixture(scope="module")
def other():
    return _login("conseiller.test@careeros.dev", "Conseil2026!")


@pytest.fixture(scope="module")
def apps(member):
    r = member.get(f"{API}/careeros/applications", timeout=30)
    assert r.status_code == 200
    lst = r.json()
    assert isinstance(lst, list) and lst
    for a in lst:
        assert "apply_pending" in a
    return lst


@pytest.fixture(scope="module")
def target(member, apps):
    # pick an a_postuler app; snapshot it to restore after
    a = next(x for x in apps if x["pipeline_status"] == "a_postuler")
    full = member.get(f"{API}/careeros/applications/{a['id']}", timeout=30).json()
    yield full
    member.patch(f"{API}/careeros/applications/{a['id']}/status", json={"pipeline_status": "a_postuler"}, timeout=30)
    member.post(f"{API}/careeros/applications/{a['id']}/apply-not-yet", timeout=30)
    # note: test_offer_link_save leaves offer_link set; restore via mongo if needed


# GET detail exposes offer_link / offer_source
def test_detail_has_offer_fields(member, apps):
    for a in apps[:13]:
        d = member.get(f"{API}/careeros/applications/{a['id']}", timeout=30).json()
        assert "offer_link" in d and "offer_source" in d
        assert isinstance(d["offer_link"], str)
        print(a["id"], d.get("origin", {}).get("url") if d.get("origin") else None, "->", d["offer_link"], d["offer_source"])
        if d.get("origin") and d["origin"].get("url") and not d.get("offer_link_saved"):
            assert d["offer_link"]


# PUT offer-link validation
@pytest.mark.parametrize("bad", ["", "notaurl", "ftp://x.com/a", "https://", "javascript:alert(1)", "https://nodot"])
def test_offer_link_invalid(member, target, bad):
    r = member.put(f"{API}/careeros/applications/{target['id']}/offer-link", json={"url": bad}, timeout=30)
    assert r.status_code in (400, 422), (bad, r.status_code, r.text)


def test_offer_link_save(member, target):
    url = "https://example.com/jobs/TEST_123"
    r = member.put(f"{API}/careeros/applications/{target['id']}/offer-link", json={"url": url}, timeout=30)
    assert r.status_code == 200 and r.json()["offer_link"] == url
    d = member.get(f"{API}/careeros/applications/{target['id']}", timeout=30).json()
    assert d["offer_link"] == url


# apply-opened -> pending; not-yet clears; applied
def test_apply_opened_pending(member, target):
    r = member.post(f"{API}/careeros/applications/{target['id']}/apply-opened", timeout=30)
    assert r.status_code == 200
    d = member.get(f"{API}/careeros/applications/{target['id']}", timeout=30).json()
    assert d.get("apply_opened_at")
    lst = member.get(f"{API}/careeros/applications", timeout=30).json()
    row = next(x for x in lst if x["id"] == target["id"])
    assert row["apply_pending"] is True


def test_apply_not_yet(member, target):
    r = member.post(f"{API}/careeros/applications/{target['id']}/apply-not-yet", timeout=30)
    assert r.status_code == 200
    d = member.get(f"{API}/careeros/applications/{target['id']}", timeout=30).json()
    assert not d.get("apply_opened_at")
    row = next(x for x in member.get(f"{API}/careeros/applications", timeout=30).json() if x["id"] == target["id"])
    assert row["apply_pending"] is False


def test_applied(member, target):
    member.post(f"{API}/careeros/applications/{target['id']}/apply-opened", timeout=30)
    r = member.post(f"{API}/careeros/applications/{target['id']}/applied", timeout=30)
    assert r.status_code == 200
    j = r.json()
    assert j["pipeline_status"] == "postule" and j["applied_at"]
    d = member.get(f"{API}/careeros/applications/{target['id']}", timeout=30).json()
    assert d["pipeline_status"] == "postule" and d["applied_at"] == j["applied_at"]
    assert not d.get("apply_opened_at")
    assert any(t.get("detail") == "postule" for t in d.get("timeline", []))
    row = next(x for x in member.get(f"{API}/careeros/applications", timeout=30).json() if x["id"] == target["id"])
    assert row["apply_pending"] is False and row["pipeline_status"] == "postule"


def test_apply_opened_ignored_when_not_a_postuler(member, target):
    # target is now postule
    member.post(f"{API}/careeros/applications/{target['id']}/apply-opened", timeout=30)
    d = member.get(f"{API}/careeros/applications/{target['id']}", timeout=30).json()
    assert not d.get("apply_opened_at")


# Ownership isolation
@pytest.mark.parametrize("method,path,body", [
    ("get", "", None), ("put", "/offer-link", {"url": "https://evil.com/x"}),
    ("post", "/apply-opened", None), ("post", "/applied", None), ("post", "/apply-not-yet", None)])
def test_other_member_404(other, target, method, path, body):
    r = getattr(other, method)(f"{API}/careeros/applications/{target['id']}{path}", json=body, timeout=30)
    assert r.status_code == 404, (path, r.status_code)


def test_unauth_401():
    r = requests.post(f"{API}/careeros/applications/x/applied", timeout=30)
    assert r.status_code in (401, 403)
