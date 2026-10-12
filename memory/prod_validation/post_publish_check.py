"""Post-publication check (V1 final): official-IPS Decision Report, clean /admin, auth, full pack."""
import json, os, re, time, requests

B = "https://interview-ai-engine.onrender.com/api"
F = "https://interview-ai-engine.pages.dev"
HERE = os.path.dirname(os.path.abspath(__file__))
ctx = json.load(open(os.path.join(HERE, "ctx.json")))
R = []
SCORE = re.compile(r"\d{1,3}\s*/\s*(100|10)\b|[~≈]\s*\d|\d{1,3}\s*(pts?|points?)\b", re.I)
def ok(n, c, i=""):
    R.append((n, bool(c))); print(("PASS " if c else "FAIL ") + n, i)

def login(m):
    r = requests.post(f"{B}/auth/login", json={"email": m["email"], "password": m["password"]}, timeout=90)
    return r, {"Authorization": f"Bearer {r.json().get('access_token', '')}"}

# Frontend bundle: no debug left
html = requests.get(f"{F}/admin", timeout=60).text
js = requests.get(f"{F}/" + re.search(r'static/js/main[^"]+\.js', html).group(0), timeout=60).text
ok("bundle has no admin DEBUG output", "error.stack : " not in js and "error.name : " not in js)
ok("bundle has production admin message", "Impossible de joindre le serveur" in js)
r = requests.get(f"{B}/admin/stats", headers={"X-Admin-Password": "wrong"}, timeout=60)
ok("admin wrong password -> clean 401", r.status_code == 401 and r.json().get("detail") == "Mot de passe administrateur incorrect", r.text[:80])

# Auth stability
codes = [login(ctx["A"])[0].status_code for _ in range(3)]
ok("login stable x3", codes == [200, 200, 200], codes)
_, HA = login(ctx["A"])
ok("me 200", requests.get(f"{B}/auth/me", headers=HA, timeout=60).status_code == 200)
ok("no token 401", requests.get(f"{B}/careeros/applications", timeout=60).status_code == 401)

def check_report(a, label):
    rep, ips = a.get("decision_report") or {}, a.get("ips") or {}
    ok(f"{label}: report v2", rep.get("version") == 2)
    ok(f"{label}: summary starts with official IPS", rep.get("summary", "").startswith(f"IPS officiel CareerOS : {ips.get('score')}/100 — priorité {ips.get('priority')}."), rep.get("summary", "")[:90])
    body = rep.get("summary", "").split(".", 1)[1] if "." in rep.get("summary", "") else ""
    texts = [body] + [x.get("action", "") + " " + x.get("impact_estime", "") for x in rep.get("actions", [])] + [x.get("raison", "") for x in rep.get("strengths", []) + rep.get("weaknesses", [])]
    left = [m.group(0) for t in texts for m in SCORE.finditer(t)]
    ok(f"{label}: no AI numeric estimate", not left, left)
    ok(f"{label}: reasons/strengths/weaknesses/actions present", rep.get("why_priority") and rep.get("strengths") and rep.get("weaknesses") and rep.get("actions"))

old = requests.get(f"{B}/careeros/applications/{ctx['app_id']}", headers=HA, timeout=60).json()
check_report(old, "existing CO-2026-000001")

# New full pack
CV = ("Validation Prod — Chargée de projets marketing, Québec. 5 ans d'expérience. Desjardins (2021-2026) : campagnes numériques multicanal, "
      "budget annuel 400 k$, hausse des conversions de 22 %. Agence Cible (2019-2021) : coordination de 15 lancements produits. "
      "Compétences : Google Analytics, HubSpot, gestion de projet, rédaction. Formation : B.A.A. Marketing, Université Laval. Langues : français, anglais.")
OFFER = ("Gestionnaire marketing numérique — Vidéotron, Montréal. Responsabilités : piloter la stratégie d'acquisition numérique, gérer un budget média, "
         "encadrer 3 spécialistes, analyser la performance (GA4, Looker Studio). Exigences : 5+ ans en marketing numérique, gestion d'équipe, "
         "maîtrise de GA4 et des plateformes publicitaires, bilinguisme. Atout : certification Google Ads.")
t0 = time.time()
p = requests.post(f"{B}/careeros/packs", headers=HA, json={"cv_text": CV, "offer_text": OFFER, "posted_date": time.strftime("%Y-%m-%d"), "network": "aucun"}, timeout=60).json()
ok("new pack accepted with code", re.fullmatch(r"CO-\d{4}-\d{6}", p.get("code", "")), p.get("code"))
while True:
    a = requests.get(f"{B}/careeros/applications/{p['id']}", headers=HA, timeout=60).json()
    if a["status"] != "generating" or time.time() - t0 > 420:
        break
    time.sleep(10)
ok("new pack done, 6 parts", a["status"] == "done" and all(a["parts"].values()), f"{a['status']} {round(time.time() - t0)}s {a.get('errors')}")
rows = a["ips"]["criteria"]
ok("IPS = sum of points", a["ips"]["score"] == (min(round(sum(c['points'] for c in rows)), 40) if a["ips"]["knockout"] else round(sum(c["points"] for c in rows))))
check_report(a, f"new {p['code']}")
ctx["app2_id"], ctx["code2"] = p["id"], p["code"]
json.dump(ctx, open(os.path.join(HERE, "ctx.json"), "w"), indent=1)
print("SUMMARY", sum(1 for x in R if x[1]), "/", len(R))
