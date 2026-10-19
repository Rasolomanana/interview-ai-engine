import { useEffect, useState } from "react";
import { Compass, X } from "lucide-react";
import { useGuide } from "./GuideProvider";

const RING = ["ring-2", "ring-indigo-400", "ring-offset-2", "ring-offset-[#090a0f]"];

export const usePageTour = (key) => {
  const { beginner } = useGuide();
  const [step, setStep] = useState(null);
  useEffect(() => { try { if (beginner && localStorage.getItem(key) !== "1") { setStep(0); localStorage.setItem(key, "1"); } } catch { /* ignore */ } }, [key, beginner]);
  const close = () => { try { localStorage.setItem(key, "1"); } catch { /* ignore */ } setStep(null); };
  return { step, setStep, open: () => setStep(0), close };
};

export const PageTour = ({ tour, steps, label, testid, className = "fixed right-4 bottom-6 z-[70]" }) => {
  const { step, setStep, close } = tour;
  const s = step === null ? null : steps[step];
  useEffect(() => {
    if (!s) return undefined;
    const el = document.querySelector(`[data-testid="${s.target}"]`);
    if (!el) return undefined;
    el.scrollIntoView({ block: "center", behavior: "smooth" });
    el.classList.add(...RING);
    return () => el.classList.remove(...RING);
  }, [s]);
  if (!s) return null;
  const last = step === steps.length - 1;
  return (
    <div className={`${className} w-[min(340px,calc(100%-2rem))] rounded-2xl border border-indigo-500/30 bg-[#121520] p-4 text-slate-100 shadow-2xl`} data-testid={testid}>
      <div className="mb-2 flex items-center justify-between">
        <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-indigo-300" data-testid={`${testid}-progress`}><Compass className="h-3.5 w-3.5" />{label} · {step + 1}/{steps.length}</p>
        <button type="button" onClick={close} aria-label="Fermer" className="text-slate-500 hover:text-white" data-testid={`${testid}-close`}><X className="h-4 w-4" /></button>
      </div>
      <h3 className="text-sm font-semibold" data-testid={`${testid}-title`}>{step + 1}. {s.title}</h3>
      <p className="mt-1.5 text-xs leading-relaxed text-slate-400" data-testid={`${testid}-text`}>{s.text}</p>
      <div className="mt-3 flex gap-1">{steps.map((x, i) => <span key={x.target} className={`h-1 flex-1 rounded-full ${i < step ? "bg-emerald-400" : i === step ? "bg-indigo-400" : "bg-white/10"}`} />)}</div>
      <div className="mt-3 flex items-center justify-between">
        <button type="button" onClick={close} className="rounded-full px-3 py-1.5 text-xs text-slate-400 hover:bg-white/5 hover:text-white" data-testid={`${testid}-skip`}>Passer</button>
        <div className="flex gap-2">
          {step > 0 && <button type="button" onClick={() => setStep(step - 1)} className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300" data-testid={`${testid}-prev`}>Précédent</button>}
          <button type="button" onClick={() => (last ? close() : setStep(step + 1))} className="rounded-full bg-indigo-500 px-4 py-1.5 text-xs font-semibold text-white hover:bg-indigo-400" data-testid={last ? `${testid}-finish` : `${testid}-next`}>{last ? "Terminer" : "Suivant"}</button>
        </div>
      </div>
    </div>
  );
};

export const TourButton = ({ onClick, testid, children = "Visite guidée" }) => (
  <button type="button" onClick={onClick} className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-2 text-xs text-slate-300 hover:text-white" data-testid={testid}><Compass className="h-3.5 w-3.5" />{children}</button>
);
