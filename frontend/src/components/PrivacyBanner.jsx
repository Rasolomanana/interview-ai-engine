import { useState, useEffect } from "react";
import { ShieldCheck, X } from "lucide-react";

export default function PrivacyBanner() {
  const [show, setShow] = useState(false);
  useEffect(() => {
    try { setShow(localStorage.getItem("privacyAccepted") !== "1"); } catch { setShow(true); }
  }, []);
  if (!show) return null;
  const accept = () => {
    try { localStorage.setItem("privacyAccepted", "1"); } catch { /* ignore */ }
    setShow(false);
  };
  return (
    <div data-testid="privacy-banner" className="fixed inset-x-0 bottom-0 z-[60] border-t border-white/10 bg-slate-950/95 px-4 py-3 backdrop-blur">
      <div className="mx-auto flex max-w-5xl items-start gap-3 sm:items-center">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-emerald-400 sm:mt-0" />
        <p className="flex-1 text-[12px] leading-relaxed text-slate-300">
          Confidentialité : certaines données d'analyse (rapport ATS, score, date, IP anonymisée) peuvent être
          enregistrées à des fins administratives et d'amélioration du service. Votre CV n'est conservé que si
          vous cochez explicitement le consentement avant « Analyser ». Données supprimées automatiquement après 90 jours.
        </p>
        <button
          onClick={accept}
          data-testid="privacy-accept-btn"
          className="shrink-0 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-black hover:bg-emerald-400"
        >
          J'ai compris
        </button>
        <button onClick={accept} aria-label="Fermer" className="shrink-0 text-slate-500 hover:text-slate-300">
          <X className="h-4 w-4" />
        </button>
      </div>
    </div>
  );
}
