// Parse candidate-mode assistant output into structured parts for rendering.
export function parseCandidate(text) {
  const raw = (text || "").split("\n").map((l) => l.trim()).filter(Boolean);
  let alert = null;
  let response = null; // vision [RÉPONSE : X]
  const bullets = [];
  for (const line of raw) {
    const alertMatch = line.match(/^\[ALERTE\s*:\s*(.+?)\]$/i);
    const respMatch = line.match(/^\[R[ÉE]PONSE\s*:\s*(.+?)\]$/i);
    if (alertMatch) { alert = alertMatch[1]; continue; }
    if (respMatch) { response = respMatch[1]; continue; }
    if (line.startsWith("•") || line.startsWith("-") || line.startsWith("*")) {
      bullets.push(line.replace(/^[•\-*]\s*/, ""));
    } else if (line.startsWith("[MODE")) {
      // debug line — keep as bullet-less note handled elsewhere
    } else {
      bullets.push(line);
    }
  }
  return { alert, response, bullets };
}

// Split a bullet on **bold** markers into segments {text, bold}.
export function segmentsFor(bulletText) {
  const parts = [];
  const regex = /\*\*(.+?)\*\*/g;
  let last = 0;
  let m;
  while ((m = regex.exec(bulletText)) !== null) {
    if (m.index > last) parts.push({ text: bulletText.slice(last, m.index), bold: false });
    parts.push({ text: m[1], bold: true });
    last = regex.lastIndex;
  }
  if (last < bulletText.length) parts.push({ text: bulletText.slice(last), bold: false });
  return parts;
}

export function stripDebugLine(text) {
  const lines = (text || "").split("\n");
  if (lines[0] && /^\[MODE\s*:/.test(lines[0].trim())) {
    return { debug: lines[0].trim(), body: lines.slice(1).join("\n").trim() };
  }
  return { debug: null, body: text };
}
