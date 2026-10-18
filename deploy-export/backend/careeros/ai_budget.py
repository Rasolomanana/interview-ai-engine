"""AI budget governance: daily global cap, free-quota tracking per provider, rules-only mode and a response cache."""
import hashlib
import logging
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Header, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

FREE = ("gemini", "groq", "openrouter_free", "mistral")
PAID = ("openrouter", "openrouter_premium", "anthropic", "deepseek")
LABELS = {"gemini": "Gemini Flash", "groq": "Groq", "openrouter_free": "OpenRouter gratuit", "mistral": "Mistral", "openrouter": "OpenRouter (payant)",
          "openrouter_premium": "OpenRouter premium (payant)", "anthropic": "Anthropic (payant)", "deepseek": "DeepSeek (payant)"}
DEFAULTS = {"daily_cap": 2000, "allow_paid": False, "force_rules_only": False}
CACHE_DAYS = 30
RETRY_WINDOW = timedelta(minutes=10)  # same prompt again within 10 min = deliberate retry -> bypass the cache
_mem = {"exhausted": {}}


class QuotaReached(HTTPException):
    def __init__(self, reason: str):
        super().__init__(status_code=503, detail=f"Analyse IA momentanément indisponible ({reason}) : analyse par règles utilisée.")


def _now():
    return datetime.now(timezone.utc)


def _midnight_utc():
    return (_now() + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)


def is_quota_error(e: Exception) -> bool:
    code = getattr(e, "status_code", None) or getattr(getattr(e, "response", None), "status_code", None)
    msg = str(e).lower()
    return code == 429 or any(w in msg for w in ("429", "quota", "rate limit", "rate_limit", "resource_exhausted", "too many requests", "insufficient"))


async def config(db) -> dict:
    return {**DEFAULTS, **((await db.ai_budget_config.find_one({"_id": "config"}, {"_id": 0})) or {})}


async def mark_exhausted(db, label: str, err: str):
    until = _midnight_utc()
    _mem["exhausted"][label] = until
    await db.ai_provider_state.update_one({"label": label}, {"$set": {"exhausted_until": until.isoformat(), "last_error": err[:200], "at": _now().isoformat()}}, upsert=True)


async def exhausted(db) -> set:
    now = _now()
    out = {k for k, v in _mem["exhausted"].items() if v > now}
    async for s in db.ai_provider_state.find({"exhausted_until": {"$gt": now.isoformat()}}, {"_id": 0, "label": 1}):
        out.add(s["label"])
    return out


async def skip(db, label: str) -> bool:
    """True if this provider must not be called now (quota exhausted, or paid while paid fallback is off)."""
    cfg = await config(db)
    return label in await exhausted(db) or (label in PAID and not cfg["allow_paid"])


async def _today_calls(db) -> int:
    day = _now().date().isoformat()
    return await db.ai_usage.count_documents({"at": {"$gte": day}})


async def gate(db, free_labels: list):
    cfg = await config(db)
    if cfg["force_rules_only"]:
        raise QuotaReached("mode Règles uniquement activé")
    if await _today_calls(db) >= int(cfg["daily_cap"]):
        raise QuotaReached("plafond quotidien atteint")
    if free_labels and not cfg["allow_paid"] and set(free_labels) <= await exhausted(db):
        raise QuotaReached("quotas gratuits du jour atteints")


def governed(db, raw, free_labels):
    """Wrap a generate(system, user, tier) coroutine with cache + gate."""
    async def generate(system_message: str, user_text: str, tier: str = "eco") -> str:
        key = hashlib.sha256(f"{tier}\x00{system_message}\x00{user_text}".encode()).hexdigest()
        hit = await db.ai_cache.find_one({"key": key}, {"_id": 0})
        now = _now()
        if hit and datetime.fromisoformat(hit["used_at"]) < now - RETRY_WINDOW:
            await db.ai_cache.update_one({"key": key}, {"$set": {"used_at": now.isoformat()}, "$inc": {"hits": 1}})
            await db.ai_cache_stats.update_one({"day": now.date().isoformat()}, {"$inc": {"hits": 1}}, upsert=True)
            return hit["text"]
        await gate(db, free_labels() if callable(free_labels) else free_labels)
        txt = await raw(system_message, user_text, tier)
        await db.ai_cache.update_one({"key": key}, {"$set": {"text": txt, "used_at": now.isoformat(), "expires": now + timedelta(days=CACHE_DAYS)},
                                                    "$setOnInsert": {"hits": 0}}, upsert=True)
        return txt
    return generate


async def ensure_indexes(db):
    await db.ai_cache.create_index("key", unique=True)
    await db.ai_cache.create_index("expires", expireAfterSeconds=0)


class ConfigBody(BaseModel):
    daily_cap: int = Field(ge=0, le=1_000_000)
    allow_paid: bool
    force_rules_only: bool


def create_ai_budget_router(db, check_admin, chain_labels):
    router = APIRouter(prefix="/api/admin/ai-budget")

    @router.get("")
    async def status(x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        cfg, day, ex = await config(db), _now().date().isoformat(), await exhausted(db)
        per = {r["_id"]: r["n"] async for r in db.ai_usage.aggregate([{"$match": {"at": {"$gte": day}}}, {"$group": {"_id": "$label", "n": {"$sum": 1}}}])}
        last = await db.ai_usage.find_one({"at": {"$gte": day}}, {"_id": 0, "label": 1, "at": 1}, sort=[("at", -1)])
        labels = chain_labels()
        states = {s["label"]: s async for s in db.ai_provider_state.find({}, {"_id": 0})}
        providers = [{"label": lb, "name": LABELS.get(lb, lb), "free": lb in FREE, "calls_today": per.get(lb, 0), "exhausted": lb in ex,
                      "disabled": lb in PAID and not cfg["allow_paid"], "last_error": (states.get(lb) or {}).get("last_error", "") if lb in ex else ""} for lb in labels]
        used = sum(per.values())
        free_cfg = [lb for lb in labels if lb in FREE]
        rules_only = cfg["force_rules_only"] or used >= cfg["daily_cap"] or (bool(free_cfg) and not cfg["allow_paid"] and set(free_cfg) <= ex)
        nxt = next((p["name"] for p in providers if not p["exhausted"] and not p["disabled"]), None)
        hits = (await db.ai_cache_stats.find_one({"day": day}, {"_id": 0, "hits": 1}) or {}).get("hits", 0)
        return {"config": cfg, "used_today": used, "cap": cfg["daily_cap"], "providers": providers, "current": None if rules_only else nxt,
                "last_used": LABELS.get((last or {}).get("label"), (last or {}).get("label")), "rules_only": rules_only, "cache_hits_today": hits,
                "cache_size": await db.ai_cache.estimated_document_count(), "reset_at": _midnight_utc().isoformat()}

    @router.put("")
    async def save(body: ConfigBody, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        await db.ai_budget_config.update_one({"_id": "config"}, {"$set": body.model_dump()}, upsert=True)
        return {"ok": True}

    @router.post("/reset/{label}")
    async def reset(label: str, x_admin_password: str = Header(None)):
        check_admin(x_admin_password)
        _mem["exhausted"].pop(label, None)
        await db.ai_provider_state.delete_one({"label": label})
        return {"ok": True}

    return router
