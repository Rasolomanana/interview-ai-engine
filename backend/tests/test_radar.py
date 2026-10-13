"""CareerOS Radar + Follow-up (lot 1) backend tests.
Covers: settings GET/PUT, run+dashboard, dedupe, IPS/decision_report shape,
ignore/pack isolation, cron auth, email drafts PATCH, interview .ics generation.
"""
import os
import time
import uuid

import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().rstrip("/")
API = f"{BASE_URL}/api"

SEED_EMAIL = "membre.test@careeros.dev"
SEED_PASSWORD = "CareerOS2026!"

RADAR_CRON_SECRET = None
with open("/app/backend/.env") as f:
    for line in f:
        if line.startswith("RADAR_CRON_SECRET="):
            RADAR_CRON_SECRET = line.split("=", 1)[1].strip().strip('"')


@pytest.fixture(scope="module")
def seed_h():
    r = requests.post(f"{API}/auth/login", json={"email": SEED_EMAIL, "password": SEED_PASSWORD}, timeout=15)
    assert r.status_code == 200, r.text
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


@pytest.fixture(scope="module")
def other_h():
    email = f"test_radar_other_{uuid.uuid4().hex[:8]}@careeros.dev"
    pw = "CareerOS2026!"
    r = requests.post(f"{API}/auth/register", json={"email": email, "password": pw, "name": "Test Other"}, timeout=15)
    assert r.status_code in (200, 201), r.text
    tok = r.json().get("access_token") or requests.post(
        f"{API}/auth/login", json={"email": email, "password": pw}, timeout=15).json()["access_token"]
    return {"Authorization": f"Bearer {tok}"}


# ---------------- Settings ----------------
class TestRadarSettings:
    def test_get_settings_defaults(self, seed_h):
        r = requests.get(f"{API}/careeros/radar/settings", headers=seed_h, timeout=15)
        assert r.status_code == 200, r.text
        d = r.json()
        assert "configured" in d and "daily_limit" in d
        assert d["daily_limit"] == 50
        # No Adzuna/Jooble keys in preview
        assert d["configured"].get("adzuna") is False
        assert d["configured"].get("jooble") is False
        assert d["configured"].get("workday") is True and d["configured"].get("boards") is True
        assert isinstance(d.get("companies"), list)
        assert all(isinstance(c, dict) and "name" in c and "enabled" in c for c in d["companies"])
        assert "boards" not in d

    def test_get_settings_requires_auth(self):
        r = requests.get(f"{API}/careeros/radar/settings", timeout=10)
        assert r.status_code in (401, 403)

    def test_put_settings_invalid_portal_kind(self, seed_h):
        body = {"enabled": True, "keywords": ["Data"], "location": "Québec", "sources": ["boards"],
                "companies": [{"name": "X", "kind": "WRONG", "slug": "x"}]}
        r = requests.put(f"{API}/careeros/radar/settings", headers=seed_h, json=body, timeout=15)
        assert r.status_code == 422, r.text

    def test_put_settings_roundtrip(self, seed_h):
        # Fetch, PUT same back, confirm persistence
        cur = requests.get(f"{API}/careeros/radar/settings", headers=seed_h, timeout=15).json()
        body = {k: cur[k] for k in ("enabled", "keywords", "location", "companies", "sources")}
        r = requests.put(f"{API}/careeros/radar/settings", headers=seed_h, json=body, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["keywords"] == cur["keywords"]


    def test_adzuna_dropped_without_key_and_portal_parsed(self, seed_h, other_h):
        body = {"enabled": True, "keywords": ["analyste"], "location": "Québec", "sources": ["jooble", "workday", "adzuna"],
                "companies": ["Metro", {"name": "Desjardins", "portal_url": "https://desjardins.wd10.myworkdayjobs.com/fr-CA/Desjardins"},
                              {"name": "metro", "enabled": False}]}
        d = requests.put(f"{API}/careeros/radar/settings", headers=other_h, json=body, timeout=15).json()
        assert "adzuna" not in d["sources"]
        assert [c["name"] for c in d["companies"]] == ["Metro", "Desjardins"]
        assert d["companies"][1]["kind"] == "workday" and d["companies"][1]["slug"] == "desjardins.wd10/Desjardins"

    def test_portal_detect(self, seed_h):
        r = requests.post(f"{API}/careeros/radar/portal/detect", headers=seed_h,
                          json={"url": "https://emploi.hydroquebec.com/", "name": "Hydro-Québec"}, timeout=30).json()
        assert r["ok"] is False and r["kind"] == ""
        assert "Jooble" in (r.get("message") or "")

    def test_portal_detect_requires_auth(self):
        r = requests.post(f"{API}/careeros/radar/portal/detect", json={"url": "https://x.wd1.myworkdayjobs.com/foo"}, timeout=15)
        assert r.status_code in (401, 403)

    def test_portal_detect_desjardins_workday(self, seed_h):
        r = requests.post(f"{API}/careeros/radar/portal/detect", headers=seed_h,
                          json={"url": "https://desjardins.wd10.myworkdayjobs.com/fr-CA/Desjardins", "name": "Desjardins"},
                          timeout=60).json()
        assert r["kind"] == "workday", r
        assert r["ok"] is True, r
        assert r["count"] > 0, r

    def test_settings_no_boards_key_and_companies_objects(self, seed_h):
        d = requests.get(f"{API}/careeros/radar/settings", headers=seed_h, timeout=15).json()
        assert "boards" not in d
        for c in d["companies"]:
            assert set(["name", "enabled", "portal_url", "kind", "slug"]).issubset(c.keys())
        for k in ("jooble", "adzuna", "workday", "boards"):
            assert k in d["configured"]


# ---------------- Run + Dashboard + Dedupe ----------------
def _poll_done(headers, timeout_s=240):
    """Wait for last_run.status == done (or absent). Returns dashboard."""
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        r = requests.get(f"{API}/careeros/radar/dashboard", headers=headers, timeout=20)
        assert r.status_code == 200, r.text
        d = r.json()
        lr = d.get("last_run")
        if not lr or lr.get("status") != "running":
            return d
        time.sleep(5)
    pytest.fail("Radar run did not finish in time")


class TestRadarRun:
    def test_run_returns_started_immediately(self, seed_h):
        # Make sure no run in progress first
        _poll_done(seed_h, timeout_s=240)
        r = requests.post(f"{API}/careeros/radar/run", headers=seed_h, timeout=20)
        assert r.status_code == 200, r.text
        assert r.json().get("started") is True
        # Second call while running -> 409
        r2 = requests.post(f"{API}/careeros/radar/run", headers=seed_h, timeout=20)
        assert r2.status_code == 409, r2.text
        self._dash1 = _poll_done(seed_h, timeout_s=240)
        assert self._dash1["last_run"]["status"] == "done"

    def test_dashboard_shape(self, seed_h):
        d = requests.get(f"{API}/careeros/radar/dashboard", headers=seed_h, timeout=15).json()
        assert d["daily_limit"] == 50
        assert "analyzed_today" in d
        for k in ("top_a", "top_b", "ignored", "packed", "new_today"):
            assert isinstance(d.get(k), list), k
        lr = d["last_run"]
        for k in ("fetched", "new", "known", "analyzed", "skipped_limit", "errors", "status", "selected_sources", "by_source"):
            assert k in lr, k
        for src in ("jooble", "workday", "boards", "adzuna"):
            assert src in lr["by_source"] and set(lr["by_source"][src].keys()) >= {"fetched", "analyzed"}, lr["by_source"]
        ss = d.get("sources_status") or {}
        assert set(ss["configured"]) >= {"jooble", "workday", "boards", "adzuna"}
        assert isinstance(ss.get("selected"), list)
        # Daily limit respected
        assert d["analyzed_today"] <= 50

    def test_dedupe_second_run(self, seed_h):
        d_before = requests.get(f"{API}/careeros/radar/dashboard", headers=seed_h, timeout=15).json()
        analyzed_before = d_before["analyzed_today"]
        r = requests.post(f"{API}/careeros/radar/run", headers=seed_h, timeout=20)
        assert r.status_code == 200
        d_after = _poll_done(seed_h, timeout_s=240)
        lr = d_after["last_run"]
        # Dedupe should kick in: new==0, known>=1 (we just created them)
        assert lr["new"] == 0, lr
        assert lr["known"] >= 1, lr
        assert d_after["analyzed_today"] == analyzed_before


# ---------------- IPS shape & decision_report ----------------
class TestIpsShape:
    def test_offer_ips_and_decision_report(self, seed_h):
        d = requests.get(f"{API}/careeros/radar/dashboard", headers=seed_h, timeout=15).json()
        offers = (d["top_a"] + d["top_b"] + d["ignored"] + d["packed"])
        analyzed = [o for o in offers if o.get("ips")]
        assert analyzed, "No analyzed offer available — seed empty?"
        o = analyzed[0]
        ips = o["ips"]
        assert "criteria" in ips or "ips_criteria" in ips or isinstance(ips.get("score"), (int, float))
        assert "score" in ips and 0 <= ips["score"] <= 100
        assert ips.get("priority") in ("A", "B", "C")
        # Round(sum points) sanity
        assert isinstance(ips["score"], int) or float(ips["score"]).is_integer()
        rep = o.get("decision_report") or {}
        summary = rep.get("summary") or ""
        assert summary.startswith("IPS Radar CareerOS :"), summary[:120]
        assert "(provisoire, recalculé dans le pack)" in summary, summary[:200]
        assert f"{ips['score']}/100" in summary
        assert f"priorité {ips['priority']}" in summary
        # Radar V2: stage=='radar' and 8 criteria (exclude qualite_lettre + force_reseau)
        assert ips.get("stage") == "radar", ips
        rows = ips.get("criteria") or []
        keys = [c["key"] for c in rows]
        assert "qualite_lettre" not in keys and "force_reseau" not in keys, keys
        assert len(rows) == 8, rows
        # Priority consistency with thresholds
        score, prio, ko, gf = ips["score"], ips["priority"], ips.get("knockout"), ips.get("goal_fit", 5)
        if prio == "A":
            assert score >= 70 and gf >= 6 and not ko
        elif prio == "B":
            assert score >= 50 and not ko
        else:  # C
            assert ko or score < 50 or (score < 70 or gf < 6)
        # excerpt flag exists on the offer
        assert "excerpt" in o, "offer missing excerpt field"

    def test_runs_endpoint(self, seed_h):
        r = requests.get(f"{API}/careeros/radar/runs?days=30", headers=seed_h, timeout=15)
        assert r.status_code == 200, r.text
        runs = r.json()
        assert isinstance(runs, list)
        if runs:
            for run in runs[:3]:
                assert "user_id" not in run, "runs leaks user_id"
                assert "at" in run and "status" in run

    def test_pack_gives_official_ips_stage_pack(self, seed_h):
        """After packing a radar offer, the generated application pack should have the official IPS (stage=pack, 10 criteria)."""
        aid = getattr(pytest, "app_from_pack", None)
        if not aid:
            pytest.skip("No application from pack test available")
        a = requests.get(f"{API}/careeros/applications/{aid}", headers=seed_h, timeout=30).json()
        ips = a.get("ips") or {}
        if not ips:
            pytest.skip("Application pack has no IPS yet (generation may be async)")
        assert ips.get("stage") == "pack", ips.get("stage")
        rows = ips.get("criteria") or []
        if rows:
            keys = [c["key"] for c in rows]
            assert "qualite_lettre" in keys and "force_reseau" in keys, keys
            assert len(rows) == 10
        rep = a.get("decision_report") or {}
        summary = rep.get("summary") or ""
        if summary:
            assert summary.startswith("IPS officiel CareerOS :"), summary[:120]


# ---------------- Ignore / Pack / Isolation ----------------
class TestOfferActions:
    def test_ignore_and_pack(self, seed_h):
        d = requests.get(f"{API}/careeros/radar/dashboard", headers=seed_h, timeout=15).json()
        candidates = [o for o in (d["top_a"] + d["top_b"] + d["ignored"]) if o.get("ips") and o.get("status") not in ("pack", "ignoree")]
        if not candidates:
            pytest.skip("No active analyzed offer to act on.")
        off = candidates[0]
        # Ignore
        r = requests.post(f"{API}/careeros/radar/offers/{off['id']}/ignore", headers=seed_h, timeout=15)
        assert r.status_code == 200, r.text
        d2 = requests.get(f"{API}/careeros/radar/dashboard", headers=seed_h, timeout=15).json()
        assert any(o["id"] == off["id"] for o in d2["ignored"])

    def test_pack_creates_application_and_idempotent(self, seed_h):
        d = requests.get(f"{API}/careeros/radar/dashboard", headers=seed_h, timeout=15).json()
        candidates = [o for o in (d["top_a"] + d["top_b"]) if o.get("ips") and o.get("status") == "nouvelle"]
        if not candidates:
            # fallback — any analyzed non-packed (priority C offers are in `ignored` bucket but still packable)
            all_offers = d["top_a"] + d["top_b"] + d["ignored"]
            candidates = [o for o in all_offers if o.get("ips") and o.get("status") != "pack"]
        if not candidates:
            pytest.skip("No analyzed offer available to pack.")
        off = candidates[0]
        r = requests.post(f"{API}/careeros/radar/offers/{off['id']}/pack", headers=seed_h, timeout=180)
        assert r.status_code == 200, r.text
        res = r.json()
        app_id = res["id"]
        # Fetch application to verify code CO-YYYY-NNNNNN + origin
        a = requests.get(f"{API}/careeros/applications/{app_id}", headers=seed_h, timeout=15).json()
        import re
        assert re.match(r"^CO-\d{4}-\d{6}$", a["code"]), a.get("code")
        origin = a.get("origin") or {}
        assert origin.get("type") == "radar", origin
        # Idempotent
        r2 = requests.post(f"{API}/careeros/radar/offers/{off['id']}/pack", headers=seed_h, timeout=30)
        assert r2.status_code == 200
        assert r2.json().get("already") is True
        assert r2.json()["id"] == app_id
        pytest.app_from_pack = app_id  # type: ignore
        pytest.offer_id_other_test = off["id"]  # type: ignore

    def test_cross_member_isolation(self, other_h):
        off_id = getattr(pytest, "offer_id_other_test", None)
        if not off_id:
            pytest.skip("No offer to try cross-member on.")
        r = requests.post(f"{API}/careeros/radar/offers/{off_id}/ignore", headers=other_h, timeout=15)
        assert r.status_code == 404
        r2 = requests.post(f"{API}/careeros/radar/offers/{off_id}/pack", headers=other_h, timeout=15)
        assert r2.status_code == 404


# ---------------- Cron ----------------
class TestCron:
    def test_cron_without_secret(self):
        r = requests.post(f"{API}/careeros/radar/cron", timeout=15)
        assert r.status_code == 401

    def test_cron_wrong_secret(self):
        r = requests.post(f"{API}/careeros/radar/cron", headers={"X-Cron-Secret": "nope"}, timeout=15)
        assert r.status_code == 401

    def test_cron_correct_secret(self):
        assert RADAR_CRON_SECRET, "RADAR_CRON_SECRET missing"
        r = requests.post(f"{API}/careeros/radar/cron", headers={"X-Cron-Secret": RADAR_CRON_SECRET}, timeout=15)
        assert r.status_code == 200
        assert r.json().get("started") is True


# ---------------- Follow-up emails + interviews + ics ----------------
class TestFollowup:
    @pytest.fixture(scope="class")
    def app_id(self, seed_h):
        # Use the application created by the pack test if available, else existing seeded one.
        aid = getattr(pytest, "app_from_pack", None)
        if aid:
            return aid
        r = requests.get(f"{API}/careeros/applications", headers=seed_h, timeout=15)
        assert r.status_code == 200, r.text
        apps = r.json()
        assert apps, "No applications available"
        return apps[0]["id"]

    def test_email_draft_confirmation(self, seed_h, app_id):
        r = requests.post(f"{API}/careeros/applications/{app_id}/emails/draft", headers=seed_h,
                          json={"kind": "confirmation", "recruiter_name": "Alex RH"}, timeout=120)
        assert r.status_code == 200, r.text
        d = r.json()
        assert d["status"] == "brouillon"
        assert d["requires_member_validation"] is True
        assert d.get("application_code", "").startswith("CO-")
        assert d["kind"] == "confirmation"
        assert d["body"]
        pytest.email_id = d["id"]  # type: ignore

    def test_email_patch_pret(self, seed_h, app_id):
        eid = getattr(pytest, "email_id", None)
        assert eid
        r = requests.patch(f"{API}/careeros/applications/{app_id}/emails/{eid}",
                           headers=seed_h, json={"changes": {"status": "pret"}}, timeout=15)
        assert r.status_code == 200, r.text
        assert r.json()["status"] == "pret"

    def test_interview_and_ics(self, seed_h, app_id):
        from datetime import datetime, timedelta, timezone
        at = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat()
        r = requests.post(f"{API}/careeros/applications/{app_id}/interviews", headers=seed_h,
                          json={"stage": "rh", "scheduled_at": at, "mode": "visio", "duration_min": 45}, timeout=15)
        assert r.status_code == 200, r.text
        iv = r.json()
        iid = iv["id"]
        pytest.interview_id = iid  # type: ignore
        r2 = requests.get(f"{API}/careeros/applications/{app_id}/interviews/{iid}/ics", headers=seed_h, timeout=15)
        assert r2.status_code == 200, r2.text
        assert "text/calendar" in r2.headers.get("content-type", ""), r2.headers
        text = r2.text
        assert "BEGIN:VCALENDAR" in text
        assert "DTSTART:" in text
        assert "SUMMARY:" in text
        # Code should be in DESCRIPTION
        a = requests.get(f"{API}/careeros/applications/{app_id}", headers=seed_h, timeout=15).json()
        assert a["code"] in text

    def test_ics_cross_member_404(self, other_h, app_id):
        iid = getattr(pytest, "interview_id", None)
        assert iid
        r = requests.get(f"{API}/careeros/applications/{app_id}/interviews/{iid}/ics", headers=other_h, timeout=15)
        assert r.status_code == 404
