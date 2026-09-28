import { useEffect, useRef, useState, useCallback } from "react";
import { createPortal } from "react-dom";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  Send, Mic, MicOff, ImagePlus, X, Zap, RotateCcw, SlidersHorizontal,
  Bug, Hand, UserCircle2, ClipboardList, ArrowRight, PlayCircle, KeyRound, FileText, Headphones, PictureInPicture2, MonitorUp,
} from "lucide-react";
import * as api from "@/lib/api";
import { useVoice } from "@/lib/useVoice";
import { useAutoListen } from "@/lib/useAutoListen";
import SessionSidebar from "@/components/console/SessionSidebar";
import ContextPanel from "@/components/console/ContextPanel";
import SettingsPanel from "@/components/console/SettingsPanel";
import VoicePanel from "@/components/console/VoicePanel";
import MessageBubble from "@/components/console/MessageBubble";
import AutoListenBar from "@/components/console/AutoListenBar";
import RecapPanel from "@/components/console/RecapPanel";
import FloatingAnswer from "@/components/console/FloatingAnswer";

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
  const [settings, setSettings] = useState({ geminiKey: "", model: "gemini-3.8-flash", provider: "gemini", answerStyle: "complet", tone: "confiant", starMode: true });
  const [creating, setCreating] = useState(false);
  const [showListen, setShowListen] = useState(false);
  const [recap, setRecap] = useState({ open: false, text: "", loading: false });
  const [pipRoot, setPipRoot] = useState(null);
  const pipWinRef = useRef(null);
  const autoQRef = useRef(null);
  const listen = useAutoListen({ onQuestion: (q) => autoQRef.current?.(q) });

  const voice = useVoice();
  const controllerRef = useRef(null);
  const threadRef = useRef(null);
  const fileRef = useRef(null);
  const screenStreamRef = useRef(null);
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
      if (st.provider !== "server" && !st.geminiKey) setSettingsOpen(true);
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

  useEffect(() => () => {
    try { pipWinRef.current?.close(); } catch (e) {}
    try { screenStreamRef.current?.getTracks().forEach((t) => t.stop()); } catch (e) {}
  }, []);

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
      context: { cv: form.cv, poste: form.poste, entreprise: form.entreprise, secteur: form.secteur, atsCv: form.atsCv, score: form.score, gaps: form.gaps, missingKeywords: form.missingKeywords, redFlags: form.redFlags },
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
    setMessages([]);
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
    if (settings.provider !== "server" && !settings.geminiKey) {
      toast.error("Ajoutez une clé Gemini, ou choisissez le mode Serveur dans Réglages");
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
        onFallback: () => {
          toast("Gemini indisponible — bascule automatique sur le mode Serveur", { icon: "🔁", duration: 6000 });
        },
        onAbort: () => setStreaming((s) => ({ ...s, active: false })),
      }
    );
  };

  const submitInput = () => {
    let raw = input;
    let display = cleanDisplay(input) || "(image)";
    if ((pendingMode === "CANDIDAT" || active?.state === "CANDIDAT") && !/\[/.test(input)) {
      raw = "[REPONSE_ORALE] " + input;
      setPendingMode(null);
    }
    send(raw, display, image);
  };

  // Capture the recruiter's shared screen (desktop only) and send the frame to the
  // AI for analysis — psychotechnical tests, MCQs, diagrams shown on screen.
  // The screen stream is kept alive so repeated captures are instant (pick once).
  const captureScreen = async () => {
    if (!active || streaming.active) return;
    if (!navigator.mediaDevices?.getDisplayMedia) {
      toast.error("Capture d'écran indisponible sur cet appareil (ordinateur requis).");
      return;
    }
    try {
      let stream = screenStreamRef.current;
      if (!stream || !stream.active) {
        stream = await navigator.mediaDevices.getDisplayMedia({ video: { frameRate: 1 }, audio: false });
        screenStreamRef.current = stream;
        stream.getVideoTracks()[0].addEventListener("ended", () => { screenStreamRef.current = null; });
      }
      const track = stream.getVideoTracks()[0];
      const video = document.createElement("video");
      video.srcObject = new MediaStream([track]);
      video.muted = true;
      await new Promise((res) => { video.onloadedmetadata = res; });
      await video.play();
      await new Promise((r) => setTimeout(r, 200));
      let w = video.videoWidth || 1280;
      let h = video.videoHeight || 720;
      const maxW = 1600;
      if (w > maxW) { h = Math.round((h * maxW) / w); w = maxW; }
      const canvas = document.createElement("canvas");
      canvas.width = w; canvas.height = h;
      canvas.getContext("2d").drawImage(video, 0, 0, w, h);
      video.pause(); video.srcObject = null;
      const dataUrl = canvas.toDataURL("image/jpeg", 0.85);
      toast.success("Écran capturé — analyse en cours…");
      send("[REPONSE_ORALE] Analyse le test / la question affiché(e) sur l'écran capturé et donne la réponse à dire.", "🖼️ Capture d'écran (test)", dataUrl);
    } catch (e) {
      if (e.name === "NotAllowedError") toast("Capture annulée.");
      else toast.error("Capture impossible : " + (e.message || e.name));
    }
  };

  const lastRecruiterQuestion = [...messages].reverse().find((m) => m.role === "assistant" && m.mode === "RECRUTEUR")?.content;

  // Auto-listen -> generate a candidate answer for the heard question.
  autoQRef.current = (q) => {
    if (!q || streaming.active) return;
    send("[REPONSE_ORALE] " + q, "🎧 " + q);
    listen.clearTranscript();
  };

  const exportTranscript = () => {
    const lines = messages.map((m) => `${m.role === "user" ? "» Vous/Recruteur" : "« " + (m.mode || "IA")}: ${m.content}`);
    const header = `ENTRETIEN — ${active?.title || ""}\nPoste: ${active?.context?.poste || "-"} | Entreprise: ${active?.context?.entreprise || "-"}\n${new Date().toLocaleString("fr-FR")}\n\n`;
    const body = header + lines.join("\n\n") + (recap.text ? "\n\n=== RÉCAPITULATIF ===\n" + recap.text : "");
    const blob = new Blob([body], { type: "text/plain;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url; a.download = `entretien-${(active?.title || "session").replace(/[^a-z0-9_-]+/gi, "_")}.txt`;
    a.click(); URL.revokeObjectURL(url);
  };

  const doRecap = async () => {
    if (!messages.length) { toast("Aucun échange à analyser pour l'instant"); return; }
    setRecap({ open: true, text: "", loading: true });
    const transcript = messages.map((m) => `${m.role === "user" ? "Candidat/Question" : (m.mode || "IA")}: ${m.content}`).join("\n");
    const systemMessage = "Tu es un coach d'entretien senior. À partir de la transcription, rends un récapitulatif clair en français, structuré avec ces sections (en gras): 1) Questions posées, 2) Points forts, 3) Axes d'amélioration, 4) Conseils concrets pour la suite. Sois concis, orienté action, utilise des puces.";
    try {
      await api.streamRaw({
        systemMessage,
        userText: "Voici la transcription de l'entretien :\n\n" + transcript,
        onDelta: (c) => setRecap((r) => ({ ...r, text: r.text + c })),
        onFallback: () => toast("Gemini surchargé — bascule sur le mode Serveur…"),
      });
    } catch (e) {
      toast.error("Récap échoué : " + e.message);
    } finally {
      setRecap((r) => ({ ...r, loading: false }));
    }
  };

  const openFloating = async () => {
    if (!("documentPictureInPicture" in window)) {
      toast.error("Fenêtre flottante non supportée. Utilisez Chrome/Edge récent (v116+).");
      return;
    }
    if (pipWinRef.current) { try { pipWinRef.current.focus(); } catch (e) {} return; }
    try {
      const pip = await window.documentPictureInPicture.requestWindow({ width: 470, height: 340 });
      [...document.styleSheets].forEach((ss) => {
        try {
          const css = [...ss.cssRules].map((r) => r.cssText).join("");
          const st = pip.document.createElement("style");
          st.textContent = css;
          pip.document.head.appendChild(st);
        } catch (e) {
          if (ss.href) {
            const l = pip.document.createElement("link");
            l.rel = "stylesheet"; l.href = ss.href;
            pip.document.head.appendChild(l);
          }
        }
      });
      pip.document.body.style.margin = "0";
      pip.document.body.style.background = "#090a0f";
      const root = pip.document.createElement("div");
      pip.document.body.appendChild(root);
      pip.addEventListener("pagehide", () => { setPipRoot(null); pipWinRef.current = null; listen.stop(); });
      pipWinRef.current = pip;
      setPipRoot(root);
      toast.success("Fenêtre flottante ouverte — glissez-la sous votre caméra 🎥");
    } catch (e) {
      toast.error("Impossible d'ouvrir la fenêtre flottante : " + e.message);
    }
  };

  const state = active?.state || "NEUTRE";

  const liveActive = listen.active || !!pipRoot;
  const startLive = async () => {
    if (liveActive) {
      listen.stop();
      try { pipWinRef.current?.close(); } catch (e) {}
      toast("Mode Live arrêté");
      return;
    }
    if (settings.provider !== "server" && !settings.geminiKey) {
      toast.error("Ajoutez une clé Gemini, ou choisissez le mode Serveur dans Réglages");
      setSettingsOpen(true);
      return;
    }
    try { await listen.start("mic"); } catch (e) { toast.error(e.message); return; }
    await openFloating();
    toast.success("Mode Live activé — parlez : la réponse apparaît dans la fenêtre flottante 🎥");
  };
  const streamMsg = streaming.active ? { role: "assistant", content: streaming.text || "…", mode: streaming.mode, modules: streaming.meta?.modules || [] } : null;

  const lastCandidate = [...messages].reverse().find((m) => m.role === "assistant" && m.mode === "CANDIDAT")?.content;
  const pipContent = streaming.active && streaming.mode === "CANDIDAT" ? streaming.text : lastCandidate;
  const pipMode = streaming.active ? streaming.mode : "CANDIDAT";

  return (
    <div className="command-bg min-h-screen w-full">
      <div className="relative z-10 mx-auto grid min-h-screen max-w-[1600px] grid-cols-1 gap-4 p-4 lg:grid-cols-[260px_1fr_300px]">
        {/* LEFT */}
        <div className="glass hidden rounded-2xl p-4 lg:flex lg:flex-col lg:sticky lg:top-4 lg:self-start lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto">
          <SessionSidebar sessions={sessions} activeId={active?.id} onSelect={selectSession} onNew={handleNew} onDelete={handleDelete} creating={creating} />
        </div>

        {/* CENTER */}
        <div className="glass flex min-h-[80vh] flex-col overflow-hidden rounded-2xl lg:h-[calc(100vh-2rem)] lg:min-h-0">
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
              <button onClick={startLive} data-testid="live-btn"
                className={`flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-bold transition-all ${liveActive ? "border-red-500/50 bg-red-500/20 text-red-300 pulse-ring" : "border-emerald-500/50 bg-emerald-500/15 text-emerald-300 hover:bg-emerald-500/25"}`}>
                <span className={`h-2 w-2 rounded-full ${liveActive ? "bg-red-500 animate-pulse" : "bg-emerald-400"}`} />
                {liveActive ? "Live actif" : "Live"}
              </button>
              <HeaderBtn onClick={openFloating} testid="floating-btn" icon={<PictureInPicture2 className="h-4 w-4" />} label="Flottant" active={!!pipRoot} />
              <HeaderBtn onClick={() => setShowListen((s) => !s)} testid="toggle-listen-btn" icon={<Headphones className="h-4 w-4" />} label="Écoute" active={listen.active} />
              <HeaderBtn onClick={doRecap} testid="recap-btn" icon={<FileText className="h-4 w-4" />} label="Récap" />
              <HeaderBtn onClick={() => setSettingsOpen(true)} testid="open-settings-btn" icon={<KeyRound className="h-4 w-4" />} label="Réglages" active={settings.provider !== "server" && !settings.geminiKey} />
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

          {/* Auto-listen */}
          {showListen && <AutoListenBar listen={listen} onGenerate={(q) => { if (!streaming.active) { send("[REPONSE_ORALE] " + q, "🎧 " + q); listen.clearTranscript(); } }} />}

          {/* Composer */}
          <div className="border-t border-white/[0.06] px-4 py-3">
            <div className="mb-2 flex items-center gap-1.5 font-mono text-[10px] uppercase tracking-widest text-slate-500" data-testid="composer-label">
              <Send className="h-3 w-3 text-indigo-400" /> Votre saisie — tapez ou dictez (micro vert), puis « Envoyer »
            </div>
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
              <button onClick={captureScreen} disabled={streaming.active} data-testid="capture-screen-btn" className="rounded-xl border border-sky-500/30 bg-sky-500/10 p-2.5 text-sky-300 transition-colors hover:bg-sky-500/20 disabled:opacity-40" title="Capturer l'écran partagé du recruteur (test psychotechnique) — ordinateur uniquement">
                <MonitorUp className="h-5 w-5" />
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
                rows={2}
                data-testid="message-input"
                placeholder={state === "RECRUTEUR" ? "Votre réponse au recruteur…" : "Question du recruteur à traiter…"}
                className="min-h-[48px] max-h-40 flex-1 resize-y rounded-xl border border-white/10 bg-black/40 px-4 py-2.5 text-[15px] leading-relaxed text-slate-100 outline-none transition-colors placeholder:text-slate-600 focus:border-indigo-500/60"
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
        <div className="hidden lg:block lg:sticky lg:top-4 lg:self-start lg:max-h-[calc(100vh-2rem)] lg:overflow-y-auto lg:pr-1">
          <VoicePanel metrics={voice.metrics} listening={voice.listening} meta={meta} debug={active?.debug} latency={latency} />
        </div>
      </div>

      <ContextPanel open={ctxOpen} session={active} onClose={() => setCtxOpen(false)} onSave={saveContext} />
      <SettingsPanel open={settingsOpen} settings={settings} onClose={() => setSettingsOpen(false)} onSave={saveSettingsHandler} />
      <RecapPanel open={recap.open} text={recap.text} loading={recap.loading} onClose={() => setRecap((r) => ({ ...r, open: false }))} onExport={exportTranscript} />
      {pipRoot && createPortal(<FloatingAnswer content={pipContent} streaming={streaming.active} mode={pipMode} listening={listen.active} transcript={listen.transcript} />, pipRoot)}
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
