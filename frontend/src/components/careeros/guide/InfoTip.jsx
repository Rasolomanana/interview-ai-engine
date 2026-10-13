import { Info } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { GLOSSARY } from "@/lib/guide";
import { useGuide } from "./GuideProvider";

export const InfoTip = ({ k, className = "" }) => {
  const { beginner } = useGuide();
  const g = GLOSSARY[k];
  if (!beginner || !g) return null;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" aria-label={`Qu'est-ce que : ${g.title}`} data-testid={`infotip-${k}`} onClick={(e) => e.stopPropagation()}
          className={`ml-1 inline-flex h-4 w-4 shrink-0 items-center justify-center rounded-full text-slate-500 transition-colors hover:text-indigo-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-400/50 ${className}`}>
          <Info className="h-3.5 w-3.5" />
        </button>
      </PopoverTrigger>
      <PopoverContent side="top" className="w-72 border-white/10 bg-[#121520] p-3 text-xs leading-relaxed text-slate-300 shadow-xl" data-testid={`infotip-content-${k}`}>
        <p className="mb-1 font-semibold text-white">{g.title}</p>
        {g.text}
      </PopoverContent>
    </Popover>
  );
};

export const ConceptRow = ({ keys }) => {
  const { beginner } = useGuide();
  if (!beginner) return null;
  return (
    <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-slate-500" data-testid="concept-row">
      <span>Comprendre :</span>
      {keys.map((k) => <span key={k} className="inline-flex items-center rounded-full border border-white/[0.07] px-2 py-0.5 text-slate-400">{GLOSSARY[k].title}<InfoTip k={k} /></span>)}
    </div>
  );
};
