const TONE = { same: "text-slate-500", improved: "bg-amber-400/15 text-amber-100", added: "bg-emerald-400/15 text-emerald-100", removed: "text-rose-300/70 line-through" };

// Side-by-side: current CV | optimised CV (green = added, yellow = improved, grey = unchanged).
export const CvDiff = ({ cv, rows, afterTitle = "CV optimisé" }) => (
  <div className="space-y-2" data-testid="cv-diff">
    <p className="flex flex-wrap gap-3 text-[11px] text-slate-400">
      <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-emerald-400/60" />Ajout</span>
      <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-amber-400/60" />Amélioration</span>
      <span><i className="mr-1 inline-block h-2.5 w-2.5 rounded-sm bg-slate-500/60" />Inchangé</span>
      {rows.some((r) => r.tag === "removed") && <span className="text-rose-300/80 line-through">Supprimé</span>}</p>
    <div className="grid gap-3 md:grid-cols-2">
      <section className="min-w-0 rounded-xl border border-white/[0.07] p-3" data-testid="cv-diff-before">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-slate-400">CV actuel</p>
        <div className="max-h-[50vh] overflow-y-auto whitespace-pre-wrap break-words text-xs text-slate-400">{cv}</div>
      </section>
      <section className="min-w-0 rounded-xl border border-indigo-400/25 p-3" data-testid="cv-diff-after">
        <p className="mb-2 text-[11px] font-semibold uppercase tracking-wider text-indigo-200">{afterTitle}</p>
        <div className="max-h-[50vh] space-y-0.5 overflow-y-auto text-xs">
          {rows.map((r, i) => <p key={i} className={`whitespace-pre-wrap break-words rounded px-1 ${TONE[r.tag]}`} title={r.prev ? `Avant : ${r.prev.trim()}` : ""} data-testid={`cv-diff-row-${r.tag}`}>{r.text || " "}</p>)}
        </div>
      </section>
    </div>
  </div>
);
