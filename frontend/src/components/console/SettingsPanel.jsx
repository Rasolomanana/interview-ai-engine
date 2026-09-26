import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, KeyRound, Cpu, ExternalLink, Save, ShieldCheck } from "lucide-react";

const MODELS = [
  { id: "gemini-2.5-flash", label: "Gemini 2.5 Flash (rapide · gratuit)" },
  { id: "gemini-2.5-pro", label: "Gemini 2.5 Pro (qualité max)" },
  { id: "gemini-2.0-flash", label: "Gemini 2.0 Flash" },
];

export default function SettingsPanel({ open, settings, onClose, onSave }) {
  const [key, setKey] = useState("");
  const [model, setModel] = useState("gemini-2.5-flash");

  useEffect(() => {
    if (open) {
      setKey(settings?.geminiKey || "");
      setModel(settings?.model || "gemini-2.5-flash");
    }
  }, [open, settings]);

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 24, scale: 0.97 }}
            className="glass relative z-10 w-full max-w-lg overflow-hidden rounded-2xl" data-testid="settings-panel"
          >
            <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
              <div>
                <h2 className="font-display text-lg font-bold text-white">Réglages IA</h2>
                <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">100% local · aucune donnée envoyée à un serveur tiers</p>
              </div>
              <button onClick={onClose} data-testid="settings-close-btn" className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white"><X className="h-5 w-5" /></button>
            </div>

            <div className="space-y-5 px-6 py-5">
              <div>
                <label className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-slate-400">
                  <KeyRound className="h-4 w-4 text-indigo-400" /> Clé API Google Gemini
                </label>
                <input
                  type="password"
                  data-testid="gemini-key-input"
                  value={key}
                  onChange={(e) => setKey(e.target.value)}
                  placeholder="Collez votre clé AIza..."
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
                    <button
                      key={m.id}
                      data-testid={`model-${m.id}`}
                      onClick={() => setModel(m.id)}
                      className={`rounded-xl border px-3 py-2 text-left text-sm transition-all ${model === m.id ? "border-indigo-500/60 bg-indigo-500/15 text-indigo-100" : "border-white/10 bg-white/[0.03] text-slate-400 hover:text-white"}`}
                    >
                      {m.label}
                    </button>
                  ))}
                </div>
              </div>

              <div className="flex items-start gap-2 rounded-xl border border-emerald-500/20 bg-emerald-950/20 px-3 py-2.5 text-xs text-emerald-200/80">
                <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-emerald-400" />
                Votre clé est stockée uniquement dans ce navigateur (chrome.storage) et n'est jamais transmise ailleurs qu'à Google.
              </div>
            </div>

            <div className="flex justify-end gap-3 border-t border-white/[0.06] px-6 py-4">
              <button onClick={onClose} className="rounded-xl px-4 py-2 text-sm text-slate-400 hover:text-white">Fermer</button>
              <button onClick={() => onSave({ geminiKey: key.trim(), model })} data-testid="settings-save-btn" className="flex items-center gap-2 rounded-xl bg-indigo-500 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 hover:bg-indigo-400">
                <Save className="h-4 w-4" /> Enregistrer
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
