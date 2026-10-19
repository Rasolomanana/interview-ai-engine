import { ArrowRight, TrendingUp } from "lucide-react";

const fr = (n) => String(n).replace(".", ",");
const sign = (n) => (n > 0 ? `+${fr(n)}` : fr(n));

const Row = ({ label, before, after, potential, unit, testid }) => (
  <div className="rounded-xl border border-white/[0.07] bg-black/20 p-3" data-testid={testid}>
    <p className="text-[11px] uppercase tracking-wider text-slate-500">{label}</p>
    <p className="mt-1 flex flex-wrap items-baseline gap-2 font-display text-2xl font-bold tabular-nums text-white">
      <span data-testid={`${testid}-before`}>{fr(before)}{unit}</span><ArrowRight className="h-4 w-4 text-slate-500" />
      <span className="text-emerald-300" data-testid={`${testid}-after`}>{fr(after)}{unit}</span>
      <span className="text-sm font-semibold text-emerald-300" data-testid={`${testid}-gain`}>({sign(Math.round((after - before) * 10) / 10)})</span>
    </p>
    {potential > after && <p className="text-[11px] text-amber-200" data-testid={`${testid}-potential`}>Potentiel si vous confirmez les compétences proposées : {fr(potential)}{unit} ({sign(Math.round((potential - before) * 10) / 10)})</p>}
  </div>
);

// Estimated impact BEFORE validation: compatibility + Pro strength, guaranteed vs potential, and what causes the gain.
export const ImpactPanel = ({ sim }) => {
  if (!sim) return <p className="text-xs text-slate-500" data-testid="impact-loading">Calcul de l'impact…</p>;
  if (sim.error) return <p className="rounded-xl border border-amber-400/30 bg-amber-500/5 p-3 text-xs text-amber-100" data-testid="impact-error">L'estimation n'a pas pu être calculée. Modifiez la sélection pour relancer le calcul ; la validation reste bloquée tant que l'impact n'est pas affiché.</p>;
  return (
    <section className="space-y-2" data-testid="impact-panel">
      <div className="grid gap-2 sm:grid-cols-2">
        <Row label="Compatibilité avec l'offre" before={sim.match.before} after={sim.match.after} potential={sim.match.potential} unit=" %" testid="impact-match" />
        <Row label="Indice de Force Professionnelle" before={sim.ifp.before} after={sim.ifp.after} potential={sim.ifp.potential} unit="" testid="impact-ifp" />
      </div>
      <div className="rounded-xl border border-white/[0.07] p-3" data-testid="impact-why">
        <p className="mb-1 flex items-center gap-1.5 text-xs font-semibold text-slate-200"><TrendingUp className="h-3.5 w-3.5 text-emerald-300" />{sim.parts.length ? "Pourquoi le score augmente" : "Effet de la sélection"}</p>
        {sim.parts.length ? <ul className="space-y-0.5 text-xs">{sim.parts.map((p, i) => (
          <li key={p.id} className={p.potential ? "text-amber-200" : "text-slate-300"} data-testid={`impact-part-${i}`}>
            <b className="tabular-nums">{sign(p.match)} %</b> compatibilité · <b className="tabular-nums">{sign(p.ifp)}</b> indice : {p.label}{p.potential ? " (à confirmer)" : ""}</li>))}</ul>
          : <p className="text-xs text-slate-500">Aucun gain de score estimé pour cette sélection : les modifications rendent surtout votre CV plus lisible pour cette offre.</p>}
        {sim.match.after === sim.match.before && <p className="mt-1.5 text-[11px] text-slate-400" data-testid="impact-match-zero">{sim.ifp.after > sim.ifp.before
          ? "Compatibilité inchangée : les compétences concernées sont déjà reconnues dans votre CV. Les reformulations les rendent plus visibles pour le recruteur et augmentent votre indice ; seules les compétences confirmées peuvent augmenter la compatibilité."
          : "Compatibilité inchangée : les compétences concernées sont déjà reconnues dans votre CV ; seules les compétences que vous confirmez peuvent l'augmenter."}</p>}
        {sim.criteria.length > 0 && <p className="mt-1.5 text-[11px] text-slate-500" data-testid="impact-criteria">Critères de l'indice qui progressent : {sim.criteria.map((c) => `${c.label} ${sign(c.delta)}`).join(" · ")}</p>}
        <p className="mt-1.5 text-[11px] text-slate-500">Estimation par les règles CareerOS (mêmes calculs que la comparaison CV ↔ offre et l'indice). Les gains ne s'additionnent pas toujours exactement.</p>
      </div>
    </section>
  );
};
