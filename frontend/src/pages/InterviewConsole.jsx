import { useEffect, useRef, useState, useCallback } from "react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  Send, Mic, MicOff, ImagePlus, X, Zap, RotateCcw, SlidersHorizontal,
  Bug, Hand, UserCircle2, ClipboardList, ArrowRight, PlayCircle, KeyRound,
} from "lucide-react";
import * as api from "@/lib/api";
import { useVoice } from "@/lib/useVoice";
import SessionSidebar from "@/components/console/SessionSidebar";
import ContextPanel from "@/components/console/ContextPanel";
import SettingsPanel from "@/components/console/SettingsPanel";
import VoicePanel from "@/components/console/VoicePanel";
import MessageBubble from "@/components/console/MessageBubble";

const BADGE = {
  NEUTRE: "border-slate-600 bg-slate-800/80 text-slate-300",
  CANDIDAT: "border-emerald-500/40 bg-emerald-950/80 text-emerald-400",
  RECRUTEUR: "border-violet-500/40 bg-violet-950/80 text-violet-400",
};

const MARKER_RE = /\[(RESET|RECRUTEUR|MODE_SIMULATION|REPONSE_ORALE|R[ÉE]PONSE_ORALE|DEBUG)\]/gi;
const cleanDisplay = (t) => (t || "").replace(MARKER_RE, "").trim();

export default function InterviewConsole() {
  const [sessions, setSessions] = useState([]);
  const [active, setActive] = useState(null);
  const [messages, setMessages] = useState([]);
  const [streaming, setStreaming] = useState({ active: false, text: "", meta: null, mode: "NEUTRE" });
  const [meta, setMeta] = useState(null);
  const [latency, setLatency] = useState(null);
  const [input, setInput] = useState("");
  const [image, setImage] = useState(null);
  const [pendingMode, setPendingMode] = useState(null);
  const [ctxOpen, setCtxOpen] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [settings, setSettings] = useState({ geminiKey: "", model: "gemini-3.8-flash" });
  const [creating, setCreating] = useState(false);

  const voice = useVoice();
  const controllerRef = useRef(null);
  const threadRef = useRef(null);
  const fileRef = useRef(null);
  const streamInfoRef = useRef({ mode: "NEUTRE", modules: [] });
  const initRef = useRef(false);

  const uid = () => (crypto?.randomUUID ? crypto.randomUUID() : String(Math.random()));

  const refreshSessions = useCallback(async () => {
    const list = await api.listSessions();
    setSessions(list);
    return list;
  }, []);

  useEffect(() => {
    if (initRef.current) return;
    initRef.current = true;
    (async () => {
      const st = await api.getSettings();
      setSettings(st);
      if (!st.geminiKey) setSettingsOpen(true);
      const list = await refreshSessions();
      if (list.length) selectSession(list[0].id);
      else await handleNew();
    })();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    threadRef.current?.scrollTo({ top: threadRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, streaming.text]);

  // Push voice transcript into the input while listening.
  useEffect(() => {
    if (voice.listening && voice.transcript) setInput(voice.transcript);
  }, [voice.transcript, voice.listening]);

  const selectSession = async (id) => {
    const data = await api.getSession(id);
    if (!data.session) return;
    setActive(data.session);
    setMessages(data.messages.map((m) => ({ ...m, id: uid(), content: m.role === "user" ? cleanDisplay(m.content) || "(image)" : m.content })));
    setMeta({ resolved_state: data.session.state, prev_state: data.session.prev_state, tours: data.session.tours_sans_marqueur, modules: ["—"] });
    setPendingMode(null);
  };

  const handleNew = async () => {
    setCreating(true);
    try {
      const s = await api.createSession({ title: "Nouvelle session", debug: false });
      await refreshSessions();
      await selectSession(s.id);
      toast.success("Session créée");
    } finally {
      setCreating(false);
    }
  };

  const handleDelete = async (id) => {
    await api.deleteSession(id);
    const list = await refreshSessions();
    if (active?.id === id) {
      if (list.length) selectSession(list[0].id);
      else handleNew();
    }
  };

  const saveContext = async (form) => {
    const updated = await api.updateSession(active.id, {
      title: form.title,
      context: { cv: form.cv, poste: form.poste, entreprise: form.entreprise, secteur: form.secteur },
    });
    setActive((a) => ({ ...a, ...updated }));
    await refreshSessions();
    setCtxOpen(false);
    toast.success("Contexte enregistré");
  };

  const toggleDebug = async () => {
    const updated = await api.updateSession(active.id, { debug: !active.debug });
    setActive((a) => ({ ...a, debug: updated.debug }));
    toast(updated.debug ? "Mode DEBUG activé" : "Mode DEBUG désactivé");
  };

  const doReset = async () => {
    controllerRef.current?.abort();
    await api.resetSession(active.id);
    const data = await api.getSession(active.id);
    setActive(data.session);
    setMeta({ resolved_state: "NEUTRE", prev_state: "NEUTRE", tours: 0, modules: ["RESET"] });
    setStreaming({ active: false, text: "", meta: null, mode: "NEUTRE" });
    setPendingMode(null);
    toast("État réinitialisé → NEUTRE");
  };

  const saveSettingsHandler = async (s) => {
    const saved = await api.saveSettings(s);
    setSettings(saved);
    setSettingsOpen(false);
    toast.success(saved.geminiKey ? "Clé Gemini enregistrée" : "Réglages enregistrés");
  };

  const bargeIn = () => {
    if (!streaming.active) return;
    controllerRef.current?.abort();
    toast("⛔ Barge-in — génération annulée, état inchangé");
  };

  const send = (rawText, displayText, img) => {
    if (!active || streaming.active) return;
    if (!rawText?.trim() && !img) return;
    if (!settings.geminiKey) {
      toast.error("Ajoutez votre clé API Gemini (gratuite) dans Réglages");
      setSettingsOpen(true);
      return;
    }
    const userMsg = { id: uid(), role: "user", content: displayText ?? cleanDisplay(rawText) ?? "(image)", mode: active.state };
    setMessages((m) => [...m, userMsg]);
    setStreaming({ active: true, text: "", meta: null, mode: active.state });
    streamInfoRef.current = { mode: active.state, modules: [] };
    setInput("");
    setImage(null);
    if (voice.listening) voice.stop();
    const t0 = Date.now();

    controllerRef.current = api.streamMessage(
      active.id,
      {
        text: rawText || "",
        state_candidat: voice.metrics.stateCandidat,
        voice_confidence: voice.metrics.voiceConfidence,
        image_base64: img || null,
        barge_in: false,
      },
      {
        onMeta: (m) => {
          setMeta(m);
          streamInfoRef.current = { mode: m.resolved_state, modules: m.modules || [] };
          setStreaming((s) => ({ ...s, meta: m, mode: m.resolved_state }));
          setActive((a) => ({ ...a, state: m.resolved_state, tours_sans_marqueur: m.tours }));
        },
        onDelta: (c) => setStreaming((s) => ({ ...s, text: s.text + c })),
        onDone: (full) => {
          setLatency(Date.now() - t0);
          const info = streamInfoRef.current;
          setMessages((m) => [...m, { id: uid(), role: "assistant", content: full, mode: info.mode, modules: info.modules }]);
          setStreaming({ active: false, text: "", meta: null, mode: info.mode });
          refreshSessions();
        },
        onError: (d) => {
          setStreaming({ active: false, text: "", meta: null, mode: active.state });
          toast.error("Erreur LLM : " + d);
        },
        onAbort: () => setStreaming((s) => ({ ...s, active: false })),
      }
    );
  };

  const submitInput = () => {
    let raw = input;
    let display = cleanDisplay(input) || "(image)";
    if (pendingMode === "CANDIDAT" && !/\[/.test(input)) {
      raw = "[REPONSE_ORALE] " + input;
      setPendingMode(null);
    }
    send(raw, display, image);
  };

  const lastRecruiterQuestion = [...messages].reverse().find((m) => m.role === "assistant" && m.mode === "RECRUTEUR")?.content;

  const state = active?.state || "NEUTRE";
  const streamMsg = streaming.active ? { role: "assistant", content: streaming.text || "…", mode: streaming.mode, modules: streaming.meta?.modules || [] } : null;

  return (
    <div className="command-bg min-h-screen w-full">
      <div className="relative z-10 mx-auto grid min-h-screen max-w-[1600px] grid-cols-1 gap-4 p-4 lg:grid-cols-[260px_1fr_300px]">
        {/* LEFT */}
        <div className="glass hidden rounded-2xl p-4 lg:flex lg:flex-col">
          <SessionSidebar sessions={sessions} activeId={active?.id} onSelect={selectSession} onNew={handleNew} onDelete={handleDelete} creating={creating} />
        </div>

        {/* CENTER */}
        <div className="glass flex min-h-[80vh] flex-col overflow-hidden rounded-2xl">
          {/* Header */}
          <div className="flex flex-wrap items-center justify-between gap-3 border-b border-white/[0.06] px-5 py-3">
            <div className="flex items-center gap-3">
              <motion.span
                key={state}
                initial={{ scale: 0.85, opacity: 0 }} animate={{ scale: 1, opacity: 1 }}
                className={`rounded-lg border px-3 py-1 font-mono text-xs font-bold tracking-widest ${BADGE[state]}`}
                data-testid="mode-badge"
              >
                {state}
              </motion.span>
              <span className="rounded-lg border border-white/10 bg-black/30 px-2.5 py-1 font-mono text-[11px] text-slate-400" data-testid="turn-counter">
                Tours ss marq. : {active?.tours_sans_marqueur ?? 0}
              </span>
            </div>
            <div className="flex items-center gap-1.5">
              <HeaderBtn onClick={() => setSettingsOpen(true)} testid="open-settings-btn" icon={<KeyRound className="h-4 w-4" />} label="Réglages" active={!settings.geminiKey} />
              <HeaderBtn onClick={() => setCtxOpen(true)} testid="open-context-btn" icon={<SlidersHorizontal className="h-4 w-4" />} label="Contexte" />
              <HeaderBtn onClick={toggleDebug} testid="debug-toggle-btn" icon={<Bug className="h-4 w-4" />} label="Debug" active={active?.debug} />
              <HeaderBtn onClick={doReset} testid="reset-btn" icon={<RotateCcw className="h-4 w-4" />} label="Reset" />
            </div>
          </div>

          {/* Thread */}
          <div ref={threadRef} className="flex-1 space-y-5 overflow-y-auto px-5 py-5" data-testid="message-thread">
            {messages.length === 0 && !streamMsg && (
              <EmptyState onCandidat={() => { setPendingMode("CANDIDAT"); toast("Mode Candidat prêt — saisissez la question du recruteur"); }} onRecruteur={() => send("[MODE_SIMULATION] Démarre la simulation d'entretien.", "▶ Simulation démarrée")} />
            )}
            {messages.map((m) => (
              <MessageBubble key={m.id} msg={m} streaming={false} />
            ))}
            {streamMsg && <MessageBubble msg={streamMsg} streaming />}
          </div>

          {/* Quick actions */}
          {(state === "RECRUTEUR" || state === "CANDIDAT") && messages.length > 0 && (
            <div className="flex flex-wrap gap-2 border-t border-white/[0.06] px-5 py-2.5">
              {state === "RECRUTEUR" && (
                <>
                  <QuickBtn testid="next-question-btn" onClick={() => send("[MODE_SIMULATION] Question suivante.", "→ Question suivante")} icon={<ArrowRight className="h-3.5 w-3.5" />} label="Question suivante" />
                  {lastRecruiterQuestion && (
                    <QuickBtn testid="answer-copilot-btn" onClick={() => send("[REPONSE_ORALE] " + lastRecruiterQuestion, "🎤 Répondre avec le copilote")} icon={<UserCircle2 className="h-3.5 w-3.5" />} label="Répondre (copilote)" />
                  )}
                </>
              )}
              {state === "CANDIDAT" && (
                <QuickBtn testid="to-simulation-btn" onClick={() => send("[MODE_SIMULATION] Passe en simulation d'entretien.", "▶ Passer en simulation")} icon={<PlayCircle className="h-3.5 w-3.5" />} label="Passer en simulation" />
              )}
            </div>
          )}

          {/* Composer */}
          <div className="border-t border-white/[0.06] px-4 py-3">
            {pendingMode === "CANDIDAT" && (
              <div className="mb-2 flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-3 py-1.5 text-xs text-emerald-300">
                <ClipboardList className="h-3.5 w-3.5" /> Mode Candidat — saisissez la question posée par le recruteur.
              </div>
            )}
            {image && (
              <div className="mb-2 flex items-center gap-2">
                <div className="relative">
                  <img src={image} alt="upload" className="h-16 w-16 rounded-lg border border-white/10 object-cover" data-testid="image-preview" />
                  <button onClick={() => setImage(null)} className="absolute -right-1.5 -top-1.5 rounded-full bg-red-500 p-0.5 text-white">
                    <X className="h-3 w-3" />
                  </button>
                </div>
                <span className="text-xs text-slate-400">Image jointe (test logique visuel)</span>
              </div>
            )}
            <div className="flex items-end gap-2">
              <button onClick={() => fileRef.current?.click()} data-testid="image-upload-btn" className="rounded-xl border border-white/10 bg-white/[0.03] p-2.5 text-slate-400 transition-colors hover:text-white" title="Joindre une image">
                <ImagePlus className="h-5 w-5" />
              </button>
              <input ref={fileRef} type="file" accept="image/png,image/jpeg,image/webp" className="hidden" onChange={(e) => {
                const f = e.target.files?.[0];
                if (!f) return;
                const r = new FileReader();
                r.onload = () => setImage(r.result);
                r.readAsDataURL(f);
                e.target.value = "";
              }} />

              <button
                onClick={() => (voice.listening ? voice.stop() : voice.start())}
                data-testid="mic-toggle-btn"
                disabled={!voice.supported}
                title={voice.supported ? "Dictée vocale (fr-FR)" : "Reconnaissance vocale non supportée"}
                className={`rounded-xl border p-2.5 transition-colors ${voice.listening ? "border-emerald-500/50 bg-emerald-500/15 text-emerald-400" : "border-white/10 bg-white/[0.03] text-slate-400 hover:text-white"} disabled:opacity-40`}
              >
                {voice.listening ? <Mic className="h-5 w-5" /> : <MicOff className="h-5 w-5" />}
              </button>

              <textarea
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); submitInput(); } }}
                rows={1}
                data-testid="message-input"
                placeholder={state === "RECRUTEUR" ? "Votre réponse au recruteur…" : "Question du recruteur à traiter…"}
                className="max-h-32 flex-1 resize-none rounded-xl border border-white/10 bg-black/40 px-4 py-2.5 text-[15px] text-slate-100 outline-none transition-colors placeholder:text-slate-600 focus:border-indigo-500/60"
              />

              {streaming.active ? (
                <button onClick={bargeIn} data-testid="barge-in-btn" className="pulse-ring flex items-center gap-2 rounded-xl bg-red-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-red-400">
                  <Hand className="h-4 w-4" /> Interrompre
                </button>
              ) : (
                <button onClick={submitInput} data-testid="send-btn" className="flex items-center gap-2 rounded-xl bg-gradient-to-br from-indigo-500 to-indigo-600 px-4 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/25 transition-all hover:from-indigo-400 hover:to-indigo-500">
                  <Send className="h-4 w-4" /> Envoyer
                </button>
              )}
            </div>
          </div>
        </div>

        {/* RIGHT */}
        <div className="hidden lg:block">
          <VoicePanel metrics={voice.metrics} listening={voice.listening} meta={meta} debug={active?.debug} latency={latency} />
        </div>
      </div>

      <ContextPanel open={ctxOpen} session={active} onClose={() => setCtxOpen(false)} onSave={saveContext} />
      <SettingsPanel open={settingsOpen} settings={settings} onClose={() => setSettingsOpen(false)} onSave={saveSettingsHandler} />
    </div>
  );
}

function HeaderBtn({ onClick, icon, label, active, testid }) {
  return (
    <button onClick={onClick} data-testid={testid} className={`flex items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-medium transition-colors ${active ? "border-red-500/40 bg-red-950/40 text-red-300" : "border-white/10 bg-white/[0.03] text-slate-400 hover:text-white"}`}>
      {icon} <span className="hidden sm:inline">{label}</span>
    </button>
  );
}

function QuickBtn({ onClick, icon, label, testid }) {
  return (
    <button onClick={onClick} data-testid={testid} className="flex items-center gap-1.5 rounded-lg border border-indigo-500/30 bg-indigo-500/10 px-3 py-1.5 text-xs font-medium text-indigo-200 transition-colors hover:bg-indigo-500/20">
      {icon} {label}
    </button>
  );
}

function EmptyState({ onCandidat, onRecruteur }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-6 py-12 text-center">
      <motion.div initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }}>
        <div className="mx-auto mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-gradient-to-br from-indigo-500 to-emerald-500 text-white shadow-xl shadow-indigo-500/30">
          <Zap className="h-7 w-7" />
        </div>
        <h2 className="font-display text-2xl font-extrabold text-white">Souhaitez-vous lancer une simulation<br />ou activer le copilote temps réel ?</h2>
        <p className="mt-2 text-sm text-slate-400">État NEUTRE — choisissez un mode pour démarrer.</p>
      </motion.div>
      <div className="flex flex-col gap-3 sm:flex-row">
        <button onClick={onCandidat} data-testid="activate-candidat-btn" className="group flex items-center gap-3 rounded-2xl border border-emerald-500/40 bg-emerald-500/10 px-6 py-4 text-left transition-all hover:bg-emerald-500/20">
          <UserCircle2 className="h-6 w-6 text-emerald-400" />
          <div>
            <p className="font-semibold text-emerald-200">Mode Candidat</p>
            <p className="text-xs text-emerald-400/70">Copilote discret en direct</p>
          </div>
        </button>
        <button onClick={onRecruteur} data-testid="activate-recruteur-btn" className="group flex items-center gap-3 rounded-2xl border border-violet-500/40 bg-violet-500/10 px-6 py-4 text-left transition-all hover:bg-violet-500/20">
          <PlayCircle className="h-6 w-6 text-violet-400" />
          <div>
            <p className="font-semibold text-violet-200">Mode Recruteur</p>
            <p className="text-xs text-violet-400/70">Simulation d'entretien immersive</p>
          </div>
        </button>
      </div>
    </div>
  );
}
