import { useEffect, useState } from "react";
import { Building2, CheckCircle2, Loader2, Plus, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { radar } from "@/lib/careeros";

export const EmployerDirectory = ({ companies, onAdd }) => {
  const [list, setList] = useState(null);
  const [q, setQ] = useState("");
  useEffect(() => { radar.directory().then(setList).catch((e) => toast.error(e.message)); }, []);
  const followed = (n) => companies.some((c) => c.name.toLowerCase() === n.toLowerCase());
  const shown = (list || []).filter((d) => `${d.name} ${d.sector}`.toLowerCase().includes(q.toLowerCase()));
  return (
    <div className="space-y-2 rounded-xl border border-white/10 p-3" data-testid="employer-directory">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-slate-300"><Building2 className="h-3.5 w-3.5 text-indigo-300" />Annuaire d'employeurs (portails vérifiés en direct)</p>
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filtrer…" className="w-32 rounded-lg border border-white/10 bg-black/40 px-2 py-1 text-[11px] text-white outline-none" data-testid="employer-directory-filter" />
      </div>
      {!list ? <p className="flex items-center gap-2 text-[11px] text-slate-400"><Loader2 className="h-3.5 w-3.5 animate-spin" />Vérification des portails…</p> : (
        <div className="grid max-h-56 gap-1.5 overflow-y-auto pr-1 sm:grid-cols-2">
          {shown.map((d) => {
            const on = followed(d.name);
            return (
              <div key={d.name} className="flex items-center gap-2 rounded-lg border border-white/[0.06] px-2 py-1.5 text-[11px]" data-testid={`employer-${d.name.replace(/[^a-z0-9]/gi, "-")}`}>
                {d.ok ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" /> : <TriangleAlert className="h-3.5 w-3.5 shrink-0 text-amber-400" />}
                <span className="min-w-0 flex-1"><b className="text-slate-100">{d.name}</b>
                  <span className="block truncate text-slate-500">{d.ok ? `${d.kind_label} · ${d.count} offre(s)` : d.kind ? "Portail illisible · repli Jooble" : `${d.ats || "Portail"} non pris en charge · Jooble`} · {d.sector}</span></span>
                <button type="button" disabled={on} onClick={() => onAdd(d)} className="flex shrink-0 items-center gap-1 rounded-full border border-indigo-400/40 px-2 py-0.5 text-indigo-300 disabled:border-white/10 disabled:text-slate-500" data-testid={`employer-add-${d.name.replace(/[^a-z0-9]/gi, "-")}`}>
                  {on ? "Suivie" : <><Plus className="h-3 w-3" />Ajouter</>}</button>
              </div>);
          })}
        </div>)}
      <p className="text-[11px] text-slate-500">Un clic ajoute l'entreprise avec son portail. Sans portail lisible, elle est suivie via Jooble.</p>
    </div>
  );
};
