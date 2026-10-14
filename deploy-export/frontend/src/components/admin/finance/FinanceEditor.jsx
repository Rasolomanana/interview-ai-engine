import { useEffect, useState } from "react";
import { CheckCheck, Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { adminFinanceCatalog, adminSaveFinanceMonth, adminSaveFinanceSettings } from "@/lib/api";
import { cadFine, monthLabel } from "./fmt";
import { Nature } from "./Nature";
import { DateField } from "@/components/careeros/DateField";

const pwd = () => sessionStorage.getItem("adminPwd");
const inp = "w-full rounded-lg border border-white/10 bg-slate-950 px-2.5 py-1.5 text-sm text-white outline-none focus:border-emerald-400/60";
const KINDS = [["rabais", "Rabais promotionnel (−)"], ["fondateur", "Abonnements fondateurs"], ["essai", "Essais gratuits (−)"], ["ponctuel", "Revenu ponctuel"], ["remboursement", "Crédit / remboursement (−)"], ["b2b", "Vente B2B (employeurs, RH)"], ["autre", "Autre"]];
const PRICING_LABELS = { gemini_flash: "Gemini Flash", gemini_pro: "Gemini Pro", openrouter: "OpenRouter (DeepSeek…)", openrouter_free: "OpenRouter gratuit", anthropic: "Anthropic", autre: "Autres" };
const SRC = { jetons: "jetons", recurrent: "défaut" };
const H = ({ children }) => <h4 className="mb-2 mt-5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-emerald-300">{children}</h4>;
const toNum = (v) => (v === "" || v === null || v === undefined ? null : Number(v));

const toRow = (l) => ({ provider_id: l.provider_id, name: l.name, family: l.family, est_cad: l.est_cad, est_source: l.est_source,
  default_amount: l.default_amount, default_currency: l.default_currency, estimated: l.saved_estimated ?? "", real: l.saved_real ?? "", currency: l.currency, note: l.note || "", billing_date: l.billing_date || "", due_date: l.due_date });

const LineEdit = ({ r, onChange, onRemove, onConfirm }) => (
  <div className="mb-2 rounded-lg border border-white/[0.06] p-2" data-testid={`fin-line-${r.provider_id}`}>
    <div className="mb-1.5 flex items-center justify-between gap-2 text-sm"><span className="truncate">{r.name}</span>
      {r.est_source && r.estimated === "" && <span className="shrink-0 text-[10px] text-slate-500">proposé : {cadFine(r.est_cad)} ({SRC[r.est_source]})</span>}</div>
    <div className="grid grid-cols-[1fr_1fr_76px_auto_auto] items-center gap-1.5">
      <input type="number" min="0" step="0.01" value={r.estimated} onChange={(e) => onChange({ estimated: e.target.value })} placeholder="Estimé" className={inp} data-testid={`fin-line-est-${r.provider_id}`} />
      <input type="number" min="0" step="0.01" value={r.real} onChange={(e) => onChange({ real: e.target.value })} placeholder="Réel (facture)" className={inp} data-testid={`fin-line-real-${r.provider_id}`} />
      <select value={r.currency} onChange={(e) => onChange({ currency: e.target.value })} className={inp}><option>CAD</option><option>USD</option></select>
      <button onClick={onConfirm} title="Confirmer l'estimation comme montant réel" className="rounded-md p-1.5 text-slate-400 hover:text-emerald-300" data-testid={`fin-line-confirm-${r.provider_id}`}><CheckCheck className="h-4 w-4" /></button>
      <button onClick={onRemove} title="Retirer la saisie" className="rounded-md p-1.5 text-slate-500 hover:text-rose-400"><Trash2 className="h-4 w-4" /></button>
    </div>
    <div className="mt-1.5 grid grid-cols-[150px_1fr] gap-1.5">
      <DateField value={r.billing_date} onChange={(v) => onChange({ billing_date: v })} className={inp} testid={`fin-line-date-${r.provider_id}`} />
      <input value={r.note} onChange={(e) => onChange({ note: e.target.value })} maxLength={200} placeholder={r.due_date ? `Note (facture prévue le ${r.due_date})` : "Note facultative"} className={inp} data-testid={`fin-line-note-${r.provider_id}`} />
    </div>
    {r.real !== "" && !r.billing_date && <p className="mt-1 text-[11px] text-amber-300" data-testid={`fin-line-warn-${r.provider_id}`}>⚠ Date de facturation manquante (facultative)</p>}
  </div>
);

export const FinanceEditor = ({ open, onClose, s, onSaved }) => {
  const d = s.doc;
  const [f, setF] = useState({ price_cad: d.price_cad, paid_override: d.paid_override, revenue_real: d.revenue_real ?? "", adjustments: d.adjustments || [] });
  const [rows, setRows] = useState(() => s.lines.map(toRow));
  const [cat, setCat] = useState(null);
  const [pick, setPick] = useState("");
  const [st, setSt] = useState(() => ({ fx_usd_cad: s.settings.fx_usd_cad, pricing: s.settings.pricing }));
  const [busy, setBusy] = useState(false);
  useEffect(() => { adminFinanceCatalog(pwd()).then(setCat).catch(() => {}); }, []);
  const setRow = (i, patch) => setRows(rows.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  const setAdj = (i, patch) => setF({ ...f, adjustments: f.adjustments.map((a, j) => (j === i ? { ...a, ...patch } : a)) });
  const confirm = (i) => {
    const r = rows[i];
    if (r.estimated !== "") setRow(i, { real: r.estimated });
    else if (r.est_source === "recurrent") setRow(i, { real: r.default_amount, currency: r.default_currency });
    else setRow(i, { real: Math.round((r.est_cad || 0) * 100) / 100, currency: "CAD" });
  };
  const addable = (cat?.providers || []).filter((p) => p.status === "active" && !rows.some((r) => r.provider_id === p.id));
  const add = () => {
    const p = addable.find((x) => x.id === pick);
    if (!p) return;
    const c = cat.categories.find((x) => x.id === p.category_id);
    setRows([...rows, { provider_id: p.id, name: p.name, family: c?.family || "autres", est_cad: null, est_source: null, default_amount: p.default_amount, default_currency: p.currency, estimated: "", real: "", currency: p.currency, note: "", billing_date: "", due_date: null }]);
    setPick("");
  };
  const save = async () => {
    setBusy(true);
    try {
      await adminSaveFinanceSettings(pwd(), { fx_usd_cad: Number(st.fx_usd_cad), pricing: st.pricing });
      await adminSaveFinanceMonth(pwd(), s.month, {
        price_cad: Number(f.price_cad) || 0, paid_override: toNum(f.paid_override), revenue_real: toNum(f.revenue_real),
        adjustments: f.adjustments.map((a) => ({ ...a, amount: Number(a.amount) || 0 })),
        lines: rows.map((r) => ({ provider_id: r.provider_id, estimated: toNum(r.estimated), real: toNum(r.real), currency: r.currency, note: r.note, billing_date: r.billing_date || null })),
      });
      toast.success("Données financières enregistrées");
      onSaved();
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto border-white/10 bg-slate-950 text-slate-200 sm:max-w-xl" data-testid="finance-editor">
        <SheetHeader><SheetTitle className="text-white">Saisir {monthLabel(s.month)}</SheetTitle><SheetDescription>Montants en CAD sauf mention USD (converti automatiquement). « Réel » = facture ou encaissement.</SheetDescription></SheetHeader>
        <H>Revenus</H>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs text-slate-400">Prix mensuel standard (CAD)<input type="number" step="0.01" min="0" value={f.price_cad} onChange={(e) => setF({ ...f, price_cad: e.target.value })} className={inp} data-testid="fin-price" /></label>
          <label className="text-xs text-slate-400">Membres payants (vide = membres cochés)<input type="number" min="0" value={f.paid_override ?? ""} onChange={(e) => setF({ ...f, paid_override: e.target.value === "" ? null : e.target.value })} className={inp} placeholder={`${s.members.paid}`} data-testid="fin-paid" /></label>
          <label className="col-span-2 text-xs text-slate-400"><span className="flex items-center gap-1.5">Revenu réellement encaissé ce mois (optionnel) <Nature kind="real" /></span><input type="number" step="0.01" min="0" value={f.revenue_real} onChange={(e) => setF({ ...f, revenue_real: e.target.value })} placeholder="Laisser vide tant que non connu" className={inp} data-testid="fin-revenue-real" /></label>
        </div>
        <H>Ajustements (causes d'écart) <Nature kind="estimated" /></H>
        {f.adjustments.map((a, i) => (
          <div key={i} className="mb-2 grid grid-cols-[1fr_1fr_90px_auto] gap-2" data-testid={`fin-adj-${i}`}>
            <select value={a.kind} onChange={(e) => setAdj(i, { kind: e.target.value })} className={inp}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <input value={a.label} onChange={(e) => setAdj(i, { label: e.target.value })} placeholder="Libellé" className={inp} />
            <input type="number" step="0.01" value={a.amount} onChange={(e) => setAdj(i, { amount: e.target.value })} className={inp} />
            <button onClick={() => setF({ ...f, adjustments: f.adjustments.filter((_, j) => j !== i) })} className="text-slate-500 hover:text-rose-400" aria-label="Supprimer"><Trash2 className="h-4 w-4" /></button>
          </div>))}
        <button onClick={() => setF({ ...f, adjustments: [...f.adjustments, { kind: "ponctuel", label: "", amount: 0 }] })} className="flex items-center gap-1 text-xs text-emerald-300" data-testid="fin-add-adj"><Plus className="h-3.5 w-3.5" />Ajouter un ajustement</button>
        {s.families_list.map(([k, label]) => {
          const idx = rows.map((r, i) => [r, i]).filter(([r]) => r.family === k);
          if (!idx.length) return null;
          return (
            <div key={k}><H>{label}</H>
              {idx.map(([r, i]) => <LineEdit key={r.provider_id} r={r} onChange={(p) => setRow(i, p)} onConfirm={() => confirm(i)} onRemove={() => setRows(rows.filter((_, j) => j !== i))} />)}
            </div>);
        })}
        <div className="mt-3 flex gap-2">
          <select value={pick} onChange={(e) => setPick(e.target.value)} className={inp} data-testid="fin-add-line-select">
            <option value="">Ajouter une dépense ponctuelle ou variable…</option>
            {addable.map((p) => <option key={p.id} value={p.id}>{p.name}</option>)}
          </select>
          <button onClick={add} disabled={!pick} className="flex shrink-0 items-center gap-1 rounded-lg border border-emerald-500/40 px-3 text-xs text-emerald-300 disabled:opacity-40" data-testid="fin-add-line"><Plus className="h-3.5 w-3.5" />Ajouter</button>
        </div>
        <H>Réglages (tous les mois)</H>
        <label className="text-xs text-slate-400">Taux de change 1 USD = ? CAD<input type="number" step="0.01" min="0.5" value={st.fx_usd_cad} onChange={(e) => setSt({ ...st, fx_usd_cad: e.target.value })} className={`${inp} w-28`} data-testid="fin-fx" /></label>
        <p className="mb-1 mt-3 text-xs text-slate-400">Tarifs officiels (USD par million de jetons : entrée / sortie)</p>
        {Object.entries(st.pricing).map(([k, v]) => (
          <div key={k} className="mb-1.5 grid grid-cols-[1fr_80px_80px] items-center gap-2 text-sm" data-testid={`fin-price-${k}`}>
            <span>{PRICING_LABELS[k] || k}</span>
            {["in", "out"].map((dd) => <input key={dd} type="number" step="0.01" min="0" value={v[dd]} onChange={(e) => setSt({ ...st, pricing: { ...st.pricing, [k]: { ...v, [dd]: e.target.value } } })} className={inp} />)}
          </div>))}
        <div className="sticky bottom-0 mt-6 flex justify-end gap-2 bg-slate-950 py-3">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-slate-400">Annuler</button>
          <button onClick={save} disabled={busy} className="flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-black disabled:opacity-60" data-testid="fin-save">{busy && <Loader2 className="h-4 w-4 animate-spin" />}Enregistrer</button>
        </div>
      </SheetContent>
    </Sheet>
  );
};
