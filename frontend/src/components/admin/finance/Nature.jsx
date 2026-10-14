const STYLES = {
  real: ["Réel", "border-emerald-400/40 bg-emerald-500/10 text-emerald-300"],
  estimated: ["Estimé", "border-amber-400/40 bg-amber-500/10 text-amber-300"],
  calculated: ["Calculé", "border-sky-400/40 bg-sky-500/10 text-sky-300"],
};
const TIPS = {
  real: "Issu d'une facture, d'un fournisseur ou d'un montant réellement encaissé",
  estimated: "Valeur saisie, montant récurrent par défaut ou calcul basé sur une hypothèse (jetons × tarif)",
  calculated: "Dérivé automatiquement par le système à partir des autres valeurs",
};

export const Nature = ({ kind, realPct, testid }) => {
  const k = kind === "mixed" ? "calculated" : kind;
  const [label, cls] = STYLES[k] || STYLES.calculated;
  const extra = kind === "mixed" || (k === "calculated" && realPct !== undefined && realPct !== null) ? ` · ${Math.floor(realPct ?? 0)} % réel` : "";
  return (
    <span title={TIPS[k]} data-testid={testid} className={`inline-flex shrink-0 items-center rounded-full border px-1.5 py-px text-[9px] font-semibold uppercase tracking-wider ${cls}`}>
      {label}{extra}
    </span>
  );
};

export const NatureLegend = () => (
  <div className="flex flex-wrap items-center gap-3 text-[11px] text-slate-400" data-testid="nature-legend">
    {Object.keys(STYLES).map((k) => <span key={k} className="flex items-center gap-1.5"><Nature kind={k} />{TIPS[k]}</span>)}
  </div>
);
