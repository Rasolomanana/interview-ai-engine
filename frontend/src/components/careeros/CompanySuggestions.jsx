import { useEffect, useState } from "react";
import { Building2, Loader2, Plus } from "lucide-react";
import { toast } from "sonner";
import { radar } from "@/lib/careeros";

export const CompanySuggestions = ({ refreshKey, onFollowed }) => {
  const [items, setItems] = useState(null);
  const [busy, setBusy] = useState("");
  useEffect(() => { radar.suggestions().then((r) => setItems(r.items)).catch(() => setItems([])); }, [refreshKey]);
  if (!items?.length) return null;
  const follow = async (g) => {
    setBusy(g.name);
    try {
      await radar.follow(g.name);
      toast.success(`${g.name} ajoutée : recherche automatique de son portail en cours.`);
      setItems(items.filter((x) => x.name !== g.name));
      onFollowed?.();
    } catch (e) { toast.error(e.message); } finally { setBusy(""); }
  };
  return (
    <section className="rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-4" data-testid="radar-company-suggestions">
      <p className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-100"><Building2 className="h-4 w-4 text-indigo-300" />Entreprises qui recrutent pour vos postes</p>
      <p className="mb-3 text-[11px] text-slate-500">Employeurs récurrents dans vos offres pertinentes (30 derniers jours), pas encore suivis. « Suivre » les ajoute et cherche leur portail automatiquement.</p>
      <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
        {items.map((g, i) => (
          <div key={g.name} className="flex min-w-0 items-start gap-3 rounded-xl border border-white/[0.06] bg-black/20 p-3 text-xs" data-testid={`suggestion-${i}`}>
            <div className="min-w-0 flex-1">
              <p className="font-semibold text-white">{g.name}{g.a > 0 && <span className="ml-1.5 rounded-full bg-emerald-400 px-1.5 text-[10px] font-bold text-emerald-950">{g.a} A</span>}</p>
              <p className="text-slate-400">{g.offers} offre(s) pertinente(s) · meilleur IPS {g.best_ips || "—"}{g.portal ? ` · portail connu : ${g.portal}` : ""}</p>
              <p className="truncate text-slate-500">{g.titles.join(" · ")}</p>
            </div>
            <button type="button" onClick={() => follow(g)} disabled={busy === g.name} className="flex shrink-0 items-center gap-1 rounded-full bg-indigo-500 px-3 py-1.5 font-semibold text-white hover:bg-indigo-400 disabled:opacity-50" data-testid={`suggestion-follow-${i}`}>
              {busy === g.name ? <Loader2 className="h-3 w-3 animate-spin" /> : <Plus className="h-3 w-3" />}Suivre</button>
          </div>))}
      </div>
    </section>
  );
};
