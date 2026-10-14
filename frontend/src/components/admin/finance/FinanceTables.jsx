import { AlertTriangle, Calculator, Cpu, Layers, Rocket, UserRound, Wallet } from "lucide-react";
import { cad, cadFine, num, pct, Panel, Row, tone, usd } from "./fmt";

const Table = ({ head, children, testid, min = 520 }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-left text-[12px]" style={{ minWidth: min }} data-testid={testid}>
      <thead className="text-slate-500"><tr className="border-b border-white/10">{head.map((h, i) => <th key={h} className={`py-2 pr-3 font-medium ${i ? "text-right" : ""}`}>{h}</th>)}</tr></thead>
      <tbody>{children}</tbody>
    </table>
  </div>
);
const Td = ({ children, left, className = "" }) => <td className={`border-b border-white/5 py-2 pr-3 tabular-nums ${left ? "" : "text-right font-mono"} ${className}`}>{children}</td>;

export const RevenueCosts = ({ s }) => (
  <div className="grid gap-4 lg:grid-cols-2">
    <Panel title="Revenus du mois" icon={Calculator} testid="finance-revenue">
      <Row label="Prix mensuel standard" value={cad(s.revenue.price_cad)} />
      <Row label="Membres payants" value={num(s.revenue.paid)} />
      <Row label="Revenu brut (théorique)" value={cad(s.revenue.gross)} />
      {(s.doc.adjustments || []).map((a, i) => <Row key={i} label={a.label || a.kind} hint={a.kind} value={cad(["rabais", "remboursement"].includes(a.kind) ? -Math.abs(a.amount) : a.amount)} />)}
      <Row label="Ajustements" value={cad(s.revenue.adjustments)} />
      <Row label="Revenu net" value={cad(s.revenue.net)} strong testid="finance-net-revenue" />
    </Panel>
    <Panel title="Répartition des coûts" icon={Layers} testid="finance-costs">
      {s.platform.length === 0 && <p className="text-xs text-slate-500">Aucun poste de coût saisi pour ce mois.</p>}
      {s.platform.map((c) => <Row key={c.name} label={c.name} hint={c.currency === "USD" ? `${c.amount} USD` : ""} value={cad(c.cad)} />)}
      <Row label="Total plateforme" value={cad(s.platform_cad)} strong />
      <Row label="Total IA (réel si facture saisie, sinon estimé)" value={cad(s.ai_cad)} strong />
      <Row label="Dépenses totales" value={cad(s.costs_cad)} strong testid="finance-total-costs" />
      <Row label="Marge nette" value={<span className={tone(s.margin_cad)}>{cad(s.margin_cad)} · {pct(s.margin_pct)}</span>} strong />
    </Panel>
  </div>
);

export const AiTables = ({ s }) => (
  <div className="grid gap-4 lg:grid-cols-2">
    <Panel title="Consommation IA par modèle" icon={Cpu} testid="finance-ai-buckets">
      <Table head={["Modèle", "Appels", "Jetons entrée", "Jetons sortie", "Coût estimé"]}>
        {s.buckets.map((b) => <tr key={b.key} data-testid={`ai-bucket-${b.key}`}><Td left>{b.label}</Td><Td>{num(b.calls)}</Td><Td>{num(b.tokens_in)}</Td><Td>{num(b.tokens_out)}</Td><Td>{cadFine(b.est_cad)}</Td></tr>)}
        <tr className="font-semibold text-white"><Td left>Total du mois</Td><Td>{num(s.calls)}</Td><Td /><Td /><Td>{cad(s.ai_est_cad)}</Td></tr>
      </Table>
      {s.features.length > 0 && <p className="mt-3 text-[11px] text-slate-400" data-testid="ai-features">Par fonctionnalité : {s.features.map((f) => `${f.feature} ${num(f.calls)} appels · ${cadFine(f.est_cad)}`).join(" — ")}</p>}
      <p className="mt-2 text-[11px] text-slate-500">Jetons estimés (≈ 4 caractères par jeton) × tarifs officiels modifiables dans « Réglages ».</p>
    </Panel>
    <Panel title="Coût par fournisseur : estimé vs réel" icon={Wallet} testid="finance-ai-providers">
      <Table head={["Fournisseur", "Estimé", "Réel", "Écart", "Erreur"]} min={460}>
        {s.providers.map((p) => (
          <tr key={p.provider} data-testid={`ai-provider-${p.provider}`}>
            <Td left>{p.label}<span className="block text-[10px] text-slate-500">{usd(p.est_usd)} estimé{p.real_amount !== null && p.real_currency === "USD" ? ` · facture ${usd(p.real_amount)}` : ""}</span></Td>
            <Td>{cadFine(p.est_cad)}</Td><Td>{cad(p.real_cad)}</Td>
            <Td className={p.gap_cad > 0 ? "text-rose-300" : "text-emerald-300"}>{p.gap_cad === null ? "—" : cad(p.gap_cad)}</Td><Td>{pct(p.gap_pct)}</Td>
          </tr>))}
        <tr className="font-semibold text-white"><Td left>Total IA</Td><Td>{cad(s.ai_est_cad)}</Td><Td>{cad(s.ai_cad)}</Td><Td>{cad(s.ai_cad - s.ai_est_cad)}</Td><Td>{s.ai_est_cad ? pct(Math.round(((s.ai_cad - s.ai_est_cad) * 1000) / s.ai_est_cad) / 10) : "—"}</Td></tr>
      </Table>
      <p className="mt-2 text-[11px] text-slate-500">Taux appliqué : 1 USD = {s.fx_usd_cad} CAD. Saisissez les factures réelles via « Saisir le mois ».</p>
    </Panel>
  </div>
);

export const PerMember = ({ s }) => {
  const p = s.per_member;
  return (
    <Panel title="Rentabilité par membre" icon={UserRound} testid="finance-per-member">
      <Table head={["Indicateur", "Par membre actif", "Par membre actif payant", "Par membre payant"]} min={560}>
        <tr><Td left>Revenu moyen</Td><Td>{cad(p.revenue_per_active)}</Td><Td>—</Td><Td>{cad(p.revenue_per_paid)}</Td></tr>
        <tr><Td left>Coût IA</Td><Td>{cadFine(p.ai_per_active)}</Td><Td>{cadFine(p.ai_per_active_paid)}</Td><Td>—</Td></tr>
        <tr><Td left>Coût plateforme</Td><Td>{cad(p.platform_per_active)}</Td><Td>{cad(p.platform_per_active_paid)}</Td><Td>—</Td></tr>
        <tr><Td left>Coût total</Td><Td>{cad(p.cost_per_active)}</Td><Td>{cad(p.cost_per_active_paid)}</Td><Td>—</Td></tr>
        <tr className="font-semibold"><Td left>Profit</Td><Td className={tone(p.profit_per_active)}>{cad(p.profit_per_active)}</Td><Td>—</Td><Td className={tone(p.profit_per_paid)}>{cad(p.profit_per_paid)}</Td></tr>
      </Table>
      <p className="mt-2 text-[11px] text-slate-500">Inscrits {num(s.members.registered)} · actifs (connectés ce mois) {num(s.members.active)} · payants {num(s.members.paid)} · actifs payants {num(s.members.active_paid)}.</p>
    </Panel>
  );
};

export const Alerts = ({ s }) => {
  const c = s.credit;
  return (
    <Panel title="Alertes et projection de consommation" icon={AlertTriangle} testid="finance-alerts">
      <div className="grid gap-3 sm:grid-cols-3">
        <div data-testid="finance-credit">
          <p className="text-[11px] uppercase text-slate-500">Crédit OpenRouter restant</p>
          {!c || c.configured === false ? <p className="text-sm text-amber-300">Non configuré</p> : c.error ? <p className="text-sm text-rose-300">{c.error}</p>
            : <p className={`text-xl font-bold ${c.low ? "text-rose-400" : "text-white"}`}>{usd(c.remaining)} <span className="text-xs font-normal text-slate-400">({c.remaining_pct} % · seuil {c.threshold} %)</span></p>}
          {c?.days_left !== undefined && c?.days_left !== null && <p className="text-[11px] text-slate-400">≈ {c.days_left} jours au rythme actuel ({usd(c.daily_usd)}/jour)</p>}
        </div>
        <div data-testid="finance-pace-ai"><p className="text-[11px] uppercase text-slate-500">Coût IA projeté fin de mois</p><p className="text-xl font-bold text-white">{cad(s.pace.ai_month_end_cad)}</p><p className="text-[11px] text-slate-400">Jour {s.pace.days_elapsed}/{s.pace.days_in_month}</p></div>
        <div data-testid="finance-pace-margin"><p className="text-[11px] uppercase text-slate-500">Marge projetée fin de mois</p><p className={`text-xl font-bold ${tone(s.pace.margin_month_end_cad)}`}>{cad(s.pace.margin_month_end_cad)}</p></div>
      </div>
      <p className="mt-3 text-[11px] text-slate-500">Le seuil d'alerte et l'e-mail se règlent dans la carte « Crédit IA restant » de l'onglet Activité.</p>
    </Panel>
  );
};

export const Projections = ({ s }) => (
  <Panel title="Projection financière" icon={Rocket} testid="finance-projections">
    <div className="grid gap-3 sm:grid-cols-3">
      {s.scenarios.map((x) => (
        <div key={x.members} className="rounded-xl border border-white/10 bg-black/30 p-4" data-testid={`projection-${x.members}`}>
          <p className="text-[11px] font-mono uppercase tracking-widest text-slate-400">{num(x.members)} membres actifs</p>
          <p className={`mt-1 text-2xl font-bold ${tone(x.margin_cad)}`}>{cad(x.margin_cad)}</p>
          <p className="text-[11px] text-slate-400">marge / mois · {pct(x.margin_pct)}</p>
          <div className="mt-2 space-y-0.5 text-[11px] text-slate-300">
            <p>Revenus {cad(x.revenue_cad)} ({num(x.paid)} payants)</p><p>IA {cad(x.ai_cad)} · Plateforme {cad(x.platform_cad)}</p>
          </div>
        </div>))}
    </div>
    <p className="mt-3 text-[11px] text-slate-500" data-testid="projection-basis">
      Hypothèses : {s.scenario_basis.ratio_assumed ? "100 % des membres actifs payants (aucun membre actif payant encore)" : `${s.scenario_basis.paid_ratio_pct} % des actifs payants (taux actuel)`} · coût IA actuel par membre actif {cadFine(s.scenario_basis.ai_per_active_cad)} · coûts plateforme fixes au niveau actuel (à revoir quand l'hébergement doit grossir).
    </p>
  </Panel>
);
