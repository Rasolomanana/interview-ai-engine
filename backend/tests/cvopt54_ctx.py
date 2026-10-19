# Helper: logs both test members in, saves their original CVs + tokens to /tmp/cvopt54.json (never committed).
import json, os, requests
API = os.environ.get("REACT_APP_BACKEND_URL").rstrip("/") + "/api"
out = {}
for em, pw in [("optcv.0e28a9@careeros.dev", "Optim2026!x"), ("membre.test@careeros.dev", "CareerOS2026!")]:
    r = requests.post(f"{API}/auth/login", json={"email": em, "password": pw}, timeout=20).json()
    tok = r.get("access_token") or r.get("tokens", {}).get("access_token")
    h = {"Authorization": "Bearer " + tok}
    p = requests.get(f"{API}/careeros/profile", headers=h, timeout=20).json()
    v = requests.get(f"{API}/careeros/cv-optimize/versions", headers=h, timeout=20).json()["items"]
    out[em] = {"login": r, "cv": p.get("cv_text"), "nversions": len(v), "title": p.get("title") or p.get("headline")}
    print(em, list(r.keys()), len(p.get("cv_text") or ""), "versions", len(v), list(p.keys())[:15])
json.dump(out, open("/tmp/cvopt54.json", "w"), ensure_ascii=False)
