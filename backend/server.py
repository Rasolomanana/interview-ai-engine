import os
import io
import base64
import logging
import uuid
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
from pydantic import BaseModel, Field, ConfigDict

from emergentintegrations.llm.chat import LlmChat, UserMessage, ImageContent, TextDelta, StreamDone
from emergentintegrations.llm.openai import OpenAISpeechToText

import state_machine as sm
import prompt as P

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / ".env")

mongo_url = os.environ["MONGO_URL"]
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ["DB_NAME"]]

EMERGENT_LLM_KEY = os.environ.get("EMERGENT_LLM_KEY")
DEEPSEEK_API_KEY = os.environ.get("DEEPSEEK_API_KEY")
LLM_MODEL = ("anthropic", "claude-sonnet-4-6")
# Server-side fallback chain: free/Emergent first, user's paid DeepSeek key strictly last.
SERVER_CHAIN = [("anthropic", "claude-sonnet-4-6"), ("openai", "gpt-5.4")]

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

app = FastAPI()
api_router = APIRouter(prefix="/api")


# ----------------------------- Models -----------------------------
class SessionContext(BaseModel):
    cv: str = ""
    poste: str = ""
    entreprise: str = ""
    secteur: str = "Autre"


class SessionCreate(BaseModel):
    title: str = "Nouvelle session"
    context: SessionContext = Field(default_factory=SessionContext)
    debug: bool = False


class ContextUpdate(BaseModel):
    title: Optional[str] = None
    context: Optional[SessionContext] = None
    debug: Optional[bool] = None


class Session(BaseModel):
    model_config = ConfigDict(extra="ignore")
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str = "Nouvelle session"
    context: SessionContext = Field(default_factory=SessionContext)
    debug: bool = False
    state: str = sm.NEUTRE
    prev_state: str = sm.NEUTRE
    tours_sans_marqueur: int = 0
    incomprehension: int = 0
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class Message(BaseModel):
    role: str  # "user" | "assistant"
    content: str
    mode: str = sm.NEUTRE
    modules: List[str] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class TurnRequest(BaseModel):
    text: str = ""
    state_candidat: Optional[str] = "NORMAL"
    voice_confidence: Optional[float] = 0.0
    image_base64: Optional[str] = None  # data URL or raw b64
    barge_in: bool = False


class ResolveRequest(BaseModel):
    current_state: str = sm.NEUTRE
    prev_state: str = sm.NEUTRE
    text: str = ""
    tours_sans_marqueur: int = 0
    voice_confidence: Optional[float] = None
    state_candidat: Optional[str] = None
    barge_in: bool = False
    has_image: bool = False


class GenerateRequest(BaseModel):
    system_message: str
    turn_message: str
    image_base64: Optional[str] = None


class CompanyAnalyzeRequest(BaseModel):
    url: str
    poste: str = ""
    cv: str = ""


class ApplicationAnalyzeRequest(BaseModel):
    cv: str = ""
    poste: str = ""
    url: str = ""


# ----------------------------- Helpers -----------------------------
async def _get_session(session_id: str) -> dict:
    doc = await db.sessions.find_one({"id": session_id}, {"_id": 0})
    if not doc:
        raise HTTPException(status_code=404, detail="Session introuvable")
    return doc


def _strip_data_url(b64: str) -> str:
    if b64 and b64.startswith("data:"):
        return b64.split(",", 1)[1]
    return b64


# ----------------------------- Routes -----------------------------
@api_router.get("/")
async def root():
    return {"message": "Interview AI Engine v4"}


@api_router.post("/sessions", response_model=Session)
async def create_session(payload: SessionCreate):
    s = Session(title=payload.title, context=payload.context, debug=payload.debug)
    await db.sessions.insert_one(s.model_dump())
    return s


@api_router.get("/sessions", response_model=List[Session])
async def list_sessions():
    docs = await db.sessions.find({}, {"_id": 0}).sort("updated_at", -1).to_list(200)
    return docs


@api_router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    s = await _get_session(session_id)
    msgs = await db.messages.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    return {"session": s, "messages": msgs}


@api_router.put("/sessions/{session_id}", response_model=Session)
async def update_session(session_id: str, payload: ContextUpdate):
    s = await _get_session(session_id)
    update = {}
    if payload.title is not None:
        update["title"] = payload.title
    if payload.context is not None:
        update["context"] = payload.context.model_dump()
    if payload.debug is not None:
        update["debug"] = payload.debug
    update["updated_at"] = datetime.now(timezone.utc).isoformat()
    await db.sessions.update_one({"id": session_id}, {"$set": update})
    s.update(update)
    return s


@api_router.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    await db.sessions.delete_one({"id": session_id})
    await db.messages.delete_many({"session_id": session_id})
    return {"ok": True}


@api_router.post("/sessions/{session_id}/reset")
async def reset_session(session_id: str):
    await _get_session(session_id)
    await db.sessions.update_one(
        {"id": session_id},
        {"$set": {
            "state": sm.NEUTRE, "prev_state": sm.NEUTRE,
            "tours_sans_marqueur": 0, "incomprehension": 0,
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }},
    )
    return {"ok": True, "state": sm.NEUTRE}


@api_router.post("/state/resolve")
async def resolve_state(req: ResolveRequest):
    """Pure deterministic resolution — used by the non-regression tests."""
    return sm.resolve(
        current_state=req.current_state,
        prev_state=req.prev_state,
        text=req.text,
        tours_in=req.tours_sans_marqueur,
        voice_confidence=req.voice_confidence,
        state_candidat=req.state_candidat,
        barge_in=req.barge_in,
        has_image=req.has_image,
    )


@api_router.post("/extract-pdf")
async def extract_pdf(file: UploadFile = File(...)):
    """Extract text from an uploaded CV PDF so the candidate profile can be filled directly."""
    from pypdf import PdfReader
    data = await file.read()
    try:
        reader = PdfReader(io.BytesIO(data))
        text = "\n".join((p.extract_text() or "") for p in reader.pages).strip()
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"PDF illisible: {e}")
    if not text:
        raise HTTPException(status_code=422, detail="Aucun texte extrait (PDF scanné/image ?). Copiez le texte manuellement.")
    return {"text": text[:20000]}


@api_router.post("/generate")
async def generate(req: GenerateRequest):
    """Stateless generation proxy — used by the client 'Serveur' provider so the
    browser never contacts an external LLM directly (works even where Google/OpenAI
    are blocked by an IT policy). Multi-provider fallback chain, DeepSeek last resort."""
    if not EMERGENT_LLM_KEY and not DEEPSEEK_API_KEY:
        raise HTTPException(status_code=500, detail="Aucun fournisseur LLM configuré")

    return StreamingResponse(
        _stream_with_fallback(req.system_message, req.turn_message, req.image_base64),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


async def _stream_with_fallback(system_message: str, turn_message: str, image_base64: Optional[str]):
    """Try Emergent providers (Claude, then OpenAI) first — free/managed — and only
    fall back to the user's paid DeepSeek key as a last resort. Only advance to the
    next provider if NOTHING has been streamed yet (avoids duplicated output)."""
    emitted = False
    errors = []
    if EMERGENT_LLM_KEY:
        for provider, model in SERVER_CHAIN:
            try:
                chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()), system_message=system_message).with_model(provider, model)
                fc = [ImageContent(image_base64=_strip_data_url(image_base64))] if image_base64 else None
                um = UserMessage(text=turn_message, file_contents=fc) if fc else UserMessage(text=turn_message)
                async for ev in chat.stream_message(um):
                    if isinstance(ev, TextDelta):
                        emitted = True
                        yield _sse("delta", {"content": ev.content})
                    elif isinstance(ev, StreamDone):
                        break
                if emitted:
                    yield _sse("done", {})
                    return
            except Exception as e:  # noqa: BLE001
                errors.append(f"{provider}: {str(e)[:160]}")
                logger.warning("Provider %s failed, trying next: %s", provider, e)
                if emitted:
                    yield _sse("done", {})
                    return

    # Last resort: DeepSeek (OpenAI-compatible), user's own key.
    if DEEPSEEK_API_KEY and not emitted:
        try:
            from openai import AsyncOpenAI
            ds = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            stream = await ds.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": system_message}, {"role": "user", "content": turn_message}],
                stream=True,
            )
            async for chunk in stream:
                delta = (chunk.choices[0].delta.content or "") if chunk.choices else ""
                if delta:
                    emitted = True
                    yield _sse("delta", {"content": delta})
            if emitted:
                yield _sse("done", {})
                return
        except Exception as e:  # noqa: BLE001
            errors.append(f"deepseek: {str(e)[:160]}")
            logger.exception("DeepSeek fallback failed")

    if not emitted:
        yield _sse("error", {"detail": "Tous les fournisseurs ont échoué. " + " | ".join(errors[-3:])})
    yield _sse("done", {})


async def _generate_text(system_message: str, user_text: str) -> str:
    """Non-streaming aggregate generation with the same fallback chain."""
    if EMERGENT_LLM_KEY:
        for provider, model in SERVER_CHAIN:
            try:
                chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()), system_message=system_message).with_model(provider, model)
                out = []
                async for ev in chat.stream_message(UserMessage(text=user_text)):
                    if isinstance(ev, TextDelta):
                        out.append(ev.content)
                    elif isinstance(ev, StreamDone):
                        break
                if out:
                    return "".join(out)
            except Exception as e:  # noqa: BLE001
                logger.warning("analyze provider %s failed: %s", provider, e)
    if DEEPSEEK_API_KEY:
        try:
            from openai import AsyncOpenAI
            ds = AsyncOpenAI(api_key=DEEPSEEK_API_KEY, base_url="https://api.deepseek.com")
            r = await ds.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "system", "content": system_message}, {"role": "user", "content": user_text}],
                stream=False,
            )
            return r.choices[0].message.content or ""
        except Exception as e:  # noqa: BLE001
            logger.exception("deepseek analyze failed")
    raise HTTPException(status_code=502, detail="Analyse indisponible (fournisseurs LLM)")


async def _fetch_page_text(url: str) -> str:
    import httpx
    from bs4 import BeautifulSoup
    import re as _re
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    async with httpx.AsyncClient(follow_redirects=True, timeout=25, headers={"User-Agent": ua}) as hc:
        r = await hc.get(url)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for t in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
            t.decompose()
        return _re.sub(r"\s+", " ", soup.get_text(" ")).strip()[:9000]


@api_router.post("/analyze-application")
async def analyze_application(req: ApplicationAnalyzeRequest):
    """Full recruiter-grade analysis: ATS-optimized CV + fit score + gaps +
    missing keywords + red flags + company briefing. Returns structured JSON."""
    site_text = ""
    if req.url.strip():
        try:
            site_text = await _fetch_page_text(req.url.strip())
        except Exception as e:  # noqa: BLE001
            logger.warning("site fetch failed: %s", e)

    system_message = (
        "Tu es un recruteur senior et un expert des systèmes ATS (Applicant Tracking System). "
        "Tu réécris des CV pour maximiser le score ATS et l'attractivité, et tu évalues objectivement "
        "l'adéquation candidat/poste. Tu réponds STRICTEMENT en JSON valide, en français."
    )
    user_text = (
        f"CV DU CANDIDAT :\n{req.cv[:6000]}\n\n"
        f"OFFRE / POSTE :\n{req.poste[:4000]}\n\n"
        f"CONTENU DU SITE ENTREPRISE (peut être vide) :\n{site_text}\n\n"
        "Analyse et renvoie UNIQUEMENT un objet JSON (aucun texte hors JSON, pas de balises markdown) avec EXACTEMENT ces clés :\n"
        "{\n"
        '  "ats_cv": "CV RÉÉCRIT optimisé ATS, en texte markdown, tel qu\'un recruteur senior de cette entreprise voudrait le lire : sections claires (Résumé, Expériences, Compétences), verbes d\'action, et des RÉALISATIONS CHIFFRÉES (%, montants, volumes, délais) — invente des ordres de grandeur plausibles à partir du CV et marque-les [à confirmer] pour que le candidat puisse les rectifier. Intègre naturellement les mots-clés de l\'offre.",\n'
        '  "score": 0-100 (entier : compatibilité globale CV vs offre),\n'
        '  "gaps": ["lacune 1", "lacune 2", ...] (écarts concrets entre le CV et les exigences du poste),\n'
        '  "missing_keywords": ["mot1","mot2","mot3","mot4","mot5"] (EXACTEMENT 5 mots-clés importants de l\'offre absents du CV),\n'
        '  "red_flags": ["signal 1", "signal 2", ...] (ce qu\'un recruteur remarquerait immédiatement : trous, incohérences, formulations faibles),\n'
        '  "company": "bref récap markdown : VALEURS & CULTURE + 5-6 QUESTIONS D\'ENTRETIEN PROBABLES liées à ces valeurs"\n'
        "}\n"
        "Le JSON doit être parsable directement."
    )
    raw = (await _generate_text(system_message, user_text)).strip()
    # Strip accidental markdown fences.
    if raw.startswith("```"):
        raw = raw.strip("`")
        if raw[:4].lower() == "json":
            raw = raw[4:]
    import json as _json
    import re as _re
    try:
        data = _json.loads(raw)
    except Exception:
        m = _re.search(r"\{.*\}", raw, _re.DOTALL)
        if not m:
            raise HTTPException(status_code=502, detail="Réponse d'analyse illisible")
        data = _json.loads(m.group(0))
    return {
        "ats_cv": str(data.get("ats_cv", "")),
        "score": int(data.get("score", 0)) if str(data.get("score", "")).strip().isdigit() else data.get("score", 0),
        "gaps": data.get("gaps", []),
        "missing_keywords": data.get("missing_keywords", []),
        "red_flags": data.get("red_flags", []),
        "company": str(data.get("company", "")),
    }


@api_router.post("/analyze-company")
async def analyze_company(req: CompanyAnalyzeRequest):
    """Fetch a company / careers page, extract its text and use the LLM to produce
    a briefing: values, culture, and the interview questions those values imply."""
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY manquant")
    import httpx
    from bs4 import BeautifulSoup
    import re as _re

    url = req.url.strip()
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    try:
        async with httpx.AsyncClient(follow_redirects=True, timeout=25, headers={"User-Agent": ua}) as hc:
            r = await hc.get(url)
            r.raise_for_status()
            html = r.text
    except Exception as e:  # noqa: BLE001
        raise HTTPException(status_code=400, detail=f"Impossible de charger la page: {e}")

    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.string if soup.title else "") or ""
    for t in soup(["script", "style", "noscript", "svg", "header", "footer", "nav"]):
        t.decompose()
    text = _re.sub(r"\s+", " ", soup.get_text(" ")).strip()[:12000]
    if len(text) < 120:
        raise HTTPException(status_code=422, detail="Page trop pauvre en texte (site dynamique ?). Collez le contenu manuellement.")

    poste_line = f"Poste visé par le candidat : {req.poste}\n" if req.poste else ""
    cv_block = f"\nPROFIL / CV DU CANDIDAT (utilise-le pour personnaliser les réponses STAR) :\n{req.cv[:4000]}\n" if req.cv.strip() else ""
    system_message = (
        "Tu es un expert senior en recrutement et coach d'entretien. À partir du contenu d'une page "
        "carrière/entreprise, tu prépares une fiche actionnable en français : tu identifies les valeurs, "
        "puis tu rédiges des réponses d'entretien prêtes à dire, avec la méthode STAR, ancrées dans ces valeurs."
    )
    user_text = (
        f"URL analysée : {url}\nTitre de la page : {title}\n{poste_line}{cv_block}\n"
        f"CONTENU EXTRAIT DU SITE :\n{text}\n\n"
        "Produis une fiche STRUCTURÉE en français, concise, avec EXACTEMENT ces sections :\n\n"
        "## VALEURS & CULTURE\n(5-7 puces : valeurs et culture de l'entreprise — ex. sécurité, innovation, collaboration…)\n\n"
        "## MISSION & PRIORITÉS\n(3-5 puces : mission, priorités, ce qui compte pour eux)\n\n"
        "## QUESTIONS D'ENTRETIEN PROBABLES\n(6 à 8 questions que le recruteur pourrait poser, ancrées dans ces valeurs, "
        "comportementales et sur les valeurs" + (", adaptées au poste visé" if req.poste else "") + ")\n\n"
        "## RÉPONSES STAR PRÊTES\n"
        "Pour les 4 questions les plus probables ci-dessus, rédige une réponse COMPLÈTE prête à dire, "
        "structurée avec la méthode STAR (puces préfixées **Situation :**, **Tâche :**, **Action :**, **Résultat :** "
        "avec un impact chiffré ou concret). CHAQUE réponse doit démontrer que le candidat a fait des recherches "
        "sur l'entreprise : relie-la EXPLICITEMENT à une valeur/mission de l'entreprise (sécurité, innovation, "
        "collaboration, etc.). "
        + ("Ancre chaque réponse dans le CV réel du candidat fourni ci-dessus (expériences, chiffres). "
           if req.cv.strip() else "Utilise des exemples génériques mais crédibles pour le poste. ")
        + "Format : « **Q1 : <la question>** » puis les 4 puces STAR.\n\n"
        "Base-toi sur le contenu extrait ; complète prudemment avec ta connaissance de l'entreprise sans inventer de faits chiffrés précis."
    )

    async def gen():
        try:
            chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=str(uuid.uuid4()), system_message=system_message).with_model(*LLM_MODEL)
            async for ev in chat.stream_message(UserMessage(text=user_text)):
                if isinstance(ev, TextDelta):
                    yield _sse("delta", {"content": ev.content})
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:  # noqa: BLE001
            logger.exception("analyze-company failed")
            yield _sse("error", {"detail": str(e)})
        yield _sse("done", {})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@api_router.post("/transcribe")
async def transcribe(file: UploadFile = File(...), language: str = Form("fr")):
    if not EMERGENT_LLM_KEY:
        raise HTTPException(status_code=500, detail="EMERGENT_LLM_KEY manquant")
    data = await file.read()
    buf = io.BytesIO(data)
    buf.name = file.filename or "audio.webm"
    stt = OpenAISpeechToText(api_key=EMERGENT_LLM_KEY)
    try:
        resp = await stt.transcribe(file=buf, model="whisper-1", response_format="json", language=language)
        return {"text": resp.text}
    except Exception as e:  # noqa: BLE001
        logger.exception("Whisper failed")
        raise HTTPException(status_code=502, detail=f"Transcription échouée: {e}")


@api_router.post("/sessions/{session_id}/message")
async def send_message(session_id: str, req: TurnRequest):
    s = await _get_session(session_id)
    has_image = bool(req.image_base64)

    resolved = sm.resolve(
        current_state=s["state"],
        prev_state=s["prev_state"],
        text=req.text,
        tours_in=s.get("tours_sans_marqueur", 0),
        voice_confidence=req.voice_confidence,
        state_candidat=req.state_candidat,
        barge_in=req.barge_in,
        has_image=has_image,
        incomprehension_in=s.get("incomprehension", 0),
    )

    # Barge-in: no generation, state untouched.
    if resolved.get("no_content") and resolved.get("modules") == ["BARGE_IN"]:
        async def _empty():
            yield _sse("meta", resolved)
            yield _sse("done", {"content": ""})
        return StreamingResponse(_empty(), media_type="text/event-stream",
                                 headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})

    history = await db.messages.find({"session_id": session_id}, {"_id": 0}).sort("created_at", 1).to_list(1000)
    hist_for_prompt = [{"role": ("Recruteur" if m["mode"] == sm.RECRUTEUR else ("Copilote" if m["mode"] == sm.CANDIDAT else "Assistant")) if m["role"] == "assistant" else "Utilisateur", "content": m["content"]} for m in history]

    system_message = P.build_system_message(s["context"])
    turn_message = P.build_turn_message(
        resolved, req.text, s["context"], hist_for_prompt,
        req.state_candidat, req.voice_confidence, s.get("debug", False), has_image,
    )

    # Persist the user turn.
    user_msg = Message(role="user", content=req.text or "(image)", mode=resolved["resolved_state"])
    await db.messages.insert_one({**user_msg.model_dump(), "session_id": session_id})

    async def event_generator():
        yield _sse("meta", resolved)
        full = ""
        try:
            chat = LlmChat(api_key=EMERGENT_LLM_KEY, session_id=session_id, system_message=system_message).with_model(*LLM_MODEL)
            file_contents = None
            if has_image:
                file_contents = [ImageContent(image_base64=_strip_data_url(req.image_base64))]
            um = UserMessage(text=turn_message, file_contents=file_contents) if file_contents else UserMessage(text=turn_message)
            async for ev in chat.stream_message(um):
                if isinstance(ev, TextDelta):
                    full += ev.content
                    yield _sse("delta", {"content": ev.content})
                elif isinstance(ev, StreamDone):
                    break
        except Exception as e:  # noqa: BLE001
            logger.exception("LLM stream failed")
            yield _sse("error", {"detail": str(e)})

        # Persist assistant turn + new state.
        assistant_msg = Message(role="assistant", content=full, mode=resolved["resolved_state"], modules=resolved.get("modules", []))
        await db.messages.insert_one({**assistant_msg.model_dump(), "session_id": session_id})
        await db.sessions.update_one(
            {"id": session_id},
            {"$set": {
                "state": resolved["resolved_state"],
                "prev_state": s["state"],
                "tours_sans_marqueur": resolved["tours"],
                "incomprehension": resolved.get("incomprehension", 0),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }},
        )
        yield _sse("done", {"content": full})

    return StreamingResponse(event_generator(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(event: str, data: dict) -> str:
    import json
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


app.include_router(api_router)
app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get("CORS_ORIGINS", "*").split(","),
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()
