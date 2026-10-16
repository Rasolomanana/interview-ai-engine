"""Offer availability check and search of the same offer elsewhere (employer portal, Jooble, Adzuna). Indeed/LinkedIn/Google: prefilled links only, never scraped."""
import asyncio
import re
import unicodedata
from datetime import datetime, timedelta, timezone
from urllib.parse import quote_plus

import httpx

from . import knowledge as KB
from . import radar_sources as S

UA = {"User-Agent": "Mozilla/5.0 (compatible; CareerOS-OfferCheck/1.0)", "Accept-Language": "fr-CA,fr;q=0.9,en;q=0.8"}
EXPIRED = ["no longer available", "job position is no longer", "this job has expired", "job has been filled", "position has been filled", "no longer accepting",
           "n'est plus disponible", "n est plus disponible", "offre a expire", "offre expiree", "cette offre n'existe plus", "poste a ete pourvu", "job not found",
           "the job you are looking for", "this posting has been closed", "l'offre que vous recherchez", "page introuvable", "page not found"]
STOP = {"de", "du", "des", "la", "le", "les", "et", "en", "a", "au", "aux", "the", "of", "and", "for", "in", "h", "f", "x", "e", "-", "sr", "jr"}


def _n(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", unicodedata.normalize("NFKD", s or "").encode("ascii", "ignore").decode().lower()).strip()


def _tok(s: str) -> set:
    return {t for t in _n(s).split() if t not in STOP and len(t) > 1}


def similarity(a: str, b: str) -> float:
    x, y = _tok(a), _tok(b)
    return round(len(x & y) / len(x | y), 2) if x and y else 0.0


def _workday_api(url: str) -> str:
    """Workday job pages are rendered in JavaScript: their public JSON endpoint tells whether the posting still exists."""
    m = re.match(r"https?://([^/]+\.myworkdayjobs\.com)/(?:[a-z]{2}-[A-Z]{2}/)?([^/?#]+)/(job/[^?#]+)", url)
    return f"https://{m.group(1)}/wday/cxs/{m.group(1).split('.')[0]}/{m.group(2)}/{m.group(3)}" if m else ""


async def check_url(url: str) -> dict:
    """available / expired / unknown (protected site or network error)."""
    now = datetime.now(timezone.utc).isoformat()
    if not url:
        return {"status": "unknown", "detail": "Aucun lien d'offre.", "checked_at": now}
    api = _workday_api(url)
    if api:
        try:
            async with httpx.AsyncClient(timeout=15, headers={**UA, "Accept": "application/json"}) as c:
                r = await c.get(api)
            if r.status_code in (404, 410) or (r.status_code == 200 and not (r.json() or {}).get("jobPostingInfo")):
                return {"status": "expired", "detail": "Workday : l'offre n'existe plus sur le portail de l'employeur.", "checked_at": now, "http": r.status_code}
            if r.status_code == 200:
                return {"status": "available", "detail": "Workday : l'offre est toujours publiée sur le portail de l'employeur.", "checked_at": now, "http": 200}
        except Exception:  # noqa: BLE001
            pass  # fall back to the page itself
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True, headers=UA) as c:
            r = await c.get(url)
    except Exception as e:  # noqa: BLE001
        return {"status": "unknown", "detail": f"Site injoignable ({type(e).__name__}).", "checked_at": now}
    if r.status_code in (404, 410):
        return {"status": "expired", "detail": f"Page supprimée (HTTP {r.status_code}).", "checked_at": now, "http": r.status_code}
    if r.status_code in (401, 403, 429) or r.status_code >= 500:
        return {"status": "unknown", "detail": f"Site protégé ou indisponible (HTTP {r.status_code}) : vérifiez en ouvrant le lien.", "checked_at": now, "http": r.status_code}
    text = _n(r.text[:400000])
    hit = next((p for p in EXPIRED if _n(p) in text), None)
    if hit:
        return {"status": "expired", "detail": f"Le site indique : « {hit} ».", "checked_at": now, "http": r.status_code}
    return {"status": "available", "detail": "La page de l'offre répond normalement.", "checked_at": now, "http": r.status_code}


async def jooble_listed(title: str, company: str, location: str, url: str):
    """Jooble pages block robots (403): ask the Jooble API whether the listing is still returned. None = cannot tell."""
    if not S.configured().get("jooble"):
        return None
    try:
        async with httpx.AsyncClient(timeout=S.TIMEOUT) as c:
            res = await asyncio.gather(S.jooble(c, f"{title} {company}".strip(), location), S.jooble(c, title, location, company) if company else asyncio.sleep(0, []),
                                       return_exceptions=True)
    except Exception:  # noqa: BLE001
        return None
    rows = [o for r in res if not isinstance(r, Exception) for o in (r or [])]
    if not rows and all(isinstance(r, Exception) for r in res):
        return None
    key = url.split("?")[0].rstrip("/").rsplit("/", 1)[-1]
    return any(o["url"] == url or (key and key in o["url"]) for o in rows)


def search_links(title: str, company: str, location: str, employer_url: str = "") -> list:
    q, loc = " ".join(x for x in (title, company) if x), location or ""
    links = [{"label": "Indeed", "url": f"https://ca.indeed.com/jobs?q={quote_plus(q)}&l={quote_plus(loc)}"},
             {"label": "LinkedIn", "url": f"https://www.linkedin.com/jobs/search/?keywords={quote_plus(q)}&location={quote_plus(loc)}"},
             {"label": "Guichet-Emplois", "url": f"https://www.guichetemplois.gc.ca/jobsearch/rechercheemplois?searchstring={quote_plus(q)}&locationstring={quote_plus(loc)}"},
             {"label": "Google Emplois", "url": f"https://www.google.com/search?q={quote_plus(f'{title} {company} emploi')}&ibp=htl;jobs"}]
    if employer_url:
        links.insert(0, {"label": f"Site carrière {company}".strip(), "url": employer_url})
    return links


async def find_elsewhere(db, user_id: str, title: str, company: str, location: str, exclude_url: str = "") -> list:
    """Same offer on the employer's official portal, other Jooble listings, Adzuna. Ranked by title similarity."""
    portals = []
    card = await KB.lookup(db, company) if company else None
    if KB.usable(card):
        portals.append((card["kind"], card["slug"]))
    st = await db.radar_settings.find_one({"user_id": user_id}, {"_id": 0, "companies": 1}) or {}
    for c in st.get("companies") or []:
        if isinstance(c, dict) and c.get("kind") and c.get("slug") and company and KB.key(c["name"]) == KB.key(company) and (c["kind"], c["slug"]) not in portals:
            portals.append((c["kind"], c["slug"]))
    kw = list(_tok(title))[:4]
    async with httpx.AsyncClient(timeout=S.TIMEOUT, follow_redirects=True) as cl:
        tasks = [("portail", S.board(cl, k, s, company, kw)) for k, s in portals[:2]]
        tasks += [("jooble", S.jooble(cl, f"{title} {company}".strip(), location)), ("jooble", S.jooble(cl, title, location, company))] if company else [("jooble", S.jooble(cl, title, location))]
        if S.configured().get("adzuna"):
            tasks.append(("adzuna", S.adzuna(cl, title, location, company, max_days=30)))
        res = await asyncio.gather(*(t for _, t in tasks), return_exceptions=True)
    seen, out = {exclude_url}, []
    for (origin, _), r in zip(tasks, res):
        if isinstance(r, Exception):
            continue
        for o in r:
            if not o.get("url") or o["url"] in seen:
                continue
            sim = similarity(title, o.get("title", ""))
            same_co = not company or origin == "portail" or S.company_match(o, company)
            if sim >= 0.5 and same_co:
                seen.add(o["url"])
                out.append({"title": o.get("title"), "company": o.get("company") or company, "location": o.get("location", ""), "url": o["url"],
                            "source": "Portail officiel" if origin == "portail" else o.get("source", origin).capitalize(), "posted_at": o.get("posted_at", ""),
                            "match": int(sim * 100), "official": origin == "portail"})
    out.sort(key=lambda x: (not x["official"], -x["match"]))
    return out[:8]


def is_stale(a: dict, hours: int = 20) -> bool:
    ck = (a.get("availability") or {}).get("checked_at") or ""
    return not ck or ck < (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
