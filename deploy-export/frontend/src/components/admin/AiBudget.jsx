import { useCallback, useEffect, useState } from "react";
import { Cpu, Loader2, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { adminAiBudget, adminAiBudgetSave, adminAiBudgetReset } from "@/lib/api";

const pwd = () => sessionStorage.getItem("adminPwd");

const Kpi = ({ label, value, sub, testid, tone = "text-white" }) => (
  <div className="rounded-xl border border-white/10 p-3" data-testid={testid}>
    <p className="text-[11px] text-slate-500">{label}</p><p className={`font-mono text-xl font-bold ${tone}`}>{value}</p>{sub && <p className="text-[11px] text-slate-500">{sub}</p>}
  </div>
);

// Global AI budget: daily counter, per-provider usage, current provider, configurable cap, rules-only mode, cache.
export const AiBudget = () => {
  const [d, setD] = useState(null);
  const [cfg, setCfg] = useState(null);
  const [busy, setBusy] = useState(false);
  const load = useCallback(() => adminAiBudget(pwd()).then((x) => { setD(x); setCfg(x.config); }).catch((e) => toast.error(e.message)), []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Loader2 className="h-5 w-5 animate-spin text-emerald-400" />;
  const save = async () => { setBusy(true); try { await adminAiBudgetSave(pwd(), { ...cfg, daily_cap: Number(cfg.daily_cap) || 0 }); toast.success("Réglages IA enregistrés"); load(); } catch (e) { toast.error(e.message); } finally { setBusy(false); } };
  const pct = d.cap ? Math.min(100, Math.round((d.used_today * 100) / d.cap)) : 100;
  return (
    <section className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-4 sm:p-5" data-testid="admin-ai-budget">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-200"><Cpu className="h-4 w-4 text-emerald-400" />IA & quotas gratuits</h3>
      {d.rules_only && <p className="rounded-lg border border-amber-400/30 bg-amber-500/10 p-2.5 text-xs text-amber-200" data-testid="ai-rules-only-banner">Mode « Règles uniquement » actif : les analyses utilisent les règles CareerOS (gratuites) jusqu'à la remise à zéro ({new Date(d.reset_at).toLocaleString("fr-CA", { timeStyle: "short", dateStyle: "short" })}).</p>}
      <div className="grid grid-cols-2 gap-2 md:grid-cols-4">
        <Kpi label="Appels IA aujourd'hui (tous membres)" value={`${d.used_today} / ${d.cap}`} sub={`${pct} % du plafond`} testid="ai-kpi-used" />
        <Kpi label="Fournisseur actuellement utilisé" value={d.current || "Règles uniquement"} sub={d.last_used ? `Dernier appel : ${d.last_used}` : "Aucun appel aujourd'hui"} testid="ai-kpi-current" tone={d.current ? "text-emerald-300" : "text-amber-300"} />
        <Kpi label="Réponses servies par le cache aujourd'hui" value={d.cache_hits_today} sub={`${d.cache_size} analyse(s) en cache · 30 jours`} testid="ai-kpi-cache" />
        <Kpi label="Mode" value={d.rules_only ? "Règles" : "IA"} sub={cfg.allow_paid ? "Secours payant autorisé" : "Gratuit uniquement"} testid="ai-kpi-mode" />
      </div>
      <div className="h-2 overflow-hidden rounded bg-white/10"><div className={`h-full ${pct >= 90 ? "bg-rose-400" : pct >= 70 ? "bg-amber-400" : "bg-emerald-400"}`} style={{ width: `${pct}%` }} /></div>
      <table className="w-full text-left text-xs" data-testid="ai-providers-table">
        <thead className="text-slate-500"><tr><th className="py-1">Ordre</th><th>Fournisseur</th><th>Type</th><th>Appels aujourd'hui</th><th>État</th><th /></tr></thead>
        <tbody>{d.providers.map((p, i) => (
          <tr key={p.label} className="border-t border-white/5" data-testid={`ai-provider-${p.label}`}>
            <td className="py-1.5 font-mono text-slate-500">{i + 1}</td><td className="text-slate-200">{p.name}</td><td className={p.free ? "text-emerald-300" : "text-amber-300"}>{p.free ? "Gratuit" : "Payant"}</td>
            <td className="font-mono text-white">{p.calls_today}</td>
            <td className={p.exhausted ? "text-rose-300" : p.disabled ? "text-slate-500" : "text-emerald-300"} title={p.last_error}>{p.exhausted ? "Quota du jour atteint" : p.disabled ? "Désactivé (payant)" : "Disponible"}</td>
            <td>{p.exhausted && <button type="button" onClick={async () => { await adminAiBudgetReset(pwd(), p.label); load(); }} className="flex items-center gap-1 text-[11px] text-indigo-300 hover:text-white" data-testid={`ai-reset-${p.label}`}><RotateCcw className="h-3 w-3" />Réactiver</button>}</td>
          </tr>))}
          {!d.providers.length && <tr><td colSpan={6} className="py-2 text-slate-500">Aucun fournisseur configuré (ajoutez les clés dans Render).</td></tr>}</tbody>
      </table>
      <div className="flex flex-wrap items-end gap-4 border-t border-white/5 pt-3 text-xs">
        <label className="text-slate-400">Plafond quotidien global (appels IA)
          <input type="number" min={0} value={cfg.daily_cap} onChange={(e) => setCfg({ ...cfg, daily_cap: e.target.value })} className="mt-1 block w-32 rounded-lg border border-white/10 bg-black/40 px-2 py-1 text-white" data-testid="ai-cap-input" /></label>
        <label className="flex items-center gap-2 text-slate-300"><input type="checkbox" checked={cfg.allow_paid} onChange={(e) => setCfg({ ...cfg, allow_paid: e.target.checked })} data-testid="ai-allow-paid" />Autoriser le secours payant (Anthropic) quand les quotas gratuits sont atteints</label>
        <label className="flex items-center gap-2 text-slate-300"><input type="checkbox" checked={cfg.force_rules_only} onChange={(e) => setCfg({ ...cfg, force_rules_only: e.target.checked })} data-testid="ai-force-rules" />Forcer « Règles uniquement »</label>
        <button type="button" onClick={save} disabled={busy} className="rounded-full bg-emerald-600 px-4 py-1.5 font-semibold text-white disabled:opacity-50" data-testid="ai-save-btn">Enregistrer</button>
      </div>
      <p className="text-[11px] text-slate-500">Chaîne : Gemini Flash → Groq → OpenRouter gratuit → Mistral → Anthropic (dernier recours, seulement si autorisé). Un fournisseur qui répond « quota atteint » (429) est sauté jusqu'à minuit UTC. Une même analyse (même CV, même offre) est resservie depuis le cache pendant 30 jours, sans appel IA.</p>
    </section>
  );
};
