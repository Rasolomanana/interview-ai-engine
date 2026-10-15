import { CheckCircle2, CircleHelp, XCircle } from "lucide-react";

const ICON = { ok: [CheckCircle2, "text-emerald-400"], missing: [XCircle, "text-rose-400"], unknown: [CircleHelp, "text-amber-300"] };

export const Requirements = ({ items, title, badge, testid }) => {
  if (!items?.length) return null;
  const ok = items.filter((r) => r.status === "ok").length;
  return (
    <div data-testid={testid}>
      <p className="mb-2 flex flex-wrap items-center gap-2 text-xs font-semibold text-slate-200">{title}
        <span className={`rounded-full border px-2 py-0.5 text-[10px] font-normal ${badge}`}>{items[0].source === "ia" ? "Confirmé par l'analyse IA" : "Détecté par règles"}</span>
        <span className="ml-auto text-slate-300" data-testid={`${testid}-total`}>{ok}/{items.length} exigences couvertes</span></p>
      <ul className="space-y-1">{items.map((r, i) => {
        const [I, c] = ICON[r.status] || ICON.unknown;
        return <li key={i} className="flex items-start gap-2 text-xs" data-testid={`${testid}-${i}`}><I className={`mt-0.5 h-3.5 w-3.5 shrink-0 ${c}`} /><span className="text-slate-200">{r.label}<span className="block text-[11px] text-slate-500">{r.evidence}</span></span></li>;
      })}</ul>
    </div>
  );
};
