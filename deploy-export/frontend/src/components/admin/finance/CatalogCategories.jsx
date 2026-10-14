import { useState } from "react";
import { Archive, Check, Pencil, Plus, RotateCcw, Trash2, X } from "lucide-react";
import { toast } from "sonner";
import { adminCatalogArchive, adminCatalogDelete, adminCatalogSave } from "@/lib/api";
import { inp, pwd, StatusBadge, IconBtn } from "./catalogUi";

const CatRow = ({ c, families, reload }) => {
  const [edit, setEdit] = useState(false);
  const [f, setF] = useState({ name: c.name, family: c.family });
  const run = async (fn, ok) => { try { await fn(); toast.success(ok); setEdit(false); reload(); } catch (e) { toast.error(e.message); } };
  const archived = c.status === "archived";
  return (
    <div className={`flex flex-wrap items-center gap-2 border-t border-white/[0.06] py-2 first:border-t-0 ${archived ? "opacity-60" : ""}`} data-testid={`cat-row-${c.id}`}>
      {edit ? <>
        <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} className={`${inp} w-40`} data-testid={`cat-name-${c.id}`} />
        <select value={f.family} onChange={(e) => setF({ ...f, family: e.target.value })} className={`${inp} w-48`}>{Object.entries(families).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <IconBtn icon={Check} label="Enregistrer" onClick={() => run(() => adminCatalogSave(pwd(), "categories", c.id, f), "Catégorie modifiée")} testid={`cat-save-${c.id}`} />
        <IconBtn icon={X} label="Annuler" onClick={() => setEdit(false)} />
      </> : <>
        <span className="min-w-0 flex-1 text-sm text-slate-200">{c.name}<span className="ml-2 text-[11px] text-slate-500">{families[c.family]} · {c.providers} fournisseur(s)</span></span>
        <StatusBadge archived={archived} />
        <IconBtn icon={Pencil} label="Modifier" onClick={() => setEdit(true)} testid={`cat-edit-${c.id}`} />
        <IconBtn icon={archived ? RotateCcw : Archive} label={archived ? "Réactiver" : "Archiver"} onClick={() => run(() => adminCatalogArchive(pwd(), "categories", c.id, !archived), archived ? "Catégorie réactivée" : "Catégorie archivée")} testid={`cat-archive-${c.id}`} />
        <IconBtn icon={Trash2} label={c.providers ? "Utilisée : archivez-la" : "Supprimer"} disabled={c.providers > 0} danger onClick={() => window.confirm(`Supprimer « ${c.name} » ?`) && run(() => adminCatalogDelete(pwd(), "categories", c.id), "Catégorie supprimée")} testid={`cat-delete-${c.id}`} />
      </>}
    </div>
  );
};

export const CatalogCategories = ({ data, reload }) => {
  const [f, setF] = useState({ name: "", family: "infrastructure" });
  const add = async () => {
    if (!f.name.trim()) return;
    try { await adminCatalogSave(pwd(), "categories", null, f); toast.success("Catégorie ajoutée"); setF({ ...f, name: "" }); reload(); } catch (e) { toast.error(e.message); }
  };
  return (
    <section data-testid="catalog-categories">
      <h4 className="mb-2 text-xs font-semibold uppercase tracking-wider text-emerald-300">Catégories</h4>
      {data.categories.map((c) => <CatRow key={c.id} c={c} families={data.families} reload={reload} />)}
      <div className="mt-2 flex flex-wrap gap-2">
        <input value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} placeholder="Nouvelle catégorie" className={`${inp} w-44`} data-testid="cat-new-name" />
        <select value={f.family} onChange={(e) => setF({ ...f, family: e.target.value })} className={`${inp} w-48`} data-testid="cat-new-family">{Object.entries(data.families).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <button onClick={add} className="flex items-center gap-1 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-black" data-testid="cat-add-btn"><Plus className="h-3.5 w-3.5" />Ajouter</button>
      </div>
    </section>
  );
};
