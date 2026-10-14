import { useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle, SheetDescription } from "@/components/ui/sheet";
import { adminSaveFinanceMonth, adminSaveFinanceSettings } from "@/lib/api";
import { monthLabel } from "./fmt";

const pwd = () => sessionStorage.getItem("adminPwd");
const inp = "w-full rounded-lg border border-white/10 bg-slate-950 px-2.5 py-1.5 text-sm text-white outline-none focus:border-emerald-400/60";
const KINDS = [["rabais", "Rabais promotionnel (−)"], ["fondateur", "Abonnements fondateurs"], ["ponctuel", "Revenu ponctuel"], ["remboursement", "Crédit / remboursement (−)"], ["b2b", "Vente B2B (employeurs, RH)"], ["autre", "Autre"]];
const BASE_INV = [["google", "Gemini (Google)"], ["openrouter", "OpenRouter"], ["anthropic", "Anthropic"]];
const PRICING_LABELS = { gemini_flash: "Gemini Flash", gemini_pro: "Gemini Pro", openrouter: "OpenRouter (DeepSeek…)", openrouter_free: "OpenRouter gratuit", anthropic: "Anthropic", autre: "Autres" };

const Cur = ({ value, onChange, testid }) => (
  <select value={value} onChange={(e) => onChange(e.target.value)} className={`${inp} w-20`} data-testid={testid}><option>CAD</option><option>USD</option></select>
);
const H = ({ children }) => <h4 className="mb-2 mt-5 text-xs font-semibold uppercase tracking-wider text-emerald-300">{children}</h4>;

const initForm = (doc) => {
  const inv = [...BASE_INV.map(([k]) => (doc.ai_invoices || []).find((i) => i.provider === k) || { provider: k, amount: null, currency: "USD" }),
    ...(doc.ai_invoices || []).filter((i) => !BASE_INV.some(([k]) => k === i.provider))];
  return { price_cad: doc.price_cad, paid_override: doc.paid_override, adjustments: doc.adjustments || [], platform_costs: doc.platform_costs || [], ai_invoices: inv };
};

export const FinanceEditor = ({ open, onClose, s, onSaved }) => {
  const [f, setF] = useState(() => initForm(s.doc));
  const [st, setSt] = useState(() => ({ fx_usd_cad: s.settings.fx_usd_cad, pricing: s.settings.pricing }));
  const [busy, setBusy] = useState(false);
  const setList = (k, i, patch) => setF({ ...f, [k]: f[k].map((x, j) => (j === i ? { ...x, ...patch } : x)) });
  const del = (k, i) => setF({ ...f, [k]: f[k].filter((_, j) => j !== i) });
  const save = async () => {
    setBusy(true);
    try {
      await adminSaveFinanceSettings(pwd(), { fx_usd_cad: Number(st.fx_usd_cad), pricing: st.pricing });
      await adminSaveFinanceMonth(pwd(), s.month, {
        price_cad: Number(f.price_cad) || 0, paid_override: f.paid_override === "" || f.paid_override === null ? null : Number(f.paid_override),
        adjustments: f.adjustments.map((a) => ({ ...a, amount: Number(a.amount) || 0 })),
        platform_costs: f.platform_costs.filter((c) => c.name.trim()).map((c) => ({ ...c, amount: Number(c.amount) || 0 })),
        ai_invoices: f.ai_invoices.filter((i) => i.provider.trim() && i.amount !== null && i.amount !== "").map((i) => ({ ...i, amount: Number(i.amount) })),
      });
      toast.success("Données financières enregistrées");
      onSaved();
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <Sheet open={open} onOpenChange={(o) => !o && onClose()}>
      <SheetContent className="w-full overflow-y-auto border-white/10 bg-slate-950 text-slate-200 sm:max-w-xl" data-testid="finance-editor">
        <SheetHeader><SheetTitle className="text-white">Saisir {monthLabel(s.month)}</SheetTitle><SheetDescription>Montants en CAD sauf mention USD (converti automatiquement).</SheetDescription></SheetHeader>
        <H>Revenus</H>
        <div className="grid grid-cols-2 gap-2">
          <label className="text-xs text-slate-400">Prix mensuel standard (CAD)<input type="number" step="0.01" min="0" value={f.price_cad} onChange={(e) => setF({ ...f, price_cad: e.target.value })} className={inp} data-testid="fin-price" /></label>
          <label className="text-xs text-slate-400">Membres payants (vide = membres cochés)<input type="number" min="0" value={f.paid_override ?? ""} onChange={(e) => setF({ ...f, paid_override: e.target.value === "" ? null : e.target.value })} className={inp} placeholder={`${s.members.paid}`} data-testid="fin-paid" /></label>
        </div>
        <H>Ajustements manuels</H>
        {f.adjustments.map((a, i) => (
          <div key={i} className="mb-2 grid grid-cols-[1fr_1fr_90px_auto] gap-2" data-testid={`fin-adj-${i}`}>
            <select value={a.kind} onChange={(e) => setList("adjustments", i, { kind: e.target.value })} className={inp}>{KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
            <input value={a.label} onChange={(e) => setList("adjustments", i, { label: e.target.value })} placeholder="Libellé" className={inp} />
            <input type="number" step="0.01" value={a.amount} onChange={(e) => setList("adjustments", i, { amount: e.target.value })} className={inp} />
            <button onClick={() => del("adjustments", i)} className="text-slate-500 hover:text-rose-400" aria-label="Supprimer"><Trash2 className="h-4 w-4" /></button>
          </div>))}
        <button onClick={() => setF({ ...f, adjustments: [...f.adjustments, { kind: "ponctuel", label: "", amount: 0 }] })} className="flex items-center gap-1 text-xs text-emerald-300" data-testid="fin-add-adj"><Plus className="h-3.5 w-3.5" />Ajouter un ajustement</button>
        <H>Coûts plateforme (hors IA)</H>
        {f.platform_costs.map((c, i) => (
          <div key={i} className="mb-2 grid grid-cols-[1fr_100px_80px_auto] gap-2" data-testid={`fin-cost-${i}`}>
            <input value={c.name} onChange={(e) => setList("platform_costs", i, { name: e.target.value })} className={inp} />
            <input type="number" step="0.01" min="0" value={c.amount} onChange={(e) => setList("platform_costs", i, { amount: e.target.value })} className={inp} />
            <Cur value={c.currency} onChange={(v) => setList("platform_costs", i, { currency: v })} />
            <button onClick={() => del("platform_costs", i)} className="text-slate-500 hover:text-rose-400" aria-label="Supprimer"><Trash2 className="h-4 w-4" /></button>
          </div>))}
        <button onClick={() => setF({ ...f, platform_costs: [...f.platform_costs, { name: "", amount: 0, currency: "CAD" }] })} className="flex items-center gap-1 text-xs text-emerald-300" data-testid="fin-add-cost"><Plus className="h-3.5 w-3.5" />Ajouter un poste</button>
        <H>Factures IA réelles du mois (laisser vide = estimation)</H>
        {f.ai_invoices.map((v, i) => (
          <div key={i} className="mb-2 grid grid-cols-[1fr_100px_80px_auto] gap-2" data-testid={`fin-inv-${v.provider || i}`}>
            {BASE_INV.some(([k]) => k === v.provider) ? <span className="self-center text-sm">{BASE_INV.find(([k]) => k === v.provider)[1]}</span>
              : <input value={v.provider} onChange={(e) => setList("ai_invoices", i, { provider: e.target.value })} placeholder="Fournisseur" className={inp} />}
            <input type="number" step="0.01" min="0" value={v.amount ?? ""} onChange={(e) => setList("ai_invoices", i, { amount: e.target.value === "" ? null : e.target.value })} placeholder="—" className={inp} />
            <Cur value={v.currency} onChange={(x) => setList("ai_invoices", i, { currency: x })} />
            {BASE_INV.some(([k]) => k === v.provider) ? <span /> : <button onClick={() => del("ai_invoices", i)} className="text-slate-500 hover:text-rose-400" aria-label="Supprimer"><Trash2 className="h-4 w-4" /></button>}
          </div>))}
        <button onClick={() => setF({ ...f, ai_invoices: [...f.ai_invoices, { provider: "", amount: null, currency: "USD" }] })} className="flex items-center gap-1 text-xs text-emerald-300" data-testid="fin-add-inv"><Plus className="h-3.5 w-3.5" />Ajouter un fournisseur</button>
        <H>Réglages (tous les mois)</H>
        <label className="text-xs text-slate-400">Taux de change 1 USD = ? CAD<input type="number" step="0.01" min="0.5" value={st.fx_usd_cad} onChange={(e) => setSt({ ...st, fx_usd_cad: e.target.value })} className={`${inp} w-28`} data-testid="fin-fx" /></label>
        <p className="mb-1 mt-3 text-xs text-slate-400">Tarifs officiels (USD par million de jetons : entrée / sortie)</p>
        {Object.entries(st.pricing).map(([k, v]) => (
          <div key={k} className="mb-1.5 grid grid-cols-[1fr_80px_80px] items-center gap-2 text-sm" data-testid={`fin-price-${k}`}>
            <span>{PRICING_LABELS[k] || k}</span>
            {["in", "out"].map((d) => <input key={d} type="number" step="0.01" min="0" value={v[d]} onChange={(e) => setSt({ ...st, pricing: { ...st.pricing, [k]: { ...v, [d]: e.target.value } } })} className={inp} />)}
          </div>))}
        <div className="sticky bottom-0 mt-6 flex justify-end gap-2 bg-slate-950 py-3">
          <button onClick={onClose} className="rounded-lg px-4 py-2 text-sm text-slate-400">Annuler</button>
          <button onClick={save} disabled={busy} className="flex items-center gap-2 rounded-lg bg-emerald-500 px-4 py-2 text-sm font-semibold text-black disabled:opacity-60" data-testid="fin-save">{busy && <Loader2 className="h-4 w-4 animate-spin" />}Enregistrer</button>
        </div>
      </SheetContent>
    </Sheet>
  );
};
