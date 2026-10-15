import { useState } from "react";
import { ArrowDown, Radar } from "lucide-react";
import { adminInsights } from "@/lib/api";
import { DetailDialog } from "@/components/admin/DetailDialog";
import { Kpi, Spinner, fmt, panel, pwd, useAdminData } from "./ui";

const PERIODS = [[30, "30 jours"], [90, "90 jours"], [0, "Depuis le début"]];
const series = (title, rows, col = "Membres") => ({ title, cols: [["day", "Jour"], ["count", col]], rows: [...(rows || [])].reverse() });

export const Overview = () => {
  const [days, setDays] = useState(30);
  const [detail, setDetail] = useState(null);
  const d = useAdminData(() => adminInsights(pwd(), "overview", days), [days]);
  if (!d) return <Spinner />;
  const m = d.members, r = d.radar;
  const funnelDetail = () => setDetail({ title: "Entonnoir de conversion · définitions", cols: [["step", "Étape"], ["count", "Nombre"], ["rate", "Taux"], ["note", "Définition"]],
    rows: d.funnel.map((f) => ({ ...f, rate: f.rate === null ? "—" : `${f.rate} %` })) });
  return (
    <div className="space-y-4" data-testid="admin-overview">
      <DetailDialog detail={detail} onClose={() => setDetail(null)} />
      <section className={panel}>
        <h3 className="mb-3 text-sm font-semibold text-slate-200">Membres</h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <Kpi label="Membres au total" value={fmt(m.total)} testid="ov-total" onClick={() => setDetail(series("Nouveaux membres par jour (30 j)", m.new_by_day))} />
          <Kpi label="Actifs 7 jours" value={fmt(m.active_7d)} testid="ov-active7" onClick={() => setDetail(series("Dernière activité par jour (30 j)", m.active_by_day))} />
          <Kpi label="Actifs 30 jours" value={fmt(m.active_30d)} testid="ov-active30" onClick={() => setDetail(series("Dernière activité par jour (30 j)", m.active_by_day))} />
          <Kpi label="Nouveaux 7 jours" value={fmt(m.new_7d)} testid="ov-new7" onClick={() => setDetail(series("Nouveaux membres par jour (30 j)", m.new_by_day))} />
          <Kpi label="Nouveaux 30 jours" value={fmt(m.new_30d)} testid="ov-new30" onClick={() => setDetail(series("Nouveaux membres par jour (30 j)", m.new_by_day))} />
          <Kpi label="Payants" value={fmt(m.paid)} testid="ov-paid" tone="text-amber-300" onClick={funnelDetail} />
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
            {i > 0 && <p className="flex items-center justify-center gap-1 text-[11px] text-slate-500"><ArrowDown className="h-3 w-3" />{f.rate} %</p>}
            <button type="button" onClick={() => setDetail({ title: `${f.step} · ${fmt(f.count)}`, cols: [["k", "Élément"], ["v", "Valeur"]], rows: [{ k: "Définition", v: f.note }, { k: "Taux vs étape précédente", v: f.rate === null ? "—" : `${f.rate} %` }] })}
              className="flex w-full items-center justify-between rounded-xl border border-emerald-400/20 bg-emerald-500/5 px-4 py-2 text-left hover:border-emerald-400/50"
              style={{ width: `${100 - i * 8}%`, marginInline: "auto" }} data-testid={`ov-funnel-${i}`}>
              <span className="text-sm text-slate-200">{f.step}</span><span className="font-mono text-lg font-bold text-white underline decoration-white/20 underline-offset-4">{fmt(f.count)}</span>
            </button>
          </div>))}
        </div>
      </section>
      <section className={panel} data-testid="ov-radar">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200"><Radar className="h-4 w-4 text-emerald-400" />Utilisation du Radar (30 jours)</h3>
        <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          <Kpi label="Radar activé" value={fmt(r.enabled)} sub={`${fmt(r.configured)} configuré(s)`} testid="ov-radar-enabled" onClick={() => setDetail({ title: "Radar · membres", cols: [["k", "Élément"], ["v", "Nombre"]], rows: [{ k: "Réglages enregistrés", v: r.configured }, { k: "Recherche quotidienne activée", v: r.enabled }, { k: "Ayant au moins un passage (30 j)", v: r.members_30d }] })} />
          <Kpi label="Membres utilisateurs" value={fmt(r.members_30d)} testid="ov-radar-members" onClick={() => setDetail(series("Passages Radar par jour", r.runs_by_day, "Passages"))} />
          <Kpi label="Passages" value={fmt(r.runs_30d)} testid="ov-radar-runs" onClick={() => setDetail(series("Passages Radar par jour", r.runs_by_day, "Passages"))} />
          <Kpi label="Automatiques / manuels" value={`${fmt(r.runs_auto)} / ${fmt(r.runs_manual)}`} testid="ov-radar-split" onClick={() => setDetail(series("Passages Radar par jour", r.runs_by_day, "Passages"))} />
          <Kpi label="Offres analysées" value={fmt(r.analyzed_30d)} testid="ov-radar-analyzed" onClick={() => setDetail({ title: "Offres analysées (30 j)", cols: [["k", "Élément"], ["v", "Nombre"]], rows: [{ k: "Offres analysées par le Radar", v: r.analyzed_30d }, { k: "Packs créés depuis le Radar", v: r.packs_30d }] })} />
          <Kpi label="Packs depuis le Radar" value={fmt(r.packs_30d)} testid="ov-radar-packs" onClick={() => setDetail({ title: "Packs créés depuis le Radar (30 j)", cols: [["k", "Élément"], ["v", "Nombre"]], rows: [{ k: "Packs", v: r.packs_30d }] })} />
        </div>
      </section>
    </div>
  );
};
