import { useEffect, useState } from "react";
import { ExternalLink, Info, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PriorityBadge } from "@/components/careeros/Ips";
import { radar } from "@/lib/careeros";

const LABEL = { new: "Nouvelles offres", found: "Offres trouvées", analyzed: "Offres analysées pendant ce passage", skipped: "Offres reportées (pas encore analysées)",
  src_jooble: "Offres Jooble", src_workday: "Offres Workday", src_boards: "Offres des sites carrières", src_adzuna: "Offres Adzuna" };
const STATUS = { nouvelle: "Nouvelle", ignoree: "Ignorée", pack: "Pack généré" };

const OfferLine = ({ o }) => (
  <li className="flex items-start gap-3 border-t border-white/[0.05] py-2.5" data-testid={`run-offer-${o.id}`}>
    <PriorityBadge priority={o.ips?.priority} testid={`run-offer-priority-${o.id}`} />
    <div className="min-w-0 flex-1">
      <p className="truncate text-sm font-medium text-white">{o.title}</p>
      <p className="truncate text-xs text-slate-500">{o.company} · {o.location} · {o.source}{o.status && o.status !== "nouvelle" ? ` · ${STATUS[o.status] || o.status}` : ""}</p>
    </div>
    <span className="whitespace-nowrap font-mono text-xs text-slate-300">{o.ips ? `IPS ${o.ips.score}` : "à analyser"}</span>
    {o.url && <a href={o.url} target="_blank" rel="noreferrer" className="text-slate-400 hover:text-white" title="Voir l'offre" data-testid={`run-offer-open-${o.id}`}><ExternalLink className="h-4 w-4" /></a>}
  </li>
);

export const RunOffersDialog = ({ sel, onClose }) => {
  const [data, setData] = useState(null);
  useEffect(() => {
    if (!sel) return;
    setData(null);
    radar.runOffers(sel.run.id, sel.kind).then(setData).catch((e) => setData({ offers: [], error: e.message }));
  }, [sel]);
  if (!sel) return null;
  const label = LABEL[sel.kind] || "Offres trouvées";
  return (
    <Dialog open onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto border-white/10 bg-[#121520] text-slate-100" data-testid="run-offers-dialog">
        <DialogHeader>
          <DialogTitle data-testid="run-offers-title">{label} · {sel.when}</DialogTitle>
          <DialogDescription className="text-slate-400">{data ? `${data.offers.length} offre(s)` : "Chargement…"}</DialogDescription>
        </DialogHeader>
        {!data ? <Loader2 className="h-5 w-5 animate-spin text-indigo-400" /> : <>
          {data.error && <p className="text-sm text-rose-300">{data.error}</p>}
          {!data.complete && <p className="flex items-start gap-2 rounded-lg border border-amber-400/20 bg-amber-500/5 p-2.5 text-xs text-amber-200" data-testid="run-offers-partial"><Info className="mt-0.5 h-3.5 w-3.5 shrink-0" />Cette recherche est antérieure au suivi détaillé : seules les offres apparues pour la première fois lors de cette recherche sont listées. Les prochaines recherches afficheront la liste complète.</p>}
          {sel.kind === "skipped" && <p className="rounded-lg border border-white/10 bg-white/5 p-2.5 text-xs text-slate-300" data-testid="run-offers-skipped-note">Ces offres ont été trouvées mais pas notées : la limite de 50 analyses par jour était atteinte. Elles passent en priorité au prochain passage, les titres les plus proches de vos postes visés d'abord. Celles qui ont été analysées depuis affichent leur IPS.</p>}
          {data.offers.length === 0 ? <p className="text-sm text-slate-500" data-testid="run-offers-empty">Aucune offre à afficher.</p>
            : <ul data-testid="run-offers-list">{data.offers.map((o) => <OfferLine key={o.id} o={o} />)}</ul>}
        </>}
      </DialogContent>
    </Dialog>
  );
};
