import { CalendarDays, X } from "lucide-react";
import { format, parseISO } from "date-fns";
import { fr } from "date-fns/locale";
import { Calendar } from "@/components/ui/calendar";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";

// ISO yyyy-MM-dd value, displayed dd/MM/yyyy in French
export const DateField = ({ value, onChange, className, testid }) => {
  const d = value ? parseISO(value) : undefined;
  return (
    <Popover>
      <PopoverTrigger asChild>
        <button type="button" className={`${className} flex items-center justify-between text-left`} data-testid={testid}>
          <span className={d ? "" : "text-slate-500"}>{d ? format(d, "dd/MM/yyyy") : "jj/mm/aaaa"}</span>
          <span className="flex items-center gap-1">
            {d && <X className="h-3.5 w-3.5 text-slate-500 hover:text-white" data-testid={`${testid}-clear`} onClick={(e) => { e.stopPropagation(); onChange(""); }} />}
            <CalendarDays className="h-4 w-4 text-slate-500" />
          </span>
        </button>
      </PopoverTrigger>
      <PopoverContent className="w-auto border-white/10 bg-[#121520] p-0" align="start">
        <Calendar mode="single" locale={fr} selected={d} disabled={{ after: new Date() }} initialFocus
          onSelect={(x) => onChange(x ? format(x, "yyyy-MM-dd") : "")} data-testid={`${testid}-calendar`} />
      </PopoverContent>
    </Popover>
  );
};
