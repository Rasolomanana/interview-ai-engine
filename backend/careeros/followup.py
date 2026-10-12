"""Follow-up preparation (member validation ALWAYS required): AI email drafts and .ics
interview events (Google Calendar / Outlook / Apple Calendar). Nothing is sent or added
automatically — drafts stay "brouillon" until the member acts."""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, Field

from .prompts import SYSTEM

KINDS = {
    "confirmation": "confirmer sa présence à l'entrevue (date, heure, format), remercier pour l'invitation, demander si quelque chose est à préparer",
    "remerciement": "remercier après l'entrevue (dans les 24 h), rappeler 1-2 points forts concrets échangés, réaffirmer l'intérêt",
    "relance": "relancer poliment après une candidature ou une entrevue sans nouvelles (7-10 jours), apporter un élément de valeur",
}


class DraftBody(BaseModel):
    kind: Literal["confirmation", "remerciement", "relance"]
    recruiter_name: str = ""
    to: str = ""
    interview_at: str = ""
    notes: str = Field(default="", max_length=1500)


def _ics_dt(iso: str) -> str:
    d = datetime.fromisoformat(iso.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _esc(t: str) -> str:
    return (t or "").replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(uid: str, title: str, start_iso: str, minutes: int, location: str, description: str) -> str:
    start = datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    end_iso = (start + timedelta(minutes=minutes or 45)).isoformat()
    return "\r\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CareerOS//Interview//FR", "CALSCALE:GREGORIAN", "METHOD:PUBLISH",
        "BEGIN:VEVENT", f"UID:{uid}@careeros", f"DTSTAMP:{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{_ics_dt(start_iso)}", f"DTEND:{_ics_dt(end_iso)}", f"SUMMARY:{_esc(title)}",
        f"LOCATION:{_esc(location)}", f"DESCRIPTION:{_esc(description)}",
        "BEGIN:VALARM", "TRIGGER:-PT60M", "ACTION:DISPLAY", "DESCRIPTION:Entrevue dans 1 heure", "END:VALARM",
        "END:VEVENT", "END:VCALENDAR", ""])


def create_followup_router(db, current_user, generate_text, parse_json, careeros_router):
    router = APIRouter(prefix="/api/careeros/applications", tags=["followup"])
    own = careeros_router.own_application

    @router.post("/{app_id}/emails/draft")
    async def draft(app_id: str, body: DraftBody, user: dict = Depends(current_user)):
        a = await own(app_id, user)
        d = (a.get("parts") or {}).get("decision") or {}
        prompt = (f"Rédige un courriel professionnel en français pour {KINDS[body.kind]}.\n"
                  f"Poste : {d.get('poste', '')} — Entreprise : {d.get('entreprise', '')} — Référence interne : {a['code']} (ne pas la citer dans le courriel).\n"
                  f"Destinataire : {body.recruiter_name or 'le/la recruteur(e)'} · Date d'entrevue : {body.interview_at or 'non précisée'}\n"
                  f"Notes du membre : {body.notes or '—'}\nCV (extrait) : {(a.get('inputs') or {}).get('cv_text', '')[:1500]}\n"
                  "Court (90-150 mots), humain, sans cliché. Signature : [Votre nom]. "
                  'Renvoie UNIQUEMENT un JSON : {"subject": "...", "body": "..."}')
        out = parse_json((await generate_text(SYSTEM, prompt)).strip()) or {}
        if not out.get("body"):
            raise HTTPException(status_code=502, detail="Brouillon indisponible, réessayez.")
        now = datetime.now(timezone.utc).isoformat()
        doc = {"id": str(uuid.uuid4()), "user_id": user["id"], "application_id": app_id, "application_code": a["code"],
               "source": "agent:followup", "created_at": now, "updated_at": now, "revisions": [], "kind": body.kind,
               "to": body.to, "subject": out.get("subject", ""), "body": out["body"], "status": "brouillon",
               "recruiter_id": "", "interview_id": "", "requires_member_validation": True}
        await db.emails.insert_one(dict(doc))
        await db.applications.update_one({"id": app_id}, {"$push": {"timeline": {"at": now, "type": "email_draft", "detail": body.kind}}})
        return doc

    @router.get("/{app_id}/interviews/{interview_id}/ics")
    async def ics(app_id: str, interview_id: str, user: dict = Depends(current_user)):
        a = await own(app_id, user)
        i = await db.interviews.find_one({"id": interview_id, "application_id": app_id}, {"_id": 0})
        if not i or not i.get("scheduled_at"):
            raise HTTPException(status_code=404, detail="Entrevue sans date")
        d = (a.get("parts") or {}).get("decision") or {}
        title = f"Entrevue {i.get('stage', '').upper()} — {d.get('poste', '')} · {d.get('entreprise', '')}"
        desc = f"Référence CareerOS : {a['code']}\nFormat : {i.get('mode', '')}\nPréparation : questions et réponses STAR dans le dossier {a['code']}."
        body = build_ics(interview_id, title, i["scheduled_at"], i.get("duration_min", 45), i.get("location", ""), desc)
        return Response(content=body, media_type="text/calendar; charset=utf-8",
                        headers={"Content-Disposition": f'attachment; filename="{a["code"]}_entrevue.ics"'})

    return router
