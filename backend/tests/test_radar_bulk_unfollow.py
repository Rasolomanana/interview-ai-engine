# Radar: bulk unfollow of followed companies (activity, remove retire/bloque, removed list, restore, suggestions exclusion, limit)
import os
import uuid
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
R = f"{BASE_URL}/api/careeros/radar"


@pytest.fixture(scope="module")
def member():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": "membre.test@careeros.dev", "password": "CareerOS2026!"})
    if r.status_code != 200:
        pytest.skip("login failed")
    tok = r.json().get("access_token") or r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


@pytest.fixture(scope="module")
def fresh():
    """Fresh dedicated account (for limit tests)."""
    s = requests.Session()
    email = f"test.bulk.{uuid.uuid4().hex[:8]}@careeros.dev"
    r = s.post(f"{BASE_URL}/api/auth/register", json={"email": email, "password": "BulkTest2026!x", "name": "TEST Bulk", "first_name": "Test", "last_name": "Bulk"})
    if r.status_code not in (200, 201):
        pytest.skip(f"register failed {r.status_code} {r.text[:200]}")
    tok = r.json().get("access_token") or r.json().get("token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


def _companies(s):
    r = s.get(f"{R}/settings")
    assert r.status_code == 200, r.text
    return r.json()["companies"]


class TestActivity:
    def test_requires_auth(self):
        assert requests.get(f"{R}/companies/activity").status_code in (401, 403)
        assert requests.post(f"{R}/companies/remove", json={"names": ["x"]}).status_code in (401, 403)

    def test_activity_shape(self, member):
        r = member.get(f"{R}/companies/activity")
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["limit"] == 100
        assert d["total"] == len(_companies(member))
        assert set(d["counts"]) >= {"active", "low", "inactive", "no_relevant_30"}
        assert sum(d["counts"][k] for k in ("active", "low", "inactive", "new")) == len(d["items"])
        for a in d["items"].values():
            assert a["status"] in ("active", "low", "inactive", "new")
            assert isinstance(a["offers"], int)


class TestRemoveRestore:
    def test_validation(self, member):
        assert member.post(f"{R}/companies/remove", json={"names": []}).status_code == 422
        assert member.post(f"{R}/companies/remove", json={"names": ["x"], "mode": "foo"}).status_code == 422
        assert member.post(f"{R}/companies/remove", json={"names": ["x"], "reason": "a" * 201}).status_code == 422

    def test_follow_remove_restore_cycle(self, member):
        n1, n2 = f"TEST_Bulk_{uuid.uuid4().hex[:6]}", f"TEST_Blk_{uuid.uuid4().hex[:6]}"
        offers_before = member.get(f"{R}/offers").status_code
        for n in (n1, n2):
            assert member.post(f"{R}/companies/follow", json={"name": n}).status_code == 200
        names = [c["name"] for c in _companies(member)]
        assert n1 in names and n2 in names
        before = len(names)
        r = member.post(f"{R}/companies/remove", json={"names": [n1], "mode": "retire", "reason": "TEST motif"})
        assert r.status_code == 200, r.text
        assert r.json()["removed"] == 1 and r.json()["total"] == before - 1
        r = member.post(f"{R}/companies/remove", json={"names": [n2], "mode": "bloque"})
        assert r.json()["removed"] == 1
        names = [c["name"] for c in _companies(member)]
        assert n1 not in names and n2 not in names
        rem = {x["name"]: x for x in member.get(f"{R}/companies/removed").json()["items"]}
        assert rem[n1]["mode"] == "retire" and rem[n1]["reason"] == "TEST motif" and rem[n1]["at"]
        assert rem[n2]["mode"] == "bloque"
        assert "_id" not in rem[n1] and "user_id" not in rem[n1]
        # restore -> followed again and gone from removed
        r = member.post(f"{R}/companies/restore", json={"name": n1, "follow": True})
        assert r.status_code == 200 and r.json().get("ok")
        assert n1 in [c["name"] for c in _companies(member)]
        assert n1 not in [x["name"] for x in member.get(f"{R}/companies/removed").json()["items"]]
        # restore without follow
        r = member.post(f"{R}/companies/restore", json={"name": n2, "follow": False})
        assert r.status_code == 200
        assert n2 not in [c["name"] for c in _companies(member)]
        assert n2 not in [x["name"] for x in member.get(f"{R}/companies/removed").json()["items"]]
        # cleanup
        member.post(f"{R}/companies/remove", json={"names": [n1]})
        member.post(f"{R}/companies/restore", json={"name": n1, "follow": False})
        assert member.get(f"{R}/offers").status_code == offers_before

    def test_remove_unknown_name(self, member):
        n = f"TEST_Ghost_{uuid.uuid4().hex[:6]}"
        before = len(_companies(member))
        r = member.post(f"{R}/companies/remove", json={"names": [n]})
        assert r.status_code == 200 and r.json()["removed"] == 0 and r.json()["total"] == before
        ghost = n in [x["name"] for x in member.get(f"{R}/companies/removed").json()["items"]]
        member.post(f"{R}/companies/restore", json={"name": n, "follow": False})
        print(f"unknown name recorded in removed list: {ghost}")

    def test_removed_excluded_from_suggestions(self, member):
        sug = member.get(f"{R}/suggestions").json()["items"]
        if not sug:
            pytest.skip("no suggestions for member")
        name = sug[0]["name"]
        member.post(f"{R}/companies/remove", json={"names": [name], "mode": "retire"})
        try:
            assert name not in [x["name"] for x in member.get(f"{R}/suggestions").json()["items"]]
        finally:
            member.post(f"{R}/companies/restore", json={"name": name, "follow": False})
        assert name in [x["name"] for x in member.get(f"{R}/suggestions").json()["items"]]


class TestLimit:
    def test_limit_and_restore_at_limit(self, fresh):
        st = fresh.get(f"{R}/settings").json()
        st["companies"] = [{"name": f"TESTCo{i:03d}x", "enabled": True, "portal_url": "", "kind": "", "slug": ""} for i in range(100)]
        r = fresh.put(f"{R}/settings", json=st)
        assert r.status_code == 200, r.text[:300]
        assert fresh.get(f"{R}/companies/activity").json()["total"] == 100
        r = fresh.post(f"{R}/companies/follow", json={"name": "TEST_Over"})
        assert r.status_code == 409 and r.json()["detail"].startswith("LIMIT:")
        # bulk remove 10 then make room
        r = fresh.post(f"{R}/companies/remove", json={"names": [f"TESTCo{i:03d}x" for i in range(10)], "mode": "bloque"})
        assert r.json()["removed"] == 10 and r.json()["total"] == 90
        # fill back to 100
        for i in range(10):
            assert fresh.post(f"{R}/companies/follow", json={"name": f"TESTNew{i}y"}).status_code == 200
        assert fresh.get(f"{R}/companies/activity").json()["total"] == 100
        # restore at limit -> 409 but blocked entry should be preserved
        r = fresh.post(f"{R}/companies/restore", json={"name": "TESTCo000x", "follow": True})
        assert r.status_code == 409
        still = "TESTCo000x" in [x["name"] for x in fresh.get(f"{R}/companies/removed").json()["items"]]
        assert still, "Restore at limit deleted the removed/blocked entry although follow failed (entry lost)"
