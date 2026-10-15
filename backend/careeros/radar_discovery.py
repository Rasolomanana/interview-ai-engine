"""Radar portal discovery: built-in employer directory + automatic detection of public career portals."""
import asyncio
import re
import time
import unicodedata

import httpx

from . import radar_sources as S

KIND_LABEL = {"workday": "Workday", "successfactors": "SuccessFactors", "oracle": "Oracle Recruiting", "icims": "iCIMS",
              "greenhouse": "Greenhouse", "lever": "Lever", "ashby": "Ashby", "smartrecruiters": "SmartRecruiters", "amazon": "amazon.jobs", "ukg": "UKG (UltiPro)",
              "taleo": "Taleo", "avature": "Avature", "phenom": "Phenom", "schema": "Site carrières (schema.org)", "taleobe": "Taleo Business Edition"}
WD = lambda host, site: f"https://{host}.myworkdayjobs.com/fr-CA/{site}"  # noqa: E731
SF = lambda host: f"https://{host}/services/rss/job/"  # noqa: E731
# Portals checked live before being proposed. url "" = no public feed → followed via Jooble.
DIRECTORY = [
    ("Desjardins", WD("desjardins.wd10", "Desjardins"), "Finance"), ("Intact Corporation financière", WD("intactfc.wd3", "intactfc"), "Assurance"),
    ("iA Groupe financier", WD("ia.wd3", "Professional"), "Assurance"), ("Beneva", WD("beneva.wd10", "BenevaSite_carriere"), "Assurance"),
    ("Saputo", WD("saputo.wd5", "Saputo_External_Careers"), "Alimentation"), ("Banque TD", WD("td.wd3", "TD_Bank_Careers"), "Finance"),
    ("CAE", WD("cae.wd3", "career"), "Aéronautique"), ("Couche-Tard (Circle K)", WD("circlek.wd3", "CircleKStoreJobs"), "Commerce de détail"),
    ("Intelcom", WD("intelcomgroup.wd3", "Intelcom"), "Logistique"),
    ("Hydro-Québec", SF("emploi.hydroquebec.com"), "Énergie"), ("Rogers", SF("jobs.rogers.com"), "Télécommunications"),
    ("Bombardier", SF("jobs.bombardier.com"), "Aéronautique"), ("TELUS", SF("careers.telus.com"), "Télécommunications"),
    ("Hydro One", SF("jobs.hydroone.com"), "Énergie"), ("Banque Scotia", SF("jobs.scotiabank.com"), "Finance"),
    ("CN", SF("careers.cn.ca"), "Transport"), ("CPKC", SF("careers.cpr.ca"), "Transport"), ("Sobeys", SF("jobs.sobeyscareers.com"), "Alimentation"),
    ("Ville de Montréal", "https://fa-exyq-saasfaprod1.fa.ocs.oraclecloud.com/hcmUI/CandidateExperience/fr-CA/sites/ExperienceCandidatVdM/jobs", "Secteur public"),
    ("Ubisoft", "https://careers.smartrecruiters.com/Ubisoft2", "Jeux vidéo"), ("Amazon", "https://www.amazon.jobs/fr", "Technologie"),
    ("Banque Nationale", "https://emplois.bnc.ca/fr_CA/careers/SearchJobs", "Finance"), ("Bell", "https://jobs.bell.ca/ca/fr/search-results", "Télécommunications"),
    ("Air Canada", "https://careers.aircanada.com/ca/fr/search-results", "Transport"),
    ("Metro", "https://talent.metro.ca/sitemap.xml", "Alimentation"), ("Airbus", WD("ag.wd3", "Airbus"), "Aéronautique"), ("Walmart Canada", WD("walmart.wd504", "WalmartExternal"), "Commerce de détail"),
    ("CGI", "", "Technologie"),
    ("Molson Coors", "https://jobs.molsoncoors.com/services/rss/job/", "Alimentation et boissons"), ("Agropur", WD("agropur.wd3", "Agropur_Careers"), "Alimentation"),
    ("Cascades", "https://jobs.cascades.com/services/rss/job/", "Industrie"), ("Purolator", "https://careers.purolator.com/services/rss/job/", "Transport et logistique"),
    ("Alstom", "https://jobsearch.alstom.com/services/rss/job/", "Transport"), ("Kuehne+Nagel", "https://careers.kuehne-nagel.com/services/rss/job/", "Transport et logistique"),
    ("Domtar", "https://jobs.domtar.com/services/rss/job/", "Industrie"), ("Home Depot Canada", WD("homedepot.wd5", "CareerDepotCanada"), "Commerce de détail"),
    ("Dollarama", "https://jobs.dollarama.com/services/rss/job/", "Commerce de détail"), ("Vidéotron", "https://careers.smartrecruiters.com/Videotron", "Télécommunications"),
    ("TD", WD("td.wd3", "TD_Bank_Careers"), "Finance"), ("BMO", WD("bmo.wd3", "External"), "Finance"), ("Thales", WD("thales.wd3", "Careers"), "Aéronautique et défense"),
    ("Colabor", "https://carrieres.colabor.com/sitemap.xml", "Distribution alimentaire"), ("Cogeco", WD("cogeco.wd3", "Cogeco_Careers"), "Télécommunications"),
]
NO_FEED_ATS = {"CGI": "Njoyn"}
UNSUPPORTED = {"taleo.net": "Taleo", "phenompeople": "Phenom", "avature": "Avature", "njoyn": "Njoyn", "silkroad": "SilkRoad", "dayforcehcm": "Dayforce (API protégée)",
               "jobvite": "Jobvite"}
ATS = [
    (r"https?://[a-z0-9-]+\.wd\d+\.myworkdayjobs\.com/(?:[a-z]{2}-[A-Z]{2}/)?[A-Za-z0-9_-]+", None),
    (r"https?://[a-z0-9.-]+\.oraclecloud\.com/hcmUI/CandidateExperience/[a-zA-Z-]+/sites/[A-Za-z0-9_]+", None),
    (r"https?://(?!www\.|cdn\d*\.|images\.)[a-z0-9-]+\.icims\.com", None), (r"https?://[a-z0-9-]+\.taleo\.net/careersection/[a-z0-9_]+/", None),
    (r"https?://[a-z0-9.-]+/(?:[a-z]{2}_[A-Z]{2}/)?[A-Za-z0-9_-]+/SearchJobs", None),
    (r"https?://[a-z0-9]+\.tbe\.taleo\.net/[a-z0-9]+/ats/careers/v2/[A-Za-z]+\?[^\s\"'<>\\]+", None), (r"https?://recruiting\d*\.ultipro\.(?:com|ca)/[A-Za-z0-9]+/JobBoard/[0-9a-f-]{36}", None), (r"https?://(?:boards|job-boards)\.greenhouse\.io/[a-z0-9_-]+", None),
    (r"https?://jobs\.lever\.co/[a-z0-9_-]+", None), (r"https?://jobs\.ashbyhq\.com/[a-z0-9_.-]+", None),
    (r"https?://(?:jobs|careers)\.smartrecruiters\.com/[A-Za-z0-9_-]+", None),
]
_cache = {"at": 0, "data": None}


def is_blocked(e) -> bool:
    resp = getattr(e, "response", None)
    if resp is None or resp.status_code not in (403, 429, 503):
        return False
    t = resp.text[:3000].lower()
    return resp.status_code == 403 or "just a moment" in t or "cf-ray" in str(resp.headers).lower() or "captcha" in t


def norm(name: str) -> str:
    t = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]", "", t)


def _variants(name: str) -> list:
    base = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    words = [w for w in re.split(r"[^a-z0-9]+", base) if w and w not in ("inc", "ltd", "ltee", "groupe", "group", "corporation", "corp", "the")]
    out = ["".join(words), "-".join(words)] + ([words[0]] if words else [])
    return list(dict.fromkeys(v for v in out if len(v) >= 2))


def directory_match(name: str):
    n = norm(name)
    for d in DIRECTORY:
        dn = norm(d[0])
        if n and (n == dn or (len(n) >= 3 and (n in dn or dn.startswith(n)))):
            return d
    return None


async def verify(client, kind: str, slug: str, name: str) -> dict:
    try:
        if kind == "workday":
            offers = await S.workday(client, slug, name, [], max_details=0)
        else:
            offers = await S.board(client, kind, slug, name, [])
        fragile = kind in S.FRAGILE
        return {"ok": True, "count": len(offers), "quality": "fragile" if fragile else "fiable",
                "message": f"Portail {KIND_LABEL[kind]} vérifié : {len(offers)} offre(s) visibles." +
                (" Lecture « au mieux » (page web sans API publique) : résultats possiblement partiels, repli Jooble en cas d'échec." if fragile else "")}
    except Exception as e:  # noqa: BLE001
        if is_blocked(e):
            return {"ok": False, "blocked": True, "count": 0,
                    "message": f"Portail {KIND_LABEL.get(kind, kind)} détecté mais bloqué volontairement par l'employeur (403 / protection anti-robot) : suivi via Jooble."}
        return {"ok": False, "count": 0, "message": f"Portail {KIND_LABEL.get(kind, kind)} détecté mais illisible ({(str(e) or type(e).__name__)[:70]}) : Jooble reste utilisé en repli."}


async def _sitemap(client, host: str) -> str:
    _, robots = await _get(client, f"https://{host}/robots.txt")
    for sm in re.findall(r"(?im)^sitemap:\s*(\S+)", robots)[:4] or [f"https://{host}/sitemap.xml"]:
        try:
            if await S.sitemap_jobs(client, sm):
                return sm
        except Exception:  # noqa: BLE001
            continue
    return ""


async def _get(client, url):
    try:
        r = await client.get(url, headers=S.UA, timeout=8)
        return str(r.url), r.text if r.status_code < 400 else ""
    except Exception:  # noqa: BLE001
        return url, ""


def _scan(url: str, text: str, found: dict, unsupported: set):
    text = text.replace("\\/", "/")
    if len(text) < 3000 and re.search(r"incapsula|_Incapsula_Resource|cf-chl|challenge-platform|Just a moment", text, re.I):
        unsupported.add("site protégé (anti-robot)")
    for pat, _ in ATS:
        for m in re.findall(pat, f"{url} {text}", re.I):
            kind, slug = S.parse_portal(m)
            if kind:
                found.setdefault((kind, slug), m)
    if "phApp.ddo" in text:  # Phenom site: base = host/country/lang
        loc = re.search(r'"locale"\s*:\s*"([a-z]{2})_([a-z]{2})"', text)
        h = S.host_of(url)
        if h and loc:
            found.setdefault(("phenom", f"{h}/{loc.group(2)}/{loc.group(1)}"), f"https://{h}/{loc.group(2)}/{loc.group(1)}/search-results")
    if "avature" in text.lower():
        k, slug = S.parse_portal(url + "/SearchJobs") if not re.search(r"/(SearchJobs|JobDetail)", url) else S.parse_portal(url)
        if k == "avature" and re.search(r"/careers?$|/[a-z]{2}_[A-Z]{2}/[A-Za-z0-9_-]+$", slug):
            found.setdefault(("avature", slug), f"https://{slug}/SearchJobs")
    if "rmkcdn.successfactors.com" in text or "/services/rss/job" in text:
        h = S.host_of(url)
        if h:
            found.setdefault(("successfactors", h), SF(h))
    for k, label in UNSUPPORTED.items():
        if re.search(rf"https?://[^\"'\s<>]*{re.escape(k)}", text, re.I):  # a real link to the platform, not a mere mention
            unsupported.add(label)


async def discover(name: str, website: str = "", shared_url: str = "") -> dict:
    found, unsupported, origin = {}, set(), {}
    d = directory_match(name)
    if shared_url and not (d and d[1]):
        k, s = S.parse_portal(shared_url)
        if k:
            found[(k, s)], origin[(k, s)] = shared_url, "annuaire partagé"
    async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as c:
        if d and not d[1]:
            unsupported.add(NO_FEED_ATS.get(d[0], "non identifié"))
        if d and d[1]:
            k, s = S.parse_portal(d[1])
            found[(k, s)], origin[(k, s)] = d[1], "annuaire"
        vs = _variants(name)
        hosts = [re.sub(r"^https?://", "", website.strip(), flags=re.I)] if website else []
        for v in vs[:2]:
            hosts += [f"{v}.com", f"{v}.ca", f"careers.{v}.com", f"careers.{v}.ca", f"jobs.{v}.com"]
        hosts = list(dict.fromkeys(h for h in hosts if h))[:10]
        pages = await asyncio.gather(*(_get(c, f"https://{h}") for h in hosts))
        extra = []
        for url, text in pages:
            if text:
                _scan(url, text, found, unsupported)
                links = list(dict.fromkeys(re.findall(r'href="([^"#]*(?:carri|career|emploi|jobs)[^"#]*)"', text, re.I)))
                for l in links[:4]:
                    extra.append(l if l.startswith("http") else f"https://{S.host_of(url)}/{l.lstrip('/')}")
        visited = [u for u, t in pages if t]
        for url, text in await asyncio.gather(*(_get(c, u) for u in list(dict.fromkeys(extra))[:8])):
            if text:
                _scan(url, text, found, unsupported)
                visited.append(url)
        if not found:  # custom career site: public sitemap + schema.org JobPosting
            career = [S.host_of(u) for u in visited if re.search(r"carri|career|emploi|jobs|talent", u, re.I)]
            for sm in await asyncio.gather(*(_sitemap(c, h) for h in list(dict.fromkeys(career))[:3])):
                if sm:
                    found.setdefault(S.parse_portal(sm), sm)
        for key in found:
            origin.setdefault(key, "site")
        guesses = []
        for v in vs[:2]:
            guesses += [("greenhouse", v), ("lever", v), ("ashby", v), ("smartrecruiters", v)]
            guesses += [("workday", f"{v}.wd{n}/{site}") for n in (1, 3, 5, 10) for site in (v, "External", "Careers")]
        known = {(k, s.lower()) for k, s in found}
        guesses = [g for g in guesses if (g[0], g[1].lower()) not in known]
        checks = await asyncio.gather(*(verify(c, k, s, name) for k, s in guesses))
        for (k, s), v in zip(guesses, checks):
            if v["ok"] and v["count"]:
                found[(k, s)], origin[(k, s)] = "", "devinette"
        results = await asyncio.gather(*(verify(c, k, s, name) for k, s in found))
    if found:
        unsupported.discard("site protégé (anti-robot)")
    unsupported -= {KIND_LABEL[k] for k, _ in found} | ({"Taleo"} if any(k == "taleobe" for k, _ in found) else set())
    out = []
    for ((k, s), url), v in zip(found.items(), results):
        if origin[(k, s)] == "devinette" or not url:
            url = {"workday": lambda: WD(*s.split("/")), "greenhouse": lambda: f"https://boards.greenhouse.io/{s}", "lever": lambda: f"https://jobs.lever.co/{s}",
                   "ashby": lambda: f"https://jobs.ashbyhq.com/{s}", "smartrecruiters": lambda: f"https://careers.smartrecruiters.com/{s}"}.get(k, lambda: url)()
        out.append({"kind": k, "kind_label": KIND_LABEL.get(k, k), "slug": s, "portal_url": url, "origin": origin[(k, s)], **v})
    out.sort(key=lambda x: (not x["ok"], x["origin"] != "annuaire", -x["count"]))
    bad = [x["kind_label"] for x in out if not x["ok"]]
    blocked = [x["kind_label"] for x in out if x.get("blocked")]
    msg = "" if any(x["ok"] for x in out) else (
        f"Portail {', '.join(dict.fromkeys(blocked))} détecté mais bloqué volontairement par l'employeur (403 / protection anti-robot) : l'entreprise reste suivie via Jooble." if blocked else
        f"Portail {', '.join(dict.fromkeys(bad))} détecté mais illisible : l'entreprise reste suivie via Jooble." if bad else
        f"Portail {', '.join(sorted(unsupported))} détecté mais non pris en charge : l'entreprise reste suivie via Jooble." if unsupported
        else "Aucun portail compatible détecté : l'entreprise reste suivie via Jooble.")
    return {"name": name, "candidates": out, "unsupported": sorted(unsupported), "message": msg,
            "directory": bool(d), "directory_no_feed": bool(d and not d[1])}


async def directory(force: bool = False) -> list:
    if _cache["data"] and not force and time.time() - _cache["at"] < 6 * 3600:
        return _cache["data"]
    async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as c:
        async def one(d):
            name, url, sector = d
            if not url:
                ats = NO_FEED_ATS.get(name, "non identifié")
                return {"name": name, "sector": sector, "portal_url": "", "kind": "", "slug": "", "ok": False, "count": 0, "ats": ats,
                        "message": f"Portail {ats} non pris en charge : suivi via Jooble."}
            k, s = S.parse_portal(url)
            return {"name": name, "sector": sector, "portal_url": url, "kind": k, "kind_label": KIND_LABEL.get(k, k), "slug": s, **await verify(c, k, s, name)}
        data = await asyncio.gather(*(one(d) for d in DIRECTORY))
    _cache.update(at=time.time(), data=data)
    return data
