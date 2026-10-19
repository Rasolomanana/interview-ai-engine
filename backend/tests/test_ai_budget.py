# AI budget governance tests: admin /api/admin/ai-budget (status, config, reset, RBAC), gate (rules-only / daily cap),
# and method-level tests of careeros.ai_budget (cache + retry window, free-quota gate, skip, quota error detection).
import asyncio
import os
import sys
import uuid
from datetime import datetime, timedelta, timezone

import pytest
import requests
from motor.motor_asyncio import AsyncIOMotorClient

sys.path.insert(0, "/app/backend")
from dotenv import dotenv_values  # noqa: E402

ENV = dotenv_values("/app/backend/.env")
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
ADMIN_PWD = ENV["ADMIN_PASSWORD"]
A = {"X-Admin-Password": ADMIN_PWD}
URL = f"{BASE_URL}/api/admin/ai-budget"
DEFAULT_CFG = {"daily_cap": 2000, "allow_paid": False, "force_rules_only": False}
MEMBRE = ("membre.test@careeros.dev", "CareerOS2026!")


def login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    assert r.status_code == 200, r.text
    d = r.json()
    return {"Authorization": f"Bearer {d.get('access_token') or d.get('tokens', {}).get('access_token')}"}


@pytest.fixture(scope="module", autouse=True)
def restore_config():
    orig = requests.get(URL, headers=A, timeout=30).json().get("config", DEFAULT_CFG)
    yield
    requests.put(URL, headers=A, json={k: orig.get(k, v) for k, v in DEFAULT_CFG.items()}, timeout=30)


# ---------- Admin endpoint ----------
class TestAdminEndpoint:
    def test_status_shape(self):
        r = requests.get(URL, headers=A, timeout=30)
        assert r.status_code == 200, r.text
        d = r.json()
        for k in ("config", "used_today", "cap", "providers", "current", "last_used", "rules_only", "cache_hits_today", "cache_size", "reset_at"):
            assert k in d, k
        assert isinstance(d["providers"], list) and isinstance(d["used_today"], int)
        print("providers:", [(p["label"], p["free"], p["disabled"], p["exhausted"]) for p in d["providers"]], "current:", d["current"])
        for p in d["providers"]:
            assert {"label", "name", "free", "calls_today", "exhausted", "disabled", "last_error"} <= set(p)

    def test_no_password_rejected(self):
        assert requests.get(URL, timeout=30).status_code in (401, 403)
        assert requests.get(URL, headers={"X-Admin-Password": "wrong"}, timeout=30).status_code == 401

    def test_marketing_member_forbidden(self):
        h = login(*MEMBRE)  # role marketing: no finance section
        assert requests.get(URL, headers=h, timeout=30).status_code == 403
        assert requests.put(URL, headers=h, json=DEFAULT_CFG, timeout=30).status_code == 403

    def test_put_validation(self):
        assert requests.put(URL, headers=A, json={**DEFAULT_CFG, "daily_cap": -1}, timeout=30).status_code == 422
        assert requests.put(URL, headers=A, json={"daily_cap": 10}, timeout=30).status_code == 422

    def test_put_persists_and_rules_only(self):
        r = requests.put(URL, headers=A, json={"daily_cap": 1234, "allow_paid": True, "force_rules_only": True}, timeout=30)
        assert r.status_code == 200 and r.json()["ok"] is True
        d = requests.get(URL, headers=A, timeout=30).json()
        assert d["config"] == {"daily_cap": 1234, "allow_paid": True, "force_rules_only": True}
        assert d["cap"] == 1234 and d["rules_only"] is True and d["current"] is None
        assert all(not p["disabled"] for p in d["providers"])  # allow_paid -> nothing disabled
        requests.put(URL, headers=A, json=DEFAULT_CFG, timeout=30)
        d = requests.get(URL, headers=A, timeout=30).json()
        assert d["rules_only"] is False and d["config"] == DEFAULT_CFG

    def test_cap_zero_is_rules_only(self):
        requests.put(URL, headers=A, json={**DEFAULT_CFG, "daily_cap": 0}, timeout=30)
        d = requests.get(URL, headers=A, timeout=30).json()
        assert d["rules_only"] is True and d["current"] is None
        requests.put(URL, headers=A, json=DEFAULT_CFG, timeout=30)


# ---------- Gate blocks real AI features (no LLM call made) ----------
class TestGateOnFeatures:
    def _app_id(self, h):
        r = requests.get(f"{BASE_URL}/api/careeros/applications", headers=h, timeout=30)
        assert r.status_code == 200
        items = r.json() if isinstance(r.json(), list) else r.json().get("items") or r.json().get("applications") or []
        if not items:
            pytest.skip("no application for membre.test")
        return items[0]["id"]

    def test_followup_draft_blocked_in_rules_only(self):
        h = login(*MEMBRE)
        app_id = self._app_id(h)
        requests.put(URL, headers=A, json={**DEFAULT_CFG, "force_rules_only": True}, timeout=30)
        try:
            r = requests.post(f"{BASE_URL}/api/careeros/applications/{app_id}/emails/draft", headers=h,
                              json={"kind": "relance", "notes": f"TEST_{uuid.uuid4()}"}, timeout=60)
            print("draft rules-only:", r.status_code, r.text[:200])
            assert r.status_code == 503
            assert "Règles uniquement" in r.json()["detail"]
        finally:
            requests.put(URL, headers=A, json=DEFAULT_CFG, timeout=30)

    def test_followup_draft_blocked_by_cap(self):
        h = login(*MEMBRE)
        app_id = self._app_id(h)
        requests.put(URL, headers=A, json={**DEFAULT_CFG, "daily_cap": 0}, timeout=30)
        try:
            r = requests.post(f"{BASE_URL}/api/careeros/applications/{app_id}/emails/draft", headers=h,
                              json={"kind": "relance", "notes": f"TEST_{uuid.uuid4()}"}, timeout=60)
            assert r.status_code == 503 and "plafond" in r.json()["detail"]
        finally:
            requests.put(URL, headers=A, json=DEFAULT_CFG, timeout=30)


# ---------- Reset of an exhausted provider (state injected in Mongo) ----------
class TestReset:
    def test_exhausted_then_reset(self):
        async def run():
            c = AsyncIOMotorClient(ENV["MONGO_URL"])
            db = c[ENV["DB_NAME"]]
            labels = [p["label"] for p in requests.get(URL, headers=A, timeout=30).json()["providers"]]
            if not labels:
                pytest.skip("no provider in chain")
            lb = labels[-1]
            until = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
            await db.ai_provider_state.update_one({"label": lb}, {"$set": {"exhausted_until": until, "last_error": "TEST_429 quota"}}, upsert=True)
            d = requests.get(URL, headers=A, timeout=30).json()
            p = next(x for x in d["providers"] if x["label"] == lb)
            assert p["exhausted"] is True and "TEST_429" in p["last_error"]
            r = requests.post(f"{URL}/reset/{lb}", headers=A, timeout=30)
            assert r.status_code == 200
            p = next(x for x in requests.get(URL, headers=A, timeout=30).json()["providers"] if x["label"] == lb)
            assert p["exhausted"] is False
            assert await db.ai_provider_state.count_documents({"label": lb}) == 0
            c.close()
        asyncio.run(run())


# ---------- Method-level tests of careeros.ai_budget (isolated temp DB) ----------
class TestModule:
    def test_quota_error_detection(self):
        from careeros import ai_budget as AB

        class E(Exception):
            status_code = 429
        assert AB.is_quota_error(E("x"))
        assert AB.is_quota_error(Exception("RESOURCE_EXHAUSTED: quota"))
        assert AB.is_quota_error(Exception("Too Many Requests"))
        assert not AB.is_quota_error(Exception("connection reset"))

    def test_cache_retry_window_and_gate(self):
        from careeros import ai_budget as AB

        async def run():
            AB._mem["exhausted"].clear()
            c = AsyncIOMotorClient(ENV["MONGO_URL"])
            db = c[f"test_ai_budget_{uuid.uuid4().hex[:8]}"]
            calls = {"n": 0}

            async def raw(s, u, tier):
                calls["n"] += 1
                return f"R{calls['n']}"
            try:
                gen = AB.governed(db, raw, ["gemini", "groq"])
                assert await gen("S", "U") == "R1"
                assert await gen("S", "U") == "R2"  # within 10 min -> deliberate retry bypasses cache
                await db.ai_cache.update_many({}, {"$set": {"used_at": (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()}})
                assert await gen("S", "U") == "R2" and calls["n"] == 2  # served from cache
                assert (await db.ai_cache_stats.find_one({}))["hits"] == 1
                assert await gen("S", "U", "premium") == "R3"  # tier part of key
                # free quotas all exhausted + paid off -> QuotaReached; cache still served before gate
                await AB.mark_exhausted(db, "gemini", "429")
                await AB.mark_exhausted(db, "groq", "429")
                with pytest.raises(AB.QuotaReached):
                    await gen("S", "other")
                # quotas gone: the cached answer is served even inside the retry window
                assert await gen("S", "U") == "R2"
                await db.ai_cache.update_many({}, {"$set": {"used_at": (datetime.now(timezone.utc) - timedelta(minutes=11)).isoformat()}})
                assert await gen("S", "U") == "R2"  # aged cache still served while quotas exhausted
                await db.ai_budget_config.update_one({"_id": "config"}, {"$set": {"allow_paid": True}}, upsert=True)
                assert await gen("S", "other") == "R4"
                # skip(): exhausted free provider skipped, paid only when allowed
                assert await AB.skip(db, "gemini") is True
                assert await AB.skip(db, "anthropic") is False
                await db.ai_budget_config.update_one({"_id": "config"}, {"$set": {"allow_paid": False}})
                assert await AB.skip(db, "anthropic") is True
                assert await AB.skip(db, "mistral") is False
            finally:
                AB._mem["exhausted"].clear()
                await c.drop_database(db.name)
                c.close()
        asyncio.run(run())
