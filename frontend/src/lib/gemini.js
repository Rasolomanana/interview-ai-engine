// Direct browser -> Google Gemini streaming call (no server, uses user's own free key).
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
  const resp = await fetch(url, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
    signal,
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
        if (txt) onDelta(txt);
      } catch (e) { /* partial json across chunks — ignored, next read completes it */ }
    }
  }
}
