import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { GeminiDiagnostic } from "./GeminiDiagnostic";
import { X, KeyRound, Cpu, ExternalLink, Save, ShieldCheck, Server, Sparkles, AlignLeft, Drama, ListChecks, Lock } from "lucide-react";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;

const MODELS = [
  { id: "gemini-flash-latest", label: "Gemini Flash (toujours à jour · recommandé)" },
  { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash (rapide · gratuit)" },
  { id: "gemini-3.5-flash", label: "Gemini 3.5 Flash" },
];

const TONES = [
  { id: "confiant", label: "Confiant" },
  { id: "humble", label: "Humble" },
  { id: "technique", label: "Technique" },
  { id: "neutre", label: "Neutre" },
];

export default function SettingsPanel({ open, settings, onClose, onSave }) {
  const [provider, setProvider] = useState("gemini");
  const [key, setKey] = useState("");
  const [model, setModel] = useState("gemini-flash-latest");
  const [answerStyle, setAnswerStyle] = useState("complet");
  const [tone, setTone] = useState("confiant");
  const [starMode, setStarMode] = useState(true);
  const [askServerPwd, setAskServerPwd] = useState(false);
  const [serverPwd, setServerPwd] = useState("");
  const [serverPwdError, setServerPwdError] = useState("");
  const [verifying, setVerifying] = useState(false);

  useEffect(() => {
    if (open) {
      setProvider(settings?.provider || "gemini");
      setKey(settings?.geminiKey || "");
      setModel(settings?.model || "gemini-flash-latest");
      setAnswerStyle(settings?.answerStyle || "complet");
      setTone(settings?.tone || "confiant");
      setStarMode(settings?.starMode !== false);
      setAskServerPwd(false);
      setServerPwd("");
      setServerPwdError("");
    }
  }, [open, settings]);

  // Manual Server selection is password-gated (protects paid credits). The
  // automatic Gemini->Server fallback lives in lib/api.js and is NOT affected.
  const handleSelectServer = () => {
    if (localStorage.getItem("serverAccessGranted") === "true") {
      setProvider("server");
      setAskServerPwd(false);
    } else {
      setAskServerPwd(true);
      setServerPwdError("");
    }
  };

  const submitServerPwd = async () => {
    setVerifying(true);
    setServerPwdError("");
    try {
      const resp = await fetch(`${BACKEND_URL}/api/verify-server-access`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ password: serverPwd }),
      });
      if (!resp.ok) throw new Error("bad");
      const data = await resp.json();
      if (!data.success) throw new Error("bad");
      localStorage.setItem("serverAccessGranted", "true");
      setProvider("server");
      setAskServerPwd(false);
      setServerPwd("");
    } catch {
      setServerPwdError("Mot de passe incorrect — vous restez en mode Gemini.");
      setProvider("gemini");
    } finally {
      setVerifying(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 24, scale: 0.97 }}
            className="glass relative z-10 flex max-h-[90vh] w-full max-w-lg flex-col overflow-hidden rounded-2xl" data-testid="settings-panel"
          >
            <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
              <div>
                <h2 className="font-display text-lg font-bold text-white">Réglages IA</h2>
                <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">Choisissez comment l'IA est appelée</p>
              </div>
              <button onClick={onClose} data-testid="settings-close-btn" className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white"><X className="h-5 w-5" /></button>
            </div>

            <div className="space-y-5 overflow-y-auto px-6 py-5">
              {/* Provider choice */}
              <div>
                <label className="mb-2 block font-mono text-[11px] uppercase tracking-widest text-slate-400">Fournisseur IA</label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <button
                    data-testid="provider-gemini"
                    onClick={() => setProvider("gemini")}
                    className={`flex items-start gap-2.5 rounded-xl border p-3 text-left transition-all ${provider === "gemini" ? "border-emerald-500/60 bg-emerald-500/10" : "border-white/10 bg-white/[0.03] hover:border-white/20"}`}
                  >
                    <Sparkles className={`mt-0.5 h-4 w-4 shrink-0 ${provider === "gemini" ? "text-emerald-400" : "text-slate-400"}`} />
                    <div>
                      <p className={`text-sm font-semibold ${provider === "gemini" ? "text-emerald-200" : "text-slate-200"}`}>Gemini (gratuit)</p>
                      <p className="text-[11px] text-slate-400">Votre clé Google. 100% local.</p>
                    </div>
                  </button>
                  <button
                    data-testid="provider-server"
                    onClick={handleSelectServer}
                    className={`flex items-start gap-2.5 rounded-xl border p-3 text-left transition-all ${provider === "server" ? "border-indigo-500/60 bg-indigo-500/10" : "border-white/10 bg-white/[0.03] hover:border-white/20"}`}
                  >
                    <Server className={`mt-0.5 h-4 w-4 shrink-0 ${provider === "server" ? "text-indigo-400" : "text-slate-400"}`} />
                    <div>
                      <p className={`text-sm font-semibold ${provider === "server" ? "text-indigo-200" : "text-slate-200"}`}>Serveur</p>
                      <p className="text-[11px] text-slate-400">Sans clé. Marche si Google est bloqué.</p>
                    </div>
                  </button>
                </div>
              </div>

              {askServerPwd && provider !== "server" && (
                <div data-testid="server-password-form" className="rounded-xl border border-amber-500/30 bg-amber-950/20 p-3">
                  <label className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-amber-300/90">
                    <Lock className="h-4 w-4" /> Mot de passe requis pour le mode Serveur
                  </label>
                  <p className="mb-2 text-[11px] text-amber-200/70">Le mode Serveur consomme des crédits payants. Entrez le mot de passe pour l'activer manuellement.</p>
                  <div className="flex gap-2">
                    <input
                      type="password"
                      data-testid="server-password-input"
                      value={serverPwd}
                      onChange={(e) => setServerPwd(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter" && serverPwd && !verifying) submitServerPwd(); }}
                      placeholder="Mot de passe"
                      className="flex-1 rounded-xl border border-white/10 bg-black/50 px-4 py-2.5 font-mono text-sm text-slate-100 outline-none focus:border-amber-500/60"
                    />
                    <button
                      data-testid="server-password-submit"
                      onClick={submitServerPwd}
                      disabled={verifying || !serverPwd}
                      className="shrink-0 rounded-xl bg-amber-500 px-4 py-2 text-sm font-semibold text-black hover:bg-amber-400 disabled:opacity-50"
                    >
                      {verifying ? "Vérification…" : "Déverrouiller"}
                    </button>
                  </div>
                  {serverPwdError && <p data-testid="server-password-error" className="mt-2 text-xs text-red-400">{serverPwdError}</p>}
                </div>
              )}

              {provider === "gemini" ? (
                <>
                  <div>
                    <label className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-slate-400">
                      <KeyRound className="h-4 w-4 text-indigo-400" /> Clé API Google Gemini
                    </label>
                    <input
                      type="password" data-testid="gemini-key-input" value={key} onChange={(e) => setKey(e.target.value)}
                      placeholder="Collez votre clé (AIza... ou AQ...)"
                      className="w-full rounded-xl border border-white/10 bg-black/50 px-4 py-2.5 font-mono text-sm text-slate-100 outline-none focus:border-indigo-500/60"
                    />
                    <a href="https://aistudio.google.com/app/apikey" target="_blank" rel="noreferrer" className="mt-2 inline-flex items-center gap-1.5 text-xs text-indigo-300 hover:text-indigo-200">
                      <ExternalLink className="h-3.5 w-3.5" /> Obtenir une clé gratuite (Google AI Studio)
                    </a>
                  </div>

                  <div>
                    <label className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-slate-400">
                      <Cpu className="h-4 w-4 text-indigo-400" /> Modèle
                    </label>
                    <div className="flex flex-col gap-2">
                      {MODELS.map((m) => (
                        <button key={m.id} data-testid={`model-${m.id}`} onClick={() => setModel(m.id)}
                          className={`rounded-xl border px-3 py-2 text-left text-sm transition-all ${model === m.id ? "border-indigo-500/60 bg-indigo-500/15 text-indigo-100" : "border-white/10 bg-white/[0.03] text-slate-400 hover:text-white"}`}>
                          {m.label}
                        </button>
                      ))}
                    </div>
                  </div>

                  <GeminiDiagnostic apiKey={key.trim()} model={model} />

                  <div className="flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-950/20 px-3 py-2.5 text-xs text-emerald-200/80">
                    <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                    Votre clé est stockée uniquement dans ce navigateur et n'est transmise qu'à Google.
                  </div>
                </>
              ) : (
                <div className="flex items-start gap-2 rounded-xl border border-indigo-500/20 bg-indigo-950/20 px-3 py-3 text-xs text-indigo-200/80">
                  <Server className="mt-0.5 h-4 w-4 shrink-0 text-indigo-400" />
                  <span>Mode Serveur : aucune clé requise. Votre navigateur parle uniquement à l'application (pas à Google), idéal si un pare-feu d'entreprise bloque l'API Google Gemini.</span>
                </div>
              )}
              {/* Answer style */}
              <div>
                <label className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-slate-400">
                  <AlignLeft className="h-4 w-4 text-indigo-400" /> Style des réponses (mode Candidat)
                </label>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                  <button data-testid="answer-complet" onClick={() => setAnswerStyle("complet")}
                    className={`rounded-xl border p-3 text-left transition-all ${answerStyle === "complet" ? "border-emerald-500/60 bg-emerald-500/10" : "border-white/10 bg-white/[0.03] hover:border-white/20"}`}>
                    <p className={`text-sm font-semibold ${answerStyle === "complet" ? "text-emerald-200" : "text-slate-200"}`}>Phrases complètes</p>
                    <p className="text-[11px] text-slate-400">À lire à voix haute, sans réfléchir.</p>
                  </button>
                  <button data-testid="answer-concis" onClick={() => setAnswerStyle("concis")}
                    className={`rounded-xl border p-3 text-left transition-all ${answerStyle === "concis" ? "border-indigo-500/60 bg-indigo-500/10" : "border-white/10 bg-white/[0.03] hover:border-white/20"}`}>
                    <p className={`text-sm font-semibold ${answerStyle === "concis" ? "text-indigo-200" : "text-slate-200"}`}>Télégraphique</p>
                    <p className="text-[11px] text-slate-400">Puces ultra-courtes (≤ 12 mots).</p>
                  </button>
                </div>
              </div>

              {/* Tone */}
              <div>
                <label className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-slate-400">
                  <Drama className="h-4 w-4 text-indigo-400" /> Ton des réponses
                </label>
                <div className="flex flex-wrap gap-2">
                  {TONES.map((t) => (
                    <button key={t.id} data-testid={`tone-${t.id}`} onClick={() => setTone(t.id)}
                      className={`rounded-lg border px-3 py-1.5 text-sm transition-all ${tone === t.id ? "border-indigo-500/60 bg-indigo-500/15 text-indigo-100" : "border-white/10 bg-white/[0.03] text-slate-400 hover:text-white"}`}>
                      {t.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* STAR method */}
              <div>
                <label className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-slate-400">
                  <ListChecks className="h-4 w-4 text-indigo-400" /> Méthode STAR
                </label>
                <button
                  data-testid="star-toggle"
                  onClick={() => setStarMode((v) => !v)}
                  className={`flex w-full items-center justify-between gap-3 rounded-xl border p-3 text-left transition-all ${starMode ? "border-emerald-500/60 bg-emerald-500/10" : "border-white/10 bg-white/[0.03] hover:border-white/20"}`}
                >
                  <span>
                    <span className={`block text-sm font-semibold ${starMode ? "text-emerald-200" : "text-slate-200"}`}>Structurer les questions comportementales</span>
                    <span className="block text-[11px] text-slate-400">Situation · Tâche · Action · Résultat (uniquement si la question demande un exemple vécu)</span>
                  </span>
                  <span className={`relative h-6 w-11 shrink-0 rounded-full transition-colors ${starMode ? "bg-emerald-500" : "bg-slate-600"}`}>
                    <span className={`absolute top-0.5 h-5 w-5 rounded-full bg-white transition-all ${starMode ? "left-[22px]" : "left-0.5"}`} />
                  </span>
                </button>
              </div>
            </div>

            <div className="flex justify-end gap-3 border-t border-white/[0.06] px-6 py-4">
              <button onClick={onClose} className="rounded-xl px-4 py-2 text-sm text-slate-400 hover:text-white">Fermer</button>
              <button onClick={() => onSave({ provider, geminiKey: key.trim(), model, answerStyle, tone, starMode })} data-testid="settings-save-btn" className="flex items-center gap-2 rounded-xl bg-indigo-500 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 hover:bg-indigo-400">
                <Save className="h-4 w-4" /> Enregistrer
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
