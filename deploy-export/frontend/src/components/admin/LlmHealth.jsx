import { useState } from "react";
import { Activity, Loader2 } from "lucide-react";
import { adminLlmHealth } from "@/lib/api";

export const LlmHealth = () => {
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const test = async () => {
    setBusy(true);
    try { setRes(await adminLlmHealth(sessionStorage.getItem("adminPwd"))); } catch (e) { setRes({ error: e.message, providers: [] }); } finally { setBusy(false); }
  };
  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-slate-900/60 p-5" data-testid="admin-llm-health">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-200"><Activity className="h-4 w-4 text-emerald-400" />Santé des fournisseurs IA du serveur</h3>
        <button onClick={test} disabled={busy} data-testid="admin-llm-health-btn" className="flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-3 py-1.5 text-xs text-emerald-200 disabled:opacity-60">
          {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}Tester les fournisseurs IA</button>
      </div>
      <p className="mt-1 text-[11px] text-slate-500">Utilisés par les packs candidature et le Radar. Un appel très court par fournisseur.</p>
      {res && (
        <div className="mt-3 space-y-1.5 text-xs" data-testid="admin-llm-health-result">
          {res.error && <p className="text-red-400">{res.error}</p>}
          {!res.error && res.providers.length === 0 && <p className="text-red-400">Aucun fournisseur configuré sur le serveur.</p>}
          {res.providers.map((p) => (
            <div key={`${p.provider}-${p.model}`} className="flex flex-wrap items-center gap-2" data-testid={`admin-llm-health-${p.provider}`}>
              <span className={`h-2.5 w-2.5 rounded-full ${p.ok ? "bg-emerald-400" : "bg-red-400"}`} />
              <span className="font-medium text-slate-200">{p.provider}</span><span className="text-slate-500">{p.model}</span>
              <span className={p.ok ? "text-emerald-300" : "text-red-300"}>{p.ok ? "OK" : p.error}</span>
            </div>))}
        </div>)}
    </div>
  );
};
