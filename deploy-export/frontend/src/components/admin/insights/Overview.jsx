import { useState } from "react";
import { ArrowDown, Radar } from "lucide-react";
import { adminInsights } from "@/lib/api";
import { useTrace } from "@/components/admin/TraceDialog";
import { Kpi, Spinner, fmt, panel, pwd, useAdminData } from "./ui";

const PERIODS = [[30, "30 jours"], [90, "90 jours"], [0, "Depuis le début"]];

export const Overview = () => {
  const [days, setDays] = useState(30);
  const [traceNode, trace] = useTrace();
  const d = useAdminData(() => adminInsights(pwd(), "overview", days), [days]);
  if (!d) return <Spinner />;
  const m = d.members, r = d.radar;
  const FUNNEL = ["f_visitors", "f_inscrits", "f_actifs", "f_payants", "f_renouv"];
  return (
    <div className="space-y-4" data-testid="admin-overview">
      {traceNode}
      <section className={panel}>
        <h3 className="mb-3 text-sm font-semibold text-slate-200">Membres</h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <Kpi label="Membres au total" value={fmt(m.total)} testid="ov-total" onClick={() => trace("m_total")} />
          <Kpi label="Actifs 7 jours" value={fmt(m.active_7d)} testid="ov-active7" onClick={() => trace("m_active7")} />
          <Kpi label="Actifs 30 jours" value={fmt(m.active_30d)} testid="ov-active30" onClick={() => trace("m_active30")} />
          <Kpi label="Nouveaux 7 jours" value={fmt(m.new_7d)} testid="ov-new7" onClick={() => trace("m_new7")} />
          <Kpi label="Nouveaux 30 jours" value={fmt(m.new_30d)} testid="ov-new30" onClick={() => trace("m_new30")} />
          <Kpi label="Payants" value={fmt(m.paid)} testid="ov-paid" tone="text-amber-300" onClick={() => trace("m_paid")} />
        </div>
      </section>
      <section className={panel} data-testid="ov-funnel">
        <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold text-slate-200">Entonnoir de conversion</h3>
          <div className="flex gap-1">{PERIODS.map(([v, l]) => (
            <button key={v} type="button" onClick={() => setDays(v)} className={`rounded-full px-3 py-1 text-[11px] ${days === v ? "bg-emerald-500 text-black" : "border border-white/10 text-slate-300"}`} data-testid={`ov-period-${v}`}>{l}</button>))}
          </div>
        </div>
        <div className="mx-auto max-w-xl space-y-1">{d.funnel.map((f, i) => (
          <div key={f.step}>
            {i > 0 && <p className="flex items-center justify-center gap-1 text-[11px] text-slate-500"><ArrowDown className="h-3 w-3" />{f.rate === null ? "taux non significatif" : `${f.rate} %`}</p>}
            <button type="button" onClick={() => trace(FUNNEL[i], "", days)} title={f.note}
              className="flex w-full items-center justify-between rounded-xl border border-emerald-400/20 bg-emerald-500/5 px-4 py-2 text-left hover:border-emerald-400/50"
              style={{ width: `${100 - i * 8}%`, marginInline: "auto" }} data-testid={`ov-funnel-${i}`}>
              <span className="text-sm text-slate-200">{f.step}</span><span className="font-mono text-lg font-bold text-white underline decoration-white/20 underline-offset-4">{fmt(f.count)}</span>
            </button>
          </div>))}
        </div>
      </section>
      <section className={panel} data-testid="ov-radar">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200"><Radar className="h-4 w-4 text-emerald-400" />Utilisation du Radar (30 jours)</h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-4 lg:grid-cols-7">
          <Kpi label="Radar activé" value={fmt(r.enabled)} sub={<button type="button" onClick={(e) => { e.stopPropagation(); trace("r_configured"); }} onKeyDown={(e) => e.stopPropagation()} className="underline" data-testid="ov-radar-configured">{fmt(r.configured)} configuré(s)</button>} testid="ov-radar-enabled" onClick={() => trace("r_enabled")} />
          <Kpi label="Membres utilisateurs" value={fmt(r.members_30d)} testid="ov-radar-members" onClick={() => trace("r_members")} />
          <Kpi label="Passages" value={fmt(r.runs_30d)} testid="ov-radar-runs" onClick={() => trace("r_runs")} />
          <Kpi label="Automatiques" value={fmt(r.runs_auto)} testid="ov-radar-auto" onClick={() => trace("r_auto")} />
          <Kpi label="Manuels" value={fmt(r.runs_manual)} testid="ov-radar-manual" onClick={() => trace("r_manual")} />
          <Kpi label="Offres analysées" value={fmt(r.analyzed_30d)} testid="ov-radar-analyzed" onClick={() => trace("r_analyzed")} />
          <Kpi label="Packs depuis le Radar" value={fmt(r.packs_30d)} testid="ov-radar-packs" onClick={() => trace("r_packs")} />
        </div>
      </section>
    </div>
  );
};
