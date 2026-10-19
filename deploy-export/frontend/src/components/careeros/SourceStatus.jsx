import { InfoTip } from "@/components/careeros/guide/InfoTip";
import { Num } from "@/components/careeros/RadarHistory";

export const SOURCES = [["jooble", "Jooble"], ["workday", "Workday"], ["boards", "Sites carrières"], ["adzuna", "Adzuna"]];

const state = (k, status) => {
  if (!status?.configured?.[k]) return { dot: "bg-amber-400", label: "Non configuré" };
  if (!status.selected?.includes(k)) return { dot: "bg-slate-500", label: "Désactivé" };
  if (status?.portals && k in status.portals && !status.portals[k]) return { dot: "bg-slate-500", label: "Aucun portail configuré" };
  return { dot: "bg-emerald-400", label: "Actif" };
};

export const SourceStatus = ({ status, run, active, onPick }) => (
  <section className="rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-4" data-testid="radar-source-status">
    <p className="mb-2 flex items-center font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">Sources<InfoTip k="sources" /></p>
    <div className="overflow-x-auto">
      <table className="w-full text-left text-xs" data-testid="radar-source-table">
        <thead className="text-slate-500"><tr><th className="py-1.5 pr-3 font-medium">Source</th><th className="pr-3 font-medium">Statut</th><th className="pr-3 text-right font-medium">Trouvées</th><th className="text-right font-medium">Analysées</th></tr></thead>
        <tbody>
          {SOURCES.filter(([k]) => status?.configured?.[k]).map(([k, l]) => {
            const s = state(k, status);
            const n = run?.by_source?.[k];
            return (
              <tr key={k} className={`border-t border-white/[0.05] ${active === k ? "bg-indigo-500/10" : ""}`} data-testid={`radar-source-status-${k}`}>
                <td className="py-2 pr-3"><span className="flex items-center gap-2 font-medium text-slate-200"><span className={`h-2.5 w-2.5 rounded-full ${s.dot}`} />{l}</span></td>
                <td className="pr-3 text-slate-400">{s.label}</td>
                <td className="pr-3 text-right"><Num n={n?.fetched || 0} onClick={() => onPick?.(k)} testid={`radar-source-count-${k}`} /></td>
                <td className="text-right"><Num n={n?.analyzed || 0} onClick={() => onPick?.(`a_${k}`)} testid={`radar-source-analyzed-${k}`} /></td>
              </tr>);
          })}
        </tbody>
      </table>
    </div>
    {run && <p className="mt-2 border-t border-white/[0.06] pt-2 text-xs text-slate-300" data-testid="radar-source-total">
      Total : <Num n={run.analyzed ?? 0} onClick={() => onPick?.("a_all")} testid="radar-source-total-analyzed" /> offres analysées sur <Num n={run.fetched ?? 0} onClick={() => onPick?.("all")} testid="radar-source-total-found" /> trouvées · cliquez un chiffre pour afficher les offres</p>}
  </section>
);
