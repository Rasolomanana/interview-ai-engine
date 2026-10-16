# Prefilled search links (17 incl. employer site, Glassdoor, Québec ordering) + auto_sources + availability search regression
import os
import pytest
import requests

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")
API = f"{BASE_URL}/api"
APP_ID = "a793f26d-ecb6-465c-b3f3-5ca25a1d78f1"
QC = ["Jobillico", "Jobboom", "Québec emploi", "Isarta"]


@pytest.fixture(scope="module")
def s():
    r = requests.post(f"{API}/auth/login", json={"email": "membre.test@careeros.dev", "password": "CareerOS2026!"}, timeout=30)
    if r.status_code != 200:
        pytest.skip("login failed")
    d = r.json()
    ss = requests.Session()
    ss.headers.update({"Authorization": f"Bearer {d.get('access_token') or d.get('token')}"})
    return ss


def _labels(app):
    return [l["label"] for l in app["search_links"]]


def test_search_links_shape(s):
    r = s.get(f"{API}/careeros/applications/{APP_ID}", timeout=30)
    assert r.status_code == 200
    a = r.json()
    links = a["search_links"]
    print([l["label"] for l in links])
    assert len(links) == 17
    for l in links:
        assert set(["label", "url", "quebec"]) <= set(l)
        assert l["url"].startswith("http")
    labels = _labels(a)
    for need in ["Glassdoor", "Indeed", "LinkedIn", "Guichet-Emplois", "Google Emplois", "Careerjet", "Talent.com", "Monster", "Eluta",
                 "CareerBeacon", "Workopolis", "ZipRecruiter"] + QC:
        assert need in labels, need
    assert labels[0].startswith("Site carrière")
    assert {l["label"] for l in links if l["quebec"]} == set(QC)
    assert len(set(labels)) == len(labels)
    assert a["auto_sources"] == ["Portail officiel"]


def test_order_quebec_then_ontario(s):
    prof = s.get(f"{API}/careeros/profile", timeout=30).json()
    orig = prof.get("province", "")
    print("profile province:", repr(orig), "location:", prof.get("location"))
    try:
        body = dict(prof); body["province"] = "Québec"
        assert s.put(f"{API}/careeros/profile", json=body, timeout=30).status_code == 200
        lb = _labels(s.get(f"{API}/careeros/applications/{APP_ID}", timeout=30).json())
        print("QC:", lb)
        i = lb.index("LinkedIn")
        assert lb[lb.index("Indeed") + 1] == "LinkedIn"
        assert lb[i + 1:i + 5] == QC
        body["province"] = "Ontario"
        assert s.put(f"{API}/careeros/profile", json=body, timeout=30).status_code == 200
        lb = _labels(s.get(f"{API}/careeros/applications/{APP_ID}", timeout=30).json())
        print("ON:", lb)
        assert lb[-4:] == QC
    finally:
        body = dict(prof); body["province"] = orig
        s.put(f"{API}/careeros/profile", json=body, timeout=30)
    assert s.get(f"{API}/careeros/profile", timeout=30).json().get("province", "") == orig


def test_availability_search(s):
    r = s.post(f"{API}/careeros/applications/{APP_ID}/availability?search=true", timeout=90)
    assert r.status_code == 200
    d = r.json()
    print(d["availability"], [(x["source"], x["title"]) for x in d["alternatives"]])
    assert "availability" in d and isinstance(d["alternatives"], list)
    assert all(x["source"] != "Careerjet" for x in d["alternatives"])
    assert d.get("alternatives_at")


def test_unauth_404(s):
    assert requests.get(f"{API}/careeros/applications/{APP_ID}", timeout=30).status_code in (401, 403)
    assert s.get(f"{API}/careeros/applications/nonexistent-id", timeout=30).status_code == 404
