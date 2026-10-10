// Client-side data + generation layer. No backend: state machine runs locally,
// generation goes directly to Google Gemini, persistence uses chrome.storage/localStorage.
import * as store from "./storage";
import { resolve as resolveState } from "./stateMachine";
import { buildSystemMessage, buildTurnMessage } from "./promptClient";
import { streamGemini } from "./gemini";
import { streamServer } from "./server";
import { estimateTurnCost } from "./costEstimate";

// Anonymous analytics ping (best-effort, never blocks the UI). Covers Gemini AND
// Server modes because it is fired from the client.
export function trackEvent(type, sessionId, meta) {
  try {
    fetch(`${process.env.REACT_APP_BACKEND_URL}/api/track`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ type, session_id: sessionId || "", meta: meta || {} }),
      keepalive: true,
    }).catch(() => {});
  } catch { /* ignore */ }
}

const ADMIN_BASE = () => `${process.env.REACT_APP_BACKEND_URL}/api/admin`;

export async function adminLogin(password) {
  const r = await fetch(`${ADMIN_BASE()}/login`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ password }),
  });
  if (!r.ok) {
    let d = ""; try { d = (await r.json())?.detail || ""; } catch { /* ignore */ }
    throw new Error(d || `Erreur ${r.status}`);
  }
  return r.json();
}

export async function adminStats(password) {
  const r = await fetch(`${ADMIN_BASE()}/stats`, { headers: { "X-Admin-Password": password } });
  if (!r.ok) {
    let d = ""; try { d = (await r.json())?.detail || ""; } catch { /* ignore */ }
    throw new Error(d || `Erreur ${r.status}`);
  }
  return r.json();
}

export async function adminExport(password, fmt) {
  const r = await fetch(`${ADMIN_BASE()}/export?fmt=${fmt}`, { headers: { "X-Admin-Password": password } });
  if (!r.ok) throw new Error(`Export échoué (${r.status})`);
  const blob = await r.blob();
  const a = document.createElement("a");
  a.href = URL.createObjectURL(blob);
  a.download = fmt === "xlsx" ? "analyses_ats.xlsx" : "analyses_ats.csv";
  document.body.appendChild(a); a.click(); a.remove();
  URL.revokeObjectURL(a.href);
}

const uid = () => (crypto?.randomUUID ? crypto.randomUUID() : String(Date.now()) + Math.random());
const now = () => new Date().toISOString();
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

// Once Gemini has failed/hung in this browsing session, stop trying it and go
// straight to the reliable Server provider — so a live interview never eats a
// repeated 9s timeout on every turn.
let geminiUnavailable = false;

// A direct browser->Google call can fail at the NETWORK/TLS layer (corporate SSL
// inspection, antivirus/VPN interception, blocked domain, wrong system clock).
// fetch() then rejects with `TypeError: Failed to fetch`, and Chrome logs
// net::ERR_SSL_VERSION_OR_CIPHER_MISMATCH / ERR_CONNECTION_* to the console.
// None of these are user barge-ins, so we must fall back to the Server provider.
function isNetworkError(err) {
  if (!err || err.name === "AbortError") return false;
  const msg = String(err.message || err).toLowerCase();
  return (
    err.name === "TypeError" ||
    msg.includes("failed to fetch") ||
    msg.includes("networkerror") ||
    msg.includes("ssl") ||
    msg.includes("err_") ||
    msg.includes("cipher") ||
    msg.includes("cert")
  );
}
// Any non-abort Gemini failure (network/SSL, 429/503, 9s watchdog) should route
// the rest of the session to the Server provider.
const shouldFallback = (err, emitted) => !emitted && err && err.name !== "AbortError";
const fallbackReason = (err) =>
  isNetworkError(err)
    ? "Accès à Google bloqué (réseau/SSL) — bascule automatique sur le mode Serveur"
    : String(err?.message || "Gemini indisponible — bascule serveur");

// Flips the session to Server mode, logs a visible console trace, and exposes an
// inspectable flag on window so you can verify the fallback fired from DevTools.
function activateServerFallback(err) {
  geminiUnavailable = true;
  const reason = fallbackReason(err);
  const kind = isNetworkError(err) ? "NETWORK/SSL" : "API";
  console.warn(
    `[Gemini→Serveur] Fallback activé (${kind}). geminiUnavailable=true. Raison:`,
    reason,
    "| Erreur d'origine:",
    err?.name, err?.message
  );
  if (typeof window !== "undefined") window.__geminiUnavailable = true;
  return reason;
}

import * as pdfjsLib from "pdfjs-dist";

pdfjsLib.GlobalWorkerOptions.workerSrc = `${process.env.PUBLIC_URL || ""}/pdf.worker.min.js`;

// Extract PDF text IN THE BROWSER (no upload) — robust on mobile/Android where
// large multipart uploads can be dropped by the proxy. Falls back to the server.
export async function extractPdf(file) {
  try {
    const buf = await file.arrayBuffer();
    const pdf = await pdfjsLib.getDocument({ data: buf }).promise;
    let out = "";
    for (let i = 1; i <= pdf.numPages; i++) {
      const page = await pdf.getPage(i);
      const tc = await page.getTextContent();
      out += tc.items.map((it) => it.str).join(" ") + "\n";
    }
    out = out.trim();
    if (out) return out.slice(0, 20000);
    // No text layer (scanned/photo PDF) — try the server as a second chance.
  } catch (e) {
    // Client parsing failed — fall back to the server extractor below.
  }
  return extractPdfServer(file);
}

async function extractPdfServer(file) {
  const fd = new FormData();
  fd.append("file", file, file.name || "cv.pdf");
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
  const t = blob.type || "audio/webm";
  const ext = t.includes("ogg") ? "ogg" : t.includes("mp4") ? "mp4" : t.includes("wav") ? "wav" : "webm";
  fd.append("file", blob, `audio.${ext}`);
  fd.append("language", "auto");
  const resp = await fetch(`${BACKEND_URL}/api/transcribe`, { method: "POST", body: fd });
  if (!resp.ok) throw new Error(`Transcription ${resp.status}`);
  return (await resp.json()).text || "";
}

// Full recruiter-grade analysis: ATS CV + score + gaps + missing keywords + red flags + company.
// Job + polling: start a background job, then poll (short requests) until done.
// This never holds a long connection open, so corporate proxies / gateways
// cannot truncate it (fixes the recurring "Analyse incomplète").
export async function analyzeApplication({ cv, poste, url, consent, sessionId, onProgress, signal }) {
  const start = await fetch(`${BACKEND_URL}/api/analyze-application`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cv: cv || "", poste: poste || "", url: url || "", consent: !!consent, session_id: sessionId || "" }),
    signal,
  });
  if (!start.ok) {
    let d = "";
    try { d = (await start.json())?.detail || ""; } catch (e) { /* ignore */ }
    throw new Error(d || `Erreur ${start.status}`);
  }
  const { job_id } = await start.json();
  if (!job_id) throw new Error("Impossible de démarrer l'analyse");

  const deadline = Date.now() + 180000; // up to 3 min
  while (Date.now() < deadline) {
    if (signal?.aborted) throw new Error("Analyse annulée");
    await new Promise((r) => setTimeout(r, 2000));
    onProgress?.();
    let poll;
    try {
      poll = await fetch(`${BACKEND_URL}/api/analyze-application/${job_id}`, { signal });
    } catch (e) {
      if (signal?.aborted) throw new Error("Analyse annulée");
      continue; // transient network blip — keep polling
    }
    if (!poll.ok) continue;
    const p = await poll.json();
    if (p.status === "done") return p.result;
    if (p.status === "error") throw new Error(p.error || "Analyse échouée");
  }
  throw new Error("Analyse expirée (délai dépassé)");
}

// Generate a one-page cover letter tailored to the job offer + (ATS) CV.
// Same job + polling model as analyzeApplication (immune to proxy timeouts).
export async function generateCoverLetter({ cv, poste, entreprise, sessionId, onProgress, signal }) {
  const start = await fetch(`${BACKEND_URL}/api/cover-letter`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ cv: cv || "", poste: poste || "", entreprise: entreprise || "", session_id: sessionId || "" }),
    signal,
  });
  if (!start.ok) {
    let d = "";
    try { d = (await start.json())?.detail || ""; } catch (e) { /* ignore */ }
    throw new Error(d || `Erreur ${start.status}`);
  }
  const { job_id } = await start.json();
  if (!job_id) throw new Error("Impossible de démarrer la génération");
  const deadline = Date.now() + 180000;
  while (Date.now() < deadline) {
    if (signal?.aborted) throw new Error("Génération annulée");
    await new Promise((r) => setTimeout(r, 2000));
    onProgress?.();
    let poll;
    try {
      poll = await fetch(`${BACKEND_URL}/api/analyze-application/${job_id}`, { signal });
    } catch (e) {
      if (signal?.aborted) throw new Error("Génération annulée");
      continue;
    }
    if (!poll.ok) continue;
    const p = await poll.json();
    if (p.status === "done") return p.result?.letter || "";
    if (p.status === "error") throw new Error(p.error || "Génération échouée");
  }
  throw new Error("Génération expirée (délai dépassé)");
}

// Analyze a company / careers URL -> streamed briefing (values, culture, likely questions).
export async function analyzeCompany({ url, poste, cv, onDelta, signal }) {
  const resp = await fetch(`${BACKEND_URL}/api/analyze-company`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ url, poste: poste || "", cv: cv || "" }),
    signal,
  });
  if (!resp.ok) {
    let d = "";
    try { d = (await resp.json())?.detail || ""; } catch (e) { /* ignore */ }
    throw new Error(d || `Erreur ${resp.status}`);
  }
  const reader = resp.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  while (true) {
    const { done, value } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    const events = buf.split("\n\n");
    buf = events.pop();
    for (const chunk of events) {
      let ev = "message"; let data = "";
      for (const l of chunk.split("\n")) {
        if (l.startsWith("event:")) ev = l.slice(6).trim();
        else if (l.startsWith("data:")) data += l.slice(5).trim();
      }
      if (!data) continue;
      const p = JSON.parse(data);
      if (ev === "delta") onDelta(p.content);
      else if (ev === "error") throw new Error(p.detail || "Erreur serveur");
    }
  }
}

// Provider-agnostic one-shot streamed generation (used for the recap).
// Mirrors streamMessage's resilience: if the direct Gemini call fails before any
// content is streamed (e.g. 503 high-demand, 429 quota), transparently fall back
// to the managed Server provider so the recap always completes.
export async function streamRaw({ systemMessage, userText, onDelta, onFallback, signal }) {
  const settings = await getSettings();
  if (settings.provider === "server" || geminiUnavailable || !settings.geminiKey) {
    await streamServer({ systemMessage, userText, signal, onDelta });
    return;
  }
  let emitted = false;
  const wrapped = (c) => { emitted = true; onDelta?.(c); };
  try {
    await streamGemini({ apiKey: settings.geminiKey, model: settings.model || "gemini-3.8-flash", systemMessage, userText, signal, onDelta: wrapped });
  } catch (err) {
    if (shouldFallback(err, emitted)) {
      onFallback?.(activateServerFallback(err));
      await streamServer({ systemMessage, userText, signal, onDelta });
    } else {
      throw err;
    }
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
  await store.set("messages:" + id, []);
  return { ok: true, state: "NEUTRE" };
}

const ALLOWED_MODELS = [
  "gemini-3.8-flash", "gemini-flash-latest", "gemini-3.5-flash",
  "gemini-3.7-flash", "gemini-3.6-flash", "gemini-3.1-pro-preview",
];

export async function getSettings() {
  const s = await store.get("settings", { geminiKey: "", model: "gemini-3.8-flash", provider: "gemini", answerStyle: "complet", tone: "confiant", starMode: true });
  if (!s.provider) s.provider = "gemini";
  if (!s.answerStyle) s.answerStyle = "complet";
  if (!s.tone) s.tone = "confiant";
  if (s.starMode === undefined) s.starMode = true;
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
      const images = (body.images && body.images.length) ? body.images : (body.image_base64 ? [body.image_base64] : []);
      const hasImage = images.length > 0;

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

      const useServer = settings.provider === "server" || geminiUnavailable;
      if (!useServer && !settings.geminiKey) {
        handlers.onError?.("Clé API Gemini manquante. Ouvrez Réglages (ou choisissez le mode Serveur).");
        return;
      }

      const history = messages.map((m) => ({ role: roleLabel(m), content: m.content }));
      const systemMessage = buildSystemMessage(session.context);
      const turnMessage = buildTurnMessage(
        resolved, body.text, session.context, history,
        body.state_candidat, body.voice_confidence, session.debug, hasImage, settings.answerStyle, settings.tone, settings.starMode
      );

      // Persist user turn.
      const msgs = messages.slice();
      msgs.push({ id: uid(), role: "user", content: body.text || "(image)", mode: resolved.resolved_state, created_at: now() });

      let full = "";
      let emitted = false;
      let providerUsed = useServer ? "server" : "gemini";
      const onDelta = (c) => { full += c; emitted = true; handlers.onDelta?.(c); };
      if (useServer) {
        await streamServer({ systemMessage, userText: turnMessage, images, signal: controller.signal, onDelta });
      } else {
        try {
          await streamGemini({
            apiKey: settings.geminiKey,
            model: settings.model || "gemini-3.8-flash",
            systemMessage, userText: turnMessage,
            images, signal: controller.signal, onDelta,
          });
        } catch (err) {
          if (shouldFallback(err, emitted)) {
            const reason = activateServerFallback(err);
            handlers.onFallback?.(reason);
            full = "";
            providerUsed = "server";
            await streamServer({ systemMessage, userText: turnMessage, images, signal: controller.signal, onDelta });
          } else {
            throw err;
          }
        }
      }

      // Rough cost/token estimate for this turn (see costEstimate.js).
      try {
        const usage = estimateTurnCost({
          provider: providerUsed,
          inputText: systemMessage + "\n" + turnMessage,
          outputText: full,
          imageCount: images.length,
        });
        handlers.onUsage?.({ ...usage, provider: providerUsed });
      } catch { /* non-blocking */ }

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
