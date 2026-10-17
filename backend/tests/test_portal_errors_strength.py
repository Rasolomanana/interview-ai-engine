# Portal errors bin (Oracle 302 handling, admin fix/undo/status, RBAC) + Indice de Force Professionnelle
import asyncio
import os
import sys

import httpx
import pytest
import requests
from dotenv import load_dotenv
from pymongo import MongoClient

sys.path.insert(0, "/app/backend")
load_dotenv("/app/backend/.env")
load_dotenv("/app/frontend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN = {"X-Admin-Password": os.environ["ADMIN_PASSWORD"]}
DB = MongoClient(os.environ["MONGO_URL"])[os.environ["DB_NAME"]]
VDM_URL = "https://fa-exyq-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/fr-CA/sites/ExperienceCandidatVdM/jobs"
VDM_SLUG = "fa-exyq-saasfaprod1.fa.ocs.oraclecloud.com/ExperienceCandidatVdM"

from careeros import radar_sources as S  # noqa: E402
from careeros import portal_errors as PE  # noqa: E402

JOBS = {"items": [{"requisitionList": [{"Id": "42", "Title": "Agent", "PrimaryLocation": "Montréal", "PostedDate": "2026-01-02"}]}]}


def run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if False else asyncio.run(coro)


# ---------- Oracle connector unit tests (MockTransport) ----------
class TestOracleUnit:
    def test_302_to_new_oracle_host_followed_and_moved(self):
        def h(req):
            if req.url.host == "old.oraclecloud.com":
                return httpx.Response(302, headers={"location": f"https://new.oraclecloud.com{req.url.path}?{req.url.query.decode()}"})
            return httpx.Response(200, json=JOBS)
        S.MOVED.clear()

        async def go():
            async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
                return await S.oracle(c, "old.oraclecloud.com/SiteX", "Co", [])
        out = run(go())
        assert len(out) == 1 and "new.oraclecloud.com" in out[0]["url"]
        assert S.MOVED.get(("oracle", "old.oraclecloud.com/SiteX")) == "new.oraclecloud.com/SiteX"
        S.MOVED.clear()

    def test_302_to_login_raises_portal_redirect_after_both_paths(self):
        seen = []

        def h(req):
            seen.append(req.url.path)
            return httpx.Response(302, headers={"location": "https://login.example.com/signin"})

        async def go():
            async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
                return await S.oracle(c, "old.oraclecloud.com/SiteX", "Co", [])
        with pytest.raises(S.PortalRedirect):
            run(go())
        assert any("/latest/" in p for p in seen) and any("/11.13.18.05/" in p for p in seen)

    def test_second_path_used_when_latest_redirects_to_login(self):
        def h(req):
            if "/latest/" in req.url.path:
                return httpx.Response(302, headers={"location": "https://login.example.com/x"})
            return httpx.Response(200, json=JOBS)

        async def go():
            async with httpx.AsyncClient(transport=httpx.MockTransport(h)) as c:
                return await S.oracle(c, "h.oraclecloud.com/S", "Co", [])
        assert len(run(go())) == 1

    def test_real_vdm_returns_offers(self):
        async def go():
            async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as c:
                return await S.oracle(c, VDM_SLUG, "Ville de Montréal", [])
        out = run(go())
        assert len(out) > 0, "Real Ville de Montréal Oracle returned no offers"

    def test_classify_and_member_message(self):
        e = S.PortalRedirect("x")
        assert PE.classify(e) == "redirection"
        msg = PE.member_message(e, True)
        assert "Redirection" in msg and "Jooble" in msg and "302" not in msg
        r404 = httpx.HTTPStatusError("nf", request=httpx.Request("GET", "https://a"), response=httpx.Response(404))
        assert PE.classify(r404) == "introuvable"
        assert PE.classify(httpx.ReadTimeout("t")) == "delai"
        assert "Jooble" not in PE.member_message(r404, False)


# ---------- Admin API ----------
def _vdm_card():
    r = requests.get(f"{BASE_URL}/api/admin/portal-errors", headers=ADMIN, timeout=30)
    assert r.status_code == 200
    d = r.json()
    card = next((x for x in d["items"] if x["name"] == "Ville de Montréal" and x["kind"] == "oracle"), None)
    return d, card


class TestAdminPortalErrors:
    def test_list_no_personal_data(self):
        d, card = _vdm_card()
        assert {"ouverte", "resolue", "ignore", "members", "total"} <= set(d["stats"])
        assert card is not None and card["etype"] == "redirection"
        assert isinstance(card["members"], int) and "user_id" not in card
        assert "@" not in str(d["items"])

    def test_fix_bad_url_422(self):
        _, card = _vdm_card()
        before = DB.portal_knowledge.find_one({"key": "de montreal ville"}, {"_id": 0})
        r = requests.post(f"{BASE_URL}/api/admin/portal-errors/{card['id']}/fix", headers=ADMIN, json={"portal_url": "https://example.com/nothing"}, timeout=60)
        assert r.status_code == 422
        assert DB.portal_knowledge.find_one({"key": "de montreal ville"}, {"_id": 0}) == before
        _, c2 = _vdm_card()
        assert c2["status"] == card["status"]

    def test_fix_valid_then_undo(self):
        _, card = _vdm_card()
        eid = card["id"]
        prev_status = card["status"]
        prev_settings = {s["user_id"]: s["companies"] for s in DB.radar_settings.find({"companies.name": "Ville de Montréal"}, {"_id": 0})}
        prev_kb = DB.portal_knowledge.find_one({"key": "de montreal ville"}, {"_id": 0})
        r = requests.post(f"{BASE_URL}/api/admin/portal-errors/{eid}/fix", headers=ADMIN, json={"portal_url": VDM_URL}, timeout=90)
        assert r.status_code == 200, r.text
        fx = r.json()["fix"]
        assert fx["offers"] > 0 and fx["members"] >= 1
        _, c2 = _vdm_card()
        assert c2["status"] == "resolue" and c2["fix"]["id"] == fx["id"]
        for s in DB.radar_settings.find({"companies.name": "Ville de Montréal"}, {"_id": 0}):
            co = next(c for c in s["companies"] if c["name"] == "Ville de Montréal")
            assert co["detected"] == "Portail corrigé par l'équipe CareerOS" and co["kind"] == "oracle"
        kb = DB.portal_knowledge.find_one({"key": "de montreal ville"}, {"_id": 0})
        assert kb["status"] == "fiable" and kb["slug"] == VDM_SLUG
        # undo
        u = requests.post(f"{BASE_URL}/api/admin/portal-errors/{eid}/undo", headers=ADMIN, timeout=30)
        assert u.status_code == 200
        after = {s["user_id"]: s["companies"] for s in DB.radar_settings.find({"companies.name": "Ville de Montréal"}, {"_id": 0})}
        for uid, comps in prev_settings.items():
            a = next(c for c in after[uid] if c["name"] == "Ville de Montréal")
            p = next(c for c in comps if c["name"] == "Ville de Montréal")
            for k in ("kind", "slug", "portal_url", "detected"):
                assert a.get(k, "") == p.get(k, ""), k
        kb2 = DB.portal_knowledge.find_one({"key": "de montreal ville"}, {"_id": 0})
        if prev_kb:
            for k in ("slug", "status", "portal_url", "validations"):
                assert kb2.get(k) == prev_kb.get(k), k
        _, c3 = _vdm_card()
        assert c3["status"] == "ouverte" and c3["fix"]["undone"] is True
        assert requests.post(f"{BASE_URL}/api/admin/portal-errors/{eid}/undo", headers=ADMIN, timeout=30).status_code == 409
        assert prev_status == "ouverte"

    def test_status_transitions(self):
        _, card = _vdm_card()
        eid = card["id"]
        for st in ("resolue", "ignore", "ouverte"):
            r = requests.post(f"{BASE_URL}/api/admin/portal-errors/{eid}/status", headers=ADMIN, json={"status": st}, timeout=30)
            assert r.status_code == 200
            assert _vdm_card()[1]["status"] == st
        assert requests.post(f"{BASE_URL}/api/admin/portal-errors/{eid}/status", headers=ADMIN, json={"status": "bad"}, timeout=30).status_code == 422
        assert requests.post(f"{BASE_URL}/api/admin/portal-errors/nope/status", headers=ADMIN, json={"status": "ouverte"}, timeout=30).status_code == 404
        h = _vdm_card()[1]["history"]
        assert any("statut" in x["action"] for x in h)

    def test_no_password_401(self):
        r = requests.get(f"{BASE_URL}/api/admin/portal-errors", timeout=30)
        assert r.status_code in (401, 403)


def _login(email, pw):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pw}, timeout=30)
    assert r.status_code == 200, r.text
    return r.json().get("access_token") or r.json().get("token")


class TestRBAC:
    def test_marketing_forbidden(self):
        t = _login("membre.test@careeros.dev", "CareerOS2026!")
        r = requests.get(f"{BASE_URL}/api/admin/portal-errors", headers={"Authorization": f"Bearer {t}"}, timeout=30)
        assert r.status_code == 403

    def test_support_allowed(self):
        u = DB.users.find_one({"email": "conseiller.test@careeros.dev"}, {"_id": 0, "admin_roles": 1})
        old = u.get("admin_roles")
        DB.users.update_one({"email": "conseiller.test@careeros.dev"}, {"$set": {"admin_roles": ["support"]}})
        try:
            t = _login("conseiller.test@careeros.dev", "Conseil2026!")
            r = requests.get(f"{BASE_URL}/api/admin/portal-errors", headers={"Authorization": f"Bearer {t}"}, timeout=30)
            assert r.status_code == 200, r.text
            assert "items" in r.json()
        finally:
            DB.users.update_one({"email": "conseiller.test@careeros.dev"}, {"$set": {"admin_roles": old}})


# ---------- Strength index ----------
class TestStrength:
    def test_strength_shape_and_history(self):
        t = _login("membre.test@careeros.dev", "CareerOS2026!")
        h = {"Authorization": f"Bearer {t}"}
        r = requests.get(f"{BASE_URL}/api/careeros/strength", headers=h, timeout=30)
        assert r.status_code == 200
        d = r.json()
        assert 0 <= d["score"] <= 100 and d["level"]
        keys = [c["key"] for c in d["criteria"]]
        assert keys == ["experience", "skills", "leadership", "certifications", "tools", "stability"]
        assert {c["key"]: c["max"] for c in d["criteria"]} == {"experience": 25, "skills": 20, "leadership": 15, "certifications": 10, "tools": 15, "stability": 15}
        assert all("evidence" in c and c["rule"] for c in d["criteria"])
        assert round(sum(c["score"] for c in d["criteria"])) == d["score"]
        assert isinstance(d["domains"], list) and isinstance(d["roles"], list) and isinstance(d["sectors"], list)
        n1 = len(d["history"])
        d2 = requests.get(f"{BASE_URL}/api/careeros/strength", headers=h, timeout=30).json()
        assert len(d2["history"]) == n1
        days = [x["day"] for x in d2["history"]]
        assert len(days) == len(set(days))

    def test_strength_unauth(self):
        assert requests.get(f"{BASE_URL}/api/careeros/strength", timeout=30).status_code in (401, 403)

    def test_compute_rules(self):
        from careeros import strength as ST
        from datetime import datetime, timezone
        p = {"cv_text": "Superviseur logistique 2015-01 à 2020-12, chef d'équipe 2021-01 à ce jour. Excel, SAP, Power BI, SQL. Certification SST, premiers secours.",
             "skills": ["Logistique", "Gestion d'équipe", "Power BI"]}
        d = ST.compute(p, datetime(2026, 1, 15, tzinfo=timezone.utc))
        crit = {c["key"]: c for c in d["criteria"]}
        assert crit["experience"]["score"] == 25
        assert crit["tools"]["score"] > 0 and crit["certifications"]["score"] > 0
        assert d["domains"] and d["domains"][0]["name"]
        assert ST.compute({})["criteria"][-1]["score"] == 7.5
