// 'Serveur' provider — streams generation through our own backend (Emergent key,
// Anthropic). The browser never contacts Google/OpenAI, so it works even on
// machines where those APIs are blocked by an IT policy.
const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

export async function streamServer({ systemMessage, userText, imageDataUrl, signal, onDelta }) {
  const resp = await fetch(`${BACKEND_URL}/api/generate`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ system_message: systemMessage, turn_message: userText, image_base64: imageDataUrl || null }),
    signal,
  });
  if (!resp.ok) {
    let d = "";
    try { d = (await resp.json())?.detail || ""; } catch (e) { d = await resp.text(); }
    throw new Error(`Serveur ${resp.status} — ${String(d).slice(0, 200)}`);
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
      let ev = "message";
      let data = "";
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
