"""Rentabilité CareerOS: AI usage log, monthly finance inputs, profitability summary (CAD)."""
import calendar
import logging
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("finance")
TZ = ZoneInfo("America/Toronto")

BUCKETS = {
    "gemini_flash": "Gemini Flash", "gemini_pro": "Gemini Pro", "openrouter": "OpenRouter (DeepSeek…)",
    "openrouter_free": "OpenRouter gratuit", "anthropic": "Anthropic", "autre": "Autres",
}
BILLING = {"google": "Gemini (Google)", "openrouter": "OpenRouter", "anthropic": "Anthropic", "autre": "Autres"}
# USD per 1M tokens (official public prices, editable in the admin).
DEFAULT_PRICING = {
    "gemini_flash": {"in": 0.0, "out": 0.0}, "gemini_pro": {"in": 1.25, "out": 10.0},
    "openrouter": {"in": 0.27, "out": 1.10}, "openrouter_free": {"in": 0.0, "out": 0.0},
    "anthropic": {"in": 3.0, "out": 15.0}, "autre": {"in": 1.25, "out": 10.0},
}
DEFAULT_PLATFORM = [
    {"name": "Render", "amount": 7.0, "currency": "USD"}, {"name": "MongoDB Atlas", "amount": 0.0, "currency": "USD"},
    {"name": "Cloudflare", "amount": 0.0, "currency": "USD"}, {"name": "Domaine", "amount": 2.0, "currency": "CAD"},
    {"name": "E-mail", "amount": 0.0, "currency": "USD"}, {"name": "Marketing", "amount": 0.0, "currency": "CAD"},
    {"name": "Autres", "amount": 0.0, "currency": "CAD"},
]
NEGATIVE_KINDS = {"rabais", "remboursement"}
SCENARIOS = (100, 500, 1000)


def month_key(dt: Optional[datetime] = None) -> str:
    return (dt or datetime.now(timezone.utc)).astimezone(TZ).strftime("%Y-%m")


def _bounds(month: str):
    y, m = map(int, month.split("-"))
    start = datetime(y, m, 1, tzinfo=TZ)
    end = datetime(y + (m == 12), m % 12 + 1, 1, tzinfo=TZ)
    return start.astimezone(timezone.utc).isoformat(), end.astimezone(timezone.utc).isoformat(), calendar.monthrange(y, m)[1]


def classify(label: str, provider: str, model: str):
    m = (model or "").lower()
    if label == "openrouter_free" or m.endswith(":free") or m == "openrouter/free":
        b = "openrouter_free"
    elif "gemini" in m and "pro" in m:
        b = "gemini_pro"
    elif provider == "gemini":
        b = "gemini_flash"
    elif provider == "openrouter":
        b = "openrouter"
    elif provider == "anthropic":
        b = "anthropic"
    else:
        b = "autre"
    billing = "google" if provider == "gemini" else provider if provider in ("openrouter", "anthropic") else "autre"
    return b, billing


async def log_ai_call(db, label: str, provider: str, model: str, in_chars: int, out_chars: int, feature: str):
    """Fire-and-forget usage record; tokens are estimated (~4 chars/token)."""
    try:
        b, billing = classify(label, provider, model)
        now = datetime.now(timezone.utc)
        await db.ai_usage.insert_one({"at": now.isoformat(), "month": month_key(now), "label": label, "provider": provider,
                                      "model": model, "bucket": b, "billing": billing, "feature": feature,
                                      "tokens_in": max(1, in_chars // 4), "tokens_out": max(0, out_chars // 4)})
    except Exception:  # noqa: BLE001
        logger.exception("ai usage log failed")


async def mark_active(db, user_id: str):
    await db.member_activity.update_one({"user_id": user_id, "month": month_key()}, {"$setOnInsert": {"at": datetime.now(timezone.utc).isoformat()}}, upsert=True)


class Adjustment(BaseModel):
    label: str = Field("", max_length=120)
    kind: str = Field("ponctuel", pattern="^(rabais|fondateur|ponctuel|remboursement|b2b|autre)$")
    amount: float = 0.0


class CostLine(BaseModel):
    name: str = Field(..., min_length=1, max_length=80)
    amount: float = Field(0.0, ge=0)
    currency: str = Field("CAD", pattern="^(CAD|USD)$")


class Invoice(BaseModel):
    provider: str = Field(..., min_length=1, max_length=60)
    amount: Optional[float] = Field(None, ge=0)
    currency: str = Field("USD", pattern="^(CAD|USD)$")


class MonthBody(BaseModel):
    price_cad: float = Field(19.99, ge=0)
    paid_override: Optional[int] = Field(None, ge=0)
    adjustments: List[Adjustment] = []
    platform_costs: List[CostLine] = []
    ai_invoices: List[Invoice] = []


class SettingsBody(BaseModel):
    fx_usd_cad: float = Field(1.37, gt=0, le=5)
    pricing: dict = {}


class PaidBody(BaseModel):
    paid: bool


def create_finance_router(db, check_admin, credits_fn=None):
    router = APIRouter(prefix="/api/admin")

    async def _settings():
        s = await db.admin_settings.find_one({"key": "finance"}, {"_id": 0}) or {}
        pricing = {k: {**v, **(s.get("pricing") or {}).get(k, {})} for k, v in DEFAULT_PRICING.items()}
        return {"fx_usd_cad": s.get("fx_usd_cad", 1.37), "pricing": pricing}

    async def _month_doc(month: str):
        doc = await db.finance_months.find_one({"month": month}, {"_id": 0})
        if doc:
            return doc, False
        prev = await db.finance_months.find_one({"month": {"$lt": month}}, {"_id": 0}, sort=[("month", -1)])
        base = {"month": month, "price_cad": 19.99, "paid_override": None, "adjustments": [], "ai_invoices": [],
                "platform_costs": DEFAULT_PLATFORM}
        if prev:
            base.update(price_cad=prev.get("price_cad", 19.99), platform_costs=prev.get("platform_costs") or DEFAULT_PLATFORM)
        if month < month_key():
            base.update(platform_costs=[], paid_override=0)
        return base, True

    async def _members(month: str):
        start, end, _ = _bounds(month)
        registered = await db.users.count_documents({"created_at": {"$lt": end}})
        active = {a["user_id"] async for a in db.member_activity.find({"month": month}, {"user_id": 1})}
        if month == month_key():
            active |= {u["id"] async for u in db.users.find({"last_seen_at": {"$gte": start}}, {"id": 1})}
        flagged = {u["id"] async for u in db.users.find({"paid": True}, {"id": 1})}
        return registered, active, flagged

    async def _ai(month: str, pricing: dict):
        rows = [r async for r in db.ai_usage.aggregate([
            {"$match": {"month": month}},
            {"$group": {"_id": {"b": "$bucket", "bill": "$billing", "f": "$feature"}, "calls": {"$sum": 1},
                        "tin": {"$sum": "$tokens_in"}, "tout": {"$sum": "$tokens_out"}}}])]
        buckets = {k: {"key": k, "label": v, "calls": 0, "tokens_in": 0, "tokens_out": 0, "est_usd": 0.0} for k, v in BUCKETS.items()}
        billing, features = {k: 0.0 for k in BILLING}, {}
        for r in rows:
            p = pricing.get(r["_id"]["b"], DEFAULT_PRICING["autre"])
            usd = (r["tin"] * p["in"] + r["tout"] * p["out"]) / 1e6
            b = buckets[r["_id"]["b"]]
            b["calls"] += r["calls"]; b["tokens_in"] += r["tin"]; b["tokens_out"] += r["tout"]; b["est_usd"] += usd
            billing[r["_id"]["bill"]] = billing.get(r["_id"]["bill"], 0.0) + usd
            f = features.setdefault(r["_id"]["f"] or "autre", {"feature": r["_id"]["f"] or "autre", "calls": 0, "est_usd": 0.0})
            f["calls"] += r["calls"]; f["est_usd"] += usd
        return list(buckets.values()), billing, list(features.values())

    def _per(x, n):
        return round(x / n, 2) if n else None

    async def summary(month: str, light: bool = False):
        st = await _settings()
        fx = st["fx_usd_cad"]
        cad = lambda a, c: (a or 0.0) * (fx if c == "USD" else 1.0)  # noqa: E731
        doc, draft = await _month_doc(month)
        registered, active, flagged = await _members(month)
        n_active = len(active)
        paid = doc["paid_override"] if doc.get("paid_override") is not None else len(flagged)
        active_paid = len(active & flagged) if flagged else min(paid, n_active)
        gross = round(doc["price_cad"] * paid, 2)
        adj = sum(-abs(a["amount"]) if a["kind"] in NEGATIVE_KINDS else a["amount"] for a in doc["adjustments"])
        net = round(gross + adj, 2)
        platform = [{**c, "cad": round(cad(c["amount"], c["currency"]), 2)} for c in doc["platform_costs"]]
        platform_cad = round(sum(c["cad"] for c in platform), 2)
        buckets, billing_est, features = await _ai(month, st["pricing"])
        inv = {i["provider"]: i for i in doc["ai_invoices"]}
        providers = []
        for key in list(BILLING) + [k for k in inv if k not in BILLING]:
            est_usd = billing_est.get(key, 0.0)
            i = inv.get(key)
            real = cad(i["amount"], i["currency"]) if i and i.get("amount") is not None else None
            est = est_usd * fx
            if key == "autre" and not est and real is None:
                continue
            providers.append({"provider": key, "label": BILLING.get(key, key), "est_usd": round(est_usd, 4), "est_cad": round(est, 2),
                              "real_cad": None if real is None else round(real, 2), "real_amount": i.get("amount") if i else None,
                              "real_currency": i.get("currency", "USD") if i else "USD",
                              "gap_cad": None if real is None else round(real - est, 2),
                              "gap_pct": None if real is None or not est else round((real - est) * 100 / est, 1),
                              "used_cad": round(est if real is None else real, 2)})
        ai_est = round(sum(p["est_cad"] for p in providers), 2)
        ai_used = round(sum(p["used_cad"] for p in providers), 2)
        costs = round(platform_cad + ai_used, 2)
        margin = round(net - costs, 2)
        out = {"month": month, "draft": draft, "fx_usd_cad": fx, "revenue": {"price_cad": doc["price_cad"], "paid": paid, "gross": gross,
               "adjustments": round(adj, 2), "net": net}, "platform_cad": platform_cad, "ai_est_cad": ai_est, "ai_cad": ai_used,
               "costs_cad": costs, "margin_cad": margin, "margin_pct": round(margin * 100 / net, 1) if net else None,
               "members": {"registered": registered, "active": n_active, "paid": paid, "active_paid": active_paid}}
        if light:
            return out
        _, _, days = _bounds(month)
        now = datetime.now(TZ)
        elapsed = now.day if month == month_key() else days
        pace = ai_used / elapsed * days if elapsed else 0.0
        out.update({
            "doc": doc, "platform": platform, "providers": providers, "features": [{**f, "est_cad": round(f["est_usd"] * fx, 4)} for f in features],
            "buckets": [{**b, "est_usd": round(b["est_usd"], 4), "est_cad": round(b["est_usd"] * fx, 4)} for b in buckets],
            "calls": sum(b["calls"] for b in buckets),
            "per_member": {
                "revenue_per_paid": _per(net, paid), "revenue_per_active": _per(net, n_active),
                "ai_per_active": _per(ai_used, n_active), "ai_per_active_paid": _per(ai_used, active_paid),
                "platform_per_active": _per(platform_cad, n_active), "platform_per_active_paid": _per(platform_cad, active_paid),
                "cost_per_active": _per(costs, n_active), "cost_per_active_paid": _per(costs, active_paid),
                "profit_per_active": _per(margin, n_active), "profit_per_paid": _per(margin, paid)},
            "pace": {"days_elapsed": elapsed, "days_in_month": days, "ai_month_end_cad": round(pace, 2),
                     "margin_month_end_cad": round(net - platform_cad - pace, 2)},
        })
        ratio = (active_paid / n_active) if n_active and active_paid else 1.0
        ai_pa = (ai_used / n_active) if n_active else 0.0
        out["scenarios"] = [{"members": n, "paid": round(n * ratio), "revenue_cad": round(n * ratio * doc["price_cad"], 2),
                             "ai_cad": round(n * ai_pa, 2), "platform_cad": platform_cad,
                             "margin_cad": round(n * ratio * doc["price_cad"] - n * ai_pa - platform_cad, 2)} for n in SCENARIOS]
        for s in out["scenarios"]:
            s["margin_pct"] = round(s["margin_cad"] * 100 / s["revenue_cad"], 1) if s["revenue_cad"] else None
        out["scenario_basis"] = {"paid_ratio_pct": round(ratio * 100, 1), "ai_per_active_cad": round(ai_pa, 4), "has_data": bool(n_active), "ratio_assumed": not (n_active and active_paid)}
        return out

    async def _credit(pace_or_usd: float):
        if not credits_fn:
            return None
        try:
            c = await credits_fn()
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)[:120]}
        if not c.get("configured"):
            return {"configured": False}
        alert = await db.admin_settings.find_one({"key": "credit_alert"}, {"_id": 0}) or {}
        daily = pace_or_usd
        return {**c, "threshold": alert.get("threshold", 20), "daily_usd": round(daily, 4),
                "days_left": round(c["remaining"] / daily, 1) if daily > 0 else None,
                "low": (c.get("remaining_pct") or 0) <= alert.get("threshold", 20)}

    @router.get("/finance")
    async def finance(month: Optional[str] = Query(None, pattern=r"^\d{4}-\d{2}$"), x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        month = month or month_key()
        s = await summary(month)
        hist, (y, m) = [], map(int, month.split("-"))
        for i in range(5, -1, -1):
            yy, mm = y + (m - 1 - i) // 12, (m - 1 - i) % 12 + 1
            hist.append(await summary(f"{yy:04d}-{mm:02d}", light=True))
        or_est = next((p["est_usd"] for p in s["providers"] if p["provider"] == "openrouter"), 0.0)
        s["credit"] = await _credit(or_est / max(1, s["pace"]["days_elapsed"]))
        s["history"] = hist
        s["settings"] = await _settings()
        return s

    @router.put("/finance/{month}")
    async def save_month(month: str, body: MonthBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        try:
            _bounds(month)
        except Exception:  # noqa: BLE001
            raise HTTPException(status_code=422, detail="Mois invalide (AAAA-MM)")
        await db.finance_months.update_one({"month": month}, {"$set": {"month": month, **body.model_dump(),
                                           "updated_at": datetime.now(timezone.utc).isoformat()}}, upsert=True)
        return {"ok": True}

    @router.put("/finance-settings")
    async def save_settings(body: SettingsBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        pricing = {k: {"in": float(v.get("in", 0)), "out": float(v.get("out", 0))} for k, v in body.pricing.items()
                   if k in DEFAULT_PRICING and isinstance(v, dict) and float(v.get("in", 0)) >= 0 and float(v.get("out", 0)) >= 0}
        await db.admin_settings.update_one({"key": "finance"}, {"$set": {"fx_usd_cad": body.fx_usd_cad, "pricing": pricing}}, upsert=True)
        return await _settings()

    @router.get("/members")
    async def members(x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        since = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        cur = db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1, "created_at": 1, "last_seen_at": 1, "paid": 1}).sort("created_at", -1).limit(1000)
        start, _, _ = _bounds(month_key())
        return [{**u, "paid": bool(u.get("paid")), "active_month": (u.get("last_seen_at") or "") >= start, "recent": (u.get("last_seen_at") or "") >= since}
                async for u in cur]

    @router.put("/members/{user_id}/paid")
    async def set_paid(user_id: str, body: PaidBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        r = await db.users.update_one({"id": user_id}, {"$set": {"paid": body.paid}})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Membre introuvable")
        return {"ok": True}

    return router


async def ensure_finance_indexes(db):
    await db.ai_usage.create_index([("month", 1), ("bucket", 1)])
    await db.member_activity.create_index([("user_id", 1), ("month", 1)], unique=True)
    await db.finance_months.create_index("month", unique=True)
