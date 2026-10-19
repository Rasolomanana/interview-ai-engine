import { useState } from "react";
import { ArrowRight, Loader2 } from "lucide-react";
import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

const sign = (n) => (n > 0 ? `+${n}` : `${n}`);

// Explicit validation (confirmation) before the master CV is replaced.
export const ApplyBar = ({ count, sim, onApply }) => {
  const [ask, setAsk] = useState(false);
  const [busy, setBusy] = useState(false);
  const go = async () => { setBusy(true); try { await onApply(); } finally { setBusy(false); setAsk(false); } };
  return (
    <div className="sticky bottom-0 flex flex-wrap items-center gap-3 border-t border-white/[0.07] bg-[#121520] pt-3">
      <p className="flex-1 text-xs text-slate-400" data-testid="cv-optimizer-selected">{count} modification(s) sélectionnée(s)</p>
      <button type="button" disabled={!count || busy} onClick={() => setAsk(true)} className="flex items-center gap-1.5 rounded-full bg-emerald-500 px-5 py-2 text-sm font-semibold text-black hover:bg-emerald-400 disabled:opacity-40" data-testid="cv-optimizer-validate">
        {busy && <Loader2 className="h-4 w-4 animate-spin" />}Valider et mettre à jour mon CV maître</button>
      <AlertDialog open={ask} onOpenChange={setAsk}>
        <AlertDialogContent className="border-white/10 bg-[#121520] text-slate-100" data-testid="cv-optimizer-confirm">
          <AlertDialogHeader><AlertDialogTitle>Mettre à jour votre CV maître ?</AlertDialogTitle>
            <AlertDialogDescription className="text-slate-400">{count} modification(s) seront appliquées.{sim ? ` Estimation : compatibilité ${sim.match.before} % → ${sim.match.after} %, indice ${String(sim.ifp.before).replace(".", ",")} → ${String(sim.ifp.after).replace(".", ",")}.` : ""} Votre CV actuel est conservé dans l'historique et peut être restauré à tout moment.</AlertDialogDescription></AlertDialogHeader>
          <AlertDialogFooter><AlertDialogCancel className="border-white/10 bg-transparent text-slate-300" data-testid="cv-optimizer-confirm-cancel">Annuler</AlertDialogCancel>
            <AlertDialogAction onClick={(e) => { e.preventDefault(); go(); }} className="bg-emerald-500 text-black hover:bg-emerald-400" data-testid="cv-optimizer-confirm-ok">{busy ? "Mise à jour…" : "Oui, mettre à jour"}</AlertDialogAction></AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
};

// Real evolution after recalculation.
export const RealResult = ({ done, onClose }) => (
  <div className="space-y-3" data-testid="cv-optimizer-real">
    <p className="text-sm font-semibold text-white">Évolution réelle après recalcul</p>
    {[["Compatibilité avec l'offre", done.match_before, done.match_after, " %", "real-match"], ["Indice de Force Professionnelle", done.ifp_before, done.ifp_after, "", "real-ifp"]].map(([l, a, b, u, t]) => (
      <p key={t} className="flex flex-wrap items-baseline gap-2 rounded-xl border border-emerald-400/25 bg-emerald-500/5 p-3 text-sm text-slate-200" data-testid={t}>{l} :
        <b className="tabular-nums text-white">{String(a).replace(".", ",")}{u}</b><ArrowRight className="h-3.5 w-3.5 text-slate-500" /><b className="tabular-nums text-emerald-300">{String(b).replace(".", ",")}{u}</b>
        <span className="text-emerald-300">({sign(Math.round((b - a) * 10) / 10)})</span></p>))}
    <p className="text-xs text-slate-400">Cette amélioration du CV fait passer votre compatibilité avec cette offre de {done.match_before} % à {done.match_after} % et votre Indice de Force Professionnelle de {String(done.ifp_before).replace(".", ",")} à {String(done.ifp_after).replace(".", ",")}.</p>
    <button type="button" onClick={onClose} className="rounded-full border border-white/10 px-4 py-1.5 text-xs text-slate-200 hover:text-white" data-testid="cv-optimizer-close">Fermer</button>
  </div>
);
