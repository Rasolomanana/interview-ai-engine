"""Tests for Rentabilité CareerOS admin finance endpoints (schema v2: lines/revenue_real + catalog)."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

ADMIN_PWD = os.environ.get("ADMIN_PASSWORD", "admin2026")
H = {"X-Admin-Password": ADMIN_PWD, "Content-Type": "application/json"}
BAD = {"X-Admin-Password": "wrong", "Content-Type": "application/json"}
CUR_MONTH = time.strftime("%Y-%m")
TEST_MONTH = "2027-03"  # dedicated test month, far in the future

FAMILIES = ("infrastructure", "ia", "developpement", "marketing", "autres")


# ---------- Auth / basic ----------
def test_finance_requires_admin():
    r = requests.get(f"{BASE_URL}/api/admin/finance", headers=BAD, timeout=30)
    assert r.status_code == 401


def test_finance_invalid_month_pattern():
    r = requests.get(f"{BASE_URL}/api/admin/finance?month=bad", headers=H, timeout=30)
    assert r.status_code == 422


# ---------- Catalog shape ----------
def test_finance_catalog_shape():
    r = requests.get(f"{BASE_URL}/api/admin/finance-catalog", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    for k in ("families", "ai_keys", "providers", "categories"):
        assert k in d
    assert set(d["families"].keys()) == set(FAMILIES)
    # 5 families seeded, so at least 5 categories (one per family)
    fams_present = {c["family"] for c in d["categories"]}
    assert fams_present == set(FAMILIES), f"missing families: {set(FAMILIES) - fams_present}"
    # ~17 providers
    assert len(d["providers"]) >= 15
    # 'used' flag per provider
    for p in d["providers"]:
        assert "used" in p and isinstance(p["used"], bool)
        for k in ("id", "name", "category_id", "recurrence", "default_amount", "currency", "status"):
            assert k in p


# ---------- Finance summary (new schema) ----------
def test_finance_summary_shape():
    r = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["month"] == CUR_MONTH
    for k in ("revenue", "families", "ops_cad", "dev_cad", "invest_cad", "total_cad",
              "operating_margin_cad", "net_margin_cad", "members", "lines", "buckets",
              "features", "per_member", "scenarios", "pace", "history", "settings", "doc"):
        assert k in d, f"missing key {k}"
    # revenue structure
    for k in ("price_cad", "paid", "theory", "adjustments", "expected", "real", "used",
              "nature", "gap_cad", "gap_pct", "unexplained_cad"):
        assert k in d["revenue"]
    # families structure
    for fk in FAMILIES:
        assert fk in d["families"]
        for k in ("used_cad", "est_cad", "real_cad", "invest_cad", "nature", "real_pct"):
            assert k in d["families"][fk]
    # members
    for k in ("registered", "active", "paid", "active_paid"):
        assert k in d["members"]
    # 6-month history
    assert len(d["history"]) == 6
    # 3 projections
    assert sorted(s["members"] for s in d["scenarios"]) == [100, 500, 1000]


def test_finance_preview_month_2026_10():
    """Preview DB has month 2026-10 with revenue_real=300, rabais=20, Render 7/6.5 USD, archived TestDev 500 CAD."""
    r = requests.get(f"{BASE_URL}/api/admin/finance?month=2026-10", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["month"] == "2026-10"
    assert d["revenue"]["real"] == 300
    assert d["revenue"]["nature"] == "real"
    # Render line should appear with est 7 / real 6.5 USD
    render = next((l for l in d["lines"] if l["name"].lower() == "render"), None)
    assert render is not None
    assert render["saved_estimated"] == 7
    assert render["saved_real"] == 6.5
    assert render["nature"] == "real"
    assert render["gap_cad"] is not None
    # TestDev is archived + has a real line -> should still appear
    testdev = next((l for l in d["lines"] if l["name"] == "TestDev"), None)
    assert testdev is not None, "archived provider with saved line must still appear"
    assert testdev["provider_status"] == "archived"
    assert testdev["family"] == "developpement"
    assert testdev["real_cad"] == 500.0
    # invest_cad includes TestDev (ponctuel developpement)
    assert d["invest_cad"] >= 500


# ---------- Catalog CRUD ----------
@pytest.fixture
def tmp_category():
    body = {"name": f"TEST_cat_{uuid.uuid4().hex[:6]}", "family": "autres"}
    r = requests.post(f"{BASE_URL}/api/admin/finance-categories", headers=H, json=body, timeout=30)
    assert r.status_code == 200, r.text
    cat = r.json()
    yield cat
    # Cleanup: remove providers first then category
    requests.delete(f"{BASE_URL}/api/admin/finance-categories/{cat['id']}", headers=H, timeout=30)


def test_category_crud_full_flow(tmp_category):
    cid = tmp_category["id"]
    # Edit
    r = requests.put(f"{BASE_URL}/api/admin/finance-categories/{cid}", headers=H,
                     json={"name": "TEST_cat_renamed", "family": "marketing"}, timeout=30)
    assert r.status_code == 200
    # Verify via GET catalog
    cat = requests.get(f"{BASE_URL}/api/admin/finance-catalog", headers=H, timeout=30).json()
    c = next((x for x in cat["categories"] if x["id"] == cid), None)
    assert c and c["name"] == "TEST_cat_renamed" and c["family"] == "marketing"
    # Archive
    r = requests.post(f"{BASE_URL}/api/admin/finance-categories/{cid}/archive", headers=H,
                     json={"archived": True}, timeout=30)
    assert r.status_code == 200
    cat = requests.get(f"{BASE_URL}/api/admin/finance-catalog", headers=H, timeout=30).json()
    c = next(x for x in cat["categories"] if x["id"] == cid)
    assert c["status"] == "archived"
    # Reactivate
    r = requests.post(f"{BASE_URL}/api/admin/finance-categories/{cid}/archive", headers=H,
                     json={"archived": False}, timeout=30)
    assert r.status_code == 200
    # Delete (empty category -> 200)
    r = requests.delete(f"{BASE_URL}/api/admin/finance-categories/{cid}", headers=H, timeout=30)
    assert r.status_code == 200


def test_category_delete_409_when_has_providers():
    # Create cat
    cat = requests.post(f"{BASE_URL}/api/admin/finance-categories", headers=H,
                        json={"name": f"TEST_catused_{uuid.uuid4().hex[:5]}", "family": "autres"}, timeout=30).json()
    cid = cat["id"]
    # Add provider in it
    prov = requests.post(f"{BASE_URL}/api/admin/finance-providers", headers=H,
                         json={"name": "TEST_prov_in_cat", "category_id": cid, "recurrence": "variable",
                               "default_amount": 0, "currency": "CAD"}, timeout=30).json()
    pid = prov["id"]
    # Delete -> 409
    r = requests.delete(f"{BASE_URL}/api/admin/finance-categories/{cid}", headers=H, timeout=30)
    assert r.status_code == 409
    # Cleanup
    requests.delete(f"{BASE_URL}/api/admin/finance-providers/{pid}", headers=H, timeout=30)
    requests.delete(f"{BASE_URL}/api/admin/finance-categories/{cid}", headers=H, timeout=30)


def test_provider_crud_and_audit(tmp_category):
    cid = tmp_category["id"]
    # Create
    body = {"name": "TEST_provcrud", "category_id": cid, "recurrence": "recurrent",
            "default_amount": 10.0, "currency": "USD", "start_month": "2027-01", "end_month": None,
            "suspended": False, "ai_key": None}
    r = requests.post(f"{BASE_URL}/api/admin/finance-providers", headers=H, json=body, timeout=30)
    assert r.status_code == 200
    p = r.json()
    pid = p["id"]
    assert p["name"] == "TEST_provcrud"
    # Edit (change amount & currency)
    body["default_amount"] = 25.0
    body["currency"] = "CAD"
    r = requests.put(f"{BASE_URL}/api/admin/finance-providers/{pid}", headers=H, json=body, timeout=30)
    assert r.status_code == 200
    # Audit should contain create + update
    aud = requests.get(f"{BASE_URL}/api/admin/finance-audit?entity_id={pid}", headers=H, timeout=30).json()
    actions = {a["action"] for a in aud}
    assert "create" in actions and "update" in actions
    # Archive
    r = requests.post(f"{BASE_URL}/api/admin/finance-providers/{pid}/archive", headers=H,
                     json={"archived": True}, timeout=30)
    assert r.status_code == 200
    aud = requests.get(f"{BASE_URL}/api/admin/finance-audit?entity_id={pid}", headers=H, timeout=30).json()
    assert "archive" in {a["action"] for a in aud}
    # Reactivate then delete (unused -> 200)
    requests.post(f"{BASE_URL}/api/admin/finance-providers/{pid}/archive", headers=H,
                  json={"archived": False}, timeout=30)
    r = requests.delete(f"{BASE_URL}/api/admin/finance-providers/{pid}", headers=H, timeout=30)
    assert r.status_code == 200


def test_provider_delete_409_when_used(tmp_category):
    cid = tmp_category["id"]
    prov = requests.post(f"{BASE_URL}/api/admin/finance-providers", headers=H,
                         json={"name": "TEST_provused", "category_id": cid, "recurrence": "variable",
                               "default_amount": 0, "currency": "CAD"}, timeout=30).json()
    pid = prov["id"]
    # Use it in a month line (real value triggers "used")
    body = {"price_cad": 19.99, "paid_override": 0, "revenue_real": None, "adjustments": [],
            "lines": [{"provider_id": pid, "estimated": None, "real": 42.0, "currency": "CAD", "note": ""}]}
    r = requests.put(f"{BASE_URL}/api/admin/finance/{TEST_MONTH}", headers=H, json=body, timeout=30)
    assert r.status_code == 200
    # Delete -> 409
    r = requests.delete(f"{BASE_URL}/api/admin/finance-providers/{pid}", headers=H, timeout=30)
    assert r.status_code == 409
    # Cleanup: empty the test month, then delete provider
    requests.put(f"{BASE_URL}/api/admin/finance/{TEST_MONTH}", headers=H,
                 json={"price_cad": 19.99, "paid_override": 0, "revenue_real": None,
                       "adjustments": [], "lines": []}, timeout=30)
    r = requests.delete(f"{BASE_URL}/api/admin/finance-providers/{pid}", headers=H, timeout=30)
    assert r.status_code == 200


# ---------- Month save: revenue math + lines + recurrent proposal ----------
def test_save_month_full_math_and_cleanup():
    """Save a full test month and verify theory/expected/real/gap/unexplained + ops/net margin + invest."""
    cat = requests.get(f"{BASE_URL}/api/admin/finance-catalog", headers=H, timeout=30).json()
    # Pick an infra provider + a developpement provider
    infra_cat = next(c for c in cat["categories"] if c["family"] == "infrastructure")
    dev_cat = next(c for c in cat["categories"] if c["family"] == "developpement")
    infra_prov = next(p for p in cat["providers"] if p["category_id"] == infra_cat["id"])
    dev_prov = next(p for p in cat["providers"] if p["category_id"] == dev_cat["id"] and p["recurrence"] == "ponctuel")

    body = {
        "price_cad": 20.0, "paid_override": 10, "revenue_real": 250.0,
        "adjustments": [
            {"label": "rabais X", "kind": "rabais", "amount": 15},
            {"label": "B2B", "kind": "b2b", "amount": 200},
            {"label": "remb", "kind": "remboursement", "amount": 10},
        ],
        "lines": [
            {"provider_id": infra_prov["id"], "estimated": 7.0, "real": 8.0, "currency": "USD", "note": ""},
            {"provider_id": dev_prov["id"], "estimated": None, "real": 500.0, "currency": "CAD", "note": ""},
        ],
    }
    r = requests.put(f"{BASE_URL}/api/admin/finance/{TEST_MONTH}", headers=H, json=body, timeout=30)
    assert r.status_code == 200

    s = requests.get(f"{BASE_URL}/api/admin/finance?month={TEST_MONTH}", headers=H, timeout=30).json()
    fx = s["fx_usd_cad"]

    # Revenue math
    assert s["revenue"]["theory"] == round(20.0 * 10, 2)                     # 200
    assert s["revenue"]["adjustments"] == -15 + 200 - 10                     # 175
    assert s["revenue"]["expected"] == round(200 + 175, 2)                   # 375
    assert s["revenue"]["real"] == 250.0
    assert s["revenue"]["used"] == 250.0
    assert s["revenue"]["nature"] == "real"
    assert s["revenue"]["gap_cad"] == round(250 - 200, 2)                    # +50
    assert s["revenue"]["unexplained_cad"] == round(250 - 375, 2)            # -125

    # Infra line: real=8 USD -> gap = 8-7 = 1 USD * fx
    infra_line = next(l for l in s["lines"] if l["provider_id"] == infra_prov["id"])
    assert infra_line["nature"] == "real"
    assert infra_line["real_cad"] == round(8.0 * fx, 2)
    assert infra_line["gap_cad"] == round((8.0 - 7.0) * fx, 2)

    # Dev ponctuel line counts towards invest_cad
    assert s["families"]["developpement"]["invest_cad"] >= 500
    assert s["invest_cad"] >= 500

    # Margins
    ops = s["ops_cad"]
    dev = s["dev_cad"]
    total = round(ops + dev, 2)
    assert abs(s["total_cad"] - total) < 0.01
    assert abs(s["operating_margin_cad"] - round(250 - ops, 2)) < 0.01
    assert abs(s["net_margin_cad"] - round(250 - total, 2)) < 0.01

    # Audit for month update
    aud = requests.get(f"{BASE_URL}/api/admin/finance-audit?entity_id={TEST_MONTH}", headers=H, timeout=30).json()
    assert any(a["action"] == "update" for a in aud)

    # Cleanup: empty the test month
    requests.put(f"{BASE_URL}/api/admin/finance/{TEST_MONTH}", headers=H,
                 json={"price_cad": 19.99, "paid_override": 0, "revenue_real": None,
                       "adjustments": [], "lines": []}, timeout=30)


def test_recurrent_auto_proposed_and_suspended_excluded(tmp_category):
    """Recurrent in-range -> appears with est_source='recurrent'. Suspended or out-of-range -> not auto-proposed."""
    cid = tmp_category["id"]
    # Three providers in a tmp category: in-range recurrent, suspended recurrent, out-of-range (end_month past)
    p_in = requests.post(f"{BASE_URL}/api/admin/finance-providers", headers=H,
                         json={"name": "TEST_rec_in", "category_id": cid, "recurrence": "recurrent",
                               "default_amount": 5.0, "currency": "CAD", "start_month": "2027-01",
                               "end_month": None, "suspended": False}, timeout=30).json()
    p_susp = requests.post(f"{BASE_URL}/api/admin/finance-providers", headers=H,
                           json={"name": "TEST_rec_susp", "category_id": cid, "recurrence": "recurrent",
                                 "default_amount": 9.0, "currency": "CAD", "start_month": "2027-01",
                                 "end_month": None, "suspended": True}, timeout=30).json()
    p_out = requests.post(f"{BASE_URL}/api/admin/finance-providers", headers=H,
                          json={"name": "TEST_rec_out", "category_id": cid, "recurrence": "recurrent",
                                "default_amount": 11.0, "currency": "CAD", "start_month": "2027-01",
                                "end_month": "2027-02", "suspended": False}, timeout=30).json()

    s = requests.get(f"{BASE_URL}/api/admin/finance?month={TEST_MONTH}", headers=H, timeout=30).json()
    names = {l["name"]: l for l in s["lines"]}
    assert "TEST_rec_in" in names
    assert names["TEST_rec_in"]["est_source"] == "recurrent"
    assert names["TEST_rec_in"]["est_cad"] == 5.0  # CAD, no FX
    assert "TEST_rec_susp" not in names, "suspended recurrent must NOT be auto-proposed"
    assert "TEST_rec_out" not in names, "out-of-range recurrent must NOT be auto-proposed"

    # Cleanup
    for pid in (p_in["id"], p_susp["id"], p_out["id"]):
        requests.delete(f"{BASE_URL}/api/admin/finance-providers/{pid}", headers=H, timeout=30)


def test_save_month_bad_pattern():
    r = requests.put(f"{BASE_URL}/api/admin/finance/notamonth", headers=H,
                     json={"price_cad": 10}, timeout=30)
    assert r.status_code == 422


# ---------- Members ----------
def test_members_list_and_404():
    arr = requests.get(f"{BASE_URL}/api/admin/members", headers=H, timeout=30).json()
    assert isinstance(arr, list) and len(arr) >= 1
    r = requests.put(f"{BASE_URL}/api/admin/members/{uuid.uuid4()}/paid",
                     headers=H, json={"paid": True}, timeout=30)
    assert r.status_code == 404


# ---------- AI logging regression via /api/generate ----------
def test_ai_generate_logs_usage():
    before = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30).json()
    calls_before = before.get("calls", 0)
    r = requests.post(f"{BASE_URL}/api/generate",
                      json={"system_message": "You are terse.", "turn_message": "Say OK."},
                      timeout=90, stream=True)
    assert r.status_code == 200
    for _ in r.iter_lines():
        pass
    r.close()
    time.sleep(1.0)
    after = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30).json()
    assert after.get("calls", 0) >= calls_before + 1
