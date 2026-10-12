import json, os, time, sys, requests

B = "https://interview-ai-engine.onrender.com/api"
R = []
def ok(name, cond, info=""):
    R.append((name, bool(cond), info)); print(("PASS " if cond else "FAIL ") + name, info)

ts = int(time.time())
A = {"email": f"validation+prod{ts}@careeros.dev", "password": "ProdCheck2026!", "name": "Validation Prod"}
Bm = {"email": f"validation+iso{ts}@careeros.dev", "password": "ProdCheck2026!", "name": "Isolation"}

r = requests.post(f"{B}/auth/register", json=A, timeout=60); ok("register A 200", r.status_code == 200, r.status_code)
ta = r.json()
ok("register returns tokens", ta.get("access_token") and ta.get("refresh_token"))
r = requests.post(f"{B}/auth/register", json=A, timeout=60); ok("duplicate email 409", r.status_code == 409, r.status_code)
r = requests.post(f"{B}/auth/register", json={**A, "email": f"x{ts}@careeros.dev", "password": "short"}, timeout=60); ok("short password 422", r.status_code == 422, r.status_code)
r = requests.post(f"{B}/auth/login", json={"email": A["email"], "password": A["password"]}, timeout=60); ok("login OK 200", r.status_code == 200, r.status_code)
ta = r.json(); HA = {"Authorization": f"Bearer {ta['access_token']}"}
r = requests.get(f"{B}/auth/me", headers=HA, timeout=60); ok("me returns user", r.status_code == 200 and r.json()["email"] == A["email"])
r = requests.post(f"{B}/auth/login", json={"email": A["email"], "password": "wrong"}, timeout=60); ok("wrong password 401", r.status_code == 401, r.json().get("detail"))
r = requests.get(f"{B}/careeros/profile", timeout=60); ok("no token 401", r.status_code == 401)
r = requests.get(f"{B}/careeros/profile", headers={"Authorization": "Bearer abc.def.ghi"}, timeout=60); ok("bad token 401", r.status_code == 401)
r = requests.get(f"{B}/careeros/profile", headers={"Authorization": f"Bearer {ta['refresh_token']}"}, timeout=60); ok("refresh token refused as access 401", r.status_code == 401)
r = requests.post(f"{B}/auth/refresh", json={"refresh_token": ta["refresh_token"]}, timeout=60); ok("refresh 200", r.status_code == 200 and r.json().get("access_token"))

# brute force on a throwaway email
bf = {"email": f"validation+bf{ts}@careeros.dev", "password": "ProdCheck2026!"}
requests.post(f"{B}/auth/register", json=bf, timeout=60)
codes = [requests.post(f"{B}/auth/login", json={"email": bf["email"], "password": "bad"}, timeout=60).status_code for _ in range(6)]
r = requests.post(f"{B}/auth/login", json=bf, timeout=60)
ok("brute force lockout (5x401 then 429, even good pw)", codes[:5] == [401]*5 and codes[5] == 429 and r.status_code == 429, f"{codes} good={r.status_code}")

# Atlas write/read: profile
prof = {"full_name": "Validation Prod", "headline": "Analyste de données", "location": "Montréal",
        "cv_text": "", "goals": ["changer d'emploi"], "target_roles": "Analyste BI", "sectors": "Énergie",
        "salary_expectation": "90k", "skills": ["SQL", "Python", "Power BI"], "certifications": [], "education": ["B.Sc. Statistique"],
        "languages": ["français", "anglais"], "achievements": "Reporting -30 %", "promotions": 0}
r = requests.put(f"{B}/careeros/profile", headers=HA, json=prof, timeout=60); ok("Atlas write profile", r.status_code == 200, r.status_code)
r = requests.get(f"{B}/careeros/profile", headers=HA, timeout=60); ok("Atlas read profile", r.json().get("target_roles") == "Analyste BI")
r = requests.get(f"{B}/careeros/career-score", headers=HA, timeout=60)
cs = r.json().get("current") or {}
ok("Career Score stored after profile save", r.status_code == 200 and isinstance(cs.get("score"), int) and cs.get("level"), f"{cs.get('score')} {cs.get('level')} hist={len(r.json().get('history', []))}")
ok("Career Score components = 5, weights sum 100", len(cs.get("components", [])) == 5 and sum(c["weight"] for c in cs["components"]) == 100)
ok("Career Score points sum == score", abs(round(sum(c["points"] for c in cs["components"])) - cs["score"]) <= 1)

r = requests.post(f"{B}/auth/register", json=Bm, timeout=60); HB = {"Authorization": f"Bearer {r.json()['access_token']}"}
json.dump({"A": A, "B": Bm}, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ctx.json"), "w"), indent=1)
print("SUMMARY", sum(1 for x in R if x[1]), "/", len(R))
