import { Filter, X } from "lucide-react";

export const StatFilter = ({ label, value, testid, active, onClick }) => (
  <button type="button" onClick={onClick} data-testid={testid} aria-pressed={active} title={active ? "Retirer le filtre" : "Filtrer la liste"}
    className={`group rounded-2xl border p-4 text-left transition-[border-color,background-color,transform] hover:-translate-y-0.5 ${active ? "border-indigo-400/60 bg-indigo-500/10" : "border-white/[0.07] bg-[#121520] hover:border-indigo-400/30"}`}>
    <p className="flex items-start justify-between gap-2 font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">
      <span>{label}</span>
      {active ? <X className="h-3.5 w-3.5 shrink-0 text-indigo-300" /> : <Filter className="h-3.5 w-3.5 shrink-0 opacity-0 transition-opacity group-hover:opacity-100" />}
    </p>
    <p className="mt-1 font-display text-2xl font-bold text-white sm:text-3xl">{value}</p>
  </button>
);

export const FilterBanner = ({ label, count, onClear, testid }) => (
  <div className="flex items-center justify-between gap-3 rounded-xl border border-indigo-400/30 bg-indigo-500/10 px-4 py-2.5 text-sm text-indigo-100" data-testid={testid}>
    <span className="flex items-center gap-2"><Filter className="h-4 w-4" />Filtre : <strong>{label}</strong> ({count})</span>
    <button type="button" onClick={onClear} data-testid={`${testid}-clear`} className="flex items-center gap-1 rounded-full px-3 py-1 text-xs hover:bg-white/10"><X className="h-3.5 w-3.5" />Tout afficher</button>
  </div>
);
