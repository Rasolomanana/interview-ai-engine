import json, os, time, requests

B = "https://interview-ai-engine.onrender.com/api"
ctx = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ctx.json")))
def _login(m):
    t = requests.post(f"{B}/auth/login", json={"email": m["email"], "password": m["password"]}, timeout=60).json()["access_token"]
    return {"Authorization": f"Bearer {t}"}
HA, HB = _login(ctx["A"]), _login(ctx["B"])
R = []
def ok(name, cond, info=""):
    R.append((name, bool(cond))); print(("PASS " if cond else "FAIL ") + name, info)

CV = ("Validation Prod — Analyste de données, Montréal. 6 ans d'expérience. Desjardins (2020-2025) : tableaux de bord Power BI pour 40 directeurs, "
      "automatisation SQL/Python réduisant le reporting de 30 %. Banque Nationale (2018-2020) : analyste junior, modèles Excel de prévision. "
      "Compétences : SQL, Python, Power BI, Excel. Formation : B.Sc. Statistique, Université de Montréal. Langues : français, anglais.")
OFFER = ("Analyste BI senior — Hydro-Québec, Montréal. Mandat : concevoir et maintenir des tableaux de bord Power BI, modéliser des données dans "
         "Azure Synapse, collaborer avec les équipes opérationnelles. Exigences : 5+ ans en BI, SQL avancé, Power BI, DAX, Azure, bilinguisme. "
         "Atout : certification PL-300, expérience secteur énergie. Poste permanent, hybride.")
t0 = time.time()
r = requests.post(f"{B}/careeros/packs", headers=HA, json={"cv_text": CV, "offer_text": OFFER, "posted_date": time.strftime("%Y-%m-%d"), "network": "contact"}, timeout=60)
ok("create pack 200", r.status_code == 200, r.text[:160])
p = r.json(); app_id, code = p["id"], p["code"]
import re
ok("code format CO-YYYY-NNNNNN", re.fullmatch(r"CO-\d{4}-\d{6}", code), code)
ctx["app_id"], ctx["code"] = app_id, code
json.dump(ctx, open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "ctx.json"), "w"))

# isolation while generating
ok("B cannot read A app (404)", requests.get(f"{B}/careeros/applications/{app_id}", headers=HB, timeout=60).status_code == 404)
ok("B list does not contain A app", all(a["id"] != app_id for a in requests.get(f"{B}/careeros/applications", headers=HB, timeout=60).json()))
ok("B cannot change status (404)", requests.patch(f"{B}/careeros/applications/{app_id}/status", headers=HB, json={"pipeline_status": "offre"}, timeout=60).status_code == 404)
ok("B cannot add recruiter (404)", requests.post(f"{B}/careeros/applications/{app_id}/recruiters", headers=HB, json={"name": "x"}, timeout=60).status_code == 404)
ok("B cannot read version (404)", requests.get(f"{B}/careeros/applications/{app_id}/versions/1", headers=HB, timeout=60).status_code == 404)
ok("B cannot archive (404)", requests.delete(f"{B}/careeros/applications/{app_id}", headers=HB, timeout=60).status_code == 404)
ok("B profile is separate", requests.get(f"{B}/careeros/profile", headers=HB, timeout=60).json().get("target_roles", "") == "")

while True:
    a = requests.get(f"{B}/careeros/applications/{app_id}", headers=HA, timeout=60).json()
    if a["status"] != "generating" or time.time() - t0 > 420:
        break
    time.sleep(10)
el = round(time.time() - t0)
ok("pack finished", a["status"] in ("done", "partial"), f"status={a['status']} in {el}s errors={a.get('errors')}")
ok("6 parts generated", all(a["parts"].get(k) for k in ["decision", "cv_ats", "cv_humain", "letter", "questions", "star"]), {k: bool(v) for k, v in a["parts"].items()})

ips = a.get("ips") or {}
W = {"adequation_profil": 20, "experience": 15, "competences": 15, "qualite_cv": 10, "concurrence": 10, "signaux_marche": 10,
     "certifications": 5, "fraicheur_offre": 5, "qualite_lettre": 5, "force_reseau": 5}
rows = {c["key"]: c for c in ips.get("criteria", [])}
ok("IPS 10 criteria with official weights", {k: c["weight"] for k, c in rows.items()} == W)
ok("each points = weight x score / 10", all(abs(c["points"] - round(c["weight"] * c["score"] / 10, 1)) < 0.06 for c in rows.values()))
raw = round(sum(c["points"] for c in rows.values()))
exp = min(raw, 40) if ips.get("knockout") else raw
ok("IPS = sum of points (cap 40 if knockout)", ips.get("score") == exp, f"score={ips.get('score')} sum={raw} knockout={ips.get('knockout')}")
s, gf, ko = ips.get("score", 0), ips.get("goal_fit", 5), ips.get("knockout")
expp = "A" if s >= 70 and gf >= 6 and not ko else "B" if s >= 50 and not ko else "C"
ok("priority follows A/B/C thresholds", ips.get("priority") == expp, f"priority={ips.get('priority')} goal_fit={gf}")
ok("deterministic: fraicheur = 10 (today)", rows["fraicheur_offre"]["score"] == 10)
ok("deterministic: reseau contact = 6", rows["force_reseau"]["score"] == 6)
ok("deterministic: lettre ready = 8", rows["qualite_lettre"]["score"] == 8)

dr = a.get("decision_report") or {}
ok("Decision Report summary", len(dr.get("summary", "")) > 20, dr.get("summary", "")[:140])
ok("Decision Report why_priority mentions priority", dr.get("why_priority") and f"Priorité {ips.get('priority')}" in dr["why_priority"][0])
ok("Decision Report strengths/weaknesses/actions", dr.get("strengths") and dr.get("weaknesses") and dr.get("actions"))
ok("ips_history v1", a.get("ips_history") and a["ips_history"][0]["version"] == 1 and a["ips_history"][0]["score"] == ips.get("score"))
v1 = requests.get(f"{B}/careeros/applications/{app_id}/versions/1", headers=HA, timeout=60).json()
ok("immutable v1 stored with inputs + parts + ips", v1.get("inputs", {}).get("cv_text") == CV and v1.get("ips", {}).get("score") == ips.get("score") and v1.get("parts", {}).get("letter"))
cs = requests.get(f"{B}/careeros/career-score", headers=HA, timeout=60).json()
ok("Career Score recomputed after pack", len(cs["history"]) >= 1 and cs["current"]["components"][1]["raison"].startswith("IPS moyen"), cs["current"]["components"][1]["raison"])
print("IPS", ips.get("score"), ips.get("priority"), [(k, c["score"]) for k, c in rows.items()])
print("SUMMARY", sum(1 for x in R if x[1]), "/", len(R))
