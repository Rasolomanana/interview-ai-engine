import { useNavigate } from "react-router-dom";
import { Clock, ExternalLink, LifeBuoy, PartyPopper } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuTrigger } from "@/components/ui/dropdown-menu";
import { TOUR } from "@/lib/guide";
import { useGuide } from "./GuideProvider";

export const HelpMenu = () => {
  const { beginner, setMode, openTour } = useGuide();
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <button className="flex items-center gap-1.5 rounded-full p-2 text-xs text-slate-400 hover:bg-white/5 hover:text-white" data-testid="help-menu-btn" title="Aide"><LifeBuoy className="h-4 w-4" /><span className="hidden lg:inline">Aide</span></button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-60 border-white/10 bg-[#121520] text-slate-200">
        <DropdownMenuItem onClick={openTour} data-testid="help-restart-tour">Revoir la visite guidée</DropdownMenuItem>
        <DropdownMenuSeparator className="bg-white/10" />
        <DropdownMenuLabel className="text-[11px] font-normal text-slate-500">Niveau d'aide</DropdownMenuLabel>
        <DropdownMenuItem onClick={() => setMode("debutant")} data-testid="help-mode-beginner">{beginner ? "● " : "○ "}Mode Débutant — guides visibles</DropdownMenuItem>
        <DropdownMenuItem onClick={() => setMode("expert")} data-testid="help-mode-expert">{!beginner ? "● " : "○ "}Mode Expert — guides masqués</DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
};

export const GuidedTour = () => {
  const { tour, goTour, closeTour, journey } = useGuide();
  const nav = useNavigate();
  if (!tour) return null;
  const end = tour.step >= TOUR.length;
  const s = TOUR[Math.min(tour.step, TOUR.length - 1)];
  return (
    <Dialog open onOpenChange={(o) => !o && closeTour()}>
      <DialogContent className="max-w-lg border-white/10 bg-[#121520] text-slate-100" data-testid="guided-tour">
        <DialogHeader>
          <p className="text-[11px] font-semibold uppercase tracking-wider text-indigo-300" data-testid="tour-progress">{end ? "Visite terminée" : `Visite guidée · étape ${tour.step + 1} sur ${TOUR.length}`}</p>
          <DialogTitle className="flex items-center gap-2 text-xl" data-testid="tour-title">{end ? <><PartyPopper className="h-5 w-5 text-emerald-400" />CareerOS est prêt</> : s.title}</DialogTitle>
          <DialogDescription className="text-sm leading-relaxed text-slate-400" data-testid="tour-text">
            {end ? `Prochaine étape : ${journey?.next?.title || "compléter votre Career Memory"}. Vous pourrez revoir cette visite à tout moment depuis le menu Aide.` : s.text}
          </DialogDescription>
        </DialogHeader>
        {!end && <div className="flex items-center justify-between text-xs text-slate-500">
          <span className="flex items-center gap-1" data-testid="tour-time"><Clock className="h-3.5 w-3.5" />Temps estimé : {s.time}</span>
          <button onClick={() => nav(s.to)} className="flex items-center gap-1 text-indigo-300 hover:text-indigo-200" data-testid="tour-open-page"><ExternalLink className="h-3.5 w-3.5" />Ouvrir cette page</button>
        </div>}
        <div className="flex gap-1.5">{TOUR.map((t, i) => <span key={t.key} className={`h-1 flex-1 rounded-full ${i < tour.step || end ? "bg-emerald-400" : i === tour.step ? "bg-indigo-400" : "bg-white/10"}`} />)}</div>
        <div className="flex items-center justify-between pt-1">
          {!end ? <button onClick={closeTour} className="rounded-full px-3 py-2 text-sm text-slate-400 hover:bg-white/5 hover:text-white" data-testid="tour-skip">Passer la visite</button> : <span />}
          <div className="flex gap-2">
            {tour.step > 0 && !end && <button onClick={() => goTour(tour.step - 1)} className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-300" data-testid="tour-prev">Précédent</button>}
            {end
              ? <button onClick={() => { closeTour(); if (journey?.next?.to) nav(journey.next.to); }} className="rounded-full bg-indigo-500 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-400" data-testid="tour-finish">Terminer</button>
              : <button onClick={() => goTour(tour.step + 1)} className="rounded-full bg-indigo-500 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-400" data-testid="tour-next">Suivant</button>}
          </div>
        </div>
      </DialogContent>
    </Dialog>
  );
};
