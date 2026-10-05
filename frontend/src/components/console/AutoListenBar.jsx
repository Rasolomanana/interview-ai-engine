import { Headphones, MonitorSpeaker, Mic, Square, Loader2, Zap, Eraser, Languages, Pause } from "lucide-react";
import { toast } from "sonner";

export default function AutoListenBar({ listen, onGenerate }) {
  const { active, source, transcript, busy, auto, setAuto, micLang, setMicLang, start, stop, supported, setTranscript, clearTranscript } = listen;

  const startSrc = async (src) => {
    try { await start(src); } catch (e) { toast.error(e.message); }
  };

  return (
    <div className="border-t border-white/[0.06] px-4 py-2.5" data-testid="auto-listen-bar">
      <div className="flex flex-wrap items-center gap-2">
        <span className="flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-slate-400">
          <Headphones className="h-3.5 w-3.5 text-indigo-400" /> Écoute auto <span className="text-slate-600 normal-case">— capte le recruteur</span>
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
            <div className="flex items-center gap-1 rounded-lg border border-white/10 bg-white/[0.03] p-0.5" data-testid="mic-lang-toggle" title="Langue du recruteur au micro">
              <Languages className="ml-1 h-3.5 w-3.5 text-slate-500" />
              {[["fr-FR", "FR"], ["en-US", "EN"]].map(([code, label]) => (
                <button key={code} data-testid={`mic-lang-${label.toLowerCase()}`} onClick={() => setMicLang(code)}
                  className={`rounded-md px-2 py-1 text-[11px] font-semibold transition-colors ${micLang === code ? "bg-emerald-500/20 text-emerald-200" : "text-slate-400 hover:text-white"}`}>
                  {label}
                </button>
              ))}
            </div>
          </>
        ) : (
          <>
            <span className="flex items-center gap-1.5 rounded-lg border border-red-500/40 bg-red-950/40 px-2.5 py-1.5 text-xs font-semibold text-red-300">
              <span className="h-2 w-2 animate-pulse rounded-full bg-red-500" />
              {source === "tab" ? "Onglet" : "Micro"} en écoute
            </span>
            <button data-testid="listen-stop-btn" onClick={stop} className="flex items-center gap-1.5 rounded-lg border border-red-500/50 bg-red-500/15 px-3 py-1.5 text-xs font-semibold text-red-200 hover:bg-red-500/25" title="Arrêter complètement l'écoute">
              <Square className="h-3.5 w-3.5" /> Arrêter l'écoute
            </button>
            {/* Garde-fou : couper/réactiver la réponse automatique sans arrêter l'écoute */}
            <button
              data-testid="listen-auto-toggle"
              onClick={() => setAuto(!auto)}
              title={auto ? "Réponse automatique ACTIVE — cliquez pour mettre en pause" : "Réponse automatique EN PAUSE — cliquez pour réactiver"}
              className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-semibold transition-colors ${auto ? "border-emerald-500/50 bg-emerald-500/15 text-emerald-200 hover:bg-emerald-500/25" : "border-amber-500/50 bg-amber-500/15 text-amber-200 hover:bg-amber-500/25"}`}
            >
              {auto ? <><Zap className="h-3.5 w-3.5" /> Réponse auto : ON</> : <><Pause className="h-3.5 w-3.5" /> Réponse auto : EN PAUSE</>}
            </button>
            {busy && <span className="flex items-center gap-1 text-xs text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> transcription…</span>}
          </>
        )}
      </div>

      {active && !auto && (
        <div className="mt-2 flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-950/30 px-3 py-1.5 text-[11px] text-amber-300" data-testid="auto-paused-hint">
          <Pause className="h-3.5 w-3.5 shrink-0" /> Réponse automatique en pause — l'écoute continue, mais rien ne se génère seul. Cliquez « Générer la réponse » quand vous voulez, ou réactivez « Réponse auto ».
        </div>
      )}

      <div className="mt-2">
          <div className="mb-1 flex items-center justify-between">
            <span className="font-mono text-[10px] uppercase tracking-widest text-slate-500">Question captée du recruteur (modifiable · redimensionnable ↕)</span>
            {transcript && (
              <button data-testid="listen-clear-btn" onClick={clearTranscript} className="flex items-center gap-1 rounded-md border border-white/10 bg-white/[0.03] px-2 py-0.5 text-[11px] text-slate-400 hover:text-white">
                <Eraser className="h-3 w-3" /> Effacer
              </button>
            )}
          </div>
          <div className="flex items-start gap-2">
            <textarea
              data-testid="listen-transcript"
              value={transcript}
              onChange={(e) => setTranscript(e.target.value)}
              rows={3}
              placeholder="Tapez ou collez la question du recruteur ici — ou lancez l'écoute ci-dessus pour la capter automatiquement (vous pourrez toujours la corriger)."
              className="min-h-[56px] max-h-72 flex-1 resize-y rounded-lg border border-white/[0.06] bg-black/30 px-3 py-2 text-sm leading-relaxed text-slate-200 outline-none placeholder:text-slate-600 focus:border-indigo-500/40"
            />
            <button data-testid="listen-generate-btn" onClick={() => onGenerate(transcript)} disabled={!transcript.trim()} className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-2 text-xs font-semibold text-white hover:bg-emerald-400 disabled:opacity-40">
              <Zap className="h-3.5 w-3.5" /> Générer la réponse
            </button>
          </div>
        </div>
    </div>
  );
}
