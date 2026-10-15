# Admin RBAC (roles/sections), Admin insights (overview/geo/business) and member-controlled sharing tests
import os
import json
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_PWD = os.environ.get("ADMIN_PASSWORD") or open("/app/backend/.env").read().split("ADMIN_PASSWORD=")[1].split("\n")[0].strip().strip('"')
A = {"X-Admin-Password": ADMIN_PWD}
MEMBRE = ("membre.test@careeros.dev", "CareerOS2026!")
CONSEIL = ("conseiller.test@careeros.dev", "Conseil2026!")


def login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    tok = d.get("access_token") or d.get("tokens", {}).get("access_token")
    assert tok, d
    return {"Authorization": f"Bearer {tok}"}


def uid(h):
    r = requests.get(f"{BASE_URL}/api/auth/me", headers=h, timeout=30)
    assert r.status_code == 200
    d = r.json()
    return (d.get("user") or d)["id"]


def set_roles(user_id, roles):
    r = requests.put(f"{BASE_URL}/api/admin/roles/{user_id}", headers=A, json={"roles": roles}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json()


@pytest.fixture(scope="module")
def ctx():
    m = login(*MEMBRE)
    c = login(*CONSEIL)
    mid, cid = uid(m), uid(c)
    yield {"m": m, "c": c, "mid": mid, "cid": cid}
    set_roles(mid, ["marketing"])
    set_roles(cid, ["conseiller"])
    for g in requests.get(f"{BASE_URL}/api/careeros/sharing", headers=m, timeout=30).json().get("given", []):
        if g["grantee_email"] == CONSEIL[0] and g.get("_test"):
            pass


# ---- /api/admin/me
class TestAdminMe:
    def test_me_password_super(self):
        r = requests.get(f"{BASE_URL}/api/admin/me", headers=A, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert d["super"] is True and d["via"] == "password"
        assert set(d["sections"]) == {"overview", "geo", "business", "activite", "connecteurs", "finance", "roles"}

    def test_me_bad_password(self):
        r = requests.get(f"{BASE_URL}/api/admin/me", headers={"X-Admin-Password": "nope"}, timeout=30)
        assert r.status_code == 401

    def test_me_no_auth(self):
        assert requests.get(f"{BASE_URL}/api/admin/me", timeout=30).status_code == 401

    def test_me_marketing(self, ctx):
        set_roles(ctx["mid"], ["marketing"])
        d = requests.get(f"{BASE_URL}/api/admin/me", headers=ctx["m"], timeout=30).json()
        assert d["via"] == "member" and d["super"] is False
        assert d["sections"] == ["overview", "geo", "business", "activite"]

    def test_me_no_role_403(self, ctx):
        set_roles(ctx["mid"], [])
        r = requests.get(f"{BASE_URL}/api/admin/me", headers=ctx["m"], timeout=30)
        set_roles(ctx["mid"], ["marketing"])
        assert r.status_code == 403


# ---- RBAC enforcement
class TestRBAC:
    @pytest.mark.parametrize("path", ["/api/admin/insights/overview", "/api/admin/insights/geo", "/api/admin/insights/business", "/api/admin/stats"])
    def test_marketing_allowed(self, ctx, path):
        set_roles(ctx["mid"], ["marketing"])
        r = requests.get(f"{BASE_URL}{path}", headers=ctx["m"], timeout=60)
        assert r.status_code == 200, r.text

    @pytest.mark.parametrize("path", ["/api/admin/finance", "/api/admin/roles", "/api/admin/connectors", "/api/admin/knowledge", "/api/admin/members", "/api/admin/credits"])
    def test_marketing_denied(self, ctx, path):
        r = requests.get(f"{BASE_URL}{path}", headers=ctx["m"], timeout=30)
        assert r.status_code == 403, f"{path} -> {r.status_code}"

    def test_marketing_cannot_set_roles(self, ctx):
        r = requests.put(f"{BASE_URL}/api/admin/roles/{ctx['mid']}", headers=ctx["m"], json={"roles": ["super_admin"]}, timeout=30)
        assert r.status_code == 403

    @pytest.mark.parametrize("path,code", [("/api/admin/insights/business", 200), ("/api/admin/insights/overview", 403),
                                           ("/api/admin/insights/geo", 403), ("/api/admin/stats", 403), ("/api/admin/finance", 403)])
    def test_conseiller(self, ctx, path, code):
        set_roles(ctx["cid"], ["conseiller"])
        assert requests.get(f"{BASE_URL}{path}", headers=ctx["c"], timeout=60).status_code == code

    def test_member_no_role_denied(self, ctx):
        set_roles(ctx["cid"], [])
        r = requests.get(f"{BASE_URL}/api/admin/insights/business", headers=ctx["c"], timeout=30)
        set_roles(ctx["cid"], ["conseiller"])
        assert r.status_code == 403

    def test_invalid_token_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/stats", headers={"Authorization": "Bearer garbage"}, timeout=30)
        assert r.status_code == 401

    def test_invalid_roles_filtered(self, ctx):
        d = set_roles(ctx["cid"], ["conseiller", "hacker", "conseiller", "support"])
        assert d["admin_roles"] == ["conseiller", "support"]
        set_roles(ctx["cid"], ["conseiller"])

    def test_set_roles_unknown_user(self):
        r = requests.put(f"{BASE_URL}/api/admin/roles/does-not-exist", headers=A, json={"roles": ["marketing"]}, timeout=30)
        assert r.status_code == 404

    def test_super_admin_role_member(self, ctx):
        set_roles(ctx["cid"], ["super_admin"])
        try:
            r1 = requests.get(f"{BASE_URL}/api/admin/roles", headers=ctx["c"], timeout=30)
            r2 = requests.get(f"{BASE_URL}/api/admin/finance", headers=ctx["c"], timeout=30)
            r3 = requests.put(f"{BASE_URL}/api/admin/roles/{ctx['cid']}", headers=ctx["c"], json={"roles": ["super_admin", "conseiller"]}, timeout=30)
            assert r1.status_code == 200 and r2.status_code == 200 and r3.status_code == 200
        finally:
            set_roles(ctx["cid"], ["conseiller"])

    def test_roles_list_password(self):
        r = requests.get(f"{BASE_URL}/api/admin/roles?q=membre.test", headers=A, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert "marketing" in d["roles"] and any(m["email"] == MEMBRE[0] for m in d["members"])


# ---- insights payloads
class TestInsights:
    @pytest.mark.parametrize("days", [30, 90, 0])
    def test_overview(self, days):
        r = requests.get(f"{BASE_URL}/api/admin/insights/overview?days={days}", headers=A, timeout=60)
        assert r.status_code == 200
        d = r.json()
        assert d["period_days"] == days
        assert [s["step"] for s in d["funnel"]] == ["Visiteurs", "Inscrits", "Actifs", "Payants", "Renouvellement"]
        for k in ("total", "active_7d", "active_30d", "new_7d", "new_30d"):
            assert isinstance(d["members"][k], int)
        assert "runs_30d" in d["radar"]
        f = [s["count"] for s in d["funnel"]][1:]  # visitors are raw tracked sessions (may be < sign-ups while tracking is recent)
        assert f == sorted(f, reverse=True), f"funnel not monotonic {f}"
        if d["funnel"][0]["count"] < d["funnel"][1]["count"]:
            assert d["funnel"][1]["rate"] is None

    def test_geo_super_and_merged(self, ctx):
        d = requests.get(f"{BASE_URL}/api/admin/insights/geo", headers=A, timeout=60).json()
        assert d["merged"] is False and d["countries"] and "provinces" in d and "cities" in d
        set_roles(ctx["mid"], ["marketing"])
        dm = requests.get(f"{BASE_URL}/api/admin/insights/geo", headers=ctx["m"], timeout=60).json()
        assert dm["merged"] is True
        for k in ("countries", "provinces", "cities"):
            for row in dm[k]:
                assert row["count"] >= 3 or row["label"].startswith("Autres"), row

    def test_business(self):
        d = requests.get(f"{BASE_URL}/api/admin/insights/business", headers=A, timeout=60).json()
        for k in ("roles", "companies", "portals", "offers", "priorities"):
            assert k in d
        assert set(d["priorities"]["radar_30d"]) == {"A", "B", "C"}

    @pytest.mark.parametrize("part", ["overview", "geo", "business"])
    def test_no_pii(self, part):
        txt = requests.get(f"{BASE_URL}/api/admin/insights/{part}", headers=A, timeout=60).text
        assert "cv_text" not in txt and "@" not in txt, part


# ---- profile geo fields
class TestProfileGeo:
    def test_profile_geo_roundtrip(self, ctx):
        h = ctx["c"]
        orig = requests.get(f"{BASE_URL}/api/careeros/profile", headers=h, timeout=30).json()
        for k in ("country", "province", "city"):
            assert k in orig
        body = {k: v for k, v in orig.items() if k not in ("user_id", "skills_detected", "updated_at", "career_score", "_id")}
        body.update(country="Canada", province="Ontario", city="Ottawa")
        r = requests.put(f"{BASE_URL}/api/careeros/profile", headers=h, json=body, timeout=60)
        assert r.status_code == 200, r.text[:300]
        g = requests.get(f"{BASE_URL}/api/careeros/profile", headers=h, timeout=30).json()
        assert (g["country"], g["province"], g["city"]) == ("Canada", "Ontario", "Ottawa")
        body.update(country=orig["country"], province=orig["province"], city=orig["city"])
        requests.put(f"{BASE_URL}/api/careeros/profile", headers=h, json=body, timeout=60)


# ---- sharing
class TestSharing:
    def test_cannot_share_self(self, ctx):
        r = requests.post(f"{BASE_URL}/api/careeros/sharing", headers=ctx["m"], json={"email": MEMBRE[0].upper(), "relation": "proche", "scopes": ["cv"]}, timeout=30)
        assert r.status_code == 400

    def test_empty_scopes(self, ctx):
        r = requests.post(f"{BASE_URL}/api/careeros/sharing", headers=ctx["m"], json={"email": "x@example.com", "scopes": []}, timeout=30)
        assert r.status_code == 400

    def test_bad_scope(self, ctx):
        r = requests.post(f"{BASE_URL}/api/careeros/sharing", headers=ctx["m"], json={"email": "x@example.com", "scopes": ["passwords"]}, timeout=30)
        assert r.status_code == 422

    def test_full_flow(self, ctx):
        m, c = ctx["m"], ctx["c"]
        r = requests.post(f"{BASE_URL}/api/careeros/sharing", headers=m, json={"email": CONSEIL[0], "relation": "conseiller", "scopes": ["memory", "applications"]}, timeout=30)
        assert r.status_code == 200, r.text
        gid = r.json()["id"]
        try:
            rec = requests.get(f"{BASE_URL}/api/careeros/sharing", headers=c, timeout=30).json()["received"]
            assert any(g["id"] == gid for g in rec)
            v = requests.get(f"{BASE_URL}/api/careeros/sharing/{gid}/view", headers=c, timeout=30)
            assert v.status_code == 200
            vd = v.json()
            assert "cv_text" not in vd and "memory" in vd and "applications" in vd
            assert sorted(vd["scopes"]) == ["applications", "memory"]
            # owner cannot view via grantee route
            assert requests.get(f"{BASE_URL}/api/careeros/sharing/{gid}/view", headers=m, timeout=30).status_code == 404
            given = requests.get(f"{BASE_URL}/api/careeros/sharing", headers=m, timeout=30).json()["given"]
            gg = next(g for g in given if g["id"] == gid)
            assert gg["views"] >= 1
            # grantee cannot revoke
            assert requests.delete(f"{BASE_URL}/api/careeros/sharing/{gid}", headers=c, timeout=30).status_code == 404
        finally:
            d = requests.delete(f"{BASE_URL}/api/careeros/sharing/{gid}", headers=m, timeout=30)
        assert d.status_code == 200
        assert requests.get(f"{BASE_URL}/api/careeros/sharing/{gid}/view", headers=c, timeout=30).status_code == 404
        rec = requests.get(f"{BASE_URL}/api/careeros/sharing", headers=c, timeout=30).json()["received"]
        assert not any(g["id"] == gid for g in rec)

    def test_cv_scope(self, ctx):
        m, c = ctx["m"], ctx["c"]
        gid = requests.post(f"{BASE_URL}/api/careeros/sharing", headers=m, json={"email": CONSEIL[0], "scopes": ["cv"]}, timeout=30).json()["id"]
        try:
            vd = requests.get(f"{BASE_URL}/api/careeros/sharing/{gid}/view", headers=c, timeout=30).json()
            assert "cv_text" in vd and "memory" not in vd and "applications" not in vd
        finally:
            requests.delete(f"{BASE_URL}/api/careeros/sharing/{gid}", headers=m, timeout=30)
