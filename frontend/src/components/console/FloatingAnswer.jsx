import { parseCandidate, segmentsFor } from "@/lib/parse";

// Rendered inside a Document Picture-in-Picture window (always-on-top, floats over
// Teams/Zoom/WhatsApp). Shows the current answer in large, readable text to place
// right under the webcam.
export default function FloatingAnswer({ content, streaming, mode, listening, transcript }) {
  const { alert, response, bullets } = parseCandidate(content || "");
  const isCandidate = mode === "CANDIDAT" || bullets.length > 0;

  return (
    <div className="command-bg" style={{ minHeight: "100vh", width: "100%", padding: "14px 16px", boxSizing: "border-box", fontFamily: "'Plus Jakarta Sans', sans-serif", color: "#f8fafc" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 10 }}>
        <span style={{ fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: 2, textTransform: "uppercase", color: "#10b981" }}>
          ● Copilote — à lire {streaming ? "…" : ""}
        </span>
        <span style={{ display: "flex", alignItems: "center", gap: 6, fontFamily: "'JetBrains Mono', monospace", fontSize: 10, letterSpacing: 1, textTransform: "uppercase", color: listening ? "#f87171" : "#64748b" }}>
          <span style={{ width: 8, height: 8, borderRadius: 999, background: listening ? "#ef4444" : "#475569", display: "inline-block", animation: listening ? "caret-blink 1s step-end infinite" : "none" }} />
          {listening ? "Écoute voix" : "Voix off"}
        </span>
      </div>

      {listening && (
        <div style={{ marginBottom: 10, borderRadius: 8, border: "1px solid rgba(255,255,255,.06)", background: "rgba(0,0,0,.3)", padding: "5px 9px", fontSize: 12, color: "#94a3b8", minHeight: 26 }}>
          {transcript ? `🎤 ${transcript}` : "🎤 En attente de la question du recruteur…"}
        </div>
      )}

      {alert && (
        <div style={{ marginBottom: 10, borderRadius: 8, border: "1px solid rgba(251,191,36,.3)", background: "rgba(69,26,3,.4)", padding: "6px 10px", fontSize: 13, color: "#fde68a" }}>
          ⚠ {alert}
        </div>
      )}
      {response && (
        <div style={{ marginBottom: 10, display: "inline-block", borderRadius: 6, border: "1px solid rgba(16,185,129,.4)", background: "rgba(6,78,59,.5)", padding: "4px 10px", fontFamily: "'JetBrains Mono', monospace", fontWeight: 700, color: "#6ee7b7" }}>
          RÉPONSE : {response}
        </div>
      )}

      {isCandidate ? (
        <ul style={{ listStyle: "none", margin: 0, padding: 0, display: "flex", flexDirection: "column", gap: 12 }}>
          {bullets.map((b, i) => (
            <li key={i} style={{ display: "flex", gap: 10, alignItems: "flex-start", fontSize: 21, lineHeight: 1.35 }}>
              <span style={{ color: "#34d399", fontWeight: 800, minWidth: 18 }}>{i + 1}.</span>
              <p style={{ margin: 0 }}>
                {segmentsFor(b).map((s, j) =>
                  s.bold ? <strong key={j} style={{ color: "#fbbf24", fontWeight: 800 }}>{s.text}</strong> : <span key={j}>{s.text}</span>
                )}
              </p>
            </li>
          ))}
          {streaming && bullets.length === 0 && <li style={{ color: "#64748b" }}>Génération…</li>}
        </ul>
      ) : (
        <p style={{ fontSize: 18, lineHeight: 1.5, color: "#e2e8f0" }}>{content}{streaming ? " …" : ""}</p>
      )}

      {!content && (
        <p style={{ color: "#64748b", fontSize: 14 }}>La réponse à lire s'affichera ici. Glissez cette fenêtre juste sous votre caméra. 🎥</p>
      )}
    </div>
  );
}
