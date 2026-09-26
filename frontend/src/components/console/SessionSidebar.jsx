import { useState } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { Plus, Trash2, MessagesSquare, Loader2 } from "lucide-react";

const MODE_DOT = {
  NEUTRE: "bg-slate-500",
  CANDIDAT: "bg-emerald-400",
  RECRUTEUR: "bg-violet-400",
};

export default function SessionSidebar({ sessions, activeId, onSelect, onNew, onDelete, creating }) {
  const [open, setOpen] = useState(true);
  return (
    <aside className="flex h-full flex-col gap-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-indigo-500 to-emerald-500 text-white shadow-lg shadow-indigo-500/20">
            <MessagesSquare className="h-4 w-4" />
          </div>
          <div>
            <p className="font-display text-sm font-bold leading-none text-white">Copilote</p>
            <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">Entretien IA v4</p>
          </div>
        </div>
      </div>

      <button
        onClick={onNew}
        disabled={creating}
        data-testid="new-session-btn"
        className="group flex items-center justify-center gap-2 rounded-xl border border-indigo-500/40 bg-indigo-500/10 px-4 py-2.5 text-sm font-semibold text-indigo-200 transition-all hover:bg-indigo-500/20 hover:border-indigo-400/60 disabled:opacity-50"
      >
        {creating ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4 transition-transform group-hover:rotate-90" />}
        Nouvelle session
      </button>

      <div className="flex items-center justify-between px-1">
        <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">Historique</span>
        <span className="font-mono text-[10px] text-slate-600">{sessions.length}</span>
      </div>

      <div className="flex-1 space-y-1.5 overflow-y-auto pr-1">
        <AnimatePresence initial={false}>
          {sessions.map((s) => (
            <motion.div
              key={s.id}
              layout
              initial={{ opacity: 0, y: 6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0, x: -12 }}
              onClick={() => onSelect(s.id)}
              data-testid={`session-item-${s.id}`}
              className={`group cursor-pointer rounded-xl border px-3 py-2.5 transition-all ${
                activeId === s.id
                  ? "border-indigo-500/50 bg-indigo-500/10"
                  : "border-white/[0.05] bg-[#12151f]/60 hover:border-white/10 hover:bg-[#1a1e2e]/70"
              }`}
            >
              <div className="flex items-center justify-between gap-2">
                <div className="flex min-w-0 items-center gap-2">
                  <span className={`h-2 w-2 shrink-0 rounded-full ${MODE_DOT[s.state] || "bg-slate-500"}`} />
                  <span className="truncate text-sm font-medium text-slate-200">{s.title}</span>
                </div>
                <button
                  onClick={(e) => { e.stopPropagation(); onDelete(s.id); }}
                  data-testid={`delete-session-${s.id}`}
                  className="opacity-0 transition-opacity group-hover:opacity-100"
                >
                  <Trash2 className="h-3.5 w-3.5 text-slate-500 hover:text-red-400" />
                </button>
              </div>
              <p className="mt-1 truncate pl-4 font-mono text-[10px] text-slate-500">
                {s.context?.poste || "Poste non défini"} · {s.state}
              </p>
            </motion.div>
          ))}
        </AnimatePresence>
        {sessions.length === 0 && (
          <p className="px-2 py-6 text-center text-xs text-slate-600">Aucune session. Créez-en une pour commencer.</p>
        )}
      </div>
    </aside>
  );
}
