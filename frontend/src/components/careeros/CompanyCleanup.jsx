import { useEffect, useMemo, useState } from "react";
import { Ban, Loader2, Sparkles, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { radar } from "@/lib/careeros";

const ST = { active: ["Active (≤ 30 j)", "text-emerald-300"], low: ["Peu active (31-89 j)", "text-amber-300"], inactive: ["Inactive (≥ 90 j)", "text-rose-300"] };
const date = (s) => (s ? new Date(s).toLocaleDateString("fr-CA") : "jamais");
export const PRESETS = { inactive: (a) => a.status === "inactive", norel: (a) => a.relevant_days == null || a.relevant_days > 30, low: (a) => a.status === "low", active: (a) => a.status === "active" };

// Detailed confirmation before unfollowing in bulk (offers already found are always kept).
export const CompanyCleanup = ({ open, onClose, preset, onRemoved }) => {
  const [act, setAct] = useState(null);
  const [sel, setSel] = useState(new Set());
  const [mode, setMode] = useState("retire");
  const [reason, setReason] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) { setAct(null); radar.companiesActivity().then(setAct).catch((e) => toast.error(e.message)); } }, [open]);
  useEffect(() => {
    if (!act) return;
    const names = Object.keys(act.items);
    setSel(new Set(Array.isArray(preset) ? preset.filter((n) => names.includes(n)) : PRESETS[preset] ? names.filter((n) => PRESETS[preset](act.items[n])) : []));
  }, [act, preset]);
  const rows = useMemo(() => (act ? Object.entries(act.items).sort((a, b) => (a[1].days ?? 9999) < (b[1].days ?? 9999) ? 1 : -1) : []), [act]);
  const toggle = (n) => setSel((s) => { const x = new Set(s); x.has(n) ? x.delete(n) : x.add(n); return x; });
  const confirm = async () => {
    setBusy(true);
    try {
      const names = [...sel];
      const r = await radar.removeCompanies({ names, mode, reason });
      toast.success(`${r.removed} entreprise(s) ${mode === "bloque" ? "bloquée(s)" : "retirée(s)"} · ${r.total}/${act.limit} suivies. Les offres déjà trouvées sont conservées.`);
      onRemoved?.(names); onClose();
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[88vh] overflow-y-auto border-white/10 bg-[#121520] text-slate-100 sm:max-w-3xl" data-testid="company-cleanup-dialog">
        <DialogHeader><DialogTitle>Faire de la place dans vos entreprises suivies</DialogTitle>
          <DialogDescription className="text-slate-400">Vérifiez la liste avant de confirmer. Les offres déjà trouvées restent dans votre Radar et votre historique.</DialogDescription></DialogHeader>
        {!act ? <Loader2 className="h-5 w-5 animate-spin text-indigo-400" /> : <>
          <div className="flex flex-wrap gap-2 text-xs">
            <span className="rounded-full border border-white/10 px-3 py-1 font-semibold" data-testid="cleanup-total">Entreprises suivies : {act.total} / {act.limit}</span>
            {[["active", act.counts.active], ["low", act.counts.low], ["inactive", act.counts.inactive]].map(([k, n]) => (
              <button key={k} type="button" onClick={() => setSel(new Set(rows.filter(([, a]) => a.status === k).map(([n2]) => n2)))} className={`rounded-full border border-white/10 px-3 py-1 hover:bg-white/5 ${ST[k][1]}`} data-testid={`cleanup-select-${k}`}>{ST[k][0]} : {n}</button>))}
            <button type="button" onClick={() => setSel(new Set(rows.filter(([, a]) => PRESETS.norel(a)).map(([n]) => n)))} className="rounded-full border border-white/10 px-3 py-1 text-slate-300 hover:bg-white/5" data-testid="cleanup-select-norel">Sans offre pertinente (A/B) depuis 30 j : {act.counts.no_relevant_30}</button>
            <button type="button" onClick={() => setSel(new Set())} className="px-2 text-slate-500 hover:text-white" data-testid="cleanup-clear">Tout désélectionner</button>
          </div>
          <div className="max-h-[40vh] overflow-y-auto rounded-xl border border-white/10">
            <table className="w-full text-left text-xs"><thead className="sticky top-0 bg-[#121520] text-slate-500"><tr><th className="p-2" /><th>Entreprise</th><th>Activité</th><th>Dernière offre</th><th>Dernière A/B</th><th>Offres</th></tr></thead>
              <tbody>{rows.map(([n, a], i) => (
                <tr key={n} className="border-t border-white/5" data-testid={`cleanup-row-${i}`}>
                  <td className="p-2"><input type="checkbox" className="accent-rose-500" checked={sel.has(n)} onChange={() => toggle(n)} data-testid={`cleanup-check-${i}`} /></td>
                  <td className="text-slate-200">{n}</td><td className={ST[a.status][1]}>{ST[a.status][0]}</td><td>{date(a.last)}</td><td>{date(a.last_relevant)}</td><td className="font-mono">{a.offers}</td>
                </tr>))}</tbody></table>
          </div>
          <div className="flex flex-wrap items-center gap-3 text-xs">
            <label className="flex items-center gap-1.5"><input type="radio" checked={mode === "retire"} onChange={() => setMode("retire")} data-testid="cleanup-mode-retire" /><Trash2 className="h-3.5 w-3.5 text-rose-300" />Retirer (restaurable, masquée des suggestions)</label>
            <label className="flex items-center gap-1.5"><input type="radio" checked={mode === "bloque"} onChange={() => setMode("bloque")} data-testid="cleanup-mode-bloque" /><Ban className="h-3.5 w-3.5 text-rose-400" />Bloquer définitivement (jamais reproposée)</label>
            <input value={reason} onChange={(e) => setReason(e.target.value)} placeholder="Motif (optionnel)" maxLength={200} className="min-w-[180px] flex-1 rounded-lg border border-white/10 bg-black/40 px-2 py-1 text-white" data-testid="cleanup-reason" />
          </div>
          <div className="flex justify-end gap-2">
            <button type="button" onClick={onClose} className="rounded-full px-4 py-2 text-xs text-slate-400 hover:text-white" data-testid="cleanup-cancel">Annuler</button>
            <button type="button" onClick={confirm} disabled={!sel.size || busy} className="flex items-center gap-1.5 rounded-full bg-rose-600 px-4 py-2 text-xs font-semibold text-white disabled:opacity-40" data-testid="cleanup-confirm">
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}Confirmer : {mode === "bloque" ? "bloquer" : "retirer"} {sel.size} entreprise(s)</button>
          </div></>}
      </DialogContent>
    </Dialog>
  );
};
