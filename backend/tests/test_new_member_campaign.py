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


# iteration_52: Radar settings prefilled from Career Memory (target_roles + location)
def test_radar_settings_prefilled_from_profile(client):
    d = client.get(f"{BASE_URL}/api/careeros/radar/settings").json()
    assert "Analyste BI" in d["keywords"], d["keywords"]
    assert d["location"] == "Montréal", d["location"]


# iteration_52: prefill survives a settings doc holding only companies / zone marker
def test_radar_settings_prefill_after_follow(client):
    r = client.post(f"{BASE_URL}/api/careeros/radar/companies/follow", json={"name": "TEST Desjardins"})
    assert r.status_code in (200, 201), r.text
    d = client.get(f"{BASE_URL}/api/careeros/radar/settings").json()
    assert "Analyste BI" in d["keywords"], d["keywords"]
    assert d["location"] == "Montréal", d["location"]


# iteration_52: external offer first line parsing "Titre — Entreprise, Lieu"
def test_external_title_parsing(client):
    text = ("Analyste BI senior — Banque Laurentienne, Montréal (hybride)\n"
            "Nous recherchons un analyste BI senior avec 5 ans d'expérience en Power BI, SQL et Python pour soutenir nos équipes.\n"
            "Bilinguisme requis. Poste permanent.")
    r = client.post(f"{BASE_URL}/api/careeros/radar/external", json={"text": text})
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["title"] == "Analyste BI senior", o["title"]
    assert o["company"] == "Banque Laurentienne", o["company"]
    assert o["location"] == "Montréal (hybride)", o["location"]
    blob = str(o.get("ips")) + str(o.get("decision_report"))
    import re as _re
    m = _re.search(r"Expérience estimée dans le CV : (\d+) an", blob)
    assert m and int(m.group(1)) >= 7, blob[:800]


# iteration_52: empty profile -> stability 0 and levers empty-state
def test_strength_empty_profile():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register", json={"name": "TEST Vide", "email": f"test_empty.{int(time.time()*1000)}@careeros.dev", "password": "Campagne2026!x"})
    tok = r.json().get("access_token") or r.json().get("token")
    d = s.get(f"{BASE_URL}/api/careeros/strength", headers={"Authorization": f"Bearer {tok}"}).json()
    crit = {c["key"]: c for c in d["criteria"]}
    print({k: c["score"] for k, c in crit.items()}, d["score"])
    assert all(c["score"] == 0 for c in crit.values()), {k: c["score"] for k, c in crit.items()}


# iteration_52: evidence uses full words, not stems
def test_strength_evidence_full_words(client):
    client.put(f"{BASE_URL}/api/careeros/profile", json={"full_name": "TEST Campagne", "target_roles": "Analyste BI", "location": "Montréal", "city": "Montréal",
               "cv_text": CV + "\n- Encadrement d'une équipe de 3 analystes ; certification PL-300", "certifications": ["Microsoft PL-300"]})
    d = client.get(f"{BASE_URL}/api/careeros/strength").json()
    blob = str(d)
    import re as _re
    stems = _re.findall(r"«\s*(encadr|certif|gestio|dirig)\s*»", blob)
    assert not stems, stems
    print({c["key"]: c.get("summary") for c in d["criteria"]})
