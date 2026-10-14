"""CareerOS Radar sources — official/legal only: Jooble API, optional Adzuna API, public career portals
(Workday, SuccessFactors, Oracle Recruiting, iCIMS, Greenhouse, Lever, Ashby, SmartRecruiters, amazon.jobs). Each fetcher returns normalized offers:
{source, external_id, title, company, location, url, description, posted_at, salary}."""
import asyncio
import html
import os
import re
from datetime import datetime, timezone

import httpx

TIMEOUT = httpx.Timeout(20.0)


def _clean(text: str) -> str:
    t = html.unescape(text or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


WORKDAY_CANADA = "a30a87ed25634629aa6c3958aa2b91ea"  # Workday's global country id for Canada
PORTAL_KINDS = ("workday", "successfactors", "oracle", "icims", "greenhouse", "lever", "ashby", "smartrecruiters", "amazon")
UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"}
SOURCE_GROUP = {"jooble": "jooble", "adzuna": "adzuna", "workday": "workday"}  # anything else → "boards"


def group(source: str) -> str:
    return SOURCE_GROUP.get(source, "boards")


def configured() -> dict:
    return {"jooble": bool(os.environ.get("JOOBLE_API_KEY")),
            "adzuna": bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY")),
            "workday": True, "boards": True}


def parse_portal(url: str) -> tuple:
    """Career-portal URL → (kind, slug). ('', '') when the platform has no public feed."""
    u = (url or "").strip()
    m = re.search(r"https?://([a-z0-9-]+)\.(wd\d+)\.myworkdayjobs\.com/(?:[a-z]{2}-[a-z]{2}/)?([^/?#]+)", u, re.I)
    if m:
        return "workday", f"{m.group(1).lower()}.{m.group(2).lower()}/{m.group(3)}"
    m = re.search(r"https?://([a-z0-9.-]+\.oraclecloud\.com)/hcmUI/CandidateExperience/[a-z]{2}(?:-[a-z]{2})?/sites/([A-Za-z0-9_]+)", u, re.I)
    if m:
        return "oracle", f"{m.group(1).lower()}/{m.group(2)}"
    m = re.search(r"https?://([a-z0-9-]+\.icims\.com)", u, re.I)
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


async def oracle(client, slug: str, company: str, keywords: list):
    """Oracle Recruiting Cloud (Candidate Experience) public REST search."""
    host, site = slug.split("/", 1)
    out = {}
    for text in (keywords[:3] or [""]):
        kw = f',keyword="{text}"' if text else ""
        r = await client.get(f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions", headers={**UA, "Accept": "application/json"},
                             params={"onlyData": "true", "expand": "requisitionList.secondaryLocations",
                                     "finder": f"findReqs;siteNumber={site},limit=25{kw},sortBy=POSTING_DATES_DESC"})
        r.raise_for_status()
        for it in r.json().get("items") or []:
            for j in it.get("requisitionList") or []:
                out[j["Id"]] = {"source": "oracle", "external_id": str(j["Id"]), "title": j.get("Title", ""), "company": company,
                                "location": j.get("PrimaryLocation") or "", "url": f"https://{host}/hcmUI/CandidateExperience/fr-CA/sites/{site}/job/{j['Id']}",
                                "description": _clean(j.get("ShortDescriptionStr") or ""), "posted_at": (j.get("PostedDate") or "")[:10], "salary": ""}
    return list(out.values())


async def icims(client, host: str, company: str, keywords: list):
    """iCIMS career portals: best-effort read of the public search page (HTML)."""
    out = {}
    for text in (keywords[:3] or [""]):
        r = await client.get(f"https://{host}/jobs/search", params={"ss": "1", "searchKeyword": text, "in_iframe": "1"}, headers=UA)
        r.raise_for_status()
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


JOOBLE_HOST = os.environ.get("JOOBLE_HOST") or "ca.jooble.org"  # keys are country-specific: ca.jooble.org = Canada


async def jooble(client, what: str, where: str, company: str = ""):
    if not configured()["jooble"]:
        return []
    body = {"keywords": company or what, "location": where, "page": 1, "ResultOnPage": 50}
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
    if kind == "icims":
        return await icims(client, slug, company, keywords or [])
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
