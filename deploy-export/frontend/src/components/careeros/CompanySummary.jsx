import { useState } from "react";
import { ChevronDown } from "lucide-react";

const KIND = { workday: "Workday", successfactors: "SuccessFactors", oracle: "Oracle", icims: "iCIMS", greenhouse: "Greenhouse", lever: "Lever", ashby: "Ashby", smartrecruiters: "SmartRecruiters", amazon: "amazon.jobs" };

export const detectedLabel = (r) => {
  if (r?.candidates?.some((p) => p.ok)) return "";
  if (r?.unsupported?.length) return `Non pris en charge : ${r.unsupported.join(", ")}`;
  const bad = (r?.candidates || []).filter((p) => !p.ok).map((p) => p.kind_label);
  if (bad.length) return `Illisible : ${[...new Set(bad)].join(", ")}`;
  return "Aucun portail détecté";
};

const Group = ({ title, items, tone, testid, render }) => {
  const [open, setOpen] = useState(false);
  return (
    <div className={`rounded-lg border px-2.5 py-2 ${tone}`} data-testid={testid}>
      <button type="button" onClick={() => setOpen(!open)} className="flex w-full items-center justify-between gap-2 text-left" data-testid={`${testid}-toggle`}>
        <span className="text-[11px]">{title}</span>
        <span className="flex items-center gap-1 font-display text-lg font-bold text-white" data-testid={`${testid}-count`}>{items.length}<ChevronDown className={`h-3.5 w-3.5 transition-transform ${open ? "rotate-180" : ""}`} /></span>
      </button>
      {open && <ul className="mt-1.5 space-y-0.5 text-[11px] text-slate-300">{items.length ? items.map((c) => <li key={c.name} className="truncate">{render(c)}</li>) : <li className="text-slate-500">Aucune</li>}</ul>}
    </div>
  );
};

export const CompanySummary = ({ companies }) => {
  const active = companies.filter((c) => c.enabled);
  const portal = active.filter((c) => c.kind);
  const jooble = active.filter((c) => !c.kind);
  const unsupported = jooble.filter((c) => (c.detected || "").startsWith("Non pris en charge") || (c.detected || "").startsWith("Illisible"));
  return (
    <div className="grid gap-2 sm:grid-cols-3" data-testid="company-summary">
      <Group title="Via portail employeur" items={portal} tone="border-emerald-400/25 bg-emerald-500/5" testid="summary-portal" render={(c) => `${c.name} · ${KIND[c.kind] || c.kind}`} />
      <Group title="Suivies via Jooble" items={jooble} tone="border-white/10 bg-white/[0.02]" testid="summary-jooble" render={(c) => `${c.name}${c.detected ? ` · ${c.detected}` : " · non détectée"}`} />
      <Group title="Détectées mais non prises en charge" items={unsupported} tone="border-amber-400/25 bg-amber-500/5" testid="summary-unsupported" render={(c) => `${c.name} · ${c.detected.replace(/^(Non pris en charge|Illisible) : /, "")} (repli Jooble)`} />
    </div>
  );
};
