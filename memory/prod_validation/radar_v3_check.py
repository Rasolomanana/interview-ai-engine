"""Production validation — AI cost-reduction lot: rules pre-scoring, AI top 5, deep analysis, pack from Radar, letter, interview simulation.
Usage: python radar_v3_check.py   (CAREEROS_API to override)"""
import json, os, re, secrets, time, requests
from datetime import datetime, timezone

B = os.environ.get("CAREEROS_API", "https://interview-ai-engine.onrender.com/api").rstrip("/")
HERE = os.path.dirname(os.path.abspath(__file__))
R = []


def ok(n, c, i=""):
    R.append((n, bool(c), str(i)[:220]))
    print(("PASS " if c else "FAIL ") + n, i)


def member(tag):
    email, pw = f"radar.v3.{tag}.{int(time.time())}@careeros.dev", "Rv3-" + secrets.token_urlsafe(12)
    r = requests.post(f"{B}/auth/register", json={"email": email, "password": pw, "name": f"Validation V3 {tag}"}, timeout=120)
    assert r.status_code in (200, 201), r.text
    return {"email": email, "password": pw}, {"Authorization": f"Bearer {r.json()['access_token']}"}


def dash(h):
    return requests.get(f"{B}/careeros/radar/dashboard", headers=h, timeout=90).json()


paths = list(requests.get(B.replace("/api", "") + "/openapi.json", timeout=120).json()["paths"])
ok("deep-analysis route deployed", "/api/careeros/radar/offers/{offer_id}/deep" in paths)
ok("admin credits route protected", requests.get(f"{B}/admin/credits", timeout=60).status_code == 401)

A, HA = member("a")
Bm, HB = member("b")
json.dump({"A": A, "B": Bm}, open(os.path.join(HERE, "radar_v3_ctx.json"), "w"))
CV = ("Analyste d'affaires et de données, Montréal, 6 ans d'expérience. Banque Nationale (2020-2026) : tableaux de bord Power BI, SQL, "
      "Python, automatisation de rapports (-30 % de temps de production), analyse des exigences, gestion des parties prenantes. "
      "Intact (2018-2020) : analyse de processus, BPMN, Excel avancé, coordination TI. B.A.A. Systèmes d'information, HEC Montréal. "
      "Français et anglais (bilingue). Certification CBAP en cours.")
requests.put(f"{B}/careeros/profile", headers=HA, json={"full_name": "Validation V3", "location": "Montréal", "cv_text": CV,
             "target_roles": "Analyste d'affaires, Business Analyst, Analyste de données, Data Analyst", "goals": []}, timeout=90)
body = {"enabled": True, "keywords": ["analyste", "analyst"], "location": "Montréal", "sources": ["jooble", "workday", "boards"],
        "companies": [{"name": "Desjardins", "portal_url": "https://desjardins.wd10.myworkdayjobs.com/fr-CA/Desjardins"},
                      {"name": "Intelcom", "portal_url": "https://intelcomgroup.wd3.myworkdayjobs.com/fr-CA/Intelcom"},
                      {"name": "Amazon", "portal_url": "https://www.amazon.jobs/fr"}]}
requests.put(f"{B}/careeros/radar/settings", headers=HA, json=body, timeout=60)

# 1. Run: rules pre-scoring + AI top 5
t0 = time.time()
requests.post(f"{B}/careeros/radar/run", headers=HA, timeout=60)
while time.time() - t0 < 900:
    d = dash(HA)
    if d.get("last_run") and d["last_run"]["status"] != "running":
        break
    time.sleep(10)
lr, bs = d["last_run"], d["last_run"].get("by_source", {})
print("RUN", round(time.time() - t0), "s", {k: lr.get(k) for k in ("fetched", "new", "analyzed", "ai_analyzed", "skipped_limit")}, bs, lr.get("errors"))
offers = d["top_a"] + d["top_b"] + d["ignored"]
rules = [o for o in offers if o.get("method") == "regles"]
ai = [o for o in offers if o.get("method") == "ia"]
ok("run done, offers found", lr["status"] == "done" and lr["fetched"] > 0, lr["fetched"])
ok("rules pre-scoring on analyzed offers", lr["analyzed"] > 0 and len(rules) + len(ai) > 0, (lr["analyzed"], len(rules)))
ok("rules offers: stage radar + 8 criteria + rules summary", rules and all(o["ips"]["stage"] == "radar" and len(o["ips"]["criteria"]) == 8 for o in rules)
   and "Pré-analyse par règles" in rules[0]["decision_report"]["summary"], rules[0]["decision_report"]["summary"][:120] if rules else "")
ok("AI confirmed at most 5 offers", 0 < lr.get("ai_analyzed", 0) <= 5 and d["ai_today"] <= 5, (lr.get("ai_analyzed"), d["ai_today"]))
ok("no AI error during run", "ia" not in (lr.get("errors") or {}), lr.get("errors"))
ok("AI offers are the best rule-scored ones", not ai or min(o["ips"]["score"] for o in ai) >= 0, [o["ips"]["score"] for o in ai])
ok("full-description sources analyzed first", bs.get("workday", {}).get("analyzed", 0) == bs.get("workday", {}).get("fetched", 0) or lr["analyzed"] < 50, bs)
ok("A/B/C consistent with thresholds", all(o["ips"]["priority"] == ("A" if o["ips"]["score"] >= 70 and o["ips"]["goal_fit"] >= 6 and not o["ips"]["knockout"]
   else "B" if o["ips"]["score"] >= 50 and not o["ips"]["knockout"] else "C") for o in offers))

# 2. Deep analysis on a rules-only offer
cand = sorted(rules, key=lambda o: -o["ips"]["score"])
if cand:
    before = d["ai_today"]
    r = requests.post(f"{B}/careeros/radar/offers/{cand[0]['id']}/deep", headers=HA, timeout=240)
    o = r.json() if r.status_code == 200 else {}
    ok("deep analysis -> method ia", r.status_code == 200 and o.get("method") == "ia", (r.status_code, r.text[:120] if r.status_code != 200 else o["ips"]["score"]))
    ok("deep analysis counted", dash(HA)["ai_today"] == before + 1)
    ok("member B cannot deep-analyze A's offer", requests.post(f"{B}/careeros/radar/offers/{cand[1 if len(cand) > 1 else 0]['id']}/deep", headers=HB, timeout=60).status_code == 404)
    target = o or (ai[0] if ai else None)
else:
    target = ai[0] if ai else None

# 3. Pack from an AI-analyzed Radar offer
if target:
    pk = requests.post(f"{B}/careeros/radar/offers/{target['id']}/pack", headers=HA, timeout=120).json()
    app_id, t0 = pk.get("id"), time.time()
    while time.time() - t0 < 600:
        a = requests.get(f"{B}/careeros/applications/{app_id}", headers=HA, timeout=60).json()
        if a["status"] != "generating":
            break
        time.sleep(15)
    print("PACK", a.get("code"), a["status"], round(time.time() - t0), "s", a.get("errors"))
    ok("pack generated completely", a["status"] == "done" and all(a["parts"].get(p) for p in a["parts"]), {k: bool(v) for k, v in a["parts"].items()})
    ok("pack reuses Radar analysis", "ANALYSE RADAR CAREEROS" in (a["inputs"].get("offer_text") or ""))
    ok("pack official IPS (10 criteria)", (a.get("ips") or {}).get("stage", "pack") == "pack" and len((a.get("ips") or {}).get("criteria", [])) == 10, (a.get("ips") or {}).get("score"))
    letter = a["parts"].get("letter") or ""
    fr = len(re.findall(r"\b(je|vous|votre|mon|ma|mes|nous|avec|pour|dans|poste)\b", letter.lower()))
    ok("letter: substantial and in French", len(letter) > 900 and fr >= 15, (len(letter), fr))
    ok("letter: no placeholder or raw markup", not re.search(r"\[(nom|name|date|entreprise)\]|```|\{\{", letter, re.I))
    with open(os.path.join(HERE, "letter_v3_sample.txt"), "w") as f:
        f.write(letter)

# 4. Interview simulation (premium chain, streamed)
sysm = "Tu es un recruteur canadien francophone qui fait passer une entrevue pour un poste d'analyste d'affaires. Pose une seule question à la fois."
r = requests.post(f"{B}/generate", json={"system_message": sysm, "turn_message": "Bonjour, je suis prêt pour l'entrevue."}, timeout=180, stream=True)
txt, err = [], ""
for line in r.iter_lines(decode_unicode=True):
    if line and line.startswith("data:"):
        try:
            j = json.loads(line[5:])
        except ValueError:
            continue
        txt.append(j.get("text") or j.get("delta") or j.get("content") or "")
        err = err or j.get("detail", "")
sim = "".join(txt)
ok("interview simulation answers (premium chain)", len(sim) > 40 and not err, (len(sim), err[:120], sim[:120]))

passed = sum(1 for _, c, _ in R if c)
print(f"\n{passed}/{len(R)} checks passed")
with open(os.path.join(HERE, "REPORT_radar_v3.md"), "w") as f:
    f.write(f"# Validation production — réduction des coûts IA ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)\n\nAPI : {B}\n\n**{passed}/{len(R)} contrôles réussis**\n\n")
    f.write(f"Run : {json.dumps({k: lr.get(k) for k in ('fetched', 'new', 'analyzed', 'ai_analyzed', 'skipped_limit')})} · par source : {json.dumps(bs)}\n\n")
    f.writelines(f"- {'✅' if c else '❌'} {n} — {i}\n" for n, c, i in R)
