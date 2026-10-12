"""CareerOS Radar sources — official/legal only: Adzuna API, Jooble API, public ATS job boards
(Greenhouse, Lever, Ashby). Each fetcher returns normalized offers:
{source, external_id, title, company, location, url, description, posted_at, salary}."""
import html
import os
import re

import httpx

TIMEOUT = httpx.Timeout(20.0)


def _clean(text: str) -> str:
    t = html.unescape(text or "")
    t = re.sub(r"<[^>]+>", " ", t)
    return re.sub(r"\s+", " ", t).strip()


def configured() -> dict:
    return {"adzuna": bool(os.environ.get("ADZUNA_APP_ID") and os.environ.get("ADZUNA_APP_KEY")),
            "jooble": bool(os.environ.get("JOOBLE_API_KEY")), "greenhouse": True, "lever": True, "ashby": True}


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


async def jooble(client, what: str, where: str, company: str = ""):
    if not configured()["jooble"]:
        return []
    r = await client.post(f"https://jooble.org/api/{os.environ['JOOBLE_API_KEY']}",
                          json={"keywords": f"{what} {company}".strip(), "location": where, "page": 1})
    r.raise_for_status()
    return [{"source": "jooble", "external_id": str(j.get("id") or j.get("link")), "title": _clean(j.get("title")),
             "company": j.get("company", ""), "location": j.get("location", ""), "url": j.get("link", ""),
             "description": _clean(j.get("snippet")), "posted_at": (j.get("updated") or "")[:10], "salary": j.get("salary", "")}
            for j in r.json().get("jobs", [])]


async def board(client, kind: str, slug: str, company: str):
    if kind == "greenhouse":
        r = await client.get(f"https://boards-api.greenhouse.io/v1/boards/{slug}/jobs", params={"content": "true"})
        r.raise_for_status()
        return [{"source": "greenhouse", "external_id": str(j["id"]), "title": j.get("title", ""), "company": company,
                 "location": (j.get("location") or {}).get("name", ""), "url": j.get("absolute_url", ""),
                 "description": _clean(j.get("content")), "posted_at": (j.get("updated_at") or "")[:10], "salary": ""} for j in r.json().get("jobs", [])]
    if kind == "lever":
        r = await client.get(f"https://api.lever.co/v0/postings/{slug}", params={"mode": "json"})
        r.raise_for_status()
        from datetime import datetime, timezone
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
