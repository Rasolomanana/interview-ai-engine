import { Link, useLocation } from "react-router-dom";
import { ArrowRight, Check, Clock, Compass } from "lucide-react";
import { Popover, PopoverContent, PopoverTrigger } from "@/components/ui/popover";
import { useGuide } from "./GuideProvider";

const activeKey = (path, next) => {
  if (path.startsWith("/careeros/memoire")) return "memory";
  if (path.startsWith("/careeros/radar")) return "radar";
  if (path.startsWith("/careeros/nouveau") || path.startsWith("/careeros/candidature")) return "pack";
  if (path.startsWith("/careeros/copilote")) return "interview";
  return next;
};

const Progress = ({ j }) => (
  <Popover>
    <PopoverTrigger asChild>
      <button className="flex shrink-0 items-center gap-2 rounded-full border border-indigo-400/25 bg-indigo-500/10 px-2.5 py-1 text-[11px] font-medium text-indigo-200" data-testid="journey-progress">
        <span className="h-1.5 w-12 overflow-hidden rounded-full bg-white/10"><span className="block h-full rounded-full bg-emerald-400" style={{ width: `${(j.completed / j.total) * 100}%` }} /></span>
        {j.completed}/{j.total} objectifs
      </button>
    </PopoverTrigger>
    <PopoverContent align="end" className="w-64 border-white/10 bg-[#121520] p-3 text-xs" data-testid="journey-milestones">
      <p className="mb-2 font-semibold text-white">Vos objectifs</p>
      {j.milestones.map((m) => (
        <p key={m.key} className={`flex items-center gap-2 py-0.5 ${m.done ? "text-emerald-300" : "text-slate-400"}`} data-testid={`milestone-${m.key}`}>
          <span className={`flex h-4 w-4 items-center justify-center rounded-full border ${m.done ? "border-emerald-400 bg-emerald-500/20" : "border-white/20"}`}>{m.done && <Check className="h-3 w-3" />}</span>{m.label}
        </p>))}
    </PopoverContent>
  </Popover>
);

export const JourneyBar = () => {
  const { journey: j, beginner } = useGuide();
  const { pathname } = useLocation();
  if (!j || !beginner) return null;
  const cur = activeKey(pathname, j.next.step);
  return (
    <div className="mb-5 flex items-center gap-3 rounded-2xl border border-white/[0.07] bg-[#121520]/60 px-3 py-2" data-testid="journey-bar">
      <ol className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto">
        {j.steps.map((s, i) => {
          const on = s.key === cur;
          return (
            <li key={s.key} className="flex shrink-0 items-center">
              {i > 0 && <span className="mx-1 h-px w-3 bg-white/10 sm:w-5" />}
              <Link to={s.to} aria-current={on ? "step" : undefined} data-testid={`journey-step-${s.key}`}
                className={`flex items-center gap-1.5 rounded-full px-2 py-1 text-xs transition-colors ${on ? "bg-indigo-500/15 font-semibold text-indigo-200 ring-1 ring-indigo-400/40" : s.done ? "text-emerald-300 hover:bg-white/5" : "text-slate-500 hover:bg-white/5 hover:text-slate-300"}`}>
                <span className={`flex h-5 w-5 items-center justify-center rounded-full text-[10px] ${s.done ? "bg-emerald-500/20 text-emerald-300" : on ? "bg-indigo-500 text-white" : "border border-white/15"}`}>{s.done ? <Check className="h-3 w-3" /> : i + 1}</span>
                <span className={on ? "" : "hidden md:inline"}>{s.label}</span>
                {on && <span className="sr-only">étape {i + 1} sur {j.steps.length}</span>}
              </Link>
            </li>);
        })}
      </ol>
      <Progress j={j} />
    </div>
  );
};

export const NextStep = () => {
  const { journey: j, beginner } = useGuide();
  const { pathname } = useLocation();
  if (!j || !beginner) return null;
  const n = j.next;
  const here = n.to === pathname;
  return (
    <div className="mb-8 flex flex-col gap-3 rounded-2xl border border-indigo-400/25 bg-indigo-500/[0.07] p-4 sm:flex-row sm:items-center sm:justify-between" data-testid="next-step-banner">
      <div className="min-w-0">
        <p className="flex items-center gap-1.5 text-[11px] font-semibold uppercase tracking-wider text-indigo-300"><Compass className="h-3.5 w-3.5" />Que faire ensuite ?</p>
        <p className="mt-1 font-medium text-white" data-testid="next-step-title">{n.title}</p>
        <p className="text-sm text-slate-400">{n.text} <span className="ml-1 inline-flex items-center gap-1 text-xs text-slate-500"><Clock className="h-3 w-3" />{n.time}</span></p>
      </div>
      {here ? <span className="shrink-0 text-xs text-indigo-200" data-testid="next-step-here">Vous êtes au bon endroit : suivez les indications de cette page.</span> : <Link to={n.to} data-testid="next-step-cta" className="inline-flex shrink-0 items-center justify-center gap-2 rounded-full bg-indigo-500 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-indigo-400">
        {n.cta}<ArrowRight className="h-4 w-4" /></Link>}
    </div>
  );
};
