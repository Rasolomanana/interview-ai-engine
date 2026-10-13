export const SOURCES = [["jooble", "Jooble"], ["workday", "Workday"], ["boards", "Sites carrières"], ["adzuna", "Adzuna"]];

const state = (k, status) => {
  if (!status?.configured?.[k]) return { dot: "bg-amber-400", label: "Non configuré" };
  if (!status.selected?.includes(k)) return { dot: "bg-slate-500", label: "Désactivé" };
  return { dot: "bg-emerald-400", label: "Actif" };
};

export const SourceStatus = ({ status, run }) => (
  <section className="rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-4" data-testid="radar-source-status">
    <p className="mb-3 font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">Sources</p>
    <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4">
      {SOURCES.map(([k, l]) => {
        const s = state(k, status);
        const n = run?.by_source?.[k];
        return (
          <div key={k} className="flex items-center gap-2 text-sm" data-testid={`radar-source-status-${k}`}>
            <span className={`h-2.5 w-2.5 rounded-full ${s.dot}`} />
            <span className="font-medium text-slate-200">{l}</span>
            <span className="text-xs text-slate-400" data-testid={`radar-source-count-${k}`}>
              {s.label !== "Actif" ? s.label : status?.portals && k in status.portals && !status.portals[k] ? "Aucun portail configuré" : `${n?.fetched ?? 0} offres`}</span>
          </div>
        );
      })}
    </div>
    {run && <p className="mt-3 border-t border-white/[0.06] pt-3 text-xs text-slate-300" data-testid="radar-source-total">
      Total : <b>{run.analyzed ?? 0}</b> offres analysées sur {run.fetched ?? 0} trouvées</p>}
  </section>
);
