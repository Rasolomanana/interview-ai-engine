import { TriangleAlert } from "lucide-react";

const LABEL = { workday: "Workday", successfactors: "SuccessFactors", oracle: "Oracle Recruiting", icims: "iCIMS", greenhouse: "Greenhouse", lever: "Lever", ashby: "Ashby", smartrecruiters: "SmartRecruiters", amazon: "amazon.jobs" };

export const PortalHealth = ({ status, run }) => {
  const portals = Object.entries(run?.portals || {});
  const configured = (status?.portals?.workday || 0) + (status?.portals?.boards || 0);
  const ok = portals.filter(([, p]) => p.ok).length;
  const rate = portals.length ? Math.round((ok * 100) / portals.length) : null;
  return (
    <section className="rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-4" data-testid="radar-portal-health">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-5 gap-y-1">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">Portails employeurs</p>
        <span className="text-xs text-slate-300" data-testid="portal-configured">{configured} configuré(s)</span>
        <span className="text-xs text-slate-300" data-testid="portal-success-rate">Lecture réussie : {rate === null ? "—" : `${ok}/${portals.length} (${rate} %)`}</span>
        <span className="text-xs text-slate-300">Offres : {portals.reduce((a, [, p]) => a + (p.fetched || 0), 0)} lues · {portals.reduce((a, [, p]) => a + (p.matched || 0), 0)} retenues</span>
      </div>
      {portals.length === 0 ? <p className="text-xs text-slate-500" data-testid="portal-none">Aucun portail lu au dernier passage. Ajoutez des entreprises depuis l'annuaire ou « Trouver le portail » dans les réglages.</p> : (
        <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
          {portals.map(([name, p]) => (
            <div key={name} className="flex items-center gap-2 text-xs" data-testid={`portal-row-${name.replace(/[^a-z0-9]/gi, "-")}`} title={p.error || ""}>
              <span className={`h-2 w-2 shrink-0 rounded-full ${p.ok ? "bg-emerald-400" : "bg-amber-400"}`} />
              <span className="min-w-0 truncate text-slate-200">{name}</span>
              <span className="shrink-0 text-slate-500">{LABEL[p.kind] || p.kind}</span>
              <span className="ml-auto shrink-0 text-slate-400">{p.ok ? `${p.fetched} lues · ${p.matched ?? 0} retenues` : <span className="flex items-center gap-1 text-amber-300"><TriangleAlert className="h-3 w-3" />échec · repli Jooble</span>}</span>
            </div>))}
        </div>)}
    </section>
  );
};
