"""Rentabilité CareerOS: AI usage log, cost catalogue (families/categories/providers), monthly lines, profitability (CAD)."""
import calendar
import logging
import uuid
from datetime import datetime, timezone, timedelta

from .testaccounts import is_test, scope, uf
from typing import List, Optional
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Header, HTTPException, Query
from pydantic import BaseModel, Field

logger = logging.getLogger("finance")
TZ = ZoneInfo("America/Toronto")

FAMILIES = {"infrastructure": "Infrastructure", "ia": "IA", "developpement": "Développement / Investissement",
            "marketing": "Marketing / Acquisition", "autres": "Autres"}
OPS_FAMILIES = ("infrastructure", "ia", "marketing", "autres")
BUCKETS = {
    "gemini_flash": "Gemini Flash", "gemini_pro": "Gemini Pro", "openrouter": "OpenRouter (DeepSeek…)",
    "openrouter_free": "OpenRouter gratuit", "groq": "Groq (gratuit)", "mistral": "Mistral (gratuit)", "anthropic": "Anthropic", "autre": "Autres",
}
AI_KEYS = {"google": "Gemini (Google)", "openrouter": "OpenRouter", "anthropic": "Anthropic", "autre": "Autres (journal IA)"}
DEFAULT_PRICING = {
    "gemini_flash": {"in": 0.0, "out": 0.0}, "gemini_pro": {"in": 1.25, "out": 10.0},
    "openrouter": {"in": 0.27, "out": 1.10}, "openrouter_free": {"in": 0.0, "out": 0.0},
    "groq": {"in": 0.0, "out": 0.0}, "mistral": {"in": 0.0, "out": 0.0},
    "anthropic": {"in": 3.0, "out": 15.0}, "autre": {"in": 1.25, "out": 10.0},
}
SEED = {
    ("Infrastructure", "infrastructure"): [("Render", 7, "USD", "recurrent", None), ("MongoDB Atlas", 0, "USD", "recurrent", None),
                                           ("Cloudflare", 0, "USD", "recurrent", None), ("Domaine", 2, "CAD", "recurrent", None),
                                           ("E-mail", 0, "USD", "recurrent", None)],
    ("IA", "ia"): [("Gemini", 0, "USD", "variable", "google"), ("OpenRouter", 0, "USD", "variable", "openrouter"),
                   ("Anthropic", 0, "USD", "variable", "anthropic")],
    ("Développement", "developpement"): [("Emergent", 0, "USD", "ponctuel", None), ("Freelance", 0, "CAD", "ponctuel", None),
                                         ("UX/UI", 0, "CAD", "ponctuel", None), ("Maintenance", 0, "CAD", "ponctuel", None),
                                         ("Sous-traitance", 0, "CAD", "ponctuel", None)],
    ("Marketing", "marketing"): [("Google Ads", 0, "CAD", "variable", None), ("LinkedIn Ads", 0, "CAD", "variable", None),
                                 ("Campagnes diverses", 0, "CAD", "variable", None)],
    ("Autres", "autres"): [("Outils et services divers", 0, "CAD", "variable", None)],
}
NEGATIVE_KINDS = {"rabais", "remboursement", "essai"}
SCENARIOS = (100, 500, 1000)
_now = lambda: datetime.now(timezone.utc).isoformat()  # noqa: E731


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
    elif provider in ("groq", "mistral"):
        b = provider
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
    await db.member_activity.update_one({"user_id": user_id, "month": month_key()}, {"$setOnInsert": {"at": _now()}}, upsert=True)


M_PATTERN = r"^\d{4}-(0[1-9]|1[0-2])$"


class Adjustment(BaseModel):
    label: str = Field("", max_length=120)
    kind: str = Field("ponctuel", pattern="^(rabais|fondateur|essai|ponctuel|remboursement|b2b|autre)$")
    amount: float = 0.0


class Line(BaseModel):
    provider_id: str
    estimated: Optional[float] = Field(None, ge=0)
    real: Optional[float] = Field(None, ge=0)
    currency: str = Field("CAD", pattern="^(CAD|USD)$")
    note: str = Field("", max_length=200)
    billing_date: Optional[str] = Field(None, pattern=r"^\d{4}-\d{2}-\d{2}$")


class MonthBody(BaseModel):
    price_cad: float = Field(19.99, ge=0)
    paid_override: Optional[int] = Field(None, ge=0)
    revenue_real: Optional[float] = Field(None, ge=0)
    adjustments: List[Adjustment] = []
    lines: List[Line] = []


class SettingsBody(BaseModel):
    fx_usd_cad: float = Field(1.37, gt=0, le=5)
    pricing: dict = {}


class PaidBody(BaseModel):
    paid: bool


class CategoryBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    family: str = Field(..., pattern="^(infrastructure|ia|developpement|marketing|autres)$")


class ProviderBody(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    category_id: str
    recurrence: str = Field("recurrent", pattern="^(recurrent|ponctuel|variable)$")
    default_amount: float = Field(0.0, ge=0)
    currency: str = Field("CAD", pattern="^(CAD|USD)$")
    start_month: Optional[str] = Field(None, pattern=M_PATTERN)
    end_month: Optional[str] = Field(None, pattern=M_PATTERN)
    suspended: bool = False
    ai_key: Optional[str] = Field(None, pattern="^(google|openrouter|anthropic|autre)$")
    billing_day: Optional[int] = Field(None, ge=1, le=31)
    billing_cycle: str = Field("mensuel", pattern="^(mensuel|annuel)$")


class ArchiveBody(BaseModel):
    archived: bool


async def _audit(db, entity: str, entity_id: str, action: str, detail: dict):
    await db.finance_audit.insert_one({"id": str(uuid.uuid4()), "at": _now(), "entity": entity, "entity_id": entity_id,
                                       "action": action, "detail": detail})


async def seed_catalog(db):
    """Default catalogue + migration of the first version (platform_costs / ai_invoices)."""
    if not await db.finance_categories.count_documents({}):
        m = month_key()
        for (cname, fam), provs in SEED.items():
            cid = str(uuid.uuid4())
            await db.finance_categories.insert_one({"id": cid, "name": cname, "family": fam, "status": "active", "created_at": _now()})
            for name, amt, cur, rec, ai in provs:
                await db.finance_providers.insert_one({"id": str(uuid.uuid4()), "name": name, "category_id": cid, "recurrence": rec,
                                                       "default_amount": float(amt), "currency": cur, "start_month": m, "end_month": None,
                                                       "suspended": False, "ai_key": ai, "status": "active", "created_at": _now()})
    async for doc in db.finance_months.find({"lines": {"$exists": False}}):
        provs = {p["name"].lower(): p async for p in db.finance_providers.find({}, {"_id": 0})}
        by_ai = {p["ai_key"]: p for p in provs.values() if p.get("ai_key")}
        other = await db.finance_categories.find_one({"family": "autres"}, {"_id": 0})
        lines = []
        for c in doc.get("platform_costs") or []:
            p = provs.get(c["name"].lower())
            if not p and other:
                p = {"id": str(uuid.uuid4()), "name": c["name"], "category_id": other["id"], "recurrence": "variable", "default_amount": 0.0,
                     "currency": c.get("currency", "CAD"), "start_month": doc["month"], "end_month": None, "suspended": False,
                     "ai_key": None, "status": "active", "created_at": _now()}
                await db.finance_providers.insert_one(dict(p))
                provs[c["name"].lower()] = p
            if p:
                lines.append({"provider_id": p["id"], "estimated": c.get("amount", 0.0), "real": None, "currency": c.get("currency", "CAD"), "note": ""})
        for i in doc.get("ai_invoices") or []:
            p = by_ai.get(i["provider"]) or provs.get(i["provider"].lower())
            if p and i.get("amount") is not None:
                lines.append({"provider_id": p["id"], "estimated": None, "real": i["amount"], "currency": i.get("currency", "USD"), "note": ""})
        await db.finance_months.update_one({"month": doc["month"]}, {"$set": {"lines": lines, "revenue_real": None},
                                                                      "$unset": {"platform_costs": "", "ai_invoices": ""}})


def _due_date(month: str, day: Optional[int]) -> Optional[str]:
    if not day:
        return None
    y, m = map(int, month.split("-"))
    return f"{month}-{min(day, calendar.monthrange(y, m)[1]):02d}"


def _bills_in(p: dict, month: str) -> bool:
    """Annual providers are billed only in the anniversary month of start_month."""
    return p.get("billing_cycle", "mensuel") != "annuel" or not p.get("start_month") or p["start_month"][5:] == month[5:]


def _shift(month: str, n: int) -> str:
    y, m = map(int, month.split("-"))
    t = y * 12 + m - 1 + n
    return f"{t // 12:04d}-{t % 12 + 1:02d}"


def next_invoice(p: dict) -> Optional[str]:
    if p.get("status") != "active" or p.get("suspended") or p.get("recurrence") != "recurrent":
        return None
    today = datetime.now(TZ).strftime("%Y-%m-%d")
    m = max(month_key(), p.get("start_month") or month_key())
    for i in range(13):
        mm = _shift(m, i)
        if p.get("end_month") and mm > p["end_month"]:
            return None
        if _bills_in(p, mm):
            d = _due_date(mm, p.get("billing_day") or 1)
            if d >= today or not p.get("billing_day"):
                return d if p.get("billing_day") else mm
    return None


def _nature(lines):
    """real / estimated / mixed for a set of lines, plus share of real amounts."""
    tot = sum(x["used_cad"] for x in lines)
    real = sum(x["used_cad"] for x in lines if x["nature"] == "real")
    n = {x["nature"] for x in lines if x["used_cad"]}
    nat = "real" if n == {"real"} else "estimated" if n <= {"estimated"} else "mixed"
    return {"nature": nat, "real_pct": round(real * 100 / tot, 1) if tot else None}


def create_finance_router(db, check_admin, credits_fn=None):
    router = APIRouter(prefix="/api/admin")

    async def _settings():
        s = await db.admin_settings.find_one({"key": "finance"}, {"_id": 0}) or {}
        pricing = {k: {**v, **(s.get("pricing") or {}).get(k, {})} for k, v in DEFAULT_PRICING.items()}
        return {"fx_usd_cad": s.get("fx_usd_cad", 1.37), "pricing": pricing}

    async def _catalog():
        cats = {c["id"]: c async for c in db.finance_categories.find({}, {"_id": 0})}
        provs = [p async for p in db.finance_providers.find({}, {"_id": 0}).sort("name", 1)]
        return cats, provs

    async def _month_doc(month: str):
        doc = await db.finance_months.find_one({"month": month}, {"_id": 0})
        if doc:
            return {"revenue_real": None, "lines": [], **doc}, False
        prev = await db.finance_months.find_one({"month": {"$lt": month}}, {"_id": 0}, sort=[("month", -1)])
        past = month < month_key()
        return {"month": month, "price_cad": (prev or {}).get("price_cad", 19.99), "paid_override": 0 if past else None,
                "revenue_real": None, "adjustments": [], "lines": []}, True

    async def _members(month: str):
        start, end, _ = _bounds(month)
        registered = await db.users.count_documents(uf({"created_at": {"$lt": end}}, "id"))
        active = {a["user_id"] async for a in db.member_activity.find(uf({"month": month}), {"user_id": 1})}
        if month == month_key():
            active |= {u["id"] async for u in db.users.find(uf({"last_seen_at": {"$gte": start}}, "id"), {"id": 1})}
        flagged = {u["id"] async for u in db.users.find(uf({"paid": True}, "id"), {"id": 1})}
        return registered, active, flagged

    async def _ai(month: str, pricing: dict):
        rows = [r async for r in db.ai_usage.aggregate([
            {"$match": {"month": month}},
            {"$group": {"_id": {"b": "$bucket", "bill": "$billing", "f": "$feature"}, "calls": {"$sum": 1},
                        "tin": {"$sum": "$tokens_in"}, "tout": {"$sum": "$tokens_out"}}}])]
        buckets = {k: {"key": k, "label": v, "calls": 0, "tokens_in": 0, "tokens_out": 0, "est_usd": 0.0} for k, v in BUCKETS.items()}
        billing, features = {k: 0.0 for k in AI_KEYS}, {}
        for r in rows:
            p = pricing.get(r["_id"]["b"], DEFAULT_PRICING["autre"])
            usd = (r["tin"] * p["in"] + r["tout"] * p["out"]) / 1e6
            b = buckets[r["_id"]["b"]]
            b["calls"] += r["calls"]; b["tokens_in"] += r["tin"]; b["tokens_out"] += r["tout"]; b["est_usd"] += usd
            billing[r["_id"]["bill"]] = billing.get(r["_id"]["bill"], 0.0) + usd
            f = features.setdefault(r["_id"]["f"] or "autre", {"feature": r["_id"]["f"] or "autre", "calls": 0, "est_usd": 0.0})
            f["calls"] += r["calls"]; f["est_usd"] += usd
        return list(buckets.values()), billing, list(features.values())

    def _lines(month, doc, cats, provs, ai_usd, cad):
        saved = {ln["provider_id"]: ln for ln in doc.get("lines") or []}
        out = []
        for p in provs:
            cat = cats.get(p["category_id"]) or {"name": "?", "family": "autres", "status": "active"}
            ln = saved.get(p["id"])
            in_range = (not p.get("start_month") or p["start_month"] <= month) and (not p.get("end_month") or month <= p["end_month"])
            live = p["status"] == "active" and cat["status"] == "active" and not p.get("suspended") and in_range
            if not ln and not (live and ((p["recurrence"] == "recurrent" and _bills_in(p, month)) or p.get("ai_key"))):
                continue
            cur = (ln or {}).get("currency") or p["currency"]
            if ln and ln.get("estimated") is not None:
                est, src = cad(ln["estimated"], cur), "saisie"
            elif p.get("ai_key"):
                est, src = ai_usd.get(p["ai_key"], 0.0) * cad(1, "USD"), "jetons"
            elif live and p["recurrence"] == "recurrent" and _bills_in(p, month):
                est, src = cad(p["default_amount"], p["currency"]), "recurrent"
            else:
                est, src = None, None
            real = cad(ln["real"], cur) if ln and ln.get("real") is not None else None
            if est is None and real is None and not live:
                continue
            used = real if real is not None else (est or 0.0)
            bdate = (ln or {}).get("billing_date")
            due = _due_date(month, p.get("billing_day"))
            today = datetime.now(TZ).strftime("%Y-%m-%d")
            overdue = month < month_key() or (due is not None and due < today)
            warnings = []
            if real is not None and not bdate:
                warnings.append("date_missing")
            if real is None and (est or 0) >= 0.01:
                warnings.append("real_unconfirmed" if overdue else "estimate_only")
            out.append({"billing_date": bdate, "due_date": due, "billing_day": p.get("billing_day"),
                        "billing_cycle": p.get("billing_cycle", "mensuel"), "warnings": warnings,"provider_id": p["id"], "name": p["name"], "category": cat["name"], "family": cat["family"],
                        "recurrence": p["recurrence"], "provider_status": p["status"], "suspended": p.get("suspended", False),
                        "ai_key": p.get("ai_key"), "currency": cur, "default_amount": p["default_amount"], "default_currency": p["currency"],
                        "saved_estimated": (ln or {}).get("estimated"), "saved_real": (ln or {}).get("real"), "note": (ln or {}).get("note", ""),
                        "est_cad": None if est is None else round(est, 4), "est_source": src, "real_cad": None if real is None else round(real, 2),
                        "gap_cad": None if real is None or est is None else round(real - est, 2),
                        "gap_pct": None if real is None or not est else round((real - est) * 100 / est, 1),
                        "used_cad": round(used, 4), "nature": "real" if real is not None else "estimated"})
        return out

    def _per(x, n):
        return round(x / n, 2) if n else None

    async def summary(month: str, light: bool = False):
        st = await _settings()
        fx = st["fx_usd_cad"]
        cad = lambda a, c: (a or 0.0) * (fx if c == "USD" else 1.0)  # noqa: E731
        doc, draft = await _month_doc(month)
        cats, provs = await _catalog()
        registered, active, flagged = await _members(month)
        n_active = len(active)
        paid = doc["paid_override"] if doc.get("paid_override") is not None else len(flagged)
        active_paid = len(active & flagged) if flagged else min(paid, n_active)
        theory = round(doc["price_cad"] * paid, 2)
        adj = round(sum(-abs(a["amount"]) if a["kind"] in NEGATIVE_KINDS else a["amount"] for a in doc["adjustments"]), 2)
        expected = round(theory + adj, 2)
        real_rev = doc.get("revenue_real")
        rev = real_rev if real_rev is not None else expected
        buckets, ai_usd, features = await _ai(month, st["pricing"])
        lines = _lines(month, doc, cats, provs, ai_usd, cad)
        fam = {}
        for k, label in FAMILIES.items():
            ls = [x for x in lines if x["family"] == k]
            fam[k] = {"key": k, "label": label, "used_cad": round(sum(x["used_cad"] for x in ls), 2),
                      "est_cad": round(sum(x["est_cad"] or 0 for x in ls), 2), "real_cad": round(sum(x["real_cad"] or 0 for x in ls), 2),
                      "invest_cad": round(sum(x["used_cad"] for x in ls if x["recurrence"] == "ponctuel"), 2), **_nature(ls)}
        ops = round(sum(fam[k]["used_cad"] for k in OPS_FAMILIES), 2)
        dev = fam["developpement"]["used_cad"]
        total = round(ops + dev, 2)
        op_margin, net_margin = round(rev - ops, 2), round(rev - total, 2)
        pctof = lambda x: round(x * 100 / rev, 1) if rev else None  # noqa: E731
        ops_nat = _nature([x for x in lines if x["family"] in OPS_FAMILIES])
        all_nat = _nature(lines)
        out = {"month": month, "draft": draft, "fx_usd_cad": fx,
               "revenue": {"price_cad": doc["price_cad"], "paid": paid, "theory": theory, "adjustments": adj, "expected": expected,
                           "real": real_rev, "used": round(rev, 2), "nature": "real" if real_rev is not None else "estimated",
                           "gap_cad": None if real_rev is None else round(real_rev - theory, 2),
                           "gap_pct": None if real_rev is None or not theory else round((real_rev - theory) * 100 / theory, 1),
                           "unexplained_cad": None if real_rev is None else round(real_rev - expected, 2)},
               "families": fam, "ops_cad": ops, "dev_cad": dev, "invest_cad": fam["developpement"]["invest_cad"], "total_cad": total,
               "ops_nature": ops_nat, "total_nature": all_nat,
               "warnings": {w: sum(w in x["warnings"] for x in lines) for w in ("date_missing", "real_unconfirmed", "estimate_only")},
               "operating_margin_cad": op_margin, "operating_margin_pct": pctof(op_margin),
               "net_margin_cad": net_margin, "net_margin_pct": pctof(net_margin),
               "members": {"registered": registered, "active": n_active, "paid": paid, "active_paid": active_paid}}
        if light:
            return out
        _, _, days = _bounds(month)
        elapsed = datetime.now(TZ).day if month == month_key() else days
        ai_used = fam["ia"]["used_cad"]
        ai_lines = [x for x in lines if x["family"] == "ia"]
        pace_ai = sum((x["used_cad"] / elapsed * days) if x["est_source"] == "jetons" and x["real_cad"] is None else x["used_cad"] for x in ai_lines)
        out.update({
            "doc": doc, "lines": lines, "families_list": list(FAMILIES.items()),
            "features": [{**f, "est_cad": round(f["est_usd"] * fx, 4)} for f in features],
            "buckets": [{**b, "est_usd": round(b["est_usd"], 4), "est_cad": round(b["est_usd"] * fx, 4)} for b in buckets],
            "calls": sum(b["calls"] for b in buckets), "ai_log_usd": {k: round(v, 4) for k, v in ai_usd.items()},
            "per_member": {
                "revenue_per_paid": _per(rev, paid), "revenue_per_active": _per(rev, n_active),
                "infra_per_active": _per(fam["infrastructure"]["used_cad"], n_active), "ai_per_active": _per(ai_used, n_active),
                "marketing_per_active": _per(fam["marketing"]["used_cad"], n_active), "dev_per_active": _per(dev, n_active),
                "ops_per_active": _per(ops, n_active), "ops_per_active_paid": _per(ops, active_paid), "ops_per_paid": _per(ops, paid),
                "total_per_active": _per(total, n_active), "total_per_active_paid": _per(total, active_paid), "total_per_paid": _per(total, paid),
                "op_profit_per_active": _per(op_margin, n_active), "net_profit_per_active": _per(net_margin, n_active),
                "op_profit_per_paid": _per(op_margin, paid), "net_profit_per_paid": _per(net_margin, paid)},
            "pace": {"days_elapsed": elapsed, "days_in_month": days, "ai_month_end_cad": round(pace_ai, 2),
                     "operating_margin_month_end_cad": round(rev - (ops - ai_used + pace_ai), 2)},
        })
        ratio = (active_paid / n_active) if n_active and active_paid else 1.0
        ai_pa = (ai_used / n_active) if n_active else 0.0
        fixed = round(ops - ai_used, 2)
        out["scenarios"] = []
        for n in SCENARIOS:
            r = round(n * ratio * doc["price_cad"], 2)
            m = round(r - n * ai_pa - fixed, 2)
            out["scenarios"].append({"members": n, "paid": round(n * ratio), "revenue_cad": r, "ai_cad": round(n * ai_pa, 2), "fixed_cad": fixed,
                                     "margin_cad": m, "margin_pct": round(m * 100 / r, 1) if r else None})
        out["scenario_basis"] = {"paid_ratio_pct": round(ratio * 100, 1), "ai_per_active_cad": round(ai_pa, 4),
                                 "ratio_assumed": not (n_active and active_paid)}
        return out

    async def _credit(daily_usd: float):
        if not credits_fn:
            return None
        try:
            c = await credits_fn()
        except Exception as e:  # noqa: BLE001
            return {"error": str(e)[:120]}
        if not c.get("configured"):
            return {"configured": False}
        alert = await db.admin_settings.find_one({"key": "credit_alert"}, {"_id": 0}) or {}
        th = alert.get("threshold", 20)
        return {**c, "threshold": th, "daily_usd": round(daily_usd, 4),
                "days_left": round(c["remaining"] / daily_usd, 1) if daily_usd > 0 else None, "low": (c.get("remaining_pct") or 0) <= th}

    @router.get("/finance")
    async def finance(month: Optional[str] = Query(None, pattern=M_PATTERN), include_test: bool = False, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        await scope(db, include_test)
        month = month or month_key()
        s = await summary(month)
        hist, (y, m) = [], map(int, month.split("-"))
        for i in range(5, -1, -1):
            yy, mm = y + (m - 1 - i) // 12, (m - 1 - i) % 12 + 1
            hist.append(await summary(f"{yy:04d}-{mm:02d}", light=True))
        s["credit"] = await _credit(s["ai_log_usd"].get("openrouter", 0.0) / max(1, s["pace"]["days_elapsed"]))
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
        ids = {p["id"] async for p in db.finance_providers.find({}, {"id": 1})}
        lines = [ln.model_dump() for ln in body.lines if ln.provider_id in ids]
        before = await db.finance_months.find_one({"month": month}, {"_id": 0}) or {}
        await db.finance_months.update_one({"month": month}, {"$set": {"month": month, **body.model_dump(), "lines": lines,
                                           "updated_at": _now()}}, upsert=True)
        changed = [ln["provider_id"] for ln in lines if ln not in (before.get("lines") or [])]
        await _audit(db, "month", month, "update", {"lines_changed": len(changed), "revenue_real": body.revenue_real,
                                                    "price_cad": body.price_cad, "paid_override": body.paid_override})
        return {"ok": True}

    @router.put("/finance-settings")
    async def save_settings(body: SettingsBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        pricing = {k: {"in": float(v.get("in", 0)), "out": float(v.get("out", 0))} for k, v in body.pricing.items()
                   if k in DEFAULT_PRICING and isinstance(v, dict) and float(v.get("in", 0)) >= 0 and float(v.get("out", 0)) >= 0}
        await db.admin_settings.update_one({"key": "finance"}, {"$set": {"fx_usd_cad": body.fx_usd_cad, "pricing": pricing}}, upsert=True)
        return await _settings()

    # ---------- catalogue ----------
    async def _used_providers():
        used = set()
        async for d in db.finance_months.find({}, {"lines": 1}):
            used |= {ln["provider_id"] for ln in d.get("lines") or [] if ln.get("estimated") is not None or ln.get("real") is not None}
        return used

    @router.get("/finance-catalog")
    async def catalog(x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        cats, provs = await _catalog()
        used = await _used_providers()
        last = {}
        async for d in db.finance_months.find({}, {"_id": 0, "month": 1, "lines": 1}).sort("month", 1):
            for ln in d.get("lines") or []:
                if ln.get("real") is not None:
                    last[ln["provider_id"]] = {"month": d["month"], "date": ln.get("billing_date"), "amount": ln["real"], "currency": ln.get("currency")}
        count = {}
        for p in provs:
            count[p["category_id"]] = count.get(p["category_id"], 0) + 1
            p["used"] = p["id"] in used
            p["last_invoice"] = last.get(p["id"])
            p["next_invoice"] = next_invoice(p)
        return {"families": FAMILIES, "ai_keys": AI_KEYS, "providers": provs,
                "categories": [{**c, "providers": count.get(c["id"], 0)} for c in sorted(cats.values(), key=lambda c: (list(FAMILIES).index(c["family"]), c["name"]))]}

    @router.post("/finance-categories")
    async def add_category(body: CategoryBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        c = {"id": str(uuid.uuid4()), **body.model_dump(), "status": "active", "created_at": _now()}
        await db.finance_categories.insert_one(dict(c))
        await _audit(db, "category", c["id"], "create", body.model_dump())
        c.pop("_id", None)
        return c

    @router.put("/finance-categories/{cid}")
    async def edit_category(cid: str, body: CategoryBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        before = await db.finance_categories.find_one({"id": cid}, {"_id": 0})
        if not before:
            raise HTTPException(status_code=404, detail="Catégorie introuvable")
        await db.finance_categories.update_one({"id": cid}, {"$set": body.model_dump()})
        await _audit(db, "category", cid, "update", {"avant": {k: before.get(k) for k in ("name", "family")}, "après": body.model_dump()})
        return {"ok": True}

    @router.post("/finance-categories/{cid}/archive")
    async def archive_category(cid: str, body: ArchiveBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        r = await db.finance_categories.update_one({"id": cid}, {"$set": {"status": "archived" if body.archived else "active"}})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Catégorie introuvable")
        await _audit(db, "category", cid, "archive" if body.archived else "reactivate", {})
        return {"ok": True}

    @router.delete("/finance-categories/{cid}")
    async def delete_category(cid: str, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        if await db.finance_providers.count_documents({"category_id": cid}):
            raise HTTPException(status_code=409, detail="Catégorie utilisée par des fournisseurs : archivez-la plutôt.")
        r = await db.finance_categories.delete_one({"id": cid})
        if not r.deleted_count:
            raise HTTPException(status_code=404, detail="Catégorie introuvable")
        await _audit(db, "category", cid, "delete", {})
        return {"ok": True}

    async def _check_cat(cid):
        if not await db.finance_categories.find_one({"id": cid}, {"_id": 1}):
            raise HTTPException(status_code=422, detail="Catégorie inconnue")

    @router.post("/finance-providers")
    async def add_provider(body: ProviderBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        await _check_cat(body.category_id)
        p = {"id": str(uuid.uuid4()), **body.model_dump(), "start_month": body.start_month or month_key(), "status": "active", "created_at": _now()}
        await db.finance_providers.insert_one(dict(p))
        await _audit(db, "provider", p["id"], "create", body.model_dump())
        p.pop("_id", None)
        return p

    @router.put("/finance-providers/{pid}")
    async def edit_provider(pid: str, body: ProviderBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        before = await db.finance_providers.find_one({"id": pid}, {"_id": 0})
        if not before:
            raise HTTPException(status_code=404, detail="Fournisseur introuvable")
        await _check_cat(body.category_id)
        new = body.model_dump()
        diff = {k: {"avant": before.get(k), "après": v} for k, v in new.items() if before.get(k) != v}
        await db.finance_providers.update_one({"id": pid}, {"$set": new})
        if diff:
            await _audit(db, "provider", pid, "update", diff)
        return {"ok": True}

    @router.post("/finance-providers/{pid}/archive")
    async def archive_provider(pid: str, body: ArchiveBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        r = await db.finance_providers.update_one({"id": pid}, {"$set": {"status": "archived" if body.archived else "active"}})
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Fournisseur introuvable")
        await _audit(db, "provider", pid, "archive" if body.archived else "reactivate", {})
        return {"ok": True}

    @router.delete("/finance-providers/{pid}")
    async def delete_provider(pid: str, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        if pid in await _used_providers():
            raise HTTPException(status_code=409, detail="Fournisseur déjà utilisé dans un mois : archivez-le plutôt.")
        r = await db.finance_providers.delete_one({"id": pid})
        if not r.deleted_count:
            raise HTTPException(status_code=404, detail="Fournisseur introuvable")
        await db.finance_months.update_many({}, {"$pull": {"lines": {"provider_id": pid}}})
        await _audit(db, "provider", pid, "delete", {})
        return {"ok": True}

    @router.get("/finance-audit")
    async def audit(entity_id: Optional[str] = None, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        q = {"entity_id": entity_id} if entity_id else {}
        return [a async for a in db.finance_audit.find(q, {"_id": 0}).sort("at", -1).limit(50)]

    # ---------- members ----------
    @router.get("/members")
    async def members(x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        since = (datetime.now(timezone.utc) - timedelta(days=400)).isoformat()
        cur = db.users.find({}, {"_id": 0, "id": 1, "email": 1, "name": 1, "created_at": 1, "last_seen_at": 1, "paid": 1, "is_test": 1}).sort("created_at", -1).limit(1000)
        start, _, _ = _bounds(month_key())
        return [{**u, "is_test": is_test(u), "paid": bool(u.get("paid")), "active_month": (u.get("last_seen_at") or "") >= start, "recent": (u.get("last_seen_at") or "") >= since}
                async for u in cur]

    @router.put("/members/{user_id}/paid")
    async def set_paid(user_id: str, body: PaidBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        prev = await db.users.find_one({"id": user_id}, {"_id": 0, "paid": 1, "paid_since": 1}) or {}
        upd = {"$set": {"paid": True, **({} if prev.get("paid") and prev.get("paid_since") else {"paid_since": datetime.now(timezone.utc).isoformat()})}} if body.paid else {"$set": {"paid": False}, "$unset": {"paid_since": ""}}
        r = await db.users.update_one({"id": user_id}, upd)
        if not r.matched_count:
            raise HTTPException(status_code=404, detail="Membre introuvable")
        return {"ok": True}

    return router


async def ensure_finance_indexes(db):
    await db.ai_usage.create_index([("month", 1), ("bucket", 1)])
    await db.member_activity.create_index([("user_id", 1), ("month", 1)], unique=True)
    await db.finance_months.create_index("month", unique=True)
    await db.finance_providers.create_index("id", unique=True)
    await db.finance_categories.create_index("id", unique=True)
    await db.finance_audit.create_index([("entity_id", 1), ("at", -1)])
    await seed_catalog(db)
