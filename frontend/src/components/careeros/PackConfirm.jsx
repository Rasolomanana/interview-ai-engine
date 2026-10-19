import { AlertDialog, AlertDialogAction, AlertDialogCancel, AlertDialogContent, AlertDialogDescription, AlertDialogFooter, AlertDialogHeader, AlertDialogTitle } from "@/components/ui/alert-dialog";

// Confirmation before an AI pack generation started from a Radar card.
export const PackConfirm = ({ offer, onCancel, onConfirm, onExplain }) => (
  <AlertDialog open={!!offer} onOpenChange={(v) => !v && onCancel()}>
    <AlertDialogContent className="border-white/10 bg-[#121520] text-slate-100" data-testid="pack-confirm-dialog">
      <AlertDialogHeader>
        <AlertDialogTitle>Générer le pack complet ?</AlertDialogTitle>
        <AlertDialogDescription className="text-slate-400">
          {offer?.title}{offer?.company ? ` — ${offer.company}` : ""}. CareerOS prépare votre CV adapté, la lettre, les questions d'entrevue et le plan de suivi (environ 1 minute).
          Vous pouvez d'abord regarder gratuitement pourquoi cette offre a obtenu son score.
        </AlertDialogDescription>
      </AlertDialogHeader>
      <AlertDialogFooter className="gap-2">
        <AlertDialogCancel className="border-white/10 bg-transparent text-slate-300" data-testid="pack-confirm-cancel">Annuler</AlertDialogCancel>
        {offer?.ips && <button type="button" onClick={() => onExplain(offer)} className="rounded-md border border-white/10 px-4 py-2 text-sm text-slate-200 hover:text-white" data-testid="pack-confirm-explain">Voir le score d'abord (gratuit)</button>}
        <AlertDialogAction onClick={() => onConfirm(offer)} className="bg-indigo-500 text-white hover:bg-indigo-400" data-testid="pack-confirm-ok">Générer le pack</AlertDialogAction>
      </AlertDialogFooter>
    </AlertDialogContent>
  </AlertDialog>
);
