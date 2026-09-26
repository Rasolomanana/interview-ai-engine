// Client-side data + generation layer. No backend: state machine runs locally,
// generation goes directly to Google Gemini, persistence uses chrome.storage/localStorage.
import * as store from "./storage";
import { resolve as resolveState } from "./stateMachine";
import { buildSystemMessage, buildTurnMessage } from "./promptClient";
import { streamGemini } from "./gemini";
import { streamServer } from "./server";

const uid = () => (crypto?.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
const now = () => new Date().toISOString();
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export async function extractPdf(file) {
  const fd = new FormData();
  fd.append("file", file, file.name);
  const resp = await fetch(`${BACKEND_URL}/api/extract-pdf`, { method: "POST", body: fd });
  if (!resp.ok) {
    let d = "";
    try { d = (await resp.json())?.detail || ""; } catch (e) { /* ignore */ }
    throw new Error(d || `Erreur ${resp.status}`);
  }
  return (await resp.json()).text;
}

export async function transcribeBlob(blob) {
  const fd = new FormData();
  fd.append("file", blob, "audio.webm");
  fd.append("language", "fr");
  const resp = await fetch(`${BACKEND_URL}/api/transcribe`, { method: "POST", body: fd });
  if (!resp.ok) throw new Error(`Transcription ${resp.status}`);
  return (await resp.json()).text || "";
}

// Provider-agnostic one-shot streamed generation (used for the recap).
export async function streamRaw({ systemMessage, userText, onDelta, signal }) {
  const settings = await getSettings();
  if (settings.provider === "server") {
    await streamServer({ systemMessage, userText, signal, onDelta });
  } else {
    if (!settings.geminiKey) throw new Error("Clé Gemini manquante (ou choisissez le mode Serveur).");
    await streamGemini({ apiKey: settings.geminiKey, model: settings.model || "gemini-3.8-flash", systemMessage, userText, signal, onDelta });
  }
}

const loadSessions = () => store.get("sessions", []);
const saveSessions = (l) => store.set("sessions", l);

export async function listSessions() {
  const l = await loadSessions();
  return [...l].sort((a, b) => (b.updated_at || "").localeCompare(a.updated_at || ""));
}

export async function createSession(payload = {}) {
  const s = {
    id: uid(),
    title: payload.title || "Nouvelle session",
    context: payload.context || { cv: "", poste: "", entreprise: "", secteur: "Autre" },
    debug: !!payload.debug,
    state: "NEUTRE", prev_state: "NEUTRE",
    tours_sans_marqueur: 0, incomprehension: 0,
    created_at: now(), updated_at: now(),
  };
  const l = await loadSessions();
  l.push(s);
  await saveSessions(l);
  await store.set("messages:" + s.id, []);
  return s;
}

export async function getSession(id) {
  const l = await loadSessions();
  const session = l.find((x) => x.id === id) || null;
  const messages = await store.get("messages:" + id, []);
  return { session, messages };
}

export async function updateSession(id, payload = {}) {
  const l = await loadSessions();
  const s = l.find((x) => x.id === id);
  if (!s) return null;
  if (payload.title != null) s.title = payload.title;
  if (payload.context != null) s.context = payload.context;
  if (payload.debug != null) s.debug = payload.debug;
  s.updated_at = now();
  await saveSessions(l);
  return s;
}

export async function deleteSession(id) {
  let l = await loadSessions();
  l = l.filter((x) => x.id !== id);
  await saveSessions(l);
  await store.del("messages:" + id);
  return { ok: true };
}

export async function resetSession(id) {
  const l = await loadSessions();
  const s = l.find((x) => x.id === id);
  if (s) {
    s.state = "NEUTRE"; s.prev_state = "NEUTRE";
    s.tours_sans_marqueur = 0; s.incomprehension = 0; s.updated_at = now();
    await saveSessions(l);
  }
  return { ok: true, state: "NEUTRE" };
}

const ALLOWED_MODELS = [
  "gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash",
  "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.1-pro-preview",
];

export async function getSettings() {
  const s = await store.get("settings", { geminiKey: "", model: "gemini-3.8-flash", provider: "gemini", answerStyle: "complet", tone: "confiant" });
  if (!s.provider) s.provider = "gemini";
  if (!s.answerStyle) s.answerStyle = "complet";
  if (!s.tone) s.tone = "confiant";
  if (!s.model || !ALLOWED_MODELS.includes(s.model)) {
    s.model = "gemini-3.8-flash";
    await store.set("settings", s);
  }
  return s;
}
export async function saveSettings(s) {
  await store.set("settings", s);
  return s;
}

function roleLabel(m) {
  if (m.role !== "assistant") return "Utilisateur";
  if (m.mode === "RECRUTEUR") return "Recruteur";
  if (m.mode === "CANDIDAT") return "Copilote";
  return "Assistant";
}

// Streams a turn. Mirrors the previous SSE contract: onMeta/onDelta/onDone/onError/onAbort.
export function streamMessage(sessionId, body, handlers) {
  const controller = new AbortController();
  (async () => {
    try {
      const { session, messages } = await getSession(sessionId);
      if (!session) { handlers.onError?.("Session introuvable"); return; }
      const settings = await getSettings();
      const hasImage = !!body.image_base64;

      const resolved = resolveState({
        current_state: session.state,
        prev_state: session.prev_state,
        text: body.text,
        tours_in: session.tours_sans_marqueur,
        voice_confidence: body.voice_confidence,
        state_candidat: body.state_candidat,
        barge_in: !!body.barge_in,
        has_image: hasImage,
        incomprehension_in: session.incomprehension,
      });
      handlers.onMeta?.(resolved);

      if ((resolved.modules || [])[0] === "BARGE_IN") { handlers.onDone?.(""); return; }

      const useServer = settings.provider === "server";
      if (!useServer && !settings.geminiKey) {
        handlers.onError?.("Clé API Gemini manquante. Ouvrez Réglages (ou choisissez le mode Serveur).");
        return;
      }

      const history = messages.map((m) => ({ role: roleLabel(m), content: m.content }));
      const systemMessage = buildSystemMessage(session.context);
      const turnMessage = buildTurnMessage(
        resolved, body.text, session.context, history,
        body.state_candidat, body.voice_confidence, session.debug, hasImage, settings.answerStyle, settings.tone
      );

      // Persist user turn.
      const msgs = messages.slice();
      msgs.push({ id: uid(), role: "user", content: body.text || "(image)", mode: resolved.resolved_state, created_at: now() });

      let full = "";
      const onDelta = (c) => { full += c; handlers.onDelta?.(c); };
      if (useServer) {
        await streamServer({ systemMessage, userText: turnMessage, imageDataUrl: body.image_base64, signal: controller.signal, onDelta });
      } else {
        await streamGemini({
          apiKey: settings.geminiKey,
          model: settings.model || "gemini-3.8-flash",
          systemMessage, userText: turnMessage,
          imageDataUrl: body.image_base64, signal: controller.signal, onDelta,
        });
      }

      msgs.push({ id: uid(), role: "assistant", content: full, mode: resolved.resolved_state, modules: resolved.modules, created_at: now() });
      await store.set("messages:" + sessionId, msgs);

      const l = await loadSessions();
      const s = l.find((x) => x.id === sessionId);
      if (s) {
        s.prev_state = s.state;
        s.state = resolved.resolved_state;
        s.tours_sans_marqueur = resolved.tours;
        s.updated_at = now();
        await saveSessions(l);
      }
      handlers.onDone?.(full);
    } catch (e) {
      if (e.name === "AbortError") handlers.onAbort?.();
      else handlers.onError?.(e.message);
    }
  })();
  return controller;
}
