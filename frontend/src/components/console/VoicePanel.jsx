import { Activity, Gauge, Mic, Radio, Bug, Cpu } from "lucide-react";

const STATE_CANDIDAT_COLOR = {
  NORMAL: "text-emerald-400",
  STRESS_HIGH: "text-red-400",
  MONOTONE: "text-amber-400",
  LECTURE_ROBOTIQUE: "text-amber-400",
  DEBIT_RAPIDE: "text-sky-400",
  DEBIT_LENT: "text-sky-400",
};

function Bar({ label, value, max = 1, color, unit = "" }) {
  const pct = Math.min(100, (value / max) * 100);
  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <span className="font-mono text-[10px] uppercase tracking-widest text-slate-400">{label}</span>
        <span className="font-mono text-xs font-bold text-slate-200">{value}{unit}</span>
      </div>
      <div className="h-1.5 overflow-hidden rounded-full bg-white/[0.06]">
        <div className={`h-full rounded-full transition-all duration-300 ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

export default function VoicePanel({ metrics, listening, meta, debug, latency }) {
  const sc = metrics.stateCandidat;
  const conf = metrics.voiceConfidence;
  const tm6Active = conf >= 0.7;
  return (
    <div className="flex h-full flex-col gap-4 overflow-y-auto pr-1" data-testid="voice-panel">
      {/* Live voice */}
      <section className="glass rounded-2xl p-4">
        <div className="mb-3 flex items-center justify-between">
          <h3 className="flex items-center gap-2 font-display text-sm font-bold text-white">
            <Activity className="h-4 w-4 text-emerald-400" /> Analyse vocale
          </h3>
          <span className={`flex items-center gap-1.5 font-mono text-[10px] ${listening ? "text-emerald-400" : "text-slate-500"}`}>
            <Radio className={`h-3 w-3 ${listening ? "animate-pulse" : ""}`} />
            {listening ? "LIVE" : "OFF"}
          </span>
        </div>

        <div className="mb-4 flex items-end justify-center gap-1 h-10">
          {listening ? (
            [...Array(11)].map((_, i) => (
              <span
                key={i}
                className="eq-bar w-1 rounded-full bg-gradient-to-t from-emerald-500 to-emerald-300"
                style={{ height: `${20 + (i % 5) * 12}px`, animationDelay: `${i * 0.08}s` }}
              />
            ))
          ) : (
            <div className="h-px w-full bg-white/10" />
          )}
        </div>

        <div className="mb-3 flex items-center justify-between rounded-xl border border-white/[0.06] bg-black/30 px-3 py-2">
          <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">State_Candidat</span>
          <span className={`font-mono text-xs font-bold ${STATE_CANDIDAT_COLOR[sc] || "text-slate-300"}`} data-testid="state-candidat-value">{sc}</span>
        </div>

        <div className="space-y-3">
          <Bar label="Confiance voix" value={conf} max={1} unit="" color={conf >= 0.7 ? "bg-emerald-400" : "bg-slate-500"} />
          <Bar label="Stress" value={metrics.stress} max={1} color="bg-red-400" />
          <Bar label="Monotone" value={metrics.monotone} max={1} color="bg-amber-400" />
          <Bar label="Débit" value={metrics.rate} max={220} unit=" mpm" color="bg-sky-400" />
        </div>
        <p className={`mt-3 text-center font-mono text-[10px] ${tm6Active ? "text-emerald-400" : "text-slate-600"}`}>
          TM6 {tm6Active ? "ACTIF (conf ≥ 0.7)" : "ignoré (conf < 0.7)"}
        </p>
      </section>

      {/* State inspector */}
      <section className="glass rounded-2xl p-4">
        <h3 className="mb-3 flex items-center gap-2 font-display text-sm font-bold text-white">
          <Gauge className="h-4 w-4 text-indigo-400" /> Inspecteur d'état
        </h3>
        <dl className="space-y-2 font-mono text-xs">
          <Row k="ÉTAT RÉSOLU" v={meta?.resolved_state || "—"} />
          <Row k="ÉTAT PRÉC." v={meta?.prev_state || "—"} />
          <Row k="TOURS_SS_MARQ" v={meta?.tours ?? "0"} />
          <Row k="MODULES" v={(meta?.modules || ["—"]).join(", ")} />
          <Row k="VOICE_MODULE" v={meta?.voice_module || "—"} />
        </dl>
      </section>

      {/* Debug telemetry */}
      {debug && (
        <section className="glass rounded-2xl border border-red-500/20 p-4" data-testid="debug-overlay">
          <h3 className="mb-3 flex items-center gap-2 font-display text-sm font-bold text-red-300">
            <Bug className="h-4 w-4" /> Télémétrie DEBUG
          </h3>
          <dl className="space-y-2 font-mono text-[11px]">
            <Row k="Latence LLM" v={latency ? `${latency} ms` : "—"} />
            <Row k="Mic actif" v={listening ? "true" : "false"} />
            <Row k="Confiance brute" v={conf} />
            <Row k="Volume RMS" v={metrics.volume} />
          </dl>
          <div className="mt-3 rounded-lg border border-white/[0.06] bg-black/40 p-2">
            <p className="mb-1 flex items-center gap-1 font-mono text-[9px] uppercase tracking-widest text-slate-500"><Cpu className="h-3 w-3" /> Trace machine d'états</p>
            <ul className="space-y-1">
              {(meta?.trace || []).map((t, i) => (
                <li key={i} className="font-mono text-[10px] leading-tight text-emerald-300/80">› {t}</li>
              ))}
              {(!meta?.trace || meta.trace.length === 0) && <li className="text-[10px] text-slate-600">Aucune trace.</li>}
            </ul>
          </div>
        </section>
      )}
    </div>
  );
}

function Row({ k, v }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <dt className="text-slate-500">{k}</dt>
      <dd className="truncate text-right text-slate-200">{String(v)}</dd>
    </div>
  );
}
