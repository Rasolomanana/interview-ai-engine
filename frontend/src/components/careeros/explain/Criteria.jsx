const SRC = { ia: "IA", formule: "Formule", neutre: "Neutre", membre: "Membre" };

export const lostOf = (r, total) => ((r.weight - r.points) * 100) / total;

export const Criteria = ({ ips }) => {
  const total = ips.criteria.reduce((a, r) => a + r.weight, 0);
  const rows = [...ips.criteria].sort((a, b) => lostOf(b, total) - lostOf(a, total));
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[560px] text-left text-xs" data-testid="explain-criteria">
        <thead className="text-[10px] uppercase tracking-wider text-slate-500"><tr>
          <th className="py-1.5 pr-3 font-medium">Critère</th><th className="pr-3 text-right font-medium">Note</th><th className="pr-3 text-right font-medium">Points</th>
          <th className="pr-3 text-right font-medium">Perdus</th><th className="font-medium">Pourquoi</th></tr></thead>
        <tbody>{rows.map((r) => {
          const lost = lostOf(r, total);
          return (
            <tr key={r.key} className="border-t border-white/[0.05] align-top" data-testid={`explain-row-${r.key}`}>
              <td className="py-2 pr-3 font-medium text-slate-200">{r.label}<span className="ml-1.5 rounded border border-white/10 px-1 text-[9px] text-slate-500">{r.source === "ia" && ips.method !== "ia" ? "Règles" : SRC[r.source] || r.source}</span></td>
              <td className="pr-3 text-right tabular-nums text-slate-300">{r.score}/10</td>
              <td className="pr-3 text-right tabular-nums text-slate-300">{(r.points * 100 / total).toFixed(1)} / {(r.weight * 100 / total).toFixed(1)}</td>
              <td className={`pr-3 text-right tabular-nums font-semibold ${lost >= 4 ? "text-rose-300" : lost >= 2 ? "text-amber-300" : "text-slate-500"}`}>−{lost.toFixed(1)}</td>
              <td className="py-2 text-slate-400">{r.justification}</td>
            </tr>);
        })}</tbody>
      </table>
    </div>
  );
};
