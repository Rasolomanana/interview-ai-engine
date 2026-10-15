import { TriangleAlert } from "lucide-react";
import { KIND_LABEL, QUALITY, qualityOf } from "@/lib/portals";

export const PortalHealth = ({ status, run }) => {
  const portals = Object.entries(run?.portals || {});
  const configured = (status?.portals?.workday || 0) + (status?.portals?.boards || 0);
  const ok = portals.filter(([, p]) => p.ok).length;
  const rate = portals.length ? Math.round((ok * 100) / portals.length) : null;
  const counts = portals.reduce((a, [, p]) => ({ ...a, [qualityOf(p)]: (a[qualityOf(p)] || 0) + 1 }), {});
  return (
    <section className="rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-4" data-testid="radar-portal-health">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-5 gap-y-1">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">Portails employeurs</p>
        <span className="text-xs text-slate-300" data-testid="portal-configured">{configured} configuré(s)</span>
        <span className="text-xs text-slate-300" data-testid="portal-success-rate">Lecture réussie : {rate === null ? "—" : `${ok}/${portals.length} (${rate} %)`}</span>
        <span className="text-xs text-slate-300">Offres : {portals.reduce((a, [, p]) => a + (p.fetched || 0), 0)} lues · {portals.reduce((a, [, p]) => a + (p.matched || 0), 0)} retenues</span>
      </div>
      {portals.length > 0 && (
        <div className="mb-3 flex flex-wrap gap-2" data-testid="portal-quality-summary">
          {Object.entries(QUALITY).map(([k, q]) => (
            <span key={k} className="flex items-center gap-1.5 rounded-full border border-white/[0.07] bg-black/20 px-2.5 py-1 text-[11px] text-slate-300" data-testid={`portal-quality-${k}`}>
              <span className={`h-2 w-2 rounded-full ${q.dot}`} />{q.label} : <b className="text-white">{counts[k] || 0}</b></span>))}
        </div>)}
      {portals.length === 0 ? <p className="text-xs text-slate-500" data-testid="portal-none">Aucun portail lu au dernier passage. Ajoutez des entreprises depuis l'annuaire ou « Trouver le portail » dans les réglages.</p> : (
        <div className="grid gap-1.5 sm:grid-cols-2 lg:grid-cols-3">
          {portals.map(([name, p]) => {
            const q = QUALITY[qualityOf(p)];
            return (
              <div key={name} className="flex items-center gap-2 text-xs" data-testid={`portal-row-${name.replace(/[^a-z0-9]/gi, "-")}`} title={p.error || q.label}>
                <span className={`h-2 w-2 shrink-0 rounded-full ${q.dot}`} />
                <span className="min-w-0 truncate text-slate-200">{name}</span>
                <span className="shrink-0 text-slate-500">{KIND_LABEL[p.kind] || p.kind}</span>
                <span className="ml-auto shrink-0 text-slate-400">{p.ok ? <>{p.fetched} lues · {p.matched ?? 0} retenues{qualityOf(p) === "fragile" && <span className={`ml-1 ${q.text}`}>· fragile</span>}</>
                  : <span className={`flex items-center gap-1 ${q.text}`}><TriangleAlert className="h-3 w-3" />{p.blocked ? "bloqué (anti-robot)" : "échec"} · repli Jooble</span>}</span>
              </div>);
          })}
        </div>)}
    </section>
  );
};
