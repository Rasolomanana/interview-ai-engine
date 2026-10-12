import { useState } from "react";
import { GitCompareArrows, Loader2, RefreshCw, TrendingDown, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { careeros } from "@/lib/careeros";

const inputCls = "w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/60";

export const VersionBar = ({ versions, viewing, onView }) => (
  <div className="flex flex-wrap items-center gap-1.5" data-testid="version-bar">
    {versions.map((v, i) => {
      const prev = versions[i - 1]?.ips;
      const d = prev != null && v.ips != null ? v.ips - prev : null;
      return (
        <button key={v.version} onClick={() => onView(v.version)} data-testid={`version-chip-${v.version}`} title={v.change_note}
          className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 font-mono text-[11px] transition-colors ${viewing === v.version ? "border-indigo-400/60 bg-indigo-500/15 text-white" : "border-white/10 text-slate-400 hover:text-white"}`}>
          v{v.version} · {v.status === "generating" ? <Loader2 className="h-3 w-3 animate-spin" /> : `IPS ${v.ips ?? "—"}`}
          {d != null && d !== 0 && <span className={d > 0 ? "text-emerald-300" : "text-rose-300"}>{d > 0 ? `+${d}` : d}</span>}
        </button>
      );
    })}
  </div>
);

export const ReanalyzeDialog = ({ open, onOpenChange, app, onStarted }) => {
  const [f, setF] = useState({ change_note: "", use_memory_cv: true, cv_text: "", network: app.inputs?.network || "aucun", posted_date: app.inputs?.posted_date || "" });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try {
      const body = { change_note: f.change_note, use_memory_cv: f.use_memory_cv, network: f.network, posted_date: f.posted_date };
      if (!f.use_memory_cv && f.cv_text.trim()) body.cv_text = f.cv_text;
      const r = await careeros.reanalyze(app.id, body);
      toast.success(`Version v${r.version} en cours de génération`);
      onOpenChange(false); onStarted(r.version);
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="border-white/10 bg-[#121520] text-slate-100 sm:max-w-lg" data-testid="reanalyze-dialog">
        <DialogHeader><DialogTitle className="font-display">Réanalyser {app.code}</DialogTitle></DialogHeader>
        <DialogDescription className="text-xs text-slate-400">Une nouvelle version sera créée. Les versions précédentes restent conservées intégralement.</DialogDescription>
        <label className="block text-xs text-slate-400">Qu'est-ce qui a changé ?
          <input value={f.change_note} onChange={(e) => setF({ ...f, change_note: e.target.value })} className={`${inputCls} mt-1`} placeholder="Ex. CV optimisé + certification PL-300" data-testid="reanalyze-note-input" /></label>
        <label className="flex items-center gap-2 text-xs text-slate-300"><input type="checkbox" className="accent-indigo-500" checked={f.use_memory_cv} onChange={(e) => setF({ ...f, use_memory_cv: e.target.checked })} data-testid="reanalyze-use-memory-cv" />Utiliser le CV actuel de ma Career Memory</label>
        {!f.use_memory_cv && <textarea rows={6} value={f.cv_text} onChange={(e) => setF({ ...f, cv_text: e.target.value })} className={`${inputCls} font-mono text-xs`} placeholder="Collez le CV mis à jour (vide = même CV que la version précédente)" data-testid="reanalyze-cv-input" />}
        <div className="grid grid-cols-2 gap-3">
          <label className="text-xs text-slate-400">Contact dans l'entreprise
            <select value={f.network} onChange={(e) => setF({ ...f, network: e.target.value })} className={`${inputCls} mt-1`} data-testid="reanalyze-network-select">
              <option value="aucun">Aucun</option><option value="contact">Un contact</option><option value="recommandation">Recommandation</option></select></label>
          <label className="text-xs text-slate-400">Date de publication
            <input type="date" value={f.posted_date} onChange={(e) => setF({ ...f, posted_date: e.target.value })} className={`${inputCls} mt-1`} data-testid="reanalyze-date-input" /></label>
        </div>
        <button onClick={submit} disabled={busy} data-testid="reanalyze-submit-btn" className="flex items-center justify-center gap-2 rounded-xl bg-indigo-500 py-2.5 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />} Lancer la réanalyse
        </button>
      </DialogContent>
    </Dialog>
  );
};

const Delta = ({ d, good }) => (
  <li className="rounded-lg bg-black/30 p-2.5 text-xs">
    <div className="flex items-center justify-between"><span className={`flex items-center gap-1 font-medium ${good ? "text-emerald-200" : "text-rose-200"}`}>{good ? <TrendingUp className="h-3.5 w-3.5" /> : <TrendingDown className="h-3.5 w-3.5" />}{d.critere}</span>
      <span className="font-mono text-slate-400">{d.avant} → {d.apres}/10 ({d.delta_points > 0 ? "+" : ""}{d.delta_points} pts)</span></div>
    <p className="mt-1 text-slate-400">{d.raison_apres}</p>
  </li>
);

export const CompareDialog = ({ open, onOpenChange, app }) => {
  const done = (app.versions || []).filter((v) => v.ips != null);
  const [a, setA] = useState(done[0]?.version);
  const [b, setB] = useState(done[done.length - 1]?.version);
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setRes(await careeros.compare(app.id, a, b)); } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  const sel = (v, set, tid) => (
    <select value={v} onChange={(e) => { set(Number(e.target.value)); setRes(null); }} className={inputCls} data-testid={tid}>
      {done.map((x) => <option key={x.version} value={x.version}>{`v${x.version} — IPS ${x.ips}`}</option>)}
    </select>
  );
  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto border-white/10 bg-[#121520] text-slate-100 sm:max-w-2xl" data-testid="compare-dialog">
        <DialogHeader><DialogTitle className="font-display">Comparer les versions — {app.code}</DialogTitle><DialogDescription className="text-xs text-slate-400">Ce qui a changé, ce qui a amélioré et ce qui a détérioré l'IPS.</DialogDescription></DialogHeader>
        <div className="grid grid-cols-[1fr_auto_1fr_auto] items-center gap-2">
          {sel(a, setA, "compare-from-select")}<span className="text-slate-500">→</span>{sel(b, setB, "compare-to-select")}
          <button onClick={run} disabled={busy || a === b} data-testid="compare-run-btn" className="flex items-center gap-1.5 rounded-xl bg-indigo-500 px-3 py-2 text-xs font-semibold text-white disabled:opacity-50">
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <GitCompareArrows className="h-3.5 w-3.5" />}Comparer</button>
        </div>
        {res && (
          <div className="space-y-4" data-testid="compare-result">
            <div className="rounded-xl border border-white/10 p-3">
              <p className="font-display text-2xl font-bold" data-testid="compare-ips-delta">IPS {res.ips.avant} → {res.ips.apres} <span className={res.ips.delta > 0 ? "text-emerald-300" : res.ips.delta < 0 ? "text-rose-300" : "text-slate-400"}>({res.ips.delta > 0 ? "+" : ""}{res.ips.delta})</span></p>
              <p className="text-xs text-slate-400">Priorité {res.priority.avant} → {res.priority.apres} · ATS {res.ats.avant ?? "—"} → {res.ats.apres ?? "—"}</p>
              <p className="mt-2 text-sm text-slate-200" data-testid="compare-explanation">{res.explanation}</p>
            </div>
            <div><p className="mb-1.5 text-xs font-semibold text-slate-300">Ce qui a changé</p><ul className="space-y-1 text-xs text-slate-400" data-testid="compare-input-changes">{res.input_changes.map((c, i) => <li key={i}>— {c}</li>)}</ul></div>
            {res.improved.length > 0 && <div><p className="mb-1.5 text-xs font-semibold text-emerald-300">Ce qui a amélioré le score</p><ul className="space-y-1.5" data-testid="compare-improved">{res.improved.map((d, i) => <Delta key={i} d={d} good />)}</ul></div>}
            {res.worsened.length > 0 && <div><p className="mb-1.5 text-xs font-semibold text-rose-300">Ce qui a détérioré le score</p><ul className="space-y-1.5" data-testid="compare-worsened">{res.worsened.map((d, i) => <Delta key={i} d={d} />)}</ul></div>}
            {(res.keywords_now_covered.length > 0 || res.keywords_newly_missing.length > 0) && (
              <p className="text-xs text-slate-400">Mots-clés désormais couverts : <span className="text-emerald-300">{res.keywords_now_covered.join(", ") || "—"}</span> · nouvellement manquants : <span className="text-rose-300">{res.keywords_newly_missing.join(", ") || "—"}</span></p>
            )}
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
};
