import { useState } from "react";
import { toast } from "sonner";
import { adminCatalogSave } from "@/lib/api";
import { inp, pwd } from "./catalogUi";

const EMPTY = { name: "", category_id: "", recurrence: "recurrent", default_amount: 0, currency: "CAD", start_month: "", end_month: "", suspended: false, ai_key: "", billing_day: "", billing_cycle: "mensuel" };
const L = ({ label, children }) => <label className="flex flex-col gap-1 text-[11px] text-slate-400">{label}{children}</label>;

export const ProviderForm = ({ data, provider, onDone }) => {
  const [f, setF] = useState(() => ({ ...EMPTY, category_id: data.categories[0]?.id || "", ...(provider || {}) }));
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });
  const save = async () => {
    try {
      await adminCatalogSave(pwd(), "providers", provider?.id, {
        name: f.name, category_id: f.category_id, recurrence: f.recurrence, default_amount: Number(f.default_amount) || 0, currency: f.currency,
        start_month: f.start_month || null, end_month: f.end_month || null, suspended: !!f.suspended, ai_key: f.ai_key || null,
        billing_day: f.billing_day ? Number(f.billing_day) : null, billing_cycle: f.billing_cycle || "mensuel",
      });
      toast.success(provider ? "Fournisseur modifié" : "Fournisseur ajouté");
      onDone(true);
    } catch (e) { toast.error(e.message); }
  };
  return (
    <div className="grid gap-2 rounded-xl border border-emerald-500/20 bg-black/30 p-3 sm:grid-cols-2" data-testid="provider-form">
      <L label="Nom"><input value={f.name} onChange={set("name")} className={inp} data-testid="prov-name" /></L>
      <L label="Catégorie"><select value={f.category_id} onChange={set("category_id")} className={inp} data-testid="prov-category">
        {data.categories.map((c) => <option key={c.id} value={c.id}>{c.name} ({data.families[c.family]}){c.status === "archived" ? " · archivée" : ""}</option>)}</select></L>
      <L label="Type"><select value={f.recurrence} onChange={set("recurrence")} className={inp} data-testid="prov-recurrence">
        <option value="recurrent">Récurrent (proposé chaque mois)</option><option value="ponctuel">Ponctuel / investissement</option><option value="variable">Variable</option></select></L>
      <div className="grid grid-cols-[1fr_80px] gap-2">
        <L label="Montant habituel par facture"><input type="number" min="0" step="0.01" value={f.default_amount} onChange={set("default_amount")} className={inp} data-testid="prov-amount" /></L>
        <L label="Devise"><select value={f.currency} onChange={set("currency")} className={inp} data-testid="prov-currency"><option>CAD</option><option>USD</option></select></L>
      </div>
      <L label="Cycle de facturation"><select value={f.billing_cycle || "mensuel"} onChange={set("billing_cycle")} className={inp} data-testid="prov-cycle">
        <option value="mensuel">Mensuel</option><option value="annuel">Annuel (mois anniversaire du début)</option></select></L>
      <L label="Jour de facturation habituel (1-31, optionnel)"><input type="number" min="1" max="31" value={f.billing_day ?? ""} onChange={set("billing_day")} className={inp} data-testid="prov-billing-day" /></L>
      <L label="Début (mois)"><input type="month" value={f.start_month || ""} onChange={set("start_month")} className={inp} data-testid="prov-start" /></L>
      <L label="Fin (mois, optionnel)"><input type="month" value={f.end_month || ""} onChange={set("end_month")} className={inp} data-testid="prov-end" /></L>
      <L label="Lien avec le journal IA (estimation automatique)"><select value={f.ai_key || ""} onChange={set("ai_key")} className={inp} data-testid="prov-ai-key">
        <option value="">Aucun</option>{Object.entries(data.ai_keys).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select></L>
      <label className="flex items-center gap-2 self-end pb-2 text-xs text-slate-300"><input type="checkbox" checked={!!f.suspended} onChange={set("suspended")} data-testid="prov-suspended" />Suspendre temporairement</label>
      <div className="flex justify-end gap-2 sm:col-span-2">
        <button onClick={() => onDone(false)} className="rounded-lg px-3 py-1.5 text-xs text-slate-400">Annuler</button>
        <button onClick={save} disabled={!f.name.trim() || !f.category_id} className="rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-black disabled:opacity-50" data-testid="prov-save">Enregistrer</button>
      </div>
    </div>
  );
};
