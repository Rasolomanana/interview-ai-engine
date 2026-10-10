const LABELS = { gemini: "Gemini", anthropic: "Anthropic", openrouter: "OpenRouter", openai: "OpenAI", deepseek: "DeepSeek", server: "Serveur (non détaillé)" };
const label = (p) => LABELS[p] || p;

export const SimulationsTable = ({ rows }) => (
  <div className="mt-4 rounded-2xl border border-white/10 bg-slate-900/60 p-5">
    <h3 className="mb-3 text-sm font-semibold text-slate-200">Dernières simulations (max 100) — fournisseur IA</h3>
    <div className="overflow-x-auto">
      <table className="w-full text-left text-[12px]">
        <thead className="text-slate-500">
          <tr className="border-b border-white/10">
            <th className="py-2 pr-4">Date</th>
            <th className="py-2 pr-4">Session</th>
            <th className="py-2 pr-4">Gemini</th>
            <th className="py-2 pr-4">Serveur</th>
            <th className="py-2 pr-4">Fournisseur principal</th>
            <th className="py-2 pr-4">Coût estimé</th>
          </tr>
        </thead>
        <tbody data-testid="admin-simulations-table">
          {rows.length === 0 ? (
            <tr><td colSpan={6} className="py-4 text-center text-slate-500">Aucune simulation enregistrée.</td></tr>
          ) : rows.map((r) => (
            <tr key={r.session_id + r.ts} data-testid={`admin-sim-row-${r.session_id}`} className="border-b border-white/5">
              <td className="py-2 pr-4 font-mono text-[11px] text-slate-400">{(r.ts || "").slice(0, 19).replace("T", " ")}</td>
              <td className="py-2 pr-4 font-mono text-[11px] text-slate-500">{r.session_id}</td>
              <td className="py-2 pr-4 text-sky-300">{r.gemini_calls}</td>
              <td className="py-2 pr-4 text-fuchsia-300">{r.server_calls}</td>
              <td className="py-2 pr-4 text-white" title={Object.entries(r.providers || {}).map(([p, n]) => `${label(p)}: ${n}`).join(" · ")}>
                {label(r.main_provider)}
                {r.mixed && <span data-testid="admin-sim-mixed" className="ml-2 rounded bg-amber-500/15 px-1.5 py-0.5 text-[10px] text-amber-300">mixte</span>}
              </td>
              <td className="py-2 pr-4 text-amber-300">${(Number(r.cost) || 0).toFixed(4)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  </div>
);
