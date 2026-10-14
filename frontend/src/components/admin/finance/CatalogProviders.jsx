import { useState } from "react";
import { Archive, History, Pencil, Plus, RotateCcw, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { adminCatalogArchive, adminCatalogDelete, adminFinanceAudit } from "@/lib/api";
import { IconBtn, pwd, StatusBadge } from "./catalogUi";
import { ProviderForm } from "./ProviderForm";

const REC = { recurrent: "Récurrent", ponctuel: "Ponctuel", variable: "Variable" };
const ACT = { create: "Création", update: "Modification", archive: "Archivage", reactivate: "Réactivation", delete: "Suppression" };
const fmtVal = (v) => (v === null || v === undefined || v === "" ? "—" : String(v));

const Audit = ({ items }) => (
  <ul className="mt-1 space-y-1 rounded-lg bg-black/30 p-2 text-[11px] text-slate-400" data-testid="provider-history">
    {items.length === 0 && <li>Aucune modification enregistrée.</li>}
    {items.map((a) => (
      <li key={a.id}><span className="text-slate-300">{new Date(a.at).toLocaleString("fr-CA")}</span> · {ACT[a.action] || a.action}
        {a.action === "update" && Object.entries(a.detail || {}).map(([k, v]) => <span key={k}> · {k} : {fmtVal(v?.avant)} → {fmtVal(v?.après)}</span>)}
      </li>))}
  </ul>
);

const ProvRow = ({ p, data, reload }) => {
  const [mode, setMode] = useState(null);
  const [hist, setHist] = useState(null);
  const cat = data.categories.find((c) => c.id === p.category_id);
  const archived = p.status === "archived";
  const run = async (fn, ok) => { try { await fn(); toast.success(ok); reload(); } catch (e) { toast.error(e.message); } };
  const showHist = async () => { if (mode === "hist") { setMode(null); return; } setMode("hist"); setHist(await adminFinanceAudit(pwd(), p.id).catch(() => [])); };
  if (mode === "edit") return <ProviderForm data={data} provider={p} onDone={(ok) => { setMode(null); if (ok) reload(); }} />;
  return (
    <div className={`border-t border-white/[0.06] py-2 first:border-t-0 ${archived ? "opacity-60" : ""}`} data-testid={`prov-row-${p.id}`}>
      <div className="flex flex-wrap items-center gap-2">
        <span className="min-w-0 flex-1 text-sm text-slate-200">{p.name}
          <span className="block text-[11px] text-slate-500">{cat?.name || "?"} · {REC[p.recurrence]} · {p.default_amount} {p.currency}/mois{p.start_month ? ` · dès ${p.start_month}` : ""}{p.end_month ? ` → ${p.end_month}` : ""}{p.ai_key ? " · lié au journal IA" : ""}</span>
        </span>
        <StatusBadge archived={archived} suspended={p.suspended} />
        <IconBtn icon={Pencil} label="Modifier" onClick={() => setMode("edit")} testid={`prov-edit-${p.id}`} />
        <IconBtn icon={History} label="Historique des modifications" onClick={showHist} testid={`prov-history-${p.id}`} />
        <IconBtn icon={archived ? RotateCcw : Archive} label={archived ? "Réactiver" : "Archiver"} onClick={() => run(() => adminCatalogArchive(pwd(), "providers", p.id, !archived), archived ? "Fournisseur réactivé" : "Fournisseur archivé")} testid={`prov-archive-${p.id}`} />
        <IconBtn icon={Trash2} label={p.used ? "Déjà utilisé : archivez-le" : "Supprimer"} disabled={p.used} danger onClick={() => window.confirm(`Supprimer « ${p.name} » ?`) && run(() => adminCatalogDelete(pwd(), "providers", p.id), "Fournisseur supprimé")} testid={`prov-delete-${p.id}`} />
      </div>
      {mode === "hist" && hist && <Audit items={hist} />}
    </div>
  );
};

export const CatalogProviders = ({ data, reload }) => {
  const [adding, setAdding] = useState(false);
  const [showArchived, setShowArchived] = useState(true);
  const list = data.providers.filter((p) => showArchived || p.status !== "archived");
  return (
    <section data-testid="catalog-providers">
      <div className="mb-2 flex items-center justify-between">
        <h4 className="text-xs font-semibold uppercase tracking-wider text-emerald-300">Fournisseurs</h4>
        <label className="flex items-center gap-1.5 text-[11px] text-slate-400"><input type="checkbox" checked={showArchived} onChange={(e) => setShowArchived(e.target.checked)} data-testid="prov-show-archived" />Afficher les archivés</label>
      </div>
      {adding ? <ProviderForm data={data} onDone={(ok) => { setAdding(false); if (ok) reload(); }} />
        : <button onClick={() => setAdding(true)} className="mb-2 flex items-center gap-1 text-xs text-emerald-300" data-testid="prov-add-btn"><Plus className="h-3.5 w-3.5" />Ajouter un fournisseur</button>}
      {Object.entries(data.families).map(([fk, fl]) => {
        const items = list.filter((p) => data.categories.find((c) => c.id === p.category_id)?.family === fk);
        if (!items.length) return null;
        return (
          <div key={fk} className="mb-3" data-testid={`prov-family-${fk}`}>
            <p className="mb-1 text-[11px] font-semibold text-slate-400">{fl}</p>
            {items.map((p) => <ProvRow key={p.id} p={p} data={data} reload={reload} />)}
          </div>);
      })}
    </section>
  );
};
