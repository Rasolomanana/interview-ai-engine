import { useState } from "react";
import { adminInsights } from "@/lib/api";
import { DetailDialog } from "@/components/admin/DetailDialog";
import { Kpi, RankList, Spinner, fmt, panel, pwd, useAdminData } from "./ui";

const TONE = { A: "text-emerald-300", B: "text-amber-300", C: "text-slate-300" };

export const Business = () => {
  const [detail, setDetail] = useState(null);
  const d = useAdminData(() => adminInsights(pwd(), "business"));
  if (!d) return <Spinner />;
  const pick = (what, unit) => (r) => setDetail({ title: `${what} · ${r.label}`, cols: [["k", "Élément"], ["v", "Valeur"]], rows: [{ k: unit, v: r.count }], note: d.note });
  const prio = (src, label) => setDetail({ title: `Priorités · ${label}`, cols: [["p", "Priorité"], ["n", "Nombre"]], rows: ["A", "B", "C"].map((p) => ({ p, n: src[p] })) });
  return (
    <div className="space-y-4" data-testid="admin-business">
      <DetailDialog detail={detail} onClose={() => setDetail(null)} />
      <p className="text-[11px] text-slate-500">{d.note}</p>
      <section className={panel}>
        <h3 className="mb-3 text-sm font-semibold text-slate-200">Offres analysées et priorités</h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-8">
          <Kpi label="Analysées (30 j)" value={fmt(d.offers.analyzed_30d)} testid="biz-analyzed30" onClick={() => setDetail({ title: "Offres analysées par source (30 j)", cols: [["label", "Source"], ["count", "Offres"]], rows: d.offers.by_source })} />
          <Kpi label="Analysées (total)" value={fmt(d.offers.analyzed_total)} testid="biz-analyzed-total" onClick={() => setDetail({ title: "Offres analysées par source (30 j)", cols: [["label", "Source"], ["count", "Offres"]], rows: d.offers.by_source })} />
          {["A", "B", "C"].map((p) => <Kpi key={`r${p}`} label={`Radar · priorité ${p}`} value={fmt(d.priorities.radar_30d[p])} tone={TONE[p]} testid={`biz-radar-${p}`} onClick={() => prio(d.priorities.radar_30d, "offres Radar (30 j)")} />)}
          {["A", "B", "C"].map((p) => <Kpi key={`a${p}`} label={`Candidatures · ${p}`} value={fmt(d.priorities.applications[p])} tone={TONE[p]} testid={`biz-apps-${p}`} onClick={() => prio(d.priorities.applications, "candidatures (packs)")} />)}
        </div>
      </section>
      <div className="grid gap-4 lg:grid-cols-3">
        <RankList title="Postes les plus recherchés" rows={d.roles} testid="biz-roles" onPick={pick("Poste recherché", "Membres (Career Memory + mots-clés Radar)")} />
        <RankList title="Entreprises les plus suivies" rows={d.companies} testid="biz-companies" onPick={pick("Entreprise suivie", "Membres qui la suivent")} />
        <RankList title="Portails les plus utilisés" rows={d.portals} testid="biz-portals" onPick={pick("Portail", "Entreprises suivies via ce portail")} />
      </div>
    </div>
  );
};
