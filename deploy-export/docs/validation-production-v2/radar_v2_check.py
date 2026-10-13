"""Production validation — CareerOS Radar V2 (Jooble, Workday, amazon.jobs, configurable companies, 50/day, dedupe, pack on demand).
Usage: python radar_v2_check.py            (production)
       CAREEROS_API=https://.../api EXPECT_JOOBLE=0 python radar_v2_check.py   (preview without Jooble key)"""
import json, os, re, secrets, time, requests
from datetime import datetime, timedelta, timezone

B = os.environ.get("CAREEROS_API", "https://interview-ai-engine.onrender.com/api").rstrip("/")
EXPECT_JOOBLE = os.environ.get("EXPECT_JOOBLE", "1") == "1"
HERE = os.path.dirname(os.path.abspath(__file__))
CTX = os.path.join(HERE, "radar_ctx.json")
R = []


def ok(n, c, i=""):
    R.append((n, bool(c), str(i)[:200]))
    print(("PASS " if c else "FAIL ") + n, i if not c or i else "")


def member(tag):
    email, pw = f"radar.validation.{tag}.{int(time.time())}@careeros.dev", "Rv2-" + secrets.token_urlsafe(12)
    r = requests.post(f"{B}/auth/register", json={"email": email, "password": pw, "name": f"Validation Radar {tag}"}, timeout=120)
    assert r.status_code in (200, 201), r.text
    return {"email": email, "password": pw}, {"Authorization": f"Bearer {r.json()['access_token']}"}


def dash(h):
    return requests.get(f"{B}/careeros/radar/dashboard", headers=h, timeout=90).json()


def wait_run(h, limit=900):
    t0 = time.time()
    while time.time() - t0 < limit:
        d = dash(h)
        if d.get("last_run") and d["last_run"]["status"] != "running":
            return d, round(time.time() - t0)
        time.sleep(10)
    return dash(h), limit


# 1. Guards
ok("settings without token -> 401", requests.get(f"{B}/careeros/radar/settings", timeout=120).status_code == 401)
ok("portal detect without token -> 401", requests.post(f"{B}/careeros/radar/portal/detect", json={"url": "https://x.example"}, timeout=60).status_code == 401)
ok("cron without secret -> 401", requests.post(f"{B}/careeros/radar/cron", timeout=60).status_code == 401)

# 2. Dedicated test members + Career Memory
A, HA = member("a")
Bm, HB = member("b")
json.dump({"A": A, "B": Bm}, open(CTX, "w"))
CV = ("Analyste d'affaires et de données, Montréal. 6 ans d'expérience. Banque Nationale (2020-2026) : tableaux de bord Power BI, "
      "SQL, automatisation de rapports, réduction de 30 % du temps de production. Intact (2018-2020) : analyse de processus, "
      "rédaction d'exigences, coordination avec les équipes TI. Compétences : SQL, Python, Power BI, Excel avancé, gestion des parties prenantes. "
      "Formation : B.A.A. Systèmes d'information, HEC Montréal. Langues : français, anglais.")
p = requests.put(f"{B}/careeros/profile", headers=HA, json={"full_name": "Validation Radar", "location": "Montréal", "cv_text": CV,
                 "target_roles": "Analyste, Analyst", "goals": []}, timeout=90)
ok("Career Memory saved", p.status_code == 200, p.status_code)

# 3. Sources + configurable companies
s = requests.get(f"{B}/careeros/radar/settings", headers=HA, timeout=60).json()
conf = s.get("configured", {})
ok("Jooble configured on server", conf.get("jooble") is True or not EXPECT_JOOBLE, conf)
ok("Workday + sites carrières available", conf.get("workday") and conf.get("boards"), conf)
ok("daily limit = 50", s.get("daily_limit") == 50, s.get("daily_limit"))
ok("no hardcoded companies for a new member", s.get("companies") == [], s.get("companies"))
body = {"enabled": True, "keywords": ["analyste", "analyst"], "location": "Montréal", "sources": ["jooble", "workday", "boards", "adzuna"],
        "companies": [{"name": "Desjardins", "portal_url": "https://desjardins.wd10.myworkdayjobs.com/fr-CA/Desjardins"},
                      {"name": "Amazon", "portal_url": "https://www.amazon.jobs/fr"},
                      {"name": "Intelcom", "portal_url": "https://intelcomgroup.wd3.myworkdayjobs.com/fr-CA/Intelcom"},
                      "Hydro-Québec", "Bombardier", {"name": "desjardins"}, {"name": "Metro", "enabled": False}]}
s = requests.put(f"{B}/careeros/radar/settings", headers=HA, json=body, timeout=60).json()
ok("Adzuna dropped when not configured", conf.get("adzuna") or "adzuna" not in s["sources"], s["sources"])
names = [c["name"] for c in s["companies"]]
ok("companies saved, duplicate removed", names == ["Desjardins", "Amazon", "Intelcom", "Hydro-Québec", "Bombardier", "Metro"], names)
kinds = {c["name"]: c["kind"] for c in s["companies"]}
ok("portals parsed (workday / amazon / jooble only)", kinds["Desjardins"] == "workday" and kinds["Amazon"] == "amazon" and kinds["Hydro-Québec"] == "", kinds)
ok("disabled company kept disabled", [c for c in s["companies"] if c["name"] == "Metro"][0]["enabled"] is False)
for name, url, expect in (("Desjardins", "https://desjardins.wd10.myworkdayjobs.com/fr-CA/Desjardins", True),
                          ("Amazon", "https://www.amazon.jobs/fr", True), ("Hydro-Québec", "https://emploi.hydroquebec.com/", False)):
    d = requests.post(f"{B}/careeros/radar/portal/detect", headers=HA, json={"url": url, "name": name}, timeout=90).json()
    ok(f"portal detect {name} -> ok={expect}", d.get("ok") is expect and (not expect or d.get("count", 0) > 0), d)

# 4. Run 1 (manual)
r = requests.post(f"{B}/careeros/radar/run", headers=HA, timeout=60)
ok("run started", r.status_code == 200 and r.json().get("started"), r.text[:80])
ok("concurrent run -> 409", requests.post(f"{B}/careeros/radar/run", headers=HA, timeout=60).status_code == 409)
d1, secs = wait_run(HA)
lr = d1["last_run"]
bs = lr.get("by_source", {})
print("RUN 1", secs, "s", {k: lr.get(k) for k in ("fetched", "new", "known", "analyzed", "skipped_limit")}, bs, lr.get("errors"))
ok("run 1 done", lr["status"] == "done", lr["status"])
ok("Jooble returns offers", bs.get("jooble", {}).get("fetched", 0) > 0 or not EXPECT_JOOBLE, bs.get("jooble"))
ok("Workday returns offers", bs.get("workday", {}).get("fetched", 0) > 0, bs.get("workday"))
ok("amazon.jobs / sites carrières return offers", bs.get("boards", {}).get("fetched", 0) > 0, bs.get("boards"))
ok("no Jooble error", not any(k.startswith("jooble") for k in lr.get("errors", {})), lr.get("errors"))
ok("analyzed <= 50 and analyzed_today <= 50", lr["analyzed"] <= 50 and d1["analyzed_today"] <= 50, (lr["analyzed"], d1["analyzed_today"]))
ok("sources_status shown", set(d1["sources_status"]["configured"]) >= {"jooble", "workday", "boards", "adzuna"})
offers = d1["top_a"] + d1["top_b"] + d1["ignored"]
an = [o for o in offers if o.get("ips")]
ok("offers analyzed with official IPS", an, len(an))
if an:
    o = an[0]
    ok("IPS 0-100 + priority A/B/C", 0 <= o["ips"]["score"] <= 100 and o["ips"]["priority"] in "ABC", o["ips"].get("score"))
    ok("Decision Report starts with IPS Radar", (o.get("decision_report") or {}).get("summary", "").startswith(
        f"IPS Radar CareerOS : {o['ips']['score']}/100 — priorité {o['ips']['priority']}"), (o.get("decision_report") or {}).get("summary", "")[:90])
    ok("radar calibration: 8 criteria, stage radar", o["ips"].get("stage") == "radar" and len(o["ips"]["criteria"]) == 8, o["ips"].get("stage"))
    ok("A/B/C consistent with official thresholds", all(x["ips"]["priority"] == ("A" if x["ips"]["score"] >= 70 and x["ips"]["goal_fit"] >= 6 and not x["ips"]["knockout"]
        else "B" if x["ips"]["score"] >= 50 and not x["ips"]["knockout"] else "C") for x in an))
    jo = [x for x in an if x.get("source") == "jooble"]
    ok("Jooble offers flagged as excerpt", all(x.get("excerpt") for x in jo), len(jo))
    ok("no pack generated automatically", d1["packed"] == [] and all(o.get("application_id") is None for o in offers))
analyzed_at = {o["id"]: o.get("analyzed_at") for o in an}

# 5. Run 2: dedupe, no re-analysis, deferred offers resumed
requests.post(f"{B}/careeros/radar/run", headers=HA, timeout=60)
d2, secs = wait_run(HA)
lr2 = d2["last_run"]
print("RUN 2", secs, "s", {k: lr2.get(k) for k in ("fetched", "new", "known", "analyzed", "skipped_limit")})
ok("run 2: already-known offers deduplicated", lr2["known"] >= 1, lr2["known"])
again = {o["id"]: o.get("analyzed_at") for o in d2["top_a"] + d2["top_b"] + d2["ignored"] if o["id"] in analyzed_at}
ok("run 2: analyzed offers not re-analyzed", all(again[k] == analyzed_at[k] for k in again), len(again))
ok("run 2: daily limit still respected", d2["analyzed_today"] <= 50, d2["analyzed_today"])
if lr["skipped_limit"] and d1["analyzed_today"] < 50:
    ok("run 2: deferred offers resumed", lr2["analyzed"] > 0, lr2["analyzed"])

# 6. Pack on demand + follow-up
target = (d2["top_a"] + d2["top_b"] + d2["ignored"])[0] if an else None
if target:
    pk = requests.post(f"{B}/careeros/radar/offers/{target['id']}/pack", headers=HA, timeout=120)
    ok("pack on demand created", pk.status_code == 200, pk.text[:100])
    app_id = pk.json().get("id")
    a = requests.get(f"{B}/careeros/applications/{app_id}", headers=HA, timeout=60).json()
    ok("application code CO-YYYY-NNNNNN + origin radar", re.fullmatch(r"CO-\d{4}-\d{6}", a.get("code", "")) and (a.get("origin") or {}).get("type") == "radar", a.get("code"))
    ok("pack idempotent", requests.post(f"{B}/careeros/radar/offers/{target['id']}/pack", headers=HA, timeout=60).json().get("already") is True)
    em = requests.post(f"{B}/careeros/applications/{app_id}/emails/draft", headers=HA, json={"kind": "confirmation"}, timeout=180).json()
    ok("email = draft requiring member validation", em.get("status") == "brouillon" and em.get("requires_member_validation") is True, em.get("status"))
    at = (datetime.now(timezone.utc) + timedelta(days=3)).replace(microsecond=0).isoformat()
    iv = requests.post(f"{B}/careeros/applications/{app_id}/interviews", headers=HA, json={"stage": "rh", "scheduled_at": at, "mode": "visio", "duration_min": 45}, timeout=60).json()
    ics = requests.get(f"{B}/careeros/applications/{app_id}/interviews/{iv['id']}/ics", headers=HA, timeout=60)
    ok(".ics valid with CO code", "BEGIN:VCALENDAR" in ics.text and a.get("code", "?") in ics.text, ics.status_code)
    # 7. Isolation
    ok("member B cannot ignore A's offer", requests.post(f"{B}/careeros/radar/offers/{target['id']}/ignore", headers=HB, timeout=60).status_code == 404)
    ok("member B cannot pack A's offer", requests.post(f"{B}/careeros/radar/offers/{target['id']}/pack", headers=HB, timeout=60).status_code == 404)
    ok("member B cannot read A's .ics", requests.get(f"{B}/careeros/applications/{app_id}/interviews/{iv['id']}/ics", headers=HB, timeout=60).status_code == 404)
db = dash(HB)
ok("member B dashboard empty", not (db["top_a"] + db["top_b"] + db["ignored"]) and not db.get("last_run"))

passed = sum(1 for _, c, _ in R if c)
print(f"\n{passed}/{len(R)} checks passed")
with open(os.path.join(HERE, "REPORT_radar_v2.md"), "w") as f:
    f.write(f"# Validation production — Radar V2 ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)\n\nAPI : {B}\n\n**{passed}/{len(R)} contrôles réussis**\n\n")
    f.write(f"Run 1 : {json.dumps({k: lr.get(k) for k in ('fetched', 'new', 'known', 'analyzed', 'skipped_limit')})} · par source : {json.dumps(bs)}\n\n")
    f.writelines(f"- {'✅' if c else '❌'} {n}{'' if c else ' — ' + i}\n" for n, c, i in R)
