import { motion, AnimatePresence } from "framer-motion";
import { X, FileText, Copy, Download, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";

export default function RecapPanel({ open, text, loading, onClose, onExport }) {
  const copy = () => { navigator.clipboard?.writeText(text || ""); toast.success("Récap copié"); };
  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.97 }} animate={{ opacity: 1, y: 0, scale: 1 }} exit={{ opacity: 0, y: 24, scale: 0.97 }}
            className="glass relative z-10 flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl" data-testid="recap-panel"
          >
            <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
              <div>
                <h2 className="flex items-center gap-2 font-display text-lg font-bold text-white"><Sparkles className="h-5 w-5 text-indigo-400" /> Récapitulatif de l'entretien</h2>
                <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">Bilan · points forts · axes d'amélioration</p>
              </div>
              <button onClick={onClose} data-testid="recap-close-btn" className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white"><X className="h-5 w-5" /></button>
            </div>

            <div className="flex-1 overflow-y-auto px-6 py-5">
              {loading && !text && (
                <div className="flex items-center gap-2 text-slate-400"><Loader2 className="h-4 w-4 animate-spin" /> Analyse de l'entretien…</div>
              )}
              <pre className="whitespace-pre-wrap font-sans text-sm leading-relaxed text-slate-200" data-testid="recap-text">{text}</pre>
              {loading && text && <span className="caret h-4" />}
            </div>

            <div className="flex flex-wrap justify-end gap-3 border-t border-white/[0.06] px-6 py-4">
              <button onClick={onExport} data-testid="recap-export-btn" className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-slate-300 hover:text-white">
                <Download className="h-4 w-4" /> Exporter l'entretien (.txt)
              </button>
              <button onClick={copy} className="flex items-center gap-2 rounded-xl border border-white/10 bg-white/[0.03] px-4 py-2 text-sm text-slate-300 hover:text-white">
                <Copy className="h-4 w-4" /> Copier
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
