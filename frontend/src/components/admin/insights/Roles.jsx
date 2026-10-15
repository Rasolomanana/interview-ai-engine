import { useState } from "react";
import { Search, ShieldCheck } from "lucide-react";
import { toast } from "sonner";
import { adminRoles, adminSetRoles } from "@/lib/api";
import { Spinner, panel, pwd, useAdminData } from "./ui";

export const ROLE_LABEL = { super_admin: "Super Admin", support: "Support", marketing: "Marketing", conseiller: "Conseiller carrière" };
const SECTION = { overview: "Tableau de bord", geo: "Géographie", business: "Analyse métier", activite: "Activité", connecteurs: "Connecteurs", finance: "Rentabilité", roles: "Rôles" };

export const Roles = () => {
  const [q, setQ] = useState("");
  const [query, setQuery] = useState("");
  const [local, setLocal] = useState({});
  const d = useAdminData(() => adminRoles(pwd(), query), [query]);
  if (!d) return <Spinner />;
  const toggle = async (u, r) => {
    const cur = local[u.id] || u.admin_roles;
    const next = cur.includes(r) ? cur.filter((x) => x !== r) : [...cur, r];
    setLocal({ ...local, [u.id]: next });
    try { await adminSetRoles(pwd(), u.id, next); toast.success(`${u.email} : ${next.map((x) => ROLE_LABEL[x]).join(", ") || "aucun rôle"}`); }
    catch (e) { setLocal({ ...local, [u.id]: cur }); toast.error(e.message); }
  };
  return (
    <section className={`${panel} space-y-4`} data-testid="admin-roles">
      <div>
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-200"><ShieldCheck className="h-4 w-4 text-emerald-400" />Gestion des rôles</h3>
        <p className="text-[11px] text-slate-500">Cochez un rôle pour ouvrir l'Admin à ce membre (connexion avec son compte CareerOS). Le mot de passe administrateur reste le Super Admin sans restriction. Aucun rôle ne donne accès aux CV, à la Career Memory ni aux candidatures : seul le membre peut les partager.</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-2 lg:grid-cols-4" data-testid="roles-legend">
        {Object.entries(ROLE_LABEL).map(([k, l]) => <div key={k} className="rounded-lg border border-white/10 p-2 text-[11px]"><p className="font-semibold text-white">{l}</p><p className="text-slate-500">{(d.role_sections[k] || []).map((s) => SECTION[s]).join(" · ")}</p></div>)}
      </div>
      <form onSubmit={(e) => { e.preventDefault(); setQuery(q); }} className="flex gap-2">
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher un membre (e-mail ou nom)" className="flex-1 rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none" data-testid="roles-search-input" />
        <button type="submit" className="flex items-center gap-1 rounded-xl border border-emerald-400/40 px-3 text-sm text-emerald-200" data-testid="roles-search-btn"><Search className="h-4 w-4" />Rechercher</button>
      </form>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[720px] text-left text-[12px]">
          <thead className="text-slate-500"><tr className="border-b border-white/10"><th className="py-2 pr-3 font-medium">Membre</th>{Object.values(ROLE_LABEL).map((l) => <th key={l} className="py-2 pr-3 text-center font-medium">{l}</th>)}</tr></thead>
          <tbody>{d.members.map((u, i) => {
            const roles = local[u.id] || u.admin_roles;
            return (
              <tr key={u.id} className="border-b border-white/5" data-testid={`roles-row-${i}`}>
                <td className="py-2 pr-3"><p className="text-white">{u.name || "—"}</p><p className="text-slate-500">{u.email}</p></td>
                {Object.keys(ROLE_LABEL).map((r) => (
                  <td key={r} className="pr-3 text-center"><input type="checkbox" className="h-4 w-4 accent-emerald-500" checked={roles.includes(r)} onChange={() => toggle(u, r)} aria-label={`${ROLE_LABEL[r]} pour ${u.email}`} data-testid={`roles-${r}-${i}`} /></td>))}
              </tr>);
          })}</tbody>
        </table>
      </div>
    </section>
  );
};
