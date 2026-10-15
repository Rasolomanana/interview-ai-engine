import { adminInsights } from "@/lib/api";
import { useTrace } from "@/components/admin/TraceDialog";
import { Kpi, RankList, Spinner, fmt, panel, pwd, useAdminData } from "./ui";

const TONE = { A: "text-emerald-300", B: "text-amber-300", C: "text-slate-300" };

export const Business = () => {
  const [traceNode, trace] = useTrace();
  const d = useAdminData(() => adminInsights(pwd(), "business"));
  if (!d) return <Spinner />;
  const pick = (metric) => (r) => trace(metric, r.label);
  return (
    <div className="space-y-4" data-testid="admin-business">
      {traceNode}
      <p className="text-[11px] text-slate-500">{d.note}</p>
      <section className={panel}>
        <h3 className="mb-3 text-sm font-semibold text-slate-200">Offres analysées et priorités</h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
          <Kpi label="Analysées (30 j)" value={fmt(d.offers.analyzed_30d)} testid="biz-analyzed30" onClick={() => trace("b_offers30")} />
          <Kpi label="Analysées (total)" value={fmt(d.offers.analyzed_total)} testid="biz-analyzed-total" onClick={() => trace("b_offers_total")} />
          {["A", "B", "C"].map((p) => <Kpi key={`r${p}`} label={`Radar · priorité ${p}`} value={fmt(d.priorities.radar_30d[p])} tone={TONE[p]} testid={`biz-radar-${p}`} onClick={() => trace("b_prio_radar", p)} />)}
          {["A", "B", "C"].map((p) => <Kpi key={`a${p}`} label={`Candidatures · ${p}`} value={fmt(d.priorities.applications[p])} tone={TONE[p]} testid={`biz-apps-${p}`} onClick={() => trace("b_prio_apps", p)} />)}
        </div>
      </section>
      <div className="grid gap-4 lg:grid-cols-3">
        <RankList title="Postes les plus recherchés" rows={d.roles} testid="biz-roles" onPick={pick("b_role")} />
        <RankList title="Entreprises les plus suivies" rows={d.companies} testid="biz-companies" onPick={pick("b_company")} />
        <RankList title="Portails les plus utilisés" rows={d.portals} testid="biz-portals" onPick={pick("b_portal")} />
        <RankList title="Offres analysées par source (30 j)" rows={d.offers.by_source} testid="biz-sources" onPick={pick("b_source")} />
      </div>
    </div>
  );
};
