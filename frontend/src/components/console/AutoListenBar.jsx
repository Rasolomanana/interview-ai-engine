import { Headphones, MonitorSpeaker, Mic, Square, Loader2, Send, Zap } from "lucide-react";

export default function AutoListenBar({ listen, onGenerate }) {
  const { active, source, transcript, busy, auto, setAuto, start, stop, supported } = listen;

  const startSrc = async (src) => {
    try { await start(src); } catch (e) { window.__toast?.(e.message) || alert(e.message); }
  };

  return (
    <div className="border-t border-white/[0.06] px-4 py-2.5" data-testid="auto-listen-bar">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-slate-400">
          <Headphones className="h-3.5 w-3.5 text-indigo-400" /> Écoute auto
        </span>

        {!active ? (
          <>
            <button data-testid="listen-tab-btn" onClick={() => startSrc("tab")} disabled={!supported}
              className="flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3 py-1.5 text-xs font-medium text-indigo-200 hover:bg-indigo-500/20 disabled:opacity-40">
              <MonitorSpeaker className="h-3.5 w-3.5" /> Onglet Teams / Zoom
            </button>
            <button data-testid="listen-mic-btn" onClick={() => startSrc("mic")} disabled={!supported}
              className="flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-medium text-emerald-200 hover:bg-emerald-500/20 disabled:opacity-40">
              <Mic className="h-3.5 w-3.5" /> Micro (téléphone à proximité)
            </button>
          </>
        ) : (
          <>
            <span className="flex items-center gap-1.5 rounded-lg border border-red-500/40 bg-red-950/40 px-2.5 py-1.5 text-xs font-semibold text-red-300">
              <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
              {source === "tab" ? "Onglet" : "Micro"} en écoute
            </span>
            <button data-testid="listen-stop-btn" onClick={stop} className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-300 hover:text-white">
              <Square className="h-3.5 w-3.5" /> Stop
            </button>
            {busy && <Loader2 className="h-4 w-4 animate-spin text-slate-400" />}
            <label className="flex items-center gap-1.5 text-xs text-slate-400">
              <input type="checkbox" checked={auto} onChange={(e) => setAuto(e.target.checked)} data-testid="listen-auto-toggle" className="accent-indigo-500" />
              Auto-répondre
            </label>
          </>
        )}
      </div>

      {(active || transcript) && (
        <div className="mt-2 flex items-start gap-2">
          <div className="flex-1 rounded-lg border border-white/[0.06] bg-black/30 px-3 py-2 text-sm text-slate-300" data-testid="listen-transcript">
            {transcript || <span className="text-slate-600">En attente de la question du recruteur…</span>}
          </div>
          {transcript && (
            <button data-testid="listen-generate-btn" onClick={() => onGenerate(transcript)} className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-400">
              <Zap className="h-3.5 w-3.5" /> Générer la réponse
            </button>
          )}
        </div>
      )}
    </div>
  );
}
