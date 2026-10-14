import { AlertTriangle, Calculator, Cpu, Layers, Rocket, UserRound } from "lucide-react";
import { cad, cadFine, num, pct, Panel, Row, tone, usd } from "./fmt";
import { Nature } from "./Nature";

const Table = ({ head, children, testid, min = 520 }) => (
  <div className="overflow-x-auto">
    <table className="w-full text-left text-[12px]" style={{ minWidth: min }} data-testid={testid}>
      <thead className="text-slate-500"><tr className="border-b border-white/10">{head.map((h, i) => <th key={h} className={`py-2 pr-3 font-medium ${i ? "text-right" : ""}`}>{h}</th>)}</tr></thead>
      <tbody>{children}</tbody>
    </table>
  </div>
);
const Td = ({ children, left, className = "" }) => <td className={`border-b border-white/5 py-2 pr-3 tabular-nums ${left ? "" : "text-right font-mono"} ${className}`}>{children}</td>;
const NRow = ({ label, value, kind, realPct, strong, testid, hint }) => <Row label={<span className="inline-flex flex-wrap items-center gap-1.5">{label}<Nature kind={kind} realPct={realPct} /></span>} hint={hint} value={value} strong={strong} testid={testid} />;
const ADJ = { rabais: "Rabais", fondateur: "Fondateurs", essai: "Essai gratuit", ponctuel: "Ponctuel", remboursement: "Remboursement", b2b: "B2B", autre: "Autre" };
const SRC = { saisie: "saisi", jetons: "jetons × tarif", recurrent: "récurrent par défaut" };
const REC = { recurrent: "Récurrent", ponctuel: "Ponctuel", variable: "Variable" };

export const RevenuePanel = ({ s }) => {
  const r = s.revenue;
  return (
    <Panel title="Revenus : théorique vs réel" icon={Calculator} testid="finance-revenue">
      <NRow label="Prix standard × membres payants" hint={`${cad(r.price_cad)} × ${num(r.paid)}`} value={cad(r.theory)} kind="estimated" testid="rev-theory" />
      {(s.doc.adjustments || []).map((a, i) => <NRow key={i} label={a.label || ADJ[a.kind]} hint={ADJ[a.kind]} value={cad(["rabais", "remboursement", "essai"].includes(a.kind) ? -Math.abs(a.amount) : a.amount)} kind="estimated" />)}
      <NRow label="Revenu attendu (théorique + ajustements)" value={cad(r.expected)} kind="calculated" testid="rev-expected" />
      <NRow label="Revenu réellement encaissé" value={r.real === null ? "non saisi" : cad(r.real)} kind={r.real === null ? "estimated" : "real"} strong testid="rev-real" />
      {r.real !== null && <>
        <NRow label="Écart réel − théorique" value={<span className={tone(r.gap_cad)}>{cad(r.gap_cad)} · {pct(r.gap_pct)}</span>} kind="calculated" testid="rev-gap" />
        <NRow label="Dont expliqué par les ajustements" value={cad(r.adjustments)} kind="calculated" />
        <NRow label="Écart non expliqué" value={cad(r.unexplained_cad)} kind="calculated" testid="rev-unexplained" />
      </>}
      <NRow label="Revenu retenu pour les marges" value={cad(r.used)} kind={r.nature} strong testid="finance-net-revenue" />
    </Panel>
  );
};

const LineRow = ({ l }) => (
  <tr data-testid={`cost-line-${l.provider_id}`} className={l.provider_status === "archived" ? "opacity-60" : ""}>
    <Td left>{l.name}<span className="block text-[10px] text-slate-500">{l.category} · {REC[l.recurrence]}{l.provider_status === "archived" ? " · archivé" : ""}{l.suspended ? " · suspendu" : ""}</span></Td>
    <Td>{l.est_cad === null ? "—" : cadFine(l.est_cad)}<span className="block text-[10px] text-slate-500">{SRC[l.est_source] || ""}</span></Td>
    <Td>{cad(l.real_cad)}</Td>
    <Td className={l.gap_cad > 0 ? "text-rose-300" : "text-emerald-300"}>{l.gap_cad === null ? "—" : `${cad(l.gap_cad)}${l.gap_pct !== null ? ` · ${pct(l.gap_pct)}` : ""}`}</Td>
    <Td>{cadFine(l.used_cad)}</Td>
    <Td><Nature kind={l.nature} /></Td>
  </tr>
);

export const CostsPanel = ({ s }) => (
  <Panel title="Dépenses par famille : estimé vs réel" icon={Layers} testid="finance-costs">
    <Table head={["Fournisseur", "Estimé", "Réel", "Écart", "Retenu", "Nature"]} min={620}>
      {s.families_list.map(([k, label]) => {
        const ls = s.lines.filter((l) => l.family === k);
        const f = s.families[k];
        return [
          <tr key={k} className="bg-white/[0.03]" data-testid={`cost-family-${k}`}>
            <Td left className="pt-3 font-semibold text-white">{label}</Td><Td>{cad(f.est_cad)}</Td><Td>{cad(f.real_cad)}</Td><Td /><Td className="font-semibold text-white">{cad(f.used_cad)}</Td>
            <Td><Nature kind="calculated" realPct={f.real_pct ?? 0} /></Td>
          </tr>,
          ...(ls.length ? ls.map((l) => <LineRow key={l.provider_id} l={l} />) : [<tr key={`${k}-empty`}><Td left className="text-slate-500">Aucune dépense ce mois</Td></tr>]),
        ];
      })}
    </Table>
    <div className="mt-3 grid gap-x-6 sm:grid-cols-2">
      <div>
        <NRow label="Coûts d'exploitation (infra + IA + marketing + autres)" value={cad(s.ops_cad)} kind="calculated" realPct={s.ops_nature.real_pct ?? 0} strong testid="total-ops" />
        <NRow label="Coûts de développement" value={cad(s.dev_cad)} kind="calculated" realPct={s.families.developpement.real_pct ?? 0} testid="total-dev" />
        <NRow label="Investissements ponctuels du mois" value={cad(s.invest_cad)} kind="calculated" testid="total-invest" />
        <NRow label="Dépenses totales" value={cad(s.total_cad)} kind="calculated" realPct={s.total_nature.real_pct ?? 0} strong testid="finance-total-costs" />
      </div>
      <div>
        <NRow label="Marge d'exploitation" value={<span className={tone(s.operating_margin_cad)}>{cad(s.operating_margin_cad)} · {pct(s.operating_margin_pct)}</span>} kind="calculated" strong testid="margin-op" />
        <NRow label="Marge nette (tout inclus)" value={<span className={tone(s.net_margin_cad)}>{cad(s.net_margin_cad)} · {pct(s.net_margin_pct)}</span>} kind="calculated" strong testid="margin-net" />
      </div>
    </div>
    <p className="mt-2 text-[11px] text-slate-500">Retenu = réel si une facture est saisie, sinon estimé. Taux : 1 USD = {s.fx_usd_cad} CAD.</p>
  </Panel>
);

export const AiTables = ({ s }) => (
  <Panel title="Consommation IA journalisée" icon={Cpu} testid="finance-ai-buckets" right={<Nature kind="estimated" />}>
    <Table head={["Modèle", "Appels", "Jetons entrée", "Jetons sortie", "Coût estimé"]}>
      {s.buckets.map((b) => <tr key={b.key} data-testid={`ai-bucket-${b.key}`}><Td left>{b.label}</Td><Td>{num(b.calls)}</Td><Td>{num(b.tokens_in)}</Td><Td>{num(b.tokens_out)}</Td><Td>{cadFine(b.est_cad)}</Td></tr>)}
      <tr className="font-semibold text-white"><Td left>Total du mois</Td><Td>{num(s.calls)}</Td><Td /><Td /><Td>{cadFine(s.buckets.reduce((a, b) => a + b.est_cad, 0))}</Td></tr>
    </Table>
    {s.features.length > 0 && <p className="mt-3 text-[11px] text-slate-400" data-testid="ai-features">Par fonctionnalité : {s.features.map((f) => `${f.feature} ${num(f.calls)} appels · ${cadFine(f.est_cad)}`).join(" — ")}</p>}
    <p className="mt-2 text-[11px] text-slate-500">Jetons estimés (≈ 4 caractères par jeton) × tarifs officiels. La facture réelle saisie dans le mois remplace cette estimation.</p>
  </Panel>
);

const per = (x, n) => (n ? x / n : null);

export const PerMember = ({ s }) => {
  const f = s.families;
  const m = s.members;
  const rows = [
    ["Revenu", s.revenue.used], ["Infrastructure", f.infrastructure.used_cad], ["IA", f.ia.used_cad], ["Marketing", f.marketing.used_cad],
    ["Développement", f.developpement.used_cad], ["Coût d'exploitation", s.ops_cad], ["Coût total", s.total_cad],
    ["Profit d'exploitation", s.operating_margin_cad], ["Profit net", s.net_margin_cad],
  ];
  return (
    <Panel title="Rentabilité par membre" icon={UserRound} testid="finance-per-member" right={<Nature kind="calculated" />}>
      <Table head={["Indicateur", "Par membre actif", "Par actif payant", "Par membre payant"]} min={560}>
        {rows.map(([l, v]) => {
          const profit = l.startsWith("Profit");
          return (
            <tr key={l} className={profit || l === "Coût total" ? "font-semibold" : ""} data-testid={`per-member-${l}`}>
              <Td left>{l}</Td>
              {[m.active, m.active_paid, m.paid].map((n, i) => <Td key={i} className={profit ? tone(per(v, n)) : ""}>{cadFine(per(v, n))}</Td>)}
            </tr>);
        })}
      </Table>
      <p className="mt-2 text-[11px] text-slate-500">Inscrits {num(m.registered)} · actifs (connectés ce mois) {num(m.active)} · payants {num(m.paid)} · actifs payants {num(m.active_paid)}.</p>
    </Panel>
  );
};

export const Alerts = ({ s }) => {
  const c = s.credit;
  return (
    <Panel title="Alertes et projection de consommation" icon={AlertTriangle} testid="finance-alerts">
      <div className="grid gap-3 sm:grid-cols-3">
        <div data-testid="finance-credit">
          <p className="flex items-center gap-1.5 text-[11px] uppercase text-slate-500">Crédit OpenRouter restant <Nature kind="real" /></p>
          {!c || c.configured === false ? <p className="text-sm text-amber-300">Non configuré</p> : c.error ? <p className="text-sm text-rose-300">{c.error}</p>
            : <p className={`text-xl font-bold ${c.low ? "text-rose-400" : "text-white"}`}>{usd(c.remaining)} <span className="text-xs font-normal text-slate-400">({c.remaining_pct} % · seuil {c.threshold} %)</span></p>}
          {c?.days_left !== undefined && c?.days_left !== null && <p className="text-[11px] text-slate-400">≈ {c.days_left} jours au rythme actuel ({usd(c.daily_usd)}/jour)</p>}
        </div>
        <div data-testid="finance-pace-ai"><p className="flex items-center gap-1.5 text-[11px] uppercase text-slate-500">IA projetée fin de mois <Nature kind="estimated" /></p><p className="text-xl font-bold text-white">{cad(s.pace.ai_month_end_cad)}</p><p className="text-[11px] text-slate-400">Jour {s.pace.days_elapsed}/{s.pace.days_in_month}</p></div>
        <div data-testid="finance-pace-margin"><p className="flex items-center gap-1.5 text-[11px] uppercase text-slate-500">Marge d'exploitation projetée <Nature kind="estimated" /></p><p className={`text-xl font-bold ${tone(s.pace.operating_margin_month_end_cad)}`}>{cad(s.pace.operating_margin_month_end_cad)}</p></div>
      </div>
      <p className="mt-3 text-[11px] text-slate-500">Le seuil d'alerte et l'e-mail se règlent dans la carte « Crédit IA restant » de l'onglet Activité.</p>
    </Panel>
  );
};

export const Projections = ({ s }) => (
  <Panel title="Projection financière (exploitation)" icon={Rocket} testid="finance-projections" right={<Nature kind="estimated" />}>
    <div className="grid gap-3 sm:grid-cols-3">
      {s.scenarios.map((x) => (
        <div key={x.members} className="rounded-xl border border-white/10 bg-black/30 p-4" data-testid={`projection-${x.members}`}>
          <p className="text-[11px] font-mono uppercase tracking-widest text-slate-400">{num(x.members)} membres actifs</p>
          <p className={`mt-1 text-2xl font-bold ${tone(x.margin_cad)}`}>{cad(x.margin_cad)}</p>
          <p className="text-[11px] text-slate-400">marge d'exploitation / mois · {pct(x.margin_pct)}</p>
          <div className="mt-2 space-y-0.5 text-[11px] text-slate-300">
            <p>Revenus {cad(x.revenue_cad)} ({num(x.paid)} payants)</p><p>IA {cad(x.ai_cad)} · Fixes {cad(x.fixed_cad)}</p>
          </div>
        </div>))}
    </div>
    <p className="mt-3 text-[11px] text-slate-500" data-testid="projection-basis">
      Hypothèses : {s.scenario_basis.ratio_assumed ? "100 % des membres actifs payants (aucun membre actif payant encore)" : `${s.scenario_basis.paid_ratio_pct} % des actifs payants (taux actuel)`} · IA {cadFine(s.scenario_basis.ai_per_active_cad)} par membre actif · infrastructure, marketing et autres fixes au niveau actuel · développement exclu.
    </p>
  </Panel>
);
