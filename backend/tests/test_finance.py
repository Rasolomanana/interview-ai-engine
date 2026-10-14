"""Tests for Rentabilité CareerOS admin finance endpoints."""
import os
import time
import uuid
import requests
import pytest

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL", "").rstrip("/")
if not BASE_URL:
    # Fallback: read from frontend .env
    with open("/app/frontend/.env") as f:
        for line in f:
            if line.startswith("REACT_APP_BACKEND_URL="):
                BASE_URL = line.split("=", 1)[1].strip().strip('"').rstrip("/")

ADMIN_PWD = "admin2026"
H = {"X-Admin-Password": ADMIN_PWD, "Content-Type": "application/json"}
BAD = {"X-Admin-Password": "wrong", "Content-Type": "application/json"}

CUR_MONTH = time.strftime("%Y-%m")


# ---------- Auth / basic ----------
def test_finance_requires_admin():
    r = requests.get(f"{BASE_URL}/api/admin/finance", headers=BAD, timeout=30)
    assert r.status_code == 401


def test_finance_current_month():
    r = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["month"] == CUR_MONTH
    for k in ("revenue", "platform_cad", "ai_cad", "ai_est_cad", "costs_cad", "margin_cad",
              "members", "providers", "buckets", "features", "per_member", "scenarios",
              "pace", "history", "settings", "platform"):
        assert k in d, f"missing key {k}"
    # 6 months history
    assert len(d["history"]) == 6
    # members block fields
    for k in ("registered", "active", "paid", "active_paid"):
        assert k in d["members"]
    # projections
    assert sorted(s["members"] for s in d["scenarios"]) == [100, 500, 1000]


def test_finance_month_query():
    r = requests.get(f"{BASE_URL}/api/admin/finance?month=2026-01", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["month"] == "2026-01"


def test_finance_past_month_zero_platform():
    # Past month, never saved
    r = requests.get(f"{BASE_URL}/api/admin/finance?month=2024-01", headers=H, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["draft"] is True
    assert d["platform_cad"] == 0
    assert d["revenue"]["paid"] == 0


def test_finance_invalid_month_pattern():
    r = requests.get(f"{BASE_URL}/api/admin/finance?month=badmonth", headers=H, timeout=30)
    assert r.status_code == 422


# ---------- Settings ----------
def test_finance_settings_update_fx_and_pricing():
    body = {"fx_usd_cad": 1.40, "pricing": {"openrouter": {"in": 0.5, "out": 2.0}}}
    r = requests.put(f"{BASE_URL}/api/admin/finance-settings", headers=H, json=body, timeout=30)
    assert r.status_code == 200
    data = r.json()
    assert data["fx_usd_cad"] == 1.40
    assert data["pricing"]["openrouter"]["in"] == 0.5
    assert data["pricing"]["openrouter"]["out"] == 2.0
    # Restore defaults
    requests.put(f"{BASE_URL}/api/admin/finance-settings", headers=H,
                 json={"fx_usd_cad": 1.37, "pricing": {}}, timeout=30)


# ---------- Save month + computations ----------
def test_save_month_and_recalc():
    # Snapshot current month doc so we can restore later
    before = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30).json()
    orig_doc = before["doc"]

    body = {
        "price_cad": 20.0,
        "paid_override": 5,
        "adjustments": [
            {"label": "rabais client X", "kind": "rabais", "amount": 15},  # positive but should subtract
            {"label": "B2B school", "kind": "b2b", "amount": 200},
            {"label": "remb pierre", "kind": "remboursement", "amount": 10},
        ],
        "platform_costs": [
            {"name": "Render", "amount": 7.0, "currency": "USD"},
            {"name": "Domaine", "amount": 2.0, "currency": "CAD"},
        ],
        "ai_invoices": [{"provider": "openrouter", "amount": 0.5, "currency": "USD"}],
    }
    r = requests.put(f"{BASE_URL}/api/admin/finance/{CUR_MONTH}", headers=H, json=body, timeout=30)
    assert r.status_code == 200
    assert r.json().get("ok") is True

    s = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30).json()
    fx = s["fx_usd_cad"]
    # gross = price * paid
    assert s["revenue"]["gross"] == round(20.0 * 5, 2)
    # adjustments: -15 + 200 - 10 = 175
    assert s["revenue"]["adjustments"] == 175.0
    assert s["revenue"]["net"] == round(100.0 + 175.0, 2)
    # platform CAD: 7*fx + 2
    expected_platform = round(7.0 * fx + 2.0, 2)
    assert s["platform_cad"] == expected_platform
    # openrouter invoice real used
    op = next(p for p in s["providers"] if p["provider"] == "openrouter")
    assert op["real_cad"] == round(0.5 * fx, 2)
    assert op["gap_cad"] is not None
    # margin = net - platform - ai_used
    assert s["margin_cad"] == round(s["revenue"]["net"] - s["platform_cad"] - s["ai_cad"], 2)
    if s["revenue"]["net"]:
        assert s["margin_pct"] == round(s["margin_cad"] * 100 / s["revenue"]["net"], 1)

    # Restore
    restore = {k: orig_doc.get(k) for k in ("price_cad", "paid_override", "adjustments", "platform_costs", "ai_invoices")}
    requests.put(f"{BASE_URL}/api/admin/finance/{CUR_MONTH}", headers=H, json=restore, timeout=30)


def test_save_month_bad_month():
    r = requests.put(f"{BASE_URL}/api/admin/finance/notamonth", headers=H,
                     json={"price_cad": 10}, timeout=30)
    assert r.status_code == 422


# ---------- Members ----------
def test_members_list():
    r = requests.get(f"{BASE_URL}/api/admin/members", headers=H, timeout=30)
    assert r.status_code == 200
    arr = r.json()
    assert isinstance(arr, list)
    assert len(arr) >= 1
    for u in arr[:3]:
        for k in ("id", "email", "paid", "active_month", "recent"):
            assert k in u


def test_members_set_paid_404():
    r = requests.put(f"{BASE_URL}/api/admin/members/{uuid.uuid4()}/paid",
                     headers=H, json={"paid": True}, timeout=30)
    assert r.status_code == 404


def test_members_toggle_paid_affects_count():
    arr = requests.get(f"{BASE_URL}/api/admin/members", headers=H, timeout=30).json()
    if not arr:
        pytest.skip("no members")
    u = arr[0]
    original = bool(u["paid"])
    uid = u["id"]
    # Ensure paid_override=null so counts follow flags
    cur = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30).json()
    orig_doc = cur["doc"]
    body = {k: orig_doc.get(k) for k in ("price_cad", "adjustments", "platform_costs", "ai_invoices")}
    body["paid_override"] = None
    requests.put(f"{BASE_URL}/api/admin/finance/{CUR_MONTH}", headers=H, json=body, timeout=30)

    before = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30).json()["members"]["paid"]

    r = requests.put(f"{BASE_URL}/api/admin/members/{uid}/paid", headers=H,
                     json={"paid": not original}, timeout=30)
    assert r.status_code == 200
    after = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30).json()["members"]["paid"]
    assert after == before + (1 if not original else -1)

    # Restore flag and paid_override
    requests.put(f"{BASE_URL}/api/admin/members/{uid}/paid", headers=H,
                 json={"paid": original}, timeout=30)
    body["paid_override"] = orig_doc.get("paid_override")
    requests.put(f"{BASE_URL}/api/admin/finance/{CUR_MONTH}", headers=H, json=body, timeout=30)


# ---------- AI logging via /api/generate (SSE) ----------
def test_ai_generate_logs_usage():
    before = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30).json()
    calls_before = before.get("calls", 0)
    cop_before = next((f["calls"] for f in before["features"] if f["feature"] == "copilote"), 0)

    r = requests.post(f"{BASE_URL}/api/generate",
                      json={"system_message": "You are terse.", "turn_message": "Say OK."},
                      timeout=90, stream=True)
    assert r.status_code == 200
    # consume stream
    for _ in r.iter_lines():
        pass
    r.close()

    time.sleep(1.0)
    after = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30).json()
    assert after.get("calls", 0) >= calls_before + 1
    cop_after = next((f["calls"] for f in after["features"] if f["feature"] == "copilote"), 0)
    assert cop_after >= cop_before + 1


# ---------- Providers / invoice gap ----------
def test_providers_list_and_gap():
    s = requests.get(f"{BASE_URL}/api/admin/finance", headers=H, timeout=30).json()
    providers = {p["provider"] for p in s["providers"]}
    # google and anthropic & openrouter present (even when zero)
    assert "openrouter" in providers
