import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";

export const panel = "min-w-0 rounded-2xl border border-white/10 bg-slate-900/60 p-4 sm:p-5";
export const fmt = (n) => (Number(n) || 0).toLocaleString("fr-CA");
export const pwd = () => sessionStorage.getItem("adminPwd");

export const useAdminData = (fn, deps = []) => {
  const [d, setD] = useState(null);
  useEffect(() => { setD(null); fn().then(setD).catch((e) => toast.error(e.message)); }, deps); // eslint-disable-line react-hooks/exhaustive-deps
  return d;
};

export const Spinner = () => <Loader2 className="h-5 w-5 animate-spin text-emerald-400" />;

// Clickable, keyboard-accessible KPI card.
export const Kpi = ({ label, value, sub, onClick, testid, tone = "text-white" }) => (
  <div role="button" tabIndex={0} onClick={onClick} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick?.(); } }}
    className="cursor-pointer rounded-xl border border-white/10 bg-black/20 p-3 transition-colors hover:border-emerald-400/40 focus:border-emerald-400/60 focus:outline-none" data-testid={testid} title="Afficher le détail">
    <p className="text-[11px] text-slate-500">{label}</p>
    <p className={`font-mono text-2xl font-bold underline decoration-white/15 underline-offset-4 ${tone}`}>{value}</p>
    {sub && <p className="text-[10px] text-slate-500">{sub}</p>}
  </div>
);

// Ranked horizontal bars; each row opens its detail.
export const RankList = ({ title, rows, testid, onPick, unit = "membre(s)" }) => {
  const max = Math.max(1, ...rows.map((r) => r.count));
  return (
    <section className={panel} data-testid={testid}>
      <h3 className="mb-3 text-sm font-semibold text-slate-200">{title}</h3>
      {rows.length === 0 ? <p className="text-xs text-slate-500">Aucune donnée pour l'instant.</p> : (
        <ul className="space-y-1.5">{rows.map((r, i) => (
          <li key={r.label}>
            <button type="button" onClick={() => onPick?.(r)} className="group flex w-full items-center gap-2 text-left text-[12px]" data-testid={`${testid}-row-${i}`}>
              <span className="w-40 shrink-0 truncate text-slate-300 group-hover:text-white sm:w-56" title={r.label}>{r.label}</span>
              <span className="h-3 flex-1 overflow-hidden rounded bg-black/40"><span className="block h-full rounded bg-emerald-500/70" style={{ width: `${(r.count / max) * 100}%` }} /></span>
              <span className="w-12 text-right font-mono text-white underline decoration-white/20 underline-offset-2">{fmt(r.count)}</span>
            </button>
          </li>))}
        </ul>)}
      <span className="sr-only">{unit}</span>
    </section>
  );
};
