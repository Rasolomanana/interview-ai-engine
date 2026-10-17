"""CareerOS Radar sources — official/legal only: Jooble API, optional Adzuna API, public career portals
(Workday, SuccessFactors, Oracle Recruiting, iCIMS, UKG, Taleo, Avature, Phenom, Greenhouse, Lever, Ashby, SmartRecruiters, amazon.jobs). Each fetcher returns normalized offers:
{source, external_id, title, company, location, url, description, posted_at, salary}."""
import asyncio
import html
import json
import os
import re
from datetime import datetime, timezone
import unicodedata
from urllib.parse import urljoin, urlparse

import httpx

TIMEOUT = httpx.Timeout(20.0)


def _clean(text: str) -> str:
    t = html.unescape(text or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


WORKDAY_CANADA = "a30a87ed25634629aa6c3958aa2b91ea"  # Workday's global country id for Canada
PORTAL_KINDS = ("workday", "successfactors", "oracle", "icims", "ukg", "taleo", "avature", "phenom", "schema", "taleobe", "greenhouse", "lever", "ashby", "smartrecruiters", "amazon")
FRAGILE = {"icims", "avature", "phenom", "taleobe"}  # read from HTML pages (no public API): best effort


def quality(kind: str, ok: bool, blocked: bool) -> str:
    return "bloquee" if blocked else "repli" if not ok else "fragile" if kind in FRAGILE else "fiable"
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
SOURCE_GROUP = {"jooble": "jooble", "adzuna": "adzuna", "workday": "workday"}  # anything else → "boards"


def group(source: str) -> str:
    return SOURCE_GROUP.get(source, "boards")


def configured() -> dict:
    return {"jooble": bool(os.environ.get("JOOBLE_API_KEY")),
            "adzuna": bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY")),
            "careerjet": bool(os.environ.get("CAREERJET_AFFID") and os.environ.get("CAREERJET_PAGE_URL")),
            "google_jobs": bool(os.environ.get("SERPAPI_API_KEY")),
            "workday": True, "boards": True}


ICIMS_HOST = r"https?://(?!www\.|cdn\d*\.|images\.)([a-z0-9-]+\.icims\.com)"


def parse_portal(url: str) -> tuple:
    """Career-portal URL → (kind, slug). ('', '') when the platform has no public feed."""
    u = (url or "").strip()
    m = re.search(r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[a-z]{2}/)?([^/?#]+)", u, re.I)
    if m:
        return "workday", f"{m.group(1).lower()}.{m.group(2).lower()}/{m.group(3)}"
    m = re.search(r"https?://([a-z0-9.-]+\.oraclecloud\.com)/hcmUI/CandidateExperience/[a-z]{2}(?:-[a-z]{2})?/sites/([A-Za-z0-9_]+)", u, re.I)
    if m:
        return "oracle", f"{m.group(1).lower()}/{m.group(2)}"
    m = re.search(r"https?://(recruiting\d*\.ultipro\.(?:com|ca))/([A-Za-z0-9]+)/JobBoard/([0-9a-f-]{36})", u, re.I)
    if m:
        return "ukg", f"{m.group(1).lower()}/{m.group(2)}/{m.group(3).lower()}"
    m = re.search(r"https?://([a-z0-9]+\.tbe\.taleo\.net)/([a-z0-9]+)/ats/careers/v2/[A-Za-z]+\?([^\s\"'<>\\]+)", u, re.I)
    org, cws = (re.search(r"org=([A-Za-z0-9_]+)", m.group(3)), re.search(r"cws=(\d+)", m.group(3))) if m else (None, None)
    if org and cws:
        return "taleobe", f"{m.group(1).lower()}/{m.group(2)}/{org.group(1)}/{cws.group(1)}"
    m = re.search(r"https?://([a-z0-9-]+\.taleo\.net)/careersection/(?!rest/)([a-z0-9_]+)/", u, re.I)
    if m:
        return "taleo", f"{m.group(1).lower()}/{m.group(2)}"
    m = re.search(r"https?://([a-z0-9.-]+)/((?:[a-z]{2}_[A-Z]{2}/)?[A-Za-z0-9_-]+)/(?:SearchJobs|JobDetail)", u) or \
        re.search(r"https?://([a-z0-9-]+\.avature\.net)/((?:[a-z]{2}_[A-Z]{2}/)?[A-Za-z0-9_-]+)", u, re.I)
    if m:
        return "avature", f"{m.group(1).lower()}/{m.group(2)}"
    m = re.search(ICIMS_HOST, u, re.I)
    if m:
        return "icims", m.group(1).lower()
    for kind, pat in (("greenhouse", r"greenhouse\.io/(?:embed/job_board\?for=)?([a-z0-9_-]+)"), ("lever", r"jobs\.lever\.co/([a-z0-9_-]+)"),
                      ("ashby", r"jobs\.ashbyhq\.com/([a-z0-9_.-]+)"), ("smartrecruiters", r"(?:jobs|careers)\.smartrecruiters\.com/([A-Za-z0-9_-]+)")):
        m = re.search(pat, u, re.I)
        if m:
            return kind, m.group(1)
    if re.search(r"amazon\.jobs", u, re.I):
        return "amazon", "amazon"
    m = re.search(r"https?://([a-z0-9.-]+)/services/rss/job", u, re.I)
    if m:
        return "successfactors", m.group(1).lower()
    m = re.search(r"https?://([a-z0-9.-]+/[^?#\s]*sitemap[^/?#\s]*\.xml)", u, re.I)
    if m:
        return "schema", m.group(1)
    m = re.search(r"https?://([a-z0-9.-]+)/([a-z]{2})/([a-z]{2})/(?:search-results|job/)", u, re.I)
    if m:
        return "phenom", f"{m.group(1).lower()}/{m.group(2).lower()}/{m.group(3).lower()}"
    return "", ""


def host_of(url: str) -> str:
    m = re.match(r"https?://([a-z0-9.-]+)", (url or "").strip(), re.I)
    return m.group(1).lower() if m else ""


def _rss_date(v: str) -> str:
    try:
        return datetime.strptime(v.strip()[5:16], "%d %b %Y").strftime("%Y-%m-%d")
    except ValueError:
        return ""


async def successfactors(client, host: str, company: str, keywords: list):
    """SAP SuccessFactors Recruiting Marketing (RMK) career sites expose a public RSS feed."""
    out = {}
    for text in (keywords[:3] or [""]):
        r = await client.get(f"https://{host}/services/rss/job/", params={"locale": "fr_FR", **({"keywords": f"({text})"} if text else {})}, headers=UA)
        r.raise_for_status()
        if "<rss" not in r.text[:500]:
            raise RuntimeError("Flux SuccessFactors illisible (page non RSS)")
        for it in re.findall(r"<item>(.*?)</item>", r.text, re.S):
            g = lambda tag: (re.search(rf"<{tag}>(?:<!\[CDATA\[)?(.*?)(?:\]\]>)?</{tag}>", it, re.S) or [None, ""])[1]  # noqa: E731
            link = html.unescape(g("link")).split("?")[0]
            title = _clean(g("title"))
            loc = re.search(r"\(([^()]*)\)\s*$", title)
            out[link] = {"source": "successfactors", "external_id": (re.search(r"/(\d+)/?$", link) or [None, link])[1],
                         "title": title[:loc.start()].strip() if loc else title, "company": company, "location": loc.group(1) if loc else "",
                         "url": link, "description": _clean(g("description")), "posted_at": _rss_date(g("pubDate")), "salary": ""}
    return list(out.values())


MOVED = {}  # (kind, old slug) -> new slug discovered through a redirect during the current process
ORACLE_PATHS = ("latest", "11.13.18.05")


class PortalRedirect(Exception):
    """Portal answered with a redirect that does not lead to a readable job API (login / maintenance page)."""


async def _oracle_get(client, host: str, params: dict):
    """GET the Oracle job API, following a redirect only towards another Oracle job API; returns (response, host)."""
    last, host0, params0 = "", host, params
    for ver in ORACLE_PATHS:
        host, params = host0, params0
        url = f"https://{host}/hcmRestApi/resources/{ver}/recruitingCEJobRequisitions"
        for _hop in range(3):
            r = await client.get(url, headers={**UA, "Accept": "application/json"}, params=params, follow_redirects=False)
            if not r.is_redirect:
                break
            loc = r.headers.get("location") or ""
            nxt = urlparse(urljoin(url, loc))
            last = f"{r.status_code} → {nxt.netloc or 'sans adresse'}{nxt.path[:60]}"
            if not loc or "recruitingCEJobRequisitions" not in nxt.path or not nxt.netloc:
                r = None
                break
            host, url, params = nxt.netloc, urljoin(url, loc), (params if not nxt.query else None)
        if r is not None and not r.is_redirect:
            r.raise_for_status()
            return r, host
    raise PortalRedirect(f"Redirection Oracle non lisible ({last or '3xx'}) : page de connexion ou de maintenance de l'employeur")


async def oracle(client, slug: str, company: str, keywords: list):
    """Oracle Recruiting Cloud (Candidate Experience) public REST search."""
    host, site = slug.split("/", 1)
    out = {}
    for text in (keywords[:3] or [""]):
        kw = f',keyword="{text}"' if text else ""
        r, new_host = await _oracle_get(client, host, {"onlyData": "true", "expand": "requisitionList.secondaryLocations",
                                                       "finder": f"findReqs;siteNumber={site},limit=25{kw},sortBy=POSTING_DATES_DESC"})
        if new_host != host:
            MOVED[("oracle", slug)] = f"{new_host}/{site}"
            host = new_host
        for it in r.json().get("items") or []:
            for j in it.get("requisitionList") or []:
                out[j["Id"]] = {"source": "oracle", "external_id": str(j["Id"]), "title": j.get("Title", ""), "company": company,
                                "location": j.get("PrimaryLocation") or "", "url": f"https://{host}/hcmUI/CandidateExperience/fr-CA/sites/{site}/job/{j['Id']}",
                                "description": _clean(j.get("ShortDescriptionStr") or ""), "posted_at": (j.get("PostedDate") or "")[:10], "salary": ""}
    return list(out.values())


async def ukg(client, slug: str, company: str, keywords: list):
    """UKG Pro (UltiPro) Recruiting job boards: public JSON search."""
    host, tenant, board = slug.split("/", 2)
    base = f"https://{host}/{tenant}/JobBoard/{board}"
    out = {}
    for text in (keywords[:3] or [""]):
        body = {"opportunitySearch": {"Top": 50, "Skip": 0, "QueryString": text,
                                      "OrderBy": [{"Value": "postedDateDesc", "PropertyName": "PostedDate", "Ascending": False}],
                                      "Filters": [{"t": "TermsSearchFilterDto", "fieldName": f, "extra": None, "values": []} for f in (4, 5, 6)]},
                "matchCriteria": {"PreferredJobs": [], "Educations": [], "LicenseAndCertifications": [], "Skills": [], "hasNoLicenses": False, "SkippedSkills": []}}
        r = await client.post(f"{base}/JobBoardView/LoadSearchResults", json=body, headers={**UA, "Accept": "application/json"})
        r.raise_for_status()
        for j in r.json().get("opportunities") or []:
            loc = ((j.get("Locations") or [{}])[0].get("Address") or {})
            out[j["Id"]] = {"source": "ukg", "external_id": j["Id"], "title": j.get("Title", ""), "company": company,
                            "location": ", ".join(x for x in (loc.get("City"), (loc.get("State") or {}).get("Code"), (loc.get("Country") or {}).get("Code")) if x),
                            "url": f"{base}/OpportunityDetail?opportunityId={j['Id']}", "description": _clean(j.get("BriefDescription") or ""),
                            "posted_at": (j.get("PostedDate") or "")[:10], "salary": ""}
    return list(out.values())


def _taleo_date(v: str) -> str:
    for f in ("%b %d, %Y", "%d %b %Y", "%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y"):
        try:
            return datetime.strptime(v.strip(), f).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return ""


async def taleo(client, slug: str, company: str, keywords: list):
    """Oracle Taleo Enterprise career sections: public JSON search used by the career site itself."""
    host, section = slug.split("/", 1)
    page = await client.get(f"https://{host}/careersection/{section}/jobsearch.ftl", params={"lang": "fr"}, headers=UA)
    page.raise_for_status()
    portal = re.search(r"portal=(\d+)|portalNo\W+(\d+)", page.text)
    if not portal:
        raise RuntimeError("Section carrières Taleo illisible (identifiant de portail introuvable)")
    out = {}
    for lang, text in [(lg, t) for lg in ("fr", "en") for t in (keywords[:3] or [""])]:  # postings are language-specific
        for no in (1, 2):
            body = {"multilineEnabled": False, "sortingSelection": {"sortBySelectionParam": "3", "ascendingSortingOrder": "false"},
                    "fieldData": {"fields": {"KEYWORD": text, "LOCATION": ""}, "valid": True},
                    "filterSelectionParam": {"searchFilterSelections": []}, "advancedSearchFiltersSelectionParam": {"searchFilterSelections": []}, "pageNo": no}
            r = await client.post(f"https://{host}/careersection/rest/jobboard/searchjobs", params={"lang": lang, "portal": portal.group(1) or portal.group(2)},
                                  json=body, headers={**UA, "tz": "GMT-04:00", "tzname": "America/Toronto", "Accept": "application/json"})
            r.raise_for_status()
            reqs = r.json().get("requisitionList") or []
            for j in reqs:
                col = j.get("column") or []
                title = col[j.get("linkedColumn") or 0] if col else ""
                loc = col[(j.get("locationsColumns") or [1])[0]] if len(col) > 1 else ""
                try:
                    loc = ", ".join(json.loads(loc)) if loc.startswith("[") else loc
                except ValueError:
                    pass
                posted = next((d for d in (_taleo_date(x) for x in col[::-1] if isinstance(x, str)) if d), "")
                out.setdefault(j["jobId"], {"source": "taleo", "external_id": str(j["jobId"]), "title": _clean(title), "company": company, "location": loc,
                                   "url": f"https://{host}/careersection/{section}/jobdetail.ftl?job={j.get('contestNo') or j['jobId']}&lang={lang}",
                                   "description": "", "posted_at": posted, "salary": ""})
            if len(reqs) < 25:
                break
    return list(out.values())


async def taleobe(client, slug: str, company: str, keywords: list):
    """Taleo Business Edition career websites: best-effort read of the public search page (HTML)."""
    host, path, org, cws = slug.split("/")
    r = await client.get(f"https://{host}/{path}/ats/careers/v2/searchResults", params={"org": org, "cws": cws}, headers=UA)
    r.raise_for_status()
    if "oracletaleocwsv2" not in r.text:
        raise RuntimeError("Page Taleo Business Edition illisible")
    out = {}
    for page in range(1, 6):
        before = len(out)
        for m in re.finditer(r'oracletaleocwsv2-head-title"><a href="([^"]+rid=(\d+))"[^>]*>(.*?)</a></h4>(.*?)</div>\s*<!--', r.text, re.S):
            divs = [_clean(x) for x in re.findall(r"<div[^>]*>(.*?)</div>", m.group(4), re.S)]
            out[m.group(2)] = {"source": "taleobe", "external_id": m.group(2), "title": _clean(m.group(3)), "company": company,
                               "location": divs[-1] if divs else "", "url": html.unescape(m.group(1)), "description": " · ".join(divs), "posted_at": "", "salary": ""}
        if len(out) == before or "rowFrom=" not in r.text:
            break
        r = await client.get(f"https://{host}/{path}/ats/careers/v2/searchResults", params={"next": "", "rowFrom": page * 10}, headers=UA)
        r.raise_for_status()
    return list(out.values())


async def avature(client, slug: str, company: str, keywords: list):
    """Avature career sites: best-effort read of the public search pages (HTML, no public API)."""
    base = f"https://{slug}"
    out = {}
    for text in (keywords[:3] or [""]):
        offset = 0
        for _ in range(3):
            r = await client.get(f"{base}/SearchJobs/", params={"search": text, "jobOffset": offset, "jobRecordsPerPage": 50}, headers=UA)
            r.raise_for_status()
            links = list(re.finditer(r'<a\b[^>]*href="(https?://[^"]*/JobDetail/[^"]*?/(\d+))"[^>]*>(.*?)</a>', r.text, re.S))
            if not links and "avature" not in r.text.lower():
                raise RuntimeError("Page Avature illisible")
            page = set()
            for k, m in enumerate(links):
                jid = m.group(2)
                title = _clean(m.group(3)) or _clean((re.search(r'title="([^"]+)"', m.group(0)) or [None, ""])[1])
                if jid in page or not title or len(title) < 3:
                    continue
                page.add(jid)
                nxt = links[k + 1].start() if k + 1 < len(links) else m.end() + 600
                loc = _clean(re.sub(r"<[^>]*$", "", r.text[m.end():min(nxt, m.end() + 600)]))[:100]
                out.setdefault(jid, {"source": "avature", "external_id": jid, "title": title, "company": company, "location": loc,
                                     "url": html.unescape(m.group(1)), "description": "", "posted_at": "", "salary": ""})
            if not page:
                break
            offset += len(page)
    return list(out.values())


def _phenom_ddo(text: str) -> dict:
    i = text.find("phApp.ddo")
    if i < 0:
        raise RuntimeError("Page Phenom illisible (données de recherche absentes)")
    return json.JSONDecoder().raw_decode(text, text.index("{", i))[0]


async def phenom(client, slug: str, company: str, keywords: list):
    """Phenom career sites: best-effort read of the search data embedded in the public search page."""
    out = {}
    for text in (keywords[:3] or [""]):
        for start in ((0, 10) if text else (0, 10, 20)):
            r = await client.get(f"https://{slug}/search-results", params={"keywords": text, "from": start, "s": 1}, headers=UA)
            r.raise_for_status()
            jobs = ((_phenom_ddo(r.text).get("eagerLoadRefineSearch") or {}).get("data") or {}).get("jobs") or []
            for j in jobs:
                jid = str(j.get("jobId") or j.get("reqId"))
                out[jid] = {"source": "phenom", "external_id": jid, "title": j.get("title", ""), "company": company,
                            "location": j.get("cityStateCountry") or j.get("location") or "", "url": f"https://{slug}/job/{jid}",
                            "description": _clean(j.get("description") or j.get("descriptionTeaser") or "")[:4000],
                            "posted_at": (j.get("postedDate") or "")[:10], "salary": ""}
            if len(jobs) < 10:
                break
    return list(out.values())


JOB_URL = re.compile(r"/(?:jobs?|emplois?|postes?|careers?|carrieres?|offres?|opportunit[a-z]*|requisitions?|job-details?)/[^/?#]{6,}", re.I)


def _ascii(t: str) -> str:
    return unicodedata.normalize("NFKD", t or "").encode("ascii", "ignore").decode().lower()


async def sitemap_jobs(client, url: str, depth: int = 0) -> list:
    r = await client.get(url, headers=UA)
    r.raise_for_status()
    locs = [html.unescape(x) for x in re.findall(r"<loc>\s*([^<\s]+)\s*</loc>", r.text)]
    if "<sitemapindex" in r.text[:2000] and depth == 0:
        subs = await asyncio.gather(*(sitemap_jobs(client, x, 1) for x in locs[:12]), return_exceptions=True)
        return list(dict.fromkeys(u for sub in subs if isinstance(sub, list) for u in sub))
    return [u for u in locs if JOB_URL.search(u)]


def _jobposting(text: str):
    for raw in re.findall(r'<script[^>]*application/ld\+json[^>]*>(.*?)</script>', text, re.S | re.I):
        try:
            data = json.loads(raw.strip())
        except ValueError:
            continue
        items = data if isinstance(data, list) else data.get("@graph", [data]) if isinstance(data, dict) else []
        for it in items:
            if isinstance(it, dict) and "JobPosting" in str(it.get("@type")):
                return it
    return None


def _jp_location(jp: dict) -> str:
    locs = jp.get("jobLocation") or []
    locs = locs if isinstance(locs, list) else [locs]
    a = ((locs[0] if locs else {}) or {}).get("address") or {}
    a = a if isinstance(a, dict) else {}
    return ", ".join(x for x in (a.get("addressLocality"), a.get("addressRegion")) if isinstance(x, str) and x)


async def schema(client, slug: str, company: str, keywords: list, max_details: int = 40):
    """Any career site publishing a public sitemap + schema.org JobPosting data (the Google for Jobs standard)."""
    urls = await sitemap_jobs(client, f"https://{slug}")
    if not urls:
        raise RuntimeError("Plan du site sans offres d'emploi")
    kws = [[w for w in re.split(r"[^a-z0-9]+", _ascii(k)) if len(w) >= 3] for k in keywords if k]
    pick = [u for u in urls if any(ws and all(w in _ascii(u) for w in ws) for ws in kws)] if kws else urls
    pick = [u for u in pick if "/en/" not in u] + [u for u in pick if "/en/" in u]  # French postings first
    sem = asyncio.Semaphore(5)

    async def one(u):
        async with sem:
            try:
                jp = _jobposting((await client.get(u, headers=UA)).text)
            except Exception:  # noqa: BLE001
                return None
        if not jp:
            return None
        if str(jp.get("validThrough") or "9999")[:10] < datetime.now(timezone.utc).strftime("%Y-%m-%d"):
            return {"expired": True}
        sal = (jp.get("baseSalary") or {}).get("value") if isinstance(jp.get("baseSalary"), dict) else None
        sal = " – ".join(str(sal.get(k)) for k in ("minValue", "maxValue") if sal.get(k)) if isinstance(sal, dict) else ""
        ident = jp.get("identifier")
        return {"source": "schema", "external_id": str((ident.get("value") if isinstance(ident, dict) else ident) or u), "title": _clean(jp.get("title")),
                "company": company, "location": _jp_location(jp), "url": u, "description": _clean(jp.get("description"))[:4000],
                "posted_at": str(jp.get("datePosted") or "")[:10], "salary": sal}
    got = await asyncio.gather(*(one(u) for u in pick[:max_details]))
    out = [o for o in got if o and not o.get("expired")]
    if pick[:max_details] and not any(got):
        raise RuntimeError("Pages d'offres sans données structurées JobPosting")
    return out


async def icims(client, host: str, company: str, keywords: list):
    """iCIMS career portals: best-effort read of the public search page (HTML)."""
    out = {}
    for text in (keywords[:3] or [""]):
        r = await client.get(f"https://{host}/jobs/search", params={"ss": "1", "searchKeyword": text, "in_iframe": "1"}, headers=UA)
        r.raise_for_status()
        if "window.top.location" in r.text[:3000] and "iCIMS_JobCardItem" not in r.text:
            raise RuntimeError("Portail iCIMS redirigé vers un autre site carrières (aucune offre lisible ici)")
        cards = re.findall(r'<li class="iCIMS_JobCardItem">(.*?)</li>', r.text, re.S)
        if not cards and "iCIMS" not in r.text:
            raise RuntimeError("Page iCIMS illisible")
        for cd in cards:
            m = re.search(r'href="([^"]+/jobs/(\d+)/[^"]*?/job)', cd)
            if not m:
                continue
            title = _clean((re.search(r"<h3[^>]*>(.*?)</h3>", cd, re.S) or [None, ""])[1])
            loc = _clean((re.search(r"map-marker.*?</dt>\s*<dd[^>]*>\s*<span[^>]*>(.*?)</span>", cd, re.S) or [None, ""])[1])
            out[m.group(2)] = {"source": "icims", "external_id": m.group(2), "title": title, "company": company, "location": loc,
                               "url": html.unescape(m.group(1)), "description": _clean(cd)[:1500], "posted_at": "", "salary": ""}
    return list(out.values())


async def smartrecruiters(client, slug: str, company: str, keywords: list, max_details: int = 10):
    out = {}
    for text in (keywords[:3] or [""]):
        r = await client.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings", params={"q": text, "country": "ca", "limit": 50}, headers=UA)
        r.raise_for_status()
        for j in r.json().get("content") or []:
            loc = j.get("location") or {}
            out[j["id"]] = {"source": "smartrecruiters", "external_id": j["id"], "title": j.get("name", ""), "company": company,
                            "location": ", ".join(x for x in (loc.get("city"), loc.get("region")) if x), "url": f"https://jobs.smartrecruiters.com/{slug}/{j['id']}",
                            "description": "", "posted_at": (j.get("releasedDate") or "")[:10], "salary": ""}
    for o in list(out.values())[:max_details]:
        try:
            d = (await client.get(f"https://api.smartrecruiters.com/v1/companies/{slug}/postings/{o['external_id']}", headers=UA)).json()
            o["description"] = _clean(" ".join((v or {}).get("text", "") for v in ((d.get("jobAd") or {}).get("sections") or {}).values()))
        except Exception:  # noqa: BLE001
            pass
    return list(out.values())


async def adzuna(client, what: str, where: str, company: str = "", max_days: int = 7):
    if not configured()["adzuna"]:
        return []
    params = {"app_id": os.environ["ADZUNA_APP_ID"], "app_key": os.environ["ADZUNA_APP_KEY"], "results_per_page": 30,
              "what": what, "where": where, "max_days_old": max_days, "content-type": "application/json"}
    if company:
        params["company"] = company
    r = await client.get("https://api.adzuna.com/v1/api/jobs/ca/search/1", params=params)
    r.raise_for_status()
    out = []
    for j in r.json().get("results", []):
        sal = " – ".join(str(int(x)) for x in (j.get("salary_min"), j.get("salary_max")) if x)
        out.append({"source": "adzuna", "external_id": str(j.get("id")), "title": j.get("title", ""),
                    "company": (j.get("company") or {}).get("display_name", ""), "location": (j.get("location") or {}).get("display_name", ""),
                    "url": j.get("redirect_url", ""), "description": _clean(j.get("description")), "posted_at": (j.get("created") or "")[:10], "salary": sal})
    return out


async def careerjet(client, what: str, where: str, user_ip: str, user_agent: str, locale: str = "fr_CA"):
    """Careerjet partner API v4. Requires the end user's IP and User-Agent (on-demand searches only, never from the cron)."""
    if not configured()["careerjet"] or not user_ip:
        return []
    params = {"locale_code": locale, "keywords": what, "location": where or "Canada", "affid": os.environ["CAREERJET_AFFID"], "user_ip": user_ip,
              "user_agent": (user_agent or "")[:512], "url": os.environ["CAREERJET_PAGE_URL"], "page": 1, "page_size": 30, "sort": "relevance"}
    key = os.environ.get("CAREERJET_API_KEY")
    r = await client.get("https://search.api.careerjet.net/v4/query", params=params, headers={"Accept": "application/json", "Referer": os.environ["CAREERJET_PAGE_URL"]},
                         auth=(key, "") if key else None)
    r.raise_for_status()
    data = r.json()
    return [{"source": "careerjet", "external_id": j.get("url", ""), "title": j.get("title", ""), "company": j.get("company", ""), "location": j.get("locations", ""),
             "url": j.get("url", ""), "description": _clean(j.get("description")), "posted_at": (j.get("date") or "")[:16], "salary": j.get("salary", "")}
            for j in (data.get("jobs") or [])] if data.get("type") != "LOCATIONS" else []


GOOGLE_JOBS_MONTHLY_CAP = 99  # hard cap requested by the owner (SerpApi credits)


async def google_jobs_budget(db) -> dict:
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    doc = await db.serpapi_usage.find_one({"_id": month}) or {}
    return {"month": month, "used": doc.get("count", 0), "cap": GOOGLE_JOBS_MONTHLY_CAP}


async def google_jobs(client, db, title: str, company: str, city: str):
    """Google Jobs via SerpApi: one credit per search, atomically capped per month. Returns one entry per 'apply on' site."""
    if not configured()["google_jobs"]:
        return []
    month = datetime.now(timezone.utc).strftime("%Y-%m")
    try:  # matches only while count < cap; at the cap the upsert collides with the month document -> refused
        await db.serpapi_usage.find_one_and_update({"_id": month, "count": {"$lt": GOOGLE_JOBS_MONTHLY_CAP}}, {"$inc": {"count": 1}}, upsert=True)
    except Exception:  # noqa: BLE001
        return []
    params = {"engine": "google_jobs", "q": " ".join(x for x in (title, company, city) if x), "gl": "ca", "hl": "fr", "api_key": os.environ["SERPAPI_API_KEY"], "no_cache": "false"}
    if city:
        params["location"] = f"{city}, Canada" if "canada" not in city.lower() else city
    r = await client.get("https://serpapi.com/search", params=params, timeout=25)
    r.raise_for_status()
    out = []
    for j in r.json().get("jobs_results") or []:
        for opt in j.get("apply_options") or []:
            if opt.get("link"):
                out.append({"source": opt.get("title") or "Google Jobs", "external_id": opt["link"], "title": j.get("title", ""), "company": j.get("company_name", ""),
                            "location": j.get("location", ""), "url": opt["link"], "description": "", "posted_at": (j.get("detected_extensions") or {}).get("posted_at", ""),
                            "salary": "", "via_google": True})
    return out


JOOBLE_HOST = os.environ.get("JOOBLE_HOST") or "ca.jooble.org"  # keys are country-specific: ca.jooble.org = Canada


async def jooble(client, what: str, where: str, company: str = "", page: int = 1):
    if not configured()["jooble"]:
        return []
    body = {"keywords": company or what, "location": where, "page": page, "ResultOnPage": 50}
    if company:
        body["companysearch"] = True
    r = await client.post(f"https://{JOOBLE_HOST}/api/{os.environ['JOOBLE_API_KEY']}", json=body)
    if r.status_code == 403:
        raise RuntimeError(f"Clé Jooble refusée (403) : la clé doit être obtenue sur {JOOBLE_HOST}/api/about.")
    r.raise_for_status()
    return [{"source": "jooble", "external_id": str(j.get("id") or j.get("link")), "title": _clean(j.get("title")),
             "company": j.get("company", ""), "location": j.get("location", ""), "url": j.get("link", ""),
             "description": _clean(j.get("snippet")), "posted_at": (j.get("updated") or "")[:10], "salary": j.get("salary", "")}
            for j in r.json().get("jobs", [])]


async def workday(client, slug: str, company: str, keywords: list, max_details: int = 15):
    host_part, site = slug.split("/", 1)
    tenant = host_part.split(".")[0]
    base = f"https://{host_part}.myworkdayjobs.com/wday/cxs/{tenant}/{site}"
    postings = {}
    for text in (keywords[:3] or [""]):
        body = {"appliedFacets": {"locationCountry": [WORKDAY_CANADA]}, "limit": 20, "offset": 0, "searchText": text}
        r = await client.post(f"{base}/jobs", json=body, headers={"Accept": "application/json"})
        if r.status_code == 400:  # tenant without a country facet
            body["appliedFacets"] = {}
            r = await client.post(f"{base}/jobs", json=body, headers={"Accept": "application/json"})
        r.raise_for_status()
        for p in r.json().get("jobPostings") or []:
            if p.get("externalPath"):
                postings.setdefault(p["externalPath"], p)
    if not max_details:  # portal check: list only
        return [{"title": p.get("title", "")} for p in postings.values()]
    sem = asyncio.Semaphore(5)

    async def detail(path, p):
        async with sem:
            try:
                d = (await client.get(base + path, headers={"Accept": "application/json"})).json().get("jobPostingInfo") or {}
            except Exception:  # noqa: BLE001
                d = {}
        return {"source": "workday", "external_id": d.get("jobReqId") or path, "title": d.get("title") or p.get("title", ""),
                "company": company, "location": d.get("location") or p.get("locationsText", ""),
                "url": d.get("externalUrl") or f"https://{host_part}.myworkdayjobs.com/{site}{path}",
                "description": _clean(d.get("jobDescription")), "posted_at": (d.get("startDate") or "")[:10], "salary": ""}
    return await asyncio.gather(*(detail(k, v) for k, v in list(postings.items())[:max_details]))


async def amazon(client, company: str, keywords: list):
    out = {}
    for text in (keywords[:3] or [""]):
        r = await client.get("https://www.amazon.jobs/en/search.json", headers={"User-Agent": "Mozilla/5.0"},
                             params={"base_query": text, "normalized_country_code[]": "CAN", "result_limit": 20, "sort": "recent"})
        r.raise_for_status()
        for j in r.json().get("jobs") or []:
            try:
                posted = datetime.strptime(j.get("posted_date", ""), "%B %d, %Y").strftime("%Y-%m-%d")
            except ValueError:
                posted = ""
            out[j.get("id_icims") or j.get("job_path")] = {
                "source": "amazon", "external_id": str(j.get("id_icims") or j.get("job_path")), "title": j.get("title", ""), "company": company,
                "location": j.get("normalized_location", ""), "url": f"https://www.amazon.jobs{j.get('job_path', '')}",
                "description": _clean(f"{j.get('description', '')} {j.get('basic_qualifications', '')}"), "posted_at": posted, "salary": ""}
    return list(out.values())


async def board(client, kind: str, slug: str, company: str, keywords: list = None):
    if kind == "workday":
        return await workday(client, slug, company, keywords or [])
    if kind == "amazon":
        return await amazon(client, company, keywords or [])
    if kind == "successfactors":
        return await successfactors(client, slug, company, keywords or [])
    if kind == "oracle":
        return await oracle(client, slug, company, keywords or [])
    if kind == "ukg":
        return await ukg(client, slug, company, keywords or [])
    if kind == "icims":
        return await icims(client, slug, company, keywords or [])
    if kind in ("taleo", "avature", "phenom", "schema", "taleobe"):
        return await {"taleo": taleo, "avature": avature, "phenom": phenom, "schema": schema, "taleobe": taleobe}[kind](client, slug, company, keywords or [])
    if kind == "smartrecruiters":
        return await smartrecruiters(client, slug, company, keywords or [])
    if kind == "greenhouse":
        r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
        r.raise_for_status()
        return [{"source": "greenhouse", "external_id": str(j["id"]), "title": j.get("title", ""), "company": company,
                 "location": (j.get("location") or {}).get("name", ""), "url": j.get("absolute_url", ""),
                 "description": _clean(j.get("content")), "posted_at": (j.get("updated_at") or "")[:10], "salary": ""} for j in r.json().get("jobs", [])]
    if kind == "lever":
        r = await client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
        r.raise_for_status()
        return [{"source": "lever", "external_id": j["id"], "title": j.get("text", ""), "company": company,
                 "location": (j.get("categories") or {}).get("location", ""), "url": j.get("hostedUrl", ""),
                 "description": _clean(j.get("descriptionPlain") or j.get("description")),
                 "posted_at": datetime.fromtimestamp(j.get("createdAt", 0) / 1000, timezone.utc).strftime("%Y-%m-%d") if j.get("createdAt") else "",
                 "salary": ""} for j in r.json()]
    if kind == "ashby":
        r = await client.get(f"https://api.ashbyhq.com/posting-api/job-board/{slug}")
        r.raise_for_status()
        return [{"source": "ashby", "external_id": j["id"], "title": j.get("title", ""), "company": company,
                 "location": j.get("location", ""), "url": j.get("jobUrl", ""), "description": _clean(j.get("descriptionPlain")),
                 "posted_at": (j.get("publishedAt") or "")[:10], "salary": ""} for j in r.json().get("jobs", [])]
    return []


def matches(offer: dict, keywords: list) -> bool:
    """Career-board feeds return every posting: keep only those matching the member's targets."""
    if not keywords:
        return True
    hay = f"{offer['title']} {offer['description'][:600]}".lower()
    return any(k.lower() in hay for k in keywords if k)


def company_match(offer: dict, company: str) -> bool:
    """Jooble company queries are keyword searches: keep only offers really from that company."""
    norm = lambda x: re.sub(r"[^a-z0-9]", "", (x or "").lower())  # noqa: E731
    a, b = norm(offer.get("company")), norm(company)
    return bool(a and b) and (b in a or a in b)
