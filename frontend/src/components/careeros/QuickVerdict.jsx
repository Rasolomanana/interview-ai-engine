import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { radar } from "@/lib/careeros";

const TONE = { A: "border-emerald-400/40 bg-emerald-500/10 text-emerald-200", B: "border-amber-400/40 bg-amber-500/10 text-amber-200", C: "border-white/15 bg-white/5 text-slate-300" };
const list = (x) => (Array.isArray(x) ? x : []).slice(0, 3).map((y) => (typeof y === "string" ? y : y?.raison || y?.critere || "")).filter(Boolean);

// Free rule-based verdict on a pasted offer, with the next step (generate the pack) one click away.
export const QuickVerdict = ({ o, onDetail, packLabel = "Générer le pack", onPack, hidePack }) => {
  const nav = useNavigate();
  const [busy, setBusy] = useState(false);
  const p = o.ips?.priority || "C";
  const r = o.decision_report || {};
  const pack = async () => {
    if (onPack) return onPack(o);
    setBusy(true);
    try { const x = await radar.pack(o.id); nav(`/careeros/candidature/${x.id}`); } catch (e) { toast.error(e.message); setBusy(false); }
  };
  return (
    <div className="space-y-3 rounded-2xl border border-white/10 bg-black/20 p-4" data-testid="quick-verdict">
      <div className="flex flex-wrap items-center gap-3">
        <span className={`rounded-full border px-3 py-1 text-sm font-bold ${TONE[p]}`} data-testid="quick-verdict-priority">Priorité {p}</span>
        <span className="font-mono text-2xl font-bold text-white" data-testid="quick-verdict-ips">IPS {o.ips?.score ?? "—"}</span>
        <span className="text-[11px] text-slate-500">Pré-analyse gratuite par règles · offre ajoutée à votre Radar</span>
      </div>
      <div className="grid gap-2 text-xs sm:grid-cols-2">
        <ul className="space-y-0.5 text-emerald-300">{list(r.strengths || r.reasons_apply).map((x, i) => <li key={i}>+ {x}</li>)}</ul>
        <ul className="space-y-0.5 text-rose-300">{list(r.weaknesses || r.reasons_avoid).map((x, i) => <li key={i}>– {x}</li>)}</ul>
      </div>
      <p className="text-xs text-slate-300" data-testid="quick-verdict-advice">{(r.summary ? `${r.summary} ` : "") + (p === "A" ? "Offre prioritaire : générez le pack maintenant." : p === "B" ? "Offre intéressante : le pack vous aidera à combler les écarts." : "Offre peu adaptée à votre profil : générez le pack seulement si elle vous tient à cœur.")}</p>
      <div className="flex flex-wrap gap-2">
        {!hidePack && <button type="button" onClick={pack} disabled={busy} className="flex items-center gap-1.5 rounded-full bg-indigo-500 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-50" data-testid="quick-verdict-pack-btn">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}{packLabel}</button>}
        {onDetail && <button type="button" onClick={() => onDetail(o)} className="rounded-full border border-white/10 px-4 py-2 text-xs text-slate-300 hover:text-white" data-testid="quick-verdict-detail-btn">Pourquoi ce score ?</button>}
      </div>
    </div>
  );
};
