// Direct browser -> Google Gemini streaming call (no server, uses user's own free key).
// Robustesse ENTRETIEN LIVE : un chien de garge "temps jusqu'au premier mot" garantit
// qu'un réseau qui bloque Google (connexion suspendue, sans erreur) ne fige JAMAIS la
// génération. Passé le délai sans premier token, on abandonne proprement en levant une
// erreur normale (non-AbortError) pour que l'appelant bascule automatiquement sur le
// mode Serveur.
const FIRST_TOKEN_TIMEOUT_MS = 9000;

export async function streamGemini({ apiKey, model, systemMessage, userText, imageDataUrl, signal, onDelta }) {
  const parts = [{ text: userText }];
  if (imageDataUrl) {
    const [meta, b64] = imageDataUrl.split(",");
    const mime = (meta.match(/data:(.*?);/) || [])[1] || "image/png";
    parts.push({ inline_data: { mime_type: mime, data: b64 } });
  }
  const body = {
    system_instruction: { parts: [{ text: systemMessage }] },
    contents: [{ role: "user", parts }],
    generationConfig: { temperature: 0.7, maxOutputTokens: 1200 },
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
      let detail = "";
      try { detail = (await resp.json())?.error?.message || ""; } catch (e) { detail = await resp.text(); }
      throw new Error(`Gemini ${resp.status} — ${String(detail).slice(0, 300)}`);
    }
    const reader = resp.body.getReader();
    const dec = new TextDecoder();
    let buf = "";
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
          const txt = cand?.content?.parts?.map((p) => p.text || "").join("") || "";
          if (txt) {
            if (!firstToken) { firstToken = true; clearTimeout(timer); }
            onDelta(txt);
          }
        } catch (e) { /* partial json across chunks — ignored, next read completes it */ }
      }
    }
  } catch (e) {
    // Watchdog abort -> normal Error so the caller falls back to Server mode.
    if (timedOut) throw new Error("Gemini: aucune réponse en 9 s (accès Google bloqué ?) — bascule serveur");
    throw e; // network error or genuine user barge-in (AbortError) propagate as-is
  } finally {
    clearTimeout(timer);
    if (signal) signal.removeEventListener("abort", onExtAbort);
  }
}
