const TONES = {
  A: { ring: "#10b981", text: "text-emerald-300", bg: "bg-emerald-500/10 ring-emerald-400/30", label: "Priorité A — postuler en premier" },
  B: { ring: "#f59e0b", text: "text-amber-300", bg: "bg-amber-500/10 ring-amber-400/30", label: "Priorité B — postuler après optimisation" },
  C: { ring: "#f43f5e", text: "text-rose-300", bg: "bg-rose-500/10 ring-rose-400/30", label: "Priorité C — à éviter ou en dernier" },
};

export const PriorityBadge = ({ priority, testid = "priority-badge" }) => {
  const t = TONES[priority];
  if (!t) return <span className="text-xs text-slate-500">—</span>;
  return <span data-testid={testid} className={`inline-flex h-7 w-7 items-center justify-center rounded-lg font-display text-sm font-bold ring-1 ${t.bg} ${t.text}`}>{priority}</span>;
};

export const IpsGauge = ({ score, priority }) => {
  const t = TONES[priority] || TONES.C;
  const pct = Math.max(0, Math.min(100, score || 0));
  const R = 54, C = 2 * Math.PI * R;
  return (
    <div className="flex items-center gap-5" data-testid="ips-gauge">
      <div className="relative h-36 w-36 shrink-0">
        <svg viewBox="0 0 128 128" className="h-full w-full -rotate-90">
          <circle cx="64" cy="64" r={R} stroke="rgba(255,255,255,0.07)" strokeWidth="10" fill="none" />
          <circle cx="64" cy="64" r={R} stroke={t.ring} strokeWidth="10" fill="none" strokeLinecap="round"
            strokeDasharray={C} strokeDashoffset={C * (1 - pct / 100)} style={{ transition: "stroke-dashoffset 900ms ease" }} />
        </svg>
        <div className="absolute inset-0 flex flex-col items-center justify-center">
          <span className="font-display text-4xl font-bold text-white" data-testid="ips-score">{score ?? "—"}</span>
          <span className="font-mono text-[10px] uppercase tracking-[0.2em] text-slate-500">IPS / 100</span>
        </div>
      </div>
      <div>
        <PriorityBadge priority={priority} />
        <p className={`mt-2 text-sm font-semibold ${t.text}`} data-testid="priority-label">{t.label}</p>
        <p className="mt-1 max-w-xs text-xs text-slate-500">Interview Probability Score — probabilité réelle d'obtenir une entrevue, calculée par la formule CareerOS.</p>
      </div>
    </div>
  );
};
