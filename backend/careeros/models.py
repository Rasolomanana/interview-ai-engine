"""Career-dossier entities linked to an application by its CareerOS code (CO-YYYY-NNNNNN).

Collections are created now so future agents (Calendar, Recruiter, Follow-Up, Plan du Jour,
Autopilot) plug in without migrations. Every document carries user_id + application_id +
application_code, plus created_at/updated_at and a `source` (member | agent:<name>)."""
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class InterviewIn(BaseModel):
    stage: Literal["rh", "gestionnaire", "technique", "panel", "final", "autre"] = "rh"
    scheduled_at: Optional[str] = None  # ISO datetime
    duration_min: int = 45
    mode: Literal["visio", "telephone", "presentiel"] = "visio"
    location: str = ""
    interviewers: List[str] = []
    outcome: Literal["a_venir", "reussie", "echouee", "annulee", "en_attente"] = "a_venir"
    notes: str = ""
    summary: str = ""
    strengths: List[str] = []
    weaknesses: List[str] = []
    next_actions: List[str] = []


class CalendarEventIn(BaseModel):
    title: str
    start: str
    end: Optional[str] = None
    provider: Literal["interne", "google", "outlook"] = "interne"
    external_id: str = ""
    interview_id: str = ""
    reminder_min: int = 60
    status: Literal["planifie", "synchronise", "annule"] = "planifie"


class RecruiterIn(BaseModel):
    name: str
    company: str = ""
    role: Literal["recruteur", "chasseur", "gestionnaire", "rh", "autre"] = "recruteur"
    email: str = ""
    phone: str = ""
    linkedin: str = ""
    notes: str = ""


class FollowupIn(BaseModel):
    kind: Literal["relance", "remerciement", "confirmation", "negociation", "autre"] = "relance"
    due_at: Optional[str] = None
    recruiter_id: str = ""
    status: Literal["a_faire", "fait", "annule"] = "a_faire"
    notes: str = ""


class EmailIn(BaseModel):
    kind: Literal["confirmation", "remerciement", "relance", "candidature", "autre"] = "autre"
    to: str = ""
    subject: str = ""
    body: str = ""
    status: Literal["brouillon", "pret", "envoye"] = "brouillon"
    recruiter_id: str = ""
    interview_id: str = ""


class EntityPatch(BaseModel):
    changes: dict = Field(default_factory=dict)


ENTITIES = {
    "interviews": InterviewIn,
    "calendar_events": CalendarEventIn,
    "recruiters": RecruiterIn,
    "followups": FollowupIn,
    "emails": EmailIn,
}
