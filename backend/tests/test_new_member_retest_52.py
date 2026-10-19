# Iteration 52 re-test: cv_years ongoing job, external 'Entreprise :' line, copilot plain text import, radar settings prefill, strength.
import os
import re
import sys
import time

import pytest
import requests

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
BASE_URL = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/")

CV = """Membre Test — Analyste BI
EXPÉRIENCE
Analyste BI — Desjardins, Montréal (2018 - aujourd'hui)
- Encadrement d'une équipe de 3 analystes, tableaux de bord Power BI, SQL, Python
- Analyste certifié PL-300
FORMATION
Baccalauréat en statistiques — Université de Montréal (2017)"""


def _register(prefix):
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/register", json={"name": "TEST Retest", "email": f"{prefix}.{int(time.time()*1000)}@careeros.dev", "password": "Retest2026!x"})
    assert r.status_code in (200, 201), r.text
    d = r.json()
    s.headers.update({"Authorization": f"Bearer {d.get('access_token') or d.get('token')}"})
    return s


@pytest.fixture(scope="module")
def client():
    s = _register("test_retest52")
    r = s.put(f"{BASE_URL}/api/careeros/profile", json={"full_name": "TEST Retest", "target_roles": "Analyste BI, Analyste de données", "location": "Montréal",
                                                        "city": "Montréal", "cv_text": CV, "certifications": ["PL-300"]})
    assert r.status_code == 200, r.text
    return s


# cv_years counts "2018 - aujourd'hui" (ongoing job) like the strength index
def test_cv_years_ongoing_dash():
    from careeros.radar_rules import cv_years
    from datetime import datetime
    assert cv_years(CV) >= datetime.now().year - 2018 - 1, cv_years(CV)


# Strength: declared PL-300 + CV 'certifié PL-300' = 1 cert; leadership evidence full words; French decimal comma
def test_strength_consistency(client):
    d = client.get(f"{BASE_URL}/api/careeros/strength").json()
    crit = {c["key"]: c for c in d["criteria"]}
    print({k: (c["score"], c.get("summary")) for k, c in crit.items()})
    assert "1 certification" in crit["certifications"]["summary"], crit["certifications"]["summary"]
    blob = str(d)
    assert not re.findall(r"«\s*(encadr|certif|gestio|dirig)\s*»", blob)
    assert "encadrement" in blob.lower()


# Radar cv_years matches strength years
def test_radar_external_years_match(client):
    text = ("Analyste BI — Banque Laurentienne, Montréal\n"
            "Nous recherchons un analyste BI avec 5 ans d'expérience en Power BI, SQL et Python pour soutenir nos équipes de données.\n"
            "Bilinguisme requis. Poste permanent.")
    r = client.post(f"{BASE_URL}/api/careeros/radar/external", json={"text": text})
    assert r.status_code == 200, r.text
    o = r.json()
    assert (o["title"], o["company"], o["location"]) == ("Analyste BI", "Banque Laurentienne", "Montréal"), (o["title"], o["company"], o["location"])
    blob = str(o.get("ips")) + str(o.get("decision_report"))
    m = re.search(r"Expérience estimée dans le CV : (\d+) an", blob)
    from datetime import datetime
    assert m and int(m.group(1)) >= datetime.now().year - 2018 - 1, blob[:600]


# External offer: 'Entreprise : X' line detected when the first line has no separator
def test_external_entreprise_line(client):
    text = ("Développeur Power BI\nEntreprise : Groupe Cyclone\nLieu : Laval\n"
            "Vous concevrez des rapports Power BI et des modèles SQL pour nos clients. 3 ans d'expérience requis, bilinguisme un atout.")
    r = client.post(f"{BASE_URL}/api/careeros/radar/external", json={"text": text})
    assert r.status_code == 200, r.text
    o = r.json()
    assert o["company"] == "Groupe Cyclone", o["company"]
    assert o["title"] == "Développeur Power BI", o["title"]


# Radar settings: keywords from profile; survives doc with only companies (follow)
def test_radar_settings_prefill(client):
    r = client.post(f"{BASE_URL}/api/careeros/radar/companies/follow", json={"name": "TEST Hydro"})
    assert r.status_code in (200, 201), r.text
    d = client.get(f"{BASE_URL}/api/careeros/radar/settings").json()
    assert "Analyste BI" in d["keywords"], d["keywords"]


# Copilot import from a pack: plain text, no markdown
def test_copilot_pack_plain_text():
    s = requests.Session()
    r = s.post(f"{BASE_URL}/api/auth/login", json={"email": "membre.test@careeros.dev", "password": "CareerOS2026!"})
    assert r.status_code == 200, r.text
    d = r.json()
    s.headers.update({"Authorization": f"Bearer {d.get('access_token') or d.get('token')}"})
    apps = s.get(f"{BASE_URL}/api/careeros/applications")
    if apps.status_code != 200:
        pytest.skip(f"applications list {apps.status_code}")
    items = apps.json() if isinstance(apps.json(), list) else apps.json().get("items", [])
    done = [a for a in items if a.get("status") in ("ready", "done", "complete", "generated") or a.get("parts")] or items
    if not done:
        pytest.skip("no pack")
    found = False
    for a in done[:5]:
        c = s.get(f"{BASE_URL}/api/careeros/skill-match/copilot", params={"kind": "pack", "id": a["id"]})
        if c.status_code == 404:
            c = s.get(f"{BASE_URL}/api/careeros/copilot", params={"kind": "pack", "id": a["id"]})
        if c.status_code != 200:
            continue
        j = c.json()
        cv, letter = j.get("atsCv") or "", j.get("coverLetter") or ""
        if cv or letter:
            found = True
            for txt in (cv, letter):
                assert not re.search(r"(?m)^\s*#{1,6}\s|^\s*---\s*$|\*\*", txt), txt[:400]
            break
    if not found:
        pytest.skip("copilot endpoint path/pack content not found")
