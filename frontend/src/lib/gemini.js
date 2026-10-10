// Direct browser -> Google Gemini streaming call (no server, uses user's own free key).
// Robustesse ENTRETIEN LIVE : un chien de garge "temps jusqu'au premier mot" garantit
// qu'un réseau qui bloque Google (connexion suspendue, sans erreur) ne fige JAMAIS la
// génération. Passé le délai sans premier token, on abandonne proprement en levant une
// erreur normale (non-AbortError) pour que l'appelant bascule automatiquement sur le
// mode Serveur.
const FIRST_TOKEN_TIMEOUT_MS = 9000;

const KIND_LABELS = {
  KEY_INVALID: "Clé API invalide",
  KEY_DENIED: "Clé refusée / API non activée",
  QUOTA: "Quota dépassé",
  MODEL_UNAVAILABLE: "Modèle indisponible",
  GOOGLE_DOWN: "Service Google indisponible",
  BAD_REQUEST: "Requête refusée par Google",
  TIMEOUT: "Timeout (aucun premier mot en 9 s)",
  NETWORK: "Erreur navigateur / réseau / CORS",
  EMPTY: "Réponse vide (bloquée ou filtrée)",
  OTHER: "Autre erreur",
};

function geminiError(kind, message, extra = {}) {
  const e = new Error(`Gemini [${KIND_LABELS[kind]}] ${message}`);
  Object.assign(e, { kind, kindLabel: KIND_LABELS[kind], detail: message, ...extra });
  return e;
}

function classifyHttp(status, gStatus, msg) {
  const m = `${gStatus} ${msg}`.toLowerCase();
  if (m.includes("api key not valid") || m.includes("api_key_invalid") || m.includes("api key expired")) return "KEY_INVALID";
  if (status === 429 || gStatus === "RESOURCE_EXHAUSTED" || m.includes("quota")) return "QUOTA";
  if (status === 404 || gStatus === "NOT_FOUND" || m.includes("is not found") || m.includes("not supported")) return "MODEL_UNAVAILABLE";
  if (status === 401 || status === 403 || gStatus === "PERMISSION_DENIED" || gStatus === "UNAUTHENTICATED") return "KEY_DENIED";
  if (status >= 500) return "GOOGLE_DOWN";
  if (status === 400) return "BAD_REQUEST";
  return "OTHER";
}

// Normalizes ANY error thrown during a Gemini call into {kind,kindLabel,detail,...}.
export function describeGeminiError(err, model) {
  if (err?.kind) return { kind: err.kind, label: err.kindLabel, detail: err.detail, status: err.status || null, model, at: new Date().toISOString() };
  const isNet = err?.name === "TypeError" || /failed to fetch|networkerror|load failed/i.test(String(err?.message));
  const detail = isNet
    ? `${err?.message} — le navigateur n'a pas pu joindre generativelanguage.googleapis.com (SSL/proxy/pare-feu, extension, hors-ligne=${typeof navigator !== "undefined" && !navigator.onLine}, ou CORS). Voir l'onglet Réseau/Console pour le code net::ERR_…`
    : String(err?.message || err);
  return { kind: isNet ? "NETWORK" : "OTHER", label: KIND_LABELS[isNet ? "NETWORK" : "OTHER"], detail, status: null, model, at: new Date().toISOString() };
}

export async function streamGemini({ apiKey, model, systemMessage, userText, imageDataUrl, images, signal, onDelta }) {
  const parts = [{ text: userText }];
  const imgs = (images && images.length) ? images : (imageDataUrl ? [imageDataUrl] : []);
  for (const img of imgs) {
    const [meta, b64] = img.split(",");
    const mime = (meta.match(/data:(.*?);/) || [])[1] || "image/png";
    parts.push({ inline_data: { mime_type: mime, data: b64 } });
  }
  const body = {
    system_instruction: { parts: [{ text: systemMessage }] },
    contents: [{ role: "user", parts }],
    generationConfig: { temperature: 0.7, maxOutputTokens: 2048 },
  };
  const url = `https://generativelanguage.googleapis.com/v1beta/models/${encodeURIComponent(model)}:streamGenerateContent?alt=sse&key=${encodeURIComponent(apiKey)}`;

  // Internal controller so the watchdog can abort a hung connection independently
  // of the caller's barge-in signal.
  const ctrl = new AbortController();
  const onExtAbort = () => ctrl.abort();
  if (signal) {
    if (signal.aborted) ctrl.abort();
    else signal.addEventListener("abort", onExtAbort, { once: true });
  }
  let firstToken = false;
  let timedOut = false;
  let timer = setTimeout(() => { if (!firstToken) { timedOut = true; ctrl.abort(); } }, FIRST_TOKEN_TIMEOUT_MS);

  try {
    const resp = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
      signal: ctrl.signal,
    });
    if (!resp.ok) {
      let detail = "", gStatus = "";
      const raw = await resp.text();
      try { const j = JSON.parse(raw)?.error || {}; detail = j.message || raw; gStatus = j.status || ""; } catch (e) { detail = raw; }
      const kind = classifyHttp(resp.status, gStatus, detail);
      throw geminiError(kind, `HTTP ${resp.status} ${gStatus} — ${String(detail).slice(0, 400)} (modèle : ${model})`, { status: resp.status, gStatus });
    }
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
    let finish = "", block = "";
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += dec.decode(value, { stream: true });
      const lines = buf.split("\n");
      buf = lines.pop();
      for (const raw of lines) {
        const l = raw.trim();
        if (!l.startsWith("data:")) continue;
        const data = l.slice(5).trim();
        if (!data || data === "[DONE]") continue;
        try {
          const j = JSON.parse(data);
          const cand = j.candidates && j.candidates[0];
          if (cand?.finishReason) finish = cand.finishReason;
          if (j.promptFeedback?.blockReason) block = j.promptFeedback.blockReason;
          if (j.error) throw geminiError(classifyHttp(j.error.code, j.error.status, j.error.message), `${j.error.status} — ${j.error.message}`, { status: j.error.code });
          const txt = cand?.content?.parts?.map((p) => p.text || "").join("") || "";
          if (txt) {
            if (!firstToken) { firstToken = true; clearTimeout(timer); }
            onDelta(txt);
          }
        } catch (e) { if (e.kind) throw e; /* partial json across chunks — next read completes it */ }
      }
    }
    if (!firstToken) throw geminiError("EMPTY", `aucun texte reçu (finishReason=${finish || "?"}, blockReason=${block || "aucun"}, modèle : ${model})`);
  } catch (e) {
    // Watchdog abort -> normal Error so the caller falls back to Server mode.
    if (timedOut) throw geminiError("TIMEOUT", `aucun premier mot après ${FIRST_TOKEN_TIMEOUT_MS / 1000} s (modèle : ${model}) — connexion suspendue par le réseau, ou modèle trop lent (réflexion) avant le premier token`);
    throw e; // network error or genuine user barge-in (AbortError) propagate as-is
  } finally {
    clearTimeout(timer);
    if (signal) signal.removeEventListener("abort", onExtAbort);
  }
}
