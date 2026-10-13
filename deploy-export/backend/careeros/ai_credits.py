"""AI credit monitoring (OpenRouter balance) + low-credit e-mail alert to the admin (Emergent managed e-mail)."""
import ipaddress
import logging
import os
import re
from datetime import datetime, timezone
from html import escape
from html.parser import HTMLParser
from urllib.parse import urlparse

import httpx

logger = logging.getLogger("careeros.credits")
EMAIL_BASE_URL = "https://integrations.emergentagent.com"
TOPUP_LINKS = {"openrouter": "https://openrouter.ai/settings/credits", "anthropic": "https://console.anthropic.com/settings/billing"}


async def openrouter_credits() -> dict:
    key = os.environ.get("OPENROUTER_API_KEY")
    if not key:
        return {"configured": False}
    h = {"Authorization": f"Bearer {key}"}
    async with httpx.AsyncClient(timeout=15) as c:
        r = await c.get("https://openrouter.ai/api/v1/credits", headers=h)
        if r.status_code == 200:
            d = r.json().get("data") or {}
            total, used = float(d.get("total_credits") or 0), float(d.get("total_usage") or 0)
        else:  # keys without account scope: fall back to the key's own limit
            r = await c.get("https://openrouter.ai/api/v1/key", headers=h)
            r.raise_for_status()
            d = r.json().get("data") or {}
            total, used = float(d.get("limit") or 0), float(d.get("usage") or 0)
    remaining = max(0.0, total - used)
    return {"configured": True, "total": round(total, 4), "used": round(used, 4), "remaining": round(remaining, 4),
            "remaining_pct": round(remaining * 100 / total, 1) if total else 0.0}


# ---------------- Guardrail gate (managed e-mail playbook) ----------------
_SHORTENERS = ("bit.ly", "tinyurl.com", "t.co", "is.gd", "cutt.ly", "goo.gl", "rebrand.ly")
_CRED_ASK = ("reply with your password", "reply with the code", "send your password", "cvv",
             "send us your password", "enter your password below", "confirm your card number",
             "your full card number", "seed phrase", "recovery phrase", "verify your card",
             "social security number", "confirm your bank details")
_HOSTISH = re.compile(r"\b(?:https?://)?((?:[a-z0-9-]+\.)+[a-z]{2,})", re.I)


def _host_ok(host: str) -> bool:
    if not host or "xn--" in host:
        return False
    try:
        ipaddress.ip_address(host)
        return False
    except ValueError:
        pass
    return not any(host == s or host.endswith("." + s) for s in _SHORTENERS)


def _same_site(shown: str, real: str) -> bool:
    return shown == real or real.endswith("." + shown) or shown.endswith("." + real)


class _EmailScan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags, self.urls, self.anchors = set(), [], []
        self._href, self._text = None, []

    def handle_starttag(self, tag, attrs):
        self.tags.add(tag.lower())
        self.urls += [v for k, v in attrs if k.lower() in ("href", "src") and v]
        if tag.lower() == "a":
            self._href = dict((k.lower(), v) for k, v in attrs).get("href")
            self._text = []

    def handle_data(self, data):
        if self._href is not None:
            self._text.append(data)

    def handle_endtag(self, tag):
        if tag.lower() == "a" and self._href is not None:
            self.anchors.append((self._href, "".join(self._text)))
            self._href, self._text = None, []


def _assert_safe_email(subject: str, html: str) -> None:
    scan = _EmailScan()
    scan.feed(html)
    if scan.tags & {"form", "input", "textarea", "select"}:
        raise ValueError("No forms or input fields in email (G2)")
    body = f"{subject}\n{html}".lower()
    for p in _CRED_ASK:
        if p in body:
            raise ValueError(f"Email asks the recipient for credentials: {p!r} (G2)")
    for url in scan.urls:
        low = url.strip().lower()
        if low.startswith(("mailto:", "tel:", "cid:", "#")):
            continue
        if not low.startswith("https://"):
            raise ValueError(f"Email links/assets must be absolute https: {url!r} (G3)")
        host = urlparse(low).hostname or ""
        if not _host_ok(host) or urlparse(low).username is not None:
            raise ValueError(f"Shortened, numeric-host or credential-bearing URL: {url!r} (G3)")
    for href, text in scan.anchors:
        real = urlparse(href.strip().lower()).hostname or ""
        if not real:
            continue
        for m in _HOSTISH.finditer(text):
            if not _same_site(m.group(1).lower(), real):
                raise ValueError(f"Anchor text {m.group(1)!r} ≠ real link host {real!r} (G3)")


async def send_email(*, to: str, subject: str, html: str) -> str:
    _assert_safe_email(subject, html)
    payload = {"to": [to], "subject": subject, "html": html, "from_name": os.environ["EMAIL_FROM_NAME"]}
    async with httpx.AsyncClient(timeout=30) as client:
        resp = await client.post(f"{EMAIL_BASE_URL}/api/v1/email/send", headers={"X-Email-Key": os.environ["EMERGENT_EMAIL_KEY"]}, json=payload)
    if resp.status_code >= 400:
        try:
            info = resp.json()
        except ValueError:
            info = {}
        logger.warning("credit alert e-mail refused (%s): %s", resp.status_code, info.get("code") or resp.text[:200])
        raise RuntimeError(info.get("message") or f"Envoi refusé ({resp.status_code})")
    return resp.json().get("id", "")


def _alert_html(c: dict, threshold: int) -> str:
    brand = escape(os.environ.get("EMAIL_FROM_NAME", "CareerOS"))
    return (f'<table role="presentation" width="100%"><tr><td style="padding:24px;font-family:Arial,sans-serif;color:#111">'
            f'<h2 style="margin:0 0 12px">Crédit IA bas : {c["remaining_pct"]} % restant</h2>'
            f'<p>Votre crédit OpenRouter est passé sous le seuil d\'alerte de {threshold} %.</p>'
            f'<p><strong>Restant :</strong> {c["remaining"]:.2f} $ sur {c["total"]:.2f} $ achetés ({c["used"]:.2f} $ utilisés).</p>'
            f'<p>Sans crédit, les packs candidature et l\'analyse approfondie du Radar s\'arrêtent ; la pré-analyse par règles continue.</p>'
            f'<p><a href="{TOPUP_LINKS["openrouter"]}" style="background:#4f46e5;color:#fff;padding:10px 16px;border-radius:8px;'
            f'text-decoration:none">Ajouter du crédit OpenRouter</a></p>'
            f'<p style="font-size:12px;color:#888">Alerte automatique envoyée par {brand} à l\'administrateur. '
            f'Nous ne demandons jamais de mot de passe ni de données de paiement par e-mail.</p></td></tr></table>')


async def alert_settings(db) -> dict:
    s = await db.admin_settings.find_one({"key": "credit_alert"}, {"_id": 0}) or {}
    return {"email": s.get("email", ""), "threshold": s.get("threshold", 20), "alerted": s.get("alerted", False), "last_sent_at": s.get("last_sent_at")}


async def save_alert_settings(db, email: str, threshold: int) -> dict:
    await db.admin_settings.update_one({"key": "credit_alert"}, {"$set": {"email": email.strip(), "threshold": threshold, "alerted": False}}, upsert=True)
    return await alert_settings(db)


async def check_alert(db, force: bool = False) -> dict:
    """Send one e-mail when the balance crosses the threshold; re-arms when credit is topped up above it."""
    st = await alert_settings(db)
    try:
        c = await openrouter_credits()
    except Exception as e:  # noqa: BLE001
        return {"sent": False, "reason": f"Solde OpenRouter illisible ({str(e)[:80]})"}
    if not c.get("configured") or not c.get("total"):
        return {"sent": False, "reason": "OpenRouter non configuré ou aucun crédit acheté"}
    low = c["remaining_pct"] <= st["threshold"]
    if not low and st["alerted"]:
        await db.admin_settings.update_one({"key": "credit_alert"}, {"$set": {"alerted": False}})
    if not st["email"] or not (force or (low and not st["alerted"])):
        return {"sent": False, "low": low, "reason": "" if st["email"] else "Aucune adresse d'alerte"}
    subject = f"{'[Test] ' if force and not low else ''}CareerOS : crédit IA à {c['remaining_pct']} %"
    await send_email(to=st["email"], subject=subject, html=_alert_html(c, st["threshold"]))
    await db.admin_settings.update_one({"key": "credit_alert"}, {"$set": {"alerted": low or st["alerted"], "last_sent_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
    return {"sent": True, "low": low}
