import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, KeyRound, Cpu, ExternalLink, Save, ShieldCheck, Server, Sparkles, AlignLeft, Drama } from "lucide-react";

const MODELS = [
  { id: "gemini-3.8-flash", label: "Gemini 3.8 Flash (rapide · gratuit)" },
  { id: "gemini-flash-latest", label: "Gemini Flash (toujours à jour)" },
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
  const [model, setModel] = useState("gemini-3.8-flash");
  const [answerStyle, setAnswerStyle] = useState("complet");
  const [tone, setTone] = useState("confiant");

  useEffect(() => {
    if (open) {
      setProvider(settings?.provider || "gemini");
      setKey(settings?.geminiKey || "");
      setModel(settings?.model || "gemini-3.8-flash");
      setAnswerStyle(settings?.answerStyle || "complet");
      setTone(settings?.tone || "confiant");
    }
  }, [open, settings]);

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
                    onClick={() => setProvider("server")}
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
            </div>

            <div className="flex justify-end gap-3 border-t border-white/[0.06] px-6 py-4">
              <button onClick={onClose} className="rounded-xl px-4 py-2 text-sm text-slate-400 hover:text-white">Fermer</button>
              <button onClick={() => onSave({ provider, geminiKey: key.trim(), model, answerStyle, tone })} data-testid="settings-save-btn" className="flex items-center gap-2 rounded-xl bg-indigo-500 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 hover:bg-indigo-400">
                <Save className="h-4 w-4" /> Enregistrer
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
