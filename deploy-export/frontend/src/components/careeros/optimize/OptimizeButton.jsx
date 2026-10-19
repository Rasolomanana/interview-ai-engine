import { useState } from "react";
import { Sparkles } from "lucide-react";
import { CvOptimizer } from "@/components/careeros/optimize/CvOptimizer";

// Very visible entry point, identical on Radar cards, pack pages and the CV <-> job comparison.
export const OptimizeButton = ({ offer, testid = "optimize-cv-btn", compact = false }) => {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} data-testid={testid}
        className={`flex items-center gap-1.5 rounded-full bg-gradient-to-r from-amber-400 to-orange-400 font-semibold text-black shadow-[0_0_18px_rgba(251,191,36,0.25)] transition-transform hover:-translate-y-0.5 ${compact ? "px-3 py-1.5 text-xs" : "px-4 py-2 text-sm"}`}>
        <Sparkles className="h-4 w-4" />Optimiser mon CV pour cette offre</button>
      {open && <CvOptimizer offer={offer} open={open} onClose={() => setOpen(false)} />}
    </>
  );
};
