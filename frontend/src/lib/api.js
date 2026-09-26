// Client-side data + generation layer. No backend: state machine runs locally,
// generation goes directly to Google Gemini, persistence uses chrome.storage/localStorage.
import * as store from "./storage";
import { resolve as resolveState } from "./stateMachine";
import { buildSystemMessage, buildTurnMessage } from "./promptClient";
import { streamGemini } from "./gemini";

const uid = () => (crypto?.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
const now = () => new Date().toISOString();

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

export async function getSettings() {
  return store.get("settings", { geminiKey: "", model: "gemini-2.5-flash" });
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

      if (!settings.geminiKey) {
        handlers.onError?.("Clé API Gemini manquante. Ouvrez Réglages pour la saisir (gratuit via Google AI Studio).");
        return;
      }

      const history = messages.map((m) => ({ role: roleLabel(m), content: m.content }));
      const systemMessage = buildSystemMessage(session.context);
      const turnMessage = buildTurnMessage(
        resolved, body.text, session.context, history,
        body.state_candidat, body.voice_confidence, session.debug, hasImage
      );

      // Persist user turn.
      const msgs = messages.slice();
      msgs.push({ id: uid(), role: "user", content: body.text || "(image)", mode: resolved.resolved_state, created_at: now() });

      let full = "";
      await streamGemini({
        apiKey: settings.geminiKey,
        model: settings.model || "gemini-2.5-flash",
        systemMessage,
        userText: turnMessage,
        imageDataUrl: body.image_base64,
        signal: controller.signal,
        onDelta: (c) => { full += c; handlers.onDelta?.(c); },
      });

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
