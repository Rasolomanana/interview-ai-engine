import { Cpu, PiggyBank, Server, TrendingUp, Users } from "lucide-react";
import { cad, num, pct, tone } from "./fmt";

const Kpi = ({ icon: Icon, label, value, sub, valueClass = "text-white", testid }) => (
  <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-4 sm:p-5" data-testid={testid}>
    <p className="flex items-center gap-2 text-[11px] font-mono uppercase tracking-widest text-slate-400"><Icon className="h-4 w-4 text-emerald-400" />{label}</p>
    <p className={`mt-2 text-2xl font-bold tabular-nums sm:text-3xl ${valueClass}`}>{value}</p>
    {sub && <p className="mt-1 text-[11px] text-slate-500">{sub}</p>}
  </div>
);

export const FinanceKpis = ({ s }) => (
  <div className="grid grid-cols-2 gap-3 lg:grid-cols-5" data-testid="finance-kpis">
    <Kpi icon={PiggyBank} label="Revenus nets" value={cad(s.revenue.net)} sub={`Brut ${cad(s.revenue.gross)} · ajust. ${cad(s.revenue.adjustments)}`} testid="kpi-revenue" />
    <Kpi icon={Server} label="Coûts plateforme" value={cad(s.platform_cad)} sub="Hébergement, outils, marketing" testid="kpi-platform" />
    <Kpi icon={Cpu} label="Coûts IA" value={cad(s.ai_cad)} sub={`Estimé ${cad(s.ai_est_cad)} · ${num(s.calls)} appels`} testid="kpi-ai" />
    <Kpi icon={TrendingUp} label="Marge nette" value={cad(s.margin_cad)} valueClass={tone(s.margin_cad)} sub={`Marge ${pct(s.margin_pct)}`} testid="kpi-margin" />
    <Kpi icon={Users} label="Membres actifs" value={num(s.members.active)} sub={`${num(s.members.paid)} payants · ${num(s.members.active_paid)} actifs payants · ${num(s.members.registered)} inscrits`} testid="kpi-active" />
  </div>
);

export const Answers = ({ s }) => (
  <div className="grid gap-2 rounded-2xl border border-emerald-500/20 bg-emerald-950/20 p-4 text-sm sm:grid-cols-2 lg:grid-cols-4" data-testid="finance-answers">
    <p><span className="text-slate-400">Combien je gagne ?</span> <b className="text-white">{cad(s.revenue.net)}</b></p>
    <p><span className="text-slate-400">Combien je dépense ?</span> <b className="text-white">{cad(s.costs_cad)}</b></p>
    <p><span className="text-slate-400">Combien me coûte un membre actif ?</span> <b className="text-white">{cad(s.per_member.cost_per_active)}</b></p>
    <p><span className="text-slate-400">Quelle est ma marge ?</span> <b className={tone(s.margin_cad)}>{cad(s.margin_cad)} ({pct(s.margin_pct)})</b></p>
  </div>
);
