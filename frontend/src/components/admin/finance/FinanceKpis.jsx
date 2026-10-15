import { Code2, Cpu, Megaphone, PiggyBank, Server, Sigma, TrendingUp, UserCheck, Users, Wallet } from "lucide-react";
import { cad, num, pct, tone } from "./fmt";
import { Nature } from "./Nature";

const go = (t) => {
  const el = document.querySelector(`[data-testid="${t}"]`);
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block: "center" });
  el.classList.add("ring-2", "ring-emerald-400/60");
  setTimeout(() => el.classList.remove("ring-2", "ring-emerald-400/60"), 1800);
};

const Kpi = ({ icon: Icon, label, value, sub, valueClass = "text-white", testid, nature, realPct, to }) => (
  <div onClick={() => go(to)} role="button" tabIndex={0} onKeyDown={(e) => e.key === "Enter" && go(to)} title="Afficher le détail" className="min-w-0 cursor-pointer rounded-2xl border border-white/10 bg-slate-900/60 p-4 transition-colors hover:border-emerald-400/40" data-testid={testid}>
    <div className="flex flex-wrap items-start justify-between gap-1.5">
      <p className="flex items-center gap-1.5 text-[10px] font-mono uppercase tracking-widest text-slate-400"><Icon className="h-3.5 w-3.5 shrink-0 text-emerald-400" />{label}</p>
      {nature && <Nature kind={nature} realPct={realPct} testid={`${testid}-nature`} />}
    </div>
    <p className={`mt-2 truncate text-xl font-bold tabular-nums underline decoration-current/25 underline-offset-4 sm:text-2xl ${valueClass}`}>{value}</p>
    {sub && <p className="mt-1 text-[11px] text-slate-500">{sub}</p>}
  </div>
);

export const FinanceKpis = ({ s }) => {
  const f = s.families;
  const fam = (k) => (f[k].nature === "real" ? "real" : f[k].nature === "mixed" ? "mixed" : "estimated");
  return (
    <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5" data-testid="finance-kpis">
      <Kpi icon={PiggyBank} label="Revenus" value={cad(s.revenue.used)} nature={s.revenue.nature} testid="kpi-revenue" to="finance-revenue"
        sub={s.revenue.real !== null ? `Théorique ${cad(s.revenue.theory)} · écart ${cad(s.revenue.gap_cad)}` : "Encaissé non saisi : théorique + ajustements"} />
      <Kpi icon={Server} label="Infrastructure" value={cad(f.infrastructure.used_cad)} nature={fam("infrastructure")} realPct={f.infrastructure.real_pct} testid="kpi-infra" to="finance-costs" />
      <Kpi icon={Cpu} label="IA" value={cad(f.ia.used_cad)} nature={fam("ia")} realPct={f.ia.real_pct} sub={`${num(s.calls)} appels journalisés`} testid="kpi-ai" to="finance-ai-buckets" />
      <Kpi icon={Megaphone} label="Marketing" value={cad(f.marketing.used_cad)} nature={fam("marketing")} realPct={f.marketing.real_pct} testid="kpi-marketing" to="finance-costs" />
      <Kpi icon={Code2} label="Développement" value={cad(f.developpement.used_cad)} nature={fam("developpement")} realPct={f.developpement.real_pct} sub={`dont investissements ponctuels ${cad(s.invest_cad)}`} testid="kpi-dev" to="finance-costs" />
      <Kpi icon={Wallet} label="Dépenses totales" value={cad(s.total_cad)} nature="calculated" realPct={s.total_nature.real_pct} sub={`Exploitation ${cad(s.ops_cad)} · dév. ${cad(s.dev_cad)}`} testid="kpi-total" to="finance-total-costs" />
      <Kpi icon={TrendingUp} label="Marge d'exploitation" value={cad(s.operating_margin_cad)} valueClass={tone(s.operating_margin_cad)} nature="calculated" sub={`${pct(s.operating_margin_pct)} · hors développement`} testid="kpi-op-margin" to="margin-op" />
      <Kpi icon={Sigma} label="Marge nette" value={cad(s.net_margin_cad)} valueClass={tone(s.net_margin_cad)} nature="calculated" sub={`${pct(s.net_margin_pct)} · tout inclus`} testid="kpi-margin" to="margin-net" />
      <Kpi icon={Users} label="Membres actifs" value={num(s.members.active)} nature="calculated" sub={`${num(s.members.registered)} inscrits`} testid="kpi-active" to="finance-per-member" />
      <Kpi icon={UserCheck} label="Membres payants" value={num(s.members.paid)} nature={s.doc.paid_override !== null && s.doc.paid_override !== undefined ? "estimated" : "calculated"} sub={`${num(s.members.active_paid)} actifs payants`} testid="kpi-paid" to="finance-members-search" />
    </div>
  );
};

const share = (x, t) => (t ? `${Math.round((x * 1000) / t) / 10} %` : "—");
const per = (x, n) => (n ? x / n : null);

export const Answers = ({ s }) => {
  const t = s.total_cad;
  const ops = s.families.infrastructure.used_cad + s.families.autres.used_cad;
  const Q = ({ q, a, testid }) => <p data-testid={testid}><span className="text-slate-400">{q}</span> <b className="text-white">{a}</b></p>;
  return (
    <div className="grid gap-2 rounded-2xl border border-emerald-500/20 bg-emerald-950/20 p-4 text-sm sm:grid-cols-2 lg:grid-cols-3" data-testid="finance-answers">
      <Q q="Combien CareerOS rapporte réellement ?" a={s.revenue.real !== null ? cad(s.revenue.real) : `${cad(s.revenue.used)} (estimé)`} testid="answer-revenue" />
      <Q q="Combien CareerOS coûte réellement ?" a={`${cad(t)} (${s.total_nature.real_pct ?? 0} % réel)`} testid="answer-costs" />
      <Q q="Part exploitation (infra + autres) ?" a={`${cad(ops)} · ${share(ops, t)}`} testid="answer-ops" />
      <Q q="Part IA ?" a={`${cad(s.families.ia.used_cad)} · ${share(s.families.ia.used_cad, t)}`} testid="answer-ai" />
      <Q q="Part développement ?" a={`${cad(s.dev_cad)} · ${share(s.dev_cad, t)}`} testid="answer-dev" />
      <Q q="Part marketing ?" a={`${cad(s.families.marketing.used_cad)} · ${share(s.families.marketing.used_cad, t)}`} testid="answer-marketing" />
      <Q q="Coût réel par membre actif ?" a={cad(per(t, s.members.active))} testid="answer-cost-active" />
      <Q q="Coût réel par membre payant ?" a={cad(per(t, s.members.paid))} testid="answer-cost-paid" />
      <Q q="Rentabilité réelle ?" a={<span className={tone(s.net_margin_cad)}>{cad(s.net_margin_cad)} ({pct(s.net_margin_pct)})</span>} testid="answer-margin" />
    </div>
  );
};
