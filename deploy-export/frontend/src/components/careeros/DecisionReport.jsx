import { CheckCircle2, AlertTriangle, ArrowUpRight, Lightbulb } from "lucide-react";

const Factor = ({ f, good }) => (
  <li className="text-sm">
    <div className="flex items-center justify-between gap-2">
      <span className={`flex items-center gap-1.5 font-medium ${good ? "text-emerald-200" : "text-rose-200"}`}>
        {good ? <CheckCircle2 className="h-3.5 w-3.5" /> : <AlertTriangle className="h-3.5 w-3.5" />}{f.critere}
      </span>
    </div>
    <p className="mt-0.5 pl-5 text-xs text-slate-400">{f.raison}</p>
  </li>
);

// Mandatory explanation shipped with every IPS / priority.
export const DecisionReport = ({ report }) => {
  if (!report) return null;
  return (
    <section className="rounded-2xl border border-indigo-400/20 bg-gradient-to-br from-indigo-500/[0.07] to-transparent p-5" data-testid="decision-report">
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-indigo-300">Decision Report</p>
      <p className="mt-2 text-base leading-relaxed text-white" data-testid="decision-report-summary">{report.summary}</p>
      <ul className="mt-3 space-y-1" data-testid="decision-report-why">
        {(report.why_priority || []).map((w, i) => <li key={i} className="text-xs text-slate-300">— {w}</li>)}
      </ul>
      <div className="mt-5 grid gap-5 md:grid-cols-3">
        <div><p className="mb-2 text-xs font-semibold text-slate-300">Ce qui porte l'IPS</p><ul className="space-y-2.5" data-testid="decision-report-strengths">{(report.strengths || []).map((f, i) => <Factor key={i} f={f} good />)}</ul></div>
        <div><p className="mb-2 text-xs font-semibold text-slate-300">Ce qui le freine</p><ul className="space-y-2.5" data-testid="decision-report-weaknesses">{(report.weaknesses || []).map((f, i) => <Factor key={i} f={f} />)}</ul></div>
        <div>
          <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-slate-300"><Lightbulb className="h-3.5 w-3.5 text-amber-300" />Actions pour l'améliorer</p>
          <ul className="space-y-2.5" data-testid="decision-report-actions">
            {(report.actions || []).map((a, i) => (
              <li key={i} className="text-sm text-slate-200"><span className="flex gap-1.5"><ArrowUpRight className="mt-0.5 h-3.5 w-3.5 shrink-0 text-amber-300" />{a.action}</span>
                <span className="block pl-5 text-[11px] text-slate-500">{[a.critere, a.impact_estime].filter(Boolean).join(" · ")}</span></li>
            ))}
          </ul>
          {(report.keywords_to_add || []).length > 0 && <p className="mt-3 text-[11px] text-slate-500">Mots-clés à intégrer : <span className="text-slate-300">{report.keywords_to_add.join(", ")}</span></p>}
        </div>
      </div>
    </section>
  );
};

export function decisionReportMd(r) {
  if (!r) return "";
  const l = (a, f) => (a || []).map(f).join("\n");
  return `## Decision Report
${r.summary}
${l(r.why_priority, (w) => `- ${w}`)}

### Ce qui porte l'IPS
${l(r.strengths, (f) => `- **${f.critere}** : ${f.raison}`)}

### Ce qui le freine
${l(r.weaknesses, (f) => `- **${f.critere}** : ${f.raison}`)}

### Actions pour l'améliorer
${l(r.actions, (a) => `- ${a.action}${a.impact_estime ? ` (${a.impact_estime})` : ""}`)}`;
}
