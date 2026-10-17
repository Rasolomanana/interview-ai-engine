import { ChevronDown, Eye, EyeOff } from "lucide-react";
import { usePersistedToggle } from "@/lib/usePersistedToggle";

// Collapsible block with a remembered Masquer / Afficher choice.
export const Foldable = ({ storageKey, title, hint, initial = true, testid, children }) => {
  const [open, toggle] = usePersistedToggle(storageKey, initial);
  return (
    <div data-testid={testid}>
      <div className="mb-2 flex items-center justify-between gap-2">
        <span className="text-xs text-slate-400">{title}{!open && hint ? <span className="ml-2 whitespace-nowrap text-slate-500">· {hint}</span> : null}</span>
        <button type="button" onClick={toggle} aria-expanded={open} className="flex shrink-0 items-center gap-1 rounded-full border border-white/10 px-2.5 py-1 text-[11px] text-slate-300 transition-colors hover:bg-white/5 hover:text-white" data-testid={`${testid}-toggle`}>
          {open ? <EyeOff className="h-3 w-3" /> : <Eye className="h-3 w-3" />}{open ? "Masquer" : "Afficher"}
          <ChevronDown className={`h-3 w-3 transition-transform ${open ? "rotate-180" : ""}`} />
        </button>
      </div>
      {open && children}
    </div>
  );
};
