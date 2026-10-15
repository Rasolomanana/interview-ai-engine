# Admin trace (/api/admin/trace): row counts match displayed numbers + RBAC/privacy
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api/admin"
SUPER = {"X-Admin-Password": "admin2026"}


def _login(email, pwd):
    r = requests.post(f"{BASE_URL}/api/auth/login", json={"email": email, "password": pwd}, timeout=30)
    if r.status_code != 200:
        pytest.skip(f"login failed {email}")
    d = r.json()
    tok = d.get("access_token") or (d.get("tokens") or {}).get("access_token")
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def mkt():
    return _login("membre.test@careeros.dev", "CareerOS2026!")


@pytest.fixture(scope="module")
def cons():
    return _login("conseiller.test@careeros.dev", "Conseil2026!")


def tr(h, metric, key="", days=None):
    p = {"metric": metric, "key": key}
    if days is not None:
        p["days"] = days
    return requests.get(f"{API}/trace", params=p, headers=h, timeout=60)


def get(h, path, **params):
    r = requests.get(f"{API}/{path}", params=params, headers=h, timeout=60)
    assert r.status_code == 200, r.text
    return r.json()


# Overview members + radar
def test_overview_members_and_radar_match():
    ov = get(SUPER, "insights/overview", days=30)
    m, rd = ov["members"], ov["radar"]
    exp = {"m_total": m["total"], "m_active7": m["active_7d"], "m_active30": m["active_30d"], "m_new7": m["new_7d"],
           "m_new30": m["new_30d"], "m_paid": m["paid"], "r_enabled": rd["enabled"], "r_configured": rd["configured"],
           "r_members": rd["members_30d"], "r_runs": rd["runs_30d"], "r_auto": rd["runs_auto"], "r_manual": rd["runs_manual"],
           "r_analyzed": rd["analyzed_30d"], "r_packs": rd["packs_30d"]}
    bad = {}
    for k, v in exp.items():
        r = tr(SUPER, k)
        assert r.status_code == 200, (k, r.text)
        d = r.json()
        assert set(d) >= {"title", "cols", "rows", "total", "truncated", "note"}
        assert d["total"] == len(d["rows"])
        if d["total"] != min(v, 1000):
            bad[k] = (v, d["total"])
    assert not bad, bad


# Funnel for 30/90/0 days
@pytest.mark.parametrize("days", [30, 90, 0])
def test_funnel_match(days):
    ov = get(SUPER, "insights/overview", days=days)
    keys = ["f_visitors", "f_inscrits", "f_actifs", "f_payants", "f_renouv"]
    bad = {}
    for k, step in zip(keys, ov["funnel"]):
        d = tr(SUPER, k, days=days).json()
        if d["total"] != min(step["count"], 1000):
            bad[k] = (step["count"], d["total"])
    assert not bad, bad


# Geography
def test_geo_match_super():
    g = get(SUPER, "insights/geo")
    bad = {}
    for metric, part in (("g_country", "countries"), ("g_province", "provinces"), ("g_city", "cities")):
        for row in g[part]:
            d = tr(SUPER, metric, row["label"]).json()
            if d["total"] != row["count"]:
                bad[(metric, row["label"])] = (row["count"], d["total"])
    assert not bad, bad


def test_geo_match_marketing(mkt):
    g = get(mkt, "insights/geo")
    bad = {}
    for metric, part in (("g_country", "countries"), ("g_province", "provinces"), ("g_city", "cities")):
        for row in g[part]:
            r = tr(mkt, metric, row["label"])
            assert r.status_code == 200
            d = r.json()
            assert "@" not in str(d["rows"])
            if d["total"] != row["count"]:
                bad[(metric, row["label"])] = (row["count"], d["total"])
    assert not bad, bad


# Business
def test_business_match():
    b = get(SUPER, "insights/business")
    bad = {}
    for metric, rows in (("b_role", b["roles"]), ("b_company", b["companies"]), ("b_portal", b["portals"]), ("b_source", b["offers"]["by_source"])):
        for row in rows:
            d = tr(SUPER, metric, row["label"]).json()
            if d["total"] != row["count"]:
                bad[(metric, row["label"])] = (row["count"], d["total"])
    for p, c in b["priorities"]["radar_30d"].items():
        d = tr(SUPER, "b_prio_radar", p).json()
        if d["total"] != c:
            bad[("b_prio_radar", p)] = (c, d["total"])
    for p, c in b["priorities"]["applications"].items():
        d = tr(SUPER, "b_prio_apps", p).json()
        if d["total"] != c:
            bad[("b_prio_apps", p)] = (c, d["total"])
    for metric, c in (("b_offers30", b["offers"]["analyzed_30d"]), ("b_offers_total", b["offers"]["analyzed_total"])):
        d = tr(SUPER, metric).json()
        if d["total"] != min(c, 1000):
            bad[metric] = (c, d["total"])
    assert not bad, bad


# Activité (stats)
def test_activity_match():
    s = get(SUPER, "stats")
    t, llm = s["totals"], s["llm"]
    exp = {("a_visitors", ""): t["visitors"], ("a_simulations", ""): t["simulations"], ("a_ats", ""): t["ats_analyses"],
           ("a_cvs", ""): t["cvs_analyzed"], ("a_letters", ""): t["cover_letters"], ("a_llm", ""): llm["calls"],
           ("a_llm", "gemini"): llm["gemini_calls"], ("a_llm", "!gemini"): llm["server_calls"]}
    for p, v in (llm.get("by_provider") or {}).items():
        exp[("a_llm", p)] = v["calls"]
    bad = {}
    for (m, k), v in exp.items():
        d = tr(SUPER, m, k).json()
        if d["total"] != min(v, 1000):
            bad[(m, k)] = (v, d["total"])
    assert not bad, bad


# Finance
def test_finance_match():
    f = get(SUPER, "finance")
    mo = f["month"]
    mem = f["members"]
    bad = {}
    for m, v in (("fin_active", mem["active"]), ("fin_paid", mem["paid"]), ("fin_active_paid", mem["active_paid"]), ("fin_ai_calls", f["calls"])):
        d = tr(SUPER, m, mo).json()
        if d["total"] != v and not (m in ("fin_paid", "fin_active_paid") and "saisi manuellement" in (d.get("note") or "")):  # manual override is explained
            bad[m] = (v, d["total"])
    assert not bad, bad


def test_unknown_metric_422():
    for m in ("zzz", "m_bogus", "r_bogus", "a_bogus"):
        assert tr(SUPER, m).status_code == 422, m


def test_no_auth_401():
    assert tr({}, "m_total").status_code == 401


# Privacy / RBAC
def test_marketing_pseudonyms(mkt):
    for m in ("m_total", "r_runs", "r_analyzed", "f_inscrits"):
        r = tr(mkt, m)
        assert r.status_code == 200, (m, r.text)
        d = r.json()
        assert "@" not in str(d["rows"]), m
        if d["rows"] and "member" in d["rows"][0]:
            assert all(str(x["member"]).startswith("Membre #") for x in d["rows"]), m
        assert d["note"]


def test_marketing_packs_hidden(mkt):
    for m, k in (("r_packs", ""), ("b_prio_apps", "C")):
        d = tr(mkt, m, k).json()
        cols = [c[0] for c in d["cols"]]
        assert "poste" not in cols and "entreprise" not in cols
        assert all("poste" not in r for r in d["rows"])
        ds = tr(SUPER, m, k).json()
        assert "poste" in [c[0] for c in ds["cols"]] and "entreprise" in [c[0] for c in ds["cols"]]


def test_super_sees_email():
    d = tr(SUPER, "m_total").json()
    assert any("@" in r["member"] for r in d["rows"])


def test_marketing_fin_forbidden(mkt):
    for m in ("fin_active", "fin_paid", "fin_active_paid", "fin_ai_calls"):
        assert tr(mkt, m).status_code == 403, m


def test_conseiller_scope(cons):
    assert tr(cons, "b_prio_radar", "C").status_code == 200
    assert tr(cons, "b_offers30").status_code == 200
    for m in ("m_total", "f_inscrits", "r_runs", "g_city", "a_llm", "fin_paid"):
        assert tr(cons, m).status_code == 403, m
    d = tr(cons, "b_company", "Desjardins").json()
    assert "@" not in str(d["rows"])
