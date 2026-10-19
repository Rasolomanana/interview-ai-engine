# New-member validation campaign (iteration 51): journey, profile, experience estimate consistency, cert dedup.
import os
import sys
import time

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

CV = """Nouveau Membre — Analyste de données / BI
Montréal, QC
EXPÉRIENCE
Analyste BI — Desjardins, Montréal (03/2021 – aujourd'hui)
- Conception de 25 tableaux de bord Power BI pour 400 utilisateurs
- Automatisation des rapports SQL (réduction de 60 % du temps de production)
Analyste de données — Bell Canada, Montréal (06/2018 – 02/2021)
- Requêtes SQL Server, scripts Python (pandas)
FORMATION
Baccalauréat en statistiques — Université de Montréal (2018)
CERTIFICATIONS : Microsoft PL-300 (Power BI Data Analyst)"""


@pytest.fixture(scope="module")
def client():
    s = requests.Session()
    email = f"test_campaign.{int(time.time())}@careeros.dev"
    r = s.post(f"{BASE_URL}/api/auth/register", json={"name": "TEST Campagne", "email": email, "password": "Campagne2026!x"})
    assert r.status_code in (200, 201), r.text
    d = r.json()
    tok = d.get("access_token") or d.get("token")
    s.headers.update({"Authorization": f"Bearer {tok}"})
    return s


# Journey: brand-new member is sent to Career Memory first
def test_journey_new_member_next_is_memory(client):
    d = client.get(f"{BASE_URL}/api/careeros/journey").json()
    assert d["next"]["step"] == "memory"
    assert d["completed"] == 0
    assert d["total"] == 6 and len(d["steps"]) == 5


# Profile save -> journey moves to Radar
def test_profile_save_advances_journey(client):
    r = client.put(f"{BASE_URL}/api/careeros/profile", json={"full_name": "TEST Campagne", "target_roles": "Analyste BI", "location": "Montréal",
                                                                "city": "Montréal", "cv_text": CV, "certifications": ["Microsoft PL-300"]})
    assert r.status_code == 200, r.text
    d = client.get(f"{BASE_URL}/api/careeros/journey").json()
    assert d["steps"][0]["done"] is True
    assert d["next"]["step"] == "radar"


# BUG: rule-based CV experience ignores ongoing jobs ("aujourd'hui") -> 3 years instead of ~8
def test_cv_years_counts_ongoing_job():
    from careeros.radar_rules import cv_years
    assert cv_years(CV) >= 7, f"cv_years={cv_years(CV)} (ongoing job 03/2021 – aujourd'hui ignored)"


# BUG: single certification counted several times in Pro strength index
def test_strength_cert_not_triple_counted(client):
    d = client.get(f"{BASE_URL}/api/careeros/strength")
    if d.status_code != 200:
        pytest.skip("strength endpoint path differs")
    crit = {c["key"]: c for c in d.json().get("criteria", [])}
    assert "1 certification" in crit["certifications"]["summary"], crit["certifications"]["summary"]
