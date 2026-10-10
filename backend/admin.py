"""Admin space: anonymous analytics, ATS submissions store, CSV/Excel export,
90-day TTL retention. Password-gated via ADMIN_PASSWORD (space disabled if unset).

Privacy by design: IPs are truncated before storage; the full CV is stored ONLY
when the user gave explicit opt-in consent. No automatic email here (Lot B).
"""
import os
import io
import csv
import hmac
from datetime import datetime, timezone, timedelta

from fastapi import APIRouter, HTTPException, Header, Request, Response
from pydantic import BaseModel

ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD")
RETENTION_DAYS = int(os.environ.get("ADMIN_RETENTION_DAYS", "90"))


def _admin_password():
    # Read live so it works regardless of load_dotenv timing / import order.
    return os.environ.get("ADMIN_PASSWORD")


def _retention_days():
    return int(os.environ.get("ADMIN_RETENTION_DAYS", "90"))


def _now():
    return datetime.now(timezone.utc)


def anonymize_ip(ip: str) -> str:
    """Truncate an IP so it is no longer directly identifying (pseudonymization)."""
    if not ip:
        return ""
    ip = ip.split(",")[0].strip()
    if ":" in ip:  # IPv6 -> keep first 3 hextets
        parts = ip.split(":")
        return ":".join(parts[:3]) + "::"
    parts = ip.split(".")
    if len(parts) == 4:
        return f"{parts[0]}.{parts[1]}.x.x"
    return ""


def client_ip(request: Request) -> str:
    xff = request.headers.get("x-forwarded-for")
    if xff:
        return xff.split(",")[0].strip()
    return request.client.host if request.client else ""


async def ensure_indexes(db):
    secs = _retention_days() * 86400
    await db.admin_events.create_index("ts", expireAfterSeconds=secs)
    await db.ats_submissions.create_index("ts", expireAfterSeconds=secs)


async def record_event(db, type_, session_id=None, ip_trunc="", meta=None):
    try:
        await db.admin_events.insert_one({
            "type": type_, "session_id": session_id or "",
            "ip_trunc": ip_trunc or "", "meta": meta or {}, "ts": _now(),
        })
    except Exception:
        pass  # analytics must never break the main flow


async def record_ats_submission(db, session_id, ip_trunc, consent, score, ats_report, cv_text, company=""):
    try:
        await db.ats_submissions.insert_one({
            "session_id": session_id or "",
            "ip_trunc": ip_trunc or "",
            "consent": bool(consent),
            "score": score,
            "ats_report": ats_report or "",
            "company": company or "",
            "cv_text": (cv_text or "") if consent else None,  # CV stored only with consent
            "ts": _now(),
        })
    except Exception:
        pass


def _check_admin(pwd):
    admin_pwd = _admin_password()
    if not admin_pwd:
        raise HTTPException(status_code=403, detail="Espace admin désactivé (ADMIN_PASSWORD non défini)")
    if not pwd or not hmac.compare_digest(str(pwd), str(admin_pwd)):
        raise HTTPException(status_code=401, detail="Mot de passe administrateur incorrect")


class AdminLogin(BaseModel):
    password: str = ""


async def _timeseries(db, fmt, since):
    pipeline = [
        {"$match": {"ts": {"$gte": since}}},
        {"$group": {
            "_id": {"b": {"$dateToString": {"format": fmt, "date": "$ts"}}, "type": "$type"},
            "n": {"$sum": 1},
        }},
    ]
    buckets = {}
    async for row in db.admin_events.aggregate(pipeline):
        b = row["_id"]["b"]
        t = row["_id"]["type"]
        buckets.setdefault(b, {"bucket": b, "simulations": 0, "ats": 0, "cover_letters": 0})
        if t == "simulation":
            buckets[b]["simulations"] += row["n"]
        elif t == "ats":
            buckets[b]["ats"] += row["n"]
        elif t == "cover_letter":
            buckets[b]["cover_letters"] += row["n"]
    return sorted(buckets.values(), key=lambda x: x["bucket"])


def create_admin_router(db):
    router = APIRouter(prefix="/api/admin")

    @router.post("/login")
    async def admin_login(body: AdminLogin):
        _check_admin(body.password)
        return {"success": True, "retention_days": _retention_days()}

    @router.get("/stats")
    async def admin_stats(x_admin_password: str = Header(None)):
        _check_admin(x_admin_password)
        try:
            return await _stats(db)
        except Exception as e:  # surface real error with CORS headers (temporary debug)
            raise HTTPException(status_code=500, detail=f"stats: {type(e).__name__}: {e}")

    async def _stats(db):
        now = _now()

        sim_sessions = await db.admin_events.distinct("session_id", {"type": "simulation"})
        simulations = await db.admin_events.count_documents({"type": "simulation"})
        ats_analyses = await db.ats_submissions.count_documents({})
        cvs_analyzed = await db.ats_submissions.count_documents({"cv_text": {"$ne": None}})
        cover_letters = await db.admin_events.count_documents({"type": "cover_letter"})

        llm = {"calls": 0, "tokens_in": 0, "tokens_out": 0, "cost": 0.0, "by_provider": {}}
        pipe = [
            {"$match": {"type": "llm_call"}},
            {"$group": {
                "_id": "$meta.provider",
                "calls": {"$sum": 1},
                "tin": {"$sum": {"$ifNull": ["$meta.tokens_in", 0]}},
                "tout": {"$sum": {"$ifNull": ["$meta.tokens_out", 0]}},
                "cost": {"$sum": {"$ifNull": ["$meta.cost", 0]}},
            }},
        ]
        async for r in db.admin_events.aggregate(pipe):
            prov = r["_id"] or "inconnu"
            llm["calls"] += r["calls"]
            llm["tokens_in"] += r["tin"]
            llm["tokens_out"] += r["tout"]
            llm["cost"] += r["cost"]
            llm["by_provider"][prov] = {
                "calls": r["calls"], "tokens_in": r["tin"],
                "tokens_out": r["tout"], "cost": round(r["cost"], 4),
            }
        llm["cost"] = round(llm["cost"], 4)

        submissions = []
        async for d in db.ats_submissions.find({}, {"_id": 0}).sort("ts", -1).limit(100):
            ts = d.get("ts")
            submissions.append({
                "ts": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "score": d.get("score"),
                "company": d.get("company", ""),
                "consent": d.get("consent", False),
                "has_cv": bool(d.get("cv_text")),
                "ip_trunc": d.get("ip_trunc", ""),
            })

        return {
            "totals": {
                "visitors": len([s for s in sim_sessions if s]),
                "simulations": simulations,
                "ats_analyses": ats_analyses,
                "cvs_analyzed": cvs_analyzed,
                "cover_letters": cover_letters,
            },
            "llm": llm,
            "by_day": await _timeseries(db, "%Y-%m-%d", now - timedelta(days=30)),
            "by_week": await _timeseries(db, "%G-S%V", now - timedelta(days=84)),
            "by_month": await _timeseries(db, "%Y-%m", now - timedelta(days=365)),
            "submissions": submissions,
            "retention_days": _retention_days(),
        }

    @router.get("/export")
    async def admin_export(fmt: str = "csv", x_admin_password: str = Header(None)):
        _check_admin(x_admin_password)
        rows = []
        async for d in db.ats_submissions.find({}, {"_id": 0}).sort("ts", -1):
            ts = d.get("ts")
            rows.append({
                "date": ts.isoformat() if hasattr(ts, "isoformat") else str(ts),
                "score": d.get("score", ""),
                "entreprise": d.get("company", ""),
                "consentement": "oui" if d.get("consent") else "non",
                "cv_stocke": "oui" if d.get("cv_text") else "non",
                "ip_anonymisee": d.get("ip_trunc", ""),
            })
        headers_cols = ["date", "score", "entreprise", "consentement", "cv_stocke", "ip_anonymisee"]

        if fmt == "xlsx":
            from openpyxl import Workbook
            wb = Workbook()
            ws = wb.active
            ws.title = "Analyses ATS"
            ws.append([h.replace("_", " ").title() for h in headers_cols])
            for r in rows:
                ws.append([r[h] for h in headers_cols])
            buf = io.BytesIO()
            wb.save(buf)
            buf.seek(0)
            return Response(
                content=buf.read(),
                media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                headers={"Content-Disposition": "attachment; filename=analyses_ats.xlsx"},
            )

        buf = io.StringIO()
        w = csv.DictWriter(buf, fieldnames=headers_cols)
        w.writeheader()
        for r in rows:
            w.writerow(r)
        return Response(
            content=buf.getvalue(),
            media_type="text/csv",
            headers={"Content-Disposition": "attachment; filename=analyses_ats.csv"},
        )

    return router
