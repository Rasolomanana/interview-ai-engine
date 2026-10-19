import { AlertTriangle, ShieldCheck } from "lucide-react";

const CONF = { "élevée": "text-emerald-300", moyenne: "text-amber-300", faible: "text-slate-400" };
const Check = ({ x, on, toggle, children }) => (
  <label className={`flex cursor-pointer gap-2 rounded-xl border p-2.5 text-xs transition-colors ${on ? "border-indigo-400/40 bg-indigo-500/[0.07]" : "border-white/[0.07] hover:border-white/15"}`} data-testid={`proposal-${x.id}`}>
    <input type="checkbox" checked={on} onChange={() => toggle(x.id)} className="mt-0.5 h-3.5 w-3.5 shrink-0 accent-indigo-500" aria-label={`Sélectionner : ${x.label || x.after}`} data-testid={`proposal-check-${x.id}`} />
    <span className="min-w-0 flex-1">{children}</span>
  </label>
);

// Member selects every change: guaranteed rewordings/highlights (checked by default) and skills to confirm (never checked by default).
export const ProposalList = ({ items, sel, toggle, setAll, rejected, ai }) => {
  const sure = items.filter((x) => x.type !== "a_confirmer"), confirm = items.filter((x) => x.type === "a_confirmer");
  const allOn = sure.length > 0 && sure.every((x) => sel.has(x.id));
  return (
    <div className="space-y-3" data-testid="proposal-list">
      <label className="flex items-center gap-2 text-xs font-semibold text-white"><input type="checkbox" checked={allOn} onChange={() => setAll(!allOn)} className="h-4 w-4 accent-indigo-500" data-testid="proposal-accept-all" />
        Accepter toutes les améliorations sûres ({sure.length})</label>
      <p className="flex items-center gap-1.5 text-[11px] text-emerald-300"><ShieldCheck className="h-3.5 w-3.5" />Gain garanti : uniquement des reformulations d'informations déjà présentes dans votre CV.</p>
      {sure.map((x) => (
        <Check key={x.id} x={x} on={sel.has(x.id)} toggle={toggle}>
          {x.before && <span className="block text-slate-500 line-through decoration-slate-600" data-testid={`proposal-before-${x.id}`}>{x.before.trim()}</span>}
          <span className={`block ${x.type === "ajout" ? "text-emerald-200" : "text-amber-100"}`} data-testid={`proposal-after-${x.id}`}>{x.after.trim()}</span>
          {x.reason && <span className="mt-0.5 block text-[11px] text-slate-400">{x.reason}</span>}
        </Check>))}
      {!sure.length && <p className="text-xs text-slate-500" data-testid="proposal-none">{ai === "ok" ? "Votre CV met déjà bien en valeur les éléments de cette offre." : "Les reformulations automatiques sont momentanément indisponibles : réessayez plus tard. Les compétences à confirmer restent disponibles."}</p>}
      {rejected?.length > 0 && <p className="text-[11px] text-slate-500" data-testid="proposal-rejected">{rejected.length} proposition(s) écartée(s) automatiquement car elle(s) ajoutai(en)t une information absente de votre CV.</p>}
      {confirm.length > 0 && <div className="space-y-2 border-t border-white/[0.07] pt-3" data-testid="proposal-confirm-group">
        <p className="flex items-center gap-1.5 text-xs font-semibold text-amber-200"><AlertTriangle className="h-3.5 w-3.5" />Gain potentiel : compétences de l'offre absentes de votre CV</p>
        <p className="text-[11px] text-slate-400">À cocher seulement si vous l'avez réellement pratiquée. CareerOS ne les ajoute jamais automatiquement.</p>
        {confirm.map((x) => (
          <Check key={x.id} x={x} on={sel.has(x.id)} toggle={toggle}>
            <span className="block font-semibold text-slate-100">{x.label}{x.required ? "" : " (souhaitée)"}</span>
            <span className="block text-[11px] text-slate-400">{x.related.length ? `Compétence absente du CV mais ${x.confidence === "élevée" ? "fortement " : ""}liée à : ${x.related.join(", ")}` : `Domaine « ${x.domain} » peu présent dans votre CV`}</span>
            <span className={`block text-[11px] ${CONF[x.confidence]}`} data-testid={`proposal-confidence-${x.id}`}>Confiance : {x.confidence}</span>
          </Check>))}
      </div>}
    </div>
  );
};
