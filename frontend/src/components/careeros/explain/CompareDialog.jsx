import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { PriorityBadge } from "@/components/careeros/Ips";
import { radar } from "@/lib/careeros";

const STATUS = {
  priorite_a: ["Trouvée · priorité A", "text-emerald-300"], priorite_b: ["Trouvée · priorité B", "text-sky-300"], priorite_c: ["Trouvée · priorité C", "text-amber-300"],
  eliminee: ["Trouvée · éliminée (exigence)", "text-rose-300"], reportee: ["Trouvée · non analysée (limite de 50/jour)", "text-amber-300"],
  ignoree: ["Trouvée · ignorée par vous", "text-slate-400"], pack: ["Trouvée · pack généré", "text-indigo-300"], non_trouvee: ["Non trouvée par le Radar", "text-rose-300"],
};
const COVER = { portail: "text-emerald-300", jooble: "text-amber-300", aucune: "text-slate-400" };

const Item = ({ it, i, onExplain }) => {
  const [label, color] = STATUS[it.status] || STATUS.non_trouvee;
  return (
    <div className="rounded-xl border border-white/[0.07] bg-black/20 p-3 text-xs" data-testid={`compare-item-${i}`}>
      <div className="flex flex-wrap items-center gap-2">
        {it.priority && <PriorityBadge priority={it.priority} testid={`compare-priority-${i}`} />}
        <p className="min-w-0 flex-1 font-semibold text-white">{it.company}{it.title ? ` – ${it.title}` : ""}</p>
        {it.ips != null && <span className="font-mono text-slate-200" data-testid={`compare-ips-${i}`}>IPS {it.ips}</span>}
      </div>
      <dl className="mt-2 grid gap-1 sm:grid-cols-[150px_1fr]">
        <dt className="text-slate-500">1. Couverture</dt><dd className={COVER[it.coverage.state]} data-testid={`compare-coverage-${i}`}>{it.coverage.label}</dd>
        <dt className="text-slate-500">2–3. Résultat Radar</dt><dd className={color} data-testid={`compare-status-${i}`}>{label}{it.offer ? ` (« ${it.offer.title} », ${it.offer.source})` : ""}</dd>
        {!it.found && <><dt className="text-slate-500">Pourquoi</dt><dd className="text-slate-300" data-testid={`compare-why-${i}`}>{it.why}</dd></>}
        {it.found && <><dt className="text-slate-500">4. Critères pénalisants</dt><dd className="text-slate-300" data-testid={`compare-losses-${i}`}>
          {it.knockout && <span className="block text-rose-300">Éliminatoire : {it.knockout}</span>}
          {(it.losses || []).map((l) => <span key={l.label} className="block">−{l.lost} pts · {l.label} : <span className="text-slate-500">{l.why}</span></span>)}
          {it.status === "reportee" && "Pas encore notée : elle passera dans les 50 prochaines analyses si son titre est proche de vos postes visés."}</dd></>}
      </dl>
      {it.offer && it.status !== "reportee" && <button type="button" onClick={() => onExplain(it.offer.id)} className="mt-2 text-indigo-300 underline underline-offset-2 hover:text-white" data-testid={`compare-explain-${i}`}>Pourquoi ce score ?</button>}
    </div>
  );
};

export const CompareDialog = ({ open, onClose, onExplain }) => {
  const [lines, setLines] = useState("");
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const run = async () => {
    setBusy(true);
    try { setRes(await radar.compare(lines)); } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(x) => !x && onClose()}>
      <DialogContent className="max-h-[92vh] overflow-y-auto border-white/10 bg-[#121520] text-slate-100 sm:max-w-3xl" data-testid="compare-dialog">
        <DialogHeader><DialogTitle className="font-display">Comparer avec LinkedIn (ou un autre site)</DialogTitle></DialogHeader>
        <p className="text-xs text-slate-400">Une offre par ligne, au format « Entreprise – Titre » (10 maximum). CareerOS indique si l'entreprise est couverte, si le Radar a trouvé l'offre, son statut et les critères qui la pénalisent. Aucune donnée n'est lue sur LinkedIn.</p>
        <textarea value={lines} onChange={(e) => setLines(e.target.value)} rows={6} placeholder={"RONA – Chef des opérations\nAirbus – Superviseur opérations\nCanpar – Operations Supervisor"}
          className="w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/50" data-testid="compare-input" />
        <div className="flex justify-end"><button type="button" onClick={run} disabled={busy || !lines.trim()} className="flex items-center gap-1.5 rounded-full bg-indigo-500 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-50" data-testid="compare-submit">
          {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}Comparer</button></div>
        {res && <div className="space-y-2" data-testid="compare-results">
          <p className="text-[11px] text-slate-500" data-testid="compare-terms">Recherches Radar actuelles ({res.location}) : {res.terms.join(" · ")}</p>
          {res.items.map((it, i) => <Item key={`${it.company}-${i}`} it={it} i={i} onExplain={onExplain} />)}
        </div>}
      </DialogContent>
    </Dialog>
  );
};
