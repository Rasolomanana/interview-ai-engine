import { useEffect, useState } from "react";
import { Compass, X } from "lucide-react";

export const COPILOT_STEPS = [
  { n: 1, target: "open-context-btn", title: "Contexte", text: "Collez l'offre, votre CV et l'entreprise. Le copilote adapte chaque réponse à ce poste." },
  { n: 2, target: "open-settings-btn", title: "Réglages", text: "Choisissez le fournisseur IA (Serveur ou Gemini), le style de réponse et le ton." },
  { n: 3, target: "toggle-listen-btn", title: "Écoute", text: "Captez la question du recruteur depuis l'onglet Teams/Zoom ou le micro." },
  { n: 4, target: "live-btn", title: "Live", text: "Mode mains-libres : écoute + fenêtre flottante en un clic pendant l'entrevue." },
  { n: 5, target: "floating-btn", title: "Fenêtre flottante", text: "Affiche la réponse dans une petite fenêtre à glisser sous votre caméra." },
  { n: 6, target: "capture-screen-btn", title: "Images & capture", text: "Joignez ou capturez un écran (test, QCM). Capture LOCALE, invisible pour le recruteur." },
  { n: 7, target: "send-btn", title: "Envoyer", text: "Tapez ou dictez la question, puis envoyez pour obtenir la réponse suggérée." },
  { n: 8, target: "recap-btn", title: "Récap", text: "Après l'entrevue : synthèse de la session et export de la transcription." },
];

const KEY = "copilotTourDone";

export const StepNum = ({ n }) => (
  <span className="flex h-4 min-w-4 items-center justify-center rounded-full bg-indigo-500 px-1 font-mono text-[10px] font-bold leading-none text-white" data-testid={`copilot-step-num-${n}`}>{n}</span>
);

export const useCopilotTour = () => {
  const [step, setStep] = useState(null);
  useEffect(() => { try { if (localStorage.getItem(KEY) !== "1") setStep(0); } catch { /* ignore */ } }, []);
  const close = () => { try { localStorage.setItem(KEY, "1"); } catch { /* ignore */ } setStep(null); };
  return { step, setStep, open: () => setStep(0), close };
};

export const CopilotTour = ({ tour }) => {
  const { step, setStep, close } = tour;
  const s = step === null ? null : COPILOT_STEPS[step];
  useEffect(() => {
    if (!s) return undefined;
    const el = document.querySelector(`[data-testid="${s.target}"]`);
    if (!el) return undefined;
    el.scrollIntoView({ block: "nearest", behavior: "smooth" });
    el.classList.add("ring-2", "ring-indigo-400", "ring-offset-2", "ring-offset-[#090a0f]");
    return () => el.classList.remove("ring-2", "ring-indigo-400", "ring-offset-2", "ring-offset-[#090a0f]");
  }, [s]);
  if (!s) return null;
  const last = step === COPILOT_STEPS.length - 1;
  return (
    <div className="fixed right-4 top-4 z-[70] w-[min(360px,calc(100vw-2rem))] rounded-2xl border border-indigo-500/30 bg-[#121520] sm:top-auto sm:bottom-28 p-4 text-slate-100 shadow-2xl backdrop-blur-xl" data-testid="copilot-tour">
      <div className="mb-2 flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-indigo-300" data-testid="copilot-tour-progress"><Compass className="h-3.5 w-3.5" />Visite du copilote · {step + 1}/{COPILOT_STEPS.length}</p>
        <button onClick={close} aria-label="Fermer" className="text-slate-500 hover:text-white" data-testid="copilot-tour-close"><X className="h-4 w-4" /></button>
      </div>
      <h3 className="flex items-center gap-2 text-base font-semibold" data-testid="copilot-tour-title"><StepNum n={s.n} />{s.title}</h3>
      <p className="mt-1.5 text-sm leading-relaxed text-slate-400" data-testid="copilot-tour-text">{s.text}</p>
      <div className="mt-3 flex gap-1">{COPILOT_STEPS.map((x, i) => <span key={x.n} className={`h-1 flex-1 rounded-full ${i < step ? "bg-emerald-400" : i === step ? "bg-indigo-400" : "bg-white/10"}`} />)}</div>
      <div className="mt-3 flex items-center justify-between">
        <button onClick={close} className="rounded-full px-3 py-1.5 text-xs text-slate-400 hover:bg-white/5 hover:text-white" data-testid="copilot-tour-skip">Passer</button>
        <div className="flex gap-2">
          {step > 0 && <button onClick={() => setStep(step - 1)} className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300" data-testid="copilot-tour-prev">Précédent</button>}
          <button onClick={() => (last ? close() : setStep(step + 1))} className="rounded-full bg-indigo-500 px-4 py-1.5 text-xs font-semibold text-white hover:bg-indigo-400" data-testid={last ? "copilot-tour-finish" : "copilot-tour-next"}>{last ? "Terminer" : "Suivant"}</button>
        </div>
      </div>
    </div>
  );
};
