"""Helper (iter 57): create a fresh TEST_ radar member cloned from membre.test (CV + radar settings); writes /tmp/fresh57.json."""
import json
import uuid

import requests

BASE = [l.split("=", 1)[1].strip() for l in open("/app/frontend/.env") if l.startswith("REACT_APP_BACKEND_URL=")][0].rstrip("/")
A = f"{BASE}/api"


def login(e, p):
    r = requests.post(f"{A}/auth/login", json={"email": e, "password": p}, timeout=20)
    return {"Authorization": f"Bearer {r.json()['access_token']}"}


src = login("membre.test@careeros.dev", "CareerOS2026!")
prof = requests.get(f"{A}/careeros/profile", headers=src, timeout=20).json()
sett = requests.get(f"{A}/careeros/radar/settings", headers=src, timeout=20).json()
email, pw = f"test_radar_ui_{uuid.uuid4().hex[:8]}@careeros.dev", "CareerOS2026!"
requests.post(f"{A}/auth/register", json={"email": email, "password": pw, "name": "TEST_ Radar UI"}, timeout=20)
h = login(email, pw)
uid = requests.get(f"{A}/auth/me", headers=h, timeout=20).json().get("id")
body = {k: v for k, v in prof.items() if k not in ("user_id", "skills_detected", "updated_at", "career_score")}
print(requests.put(f"{A}/careeros/profile", json=body, headers=h, timeout=30).status_code)
sb = {k: sett.get(k) for k in ("keywords", "location", "radius", "zones", "companies", "sources", "expand") if k in sett}
print(requests.put(f"{A}/careeros/radar/settings", json=sb, headers=h, timeout=30).status_code)
json.dump({"email": email, "pw": pw, "uid": uid}, open("/tmp/fresh57.json", "w"))
print(email, uid)
