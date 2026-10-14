import { Check, ChevronDown, X } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

const slug = (g) => g.replace(/[^a-z]/gi, "-");

export const GoalsSelect = ({ options, value = [], onToggle, onClear }) => (
  <Popover>
    <PopoverTrigger asChild>
      <button type="button" data-testid="goals-select-trigger"
        className="flex h-11 w-full items-center gap-2 overflow-hidden rounded-xl border border-white/10 bg-black/40 px-3 text-left text-sm text-white outline-none transition-colors hover:border-indigo-400/40 focus:border-indigo-400/60">
        <span className="flex min-w-0 flex-1 items-center gap-1.5 overflow-hidden" data-testid="goals-selected-summary">
          {value.length === 0 && <span className="text-slate-500">Choisir un ou plusieurs objectifs…</span>}
          {value.slice(0, 2).map((g) => <span key={g} className="shrink-0 truncate rounded-full bg-indigo-500/15 px-2.5 py-0.5 text-xs text-indigo-100">{g}</span>)}
          {value.length > 2 && <span className="shrink-0 rounded-full bg-white/10 px-2 py-0.5 text-xs text-slate-300">+{value.length - 2}</span>}
        </span>
        <span className="shrink-0 font-mono text-[11px] text-slate-500" data-testid="goals-count">{value.length}/{options.length}</span>
        <ChevronDown className="h-4 w-4 shrink-0 text-slate-400" />
      </button>
    </PopoverTrigger>
    <PopoverContent align="start" className="w-[var(--radix-popover-trigger-width)] min-w-[260px] border-white/10 bg-[#121520] p-1.5 text-slate-200" data-testid="goals-list">
      <div className="max-h-72 overflow-y-auto">
        {options.map((g) => {
          const on = value.includes(g);
          return (
            <button key={g} type="button" onClick={() => onToggle(g)} data-testid={`goal-${slug(g)}`}
              className="flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors hover:bg-white/5">
              <span className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border ${on ? "border-indigo-400 bg-indigo-500 text-white" : "border-white/20"}`}>{on && <Check className="h-3 w-3" />}</span>
              <span className={on ? "text-white" : "text-slate-400"}>{g}</span>
            </button>
          );
        })}
      </div>
      {value.length > 0 && (
        <button type="button" onClick={onClear} data-testid="goals-clear-btn"
          className="mt-1 flex w-full items-center justify-center gap-1 border-t border-white/10 pt-2 text-xs text-slate-500 hover:text-slate-300">
          <X className="h-3 w-3" /> Tout désélectionner
        </button>
      )}
    </PopoverContent>
  </Popover>
);
