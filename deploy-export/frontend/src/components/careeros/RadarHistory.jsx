import { useEffect, useState } from "react";
import { radar } from "@/lib/careeros";
import { CalendarClock, CheckCircle2, ChevronDown, CircleAlert, Clock } from "lucide-react";
import { RunOffersDialog } from "./RunOffersDialog";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const TZ = "America/Toronto";
const day = (iso) => new Date(iso).toLocaleDateString("fr-CA", { timeZone: TZ, weekday: "long", day: "numeric", month: "long", year: "numeric" });
const dayKey = (iso) => new Date(iso).toLocaleDateString("en-CA", { timeZone: TZ });
const hour = (iso) => new Date(iso).toLocaleTimeString("fr-CA", { timeZone: TZ, hour: "2-digit", minute: "2-digit" });
const isAuto = (r) => r.trigger !== "manuel";
const STATUS = { done: "Terminée", running: "En cours", interrompue: "Interrompue", error: "Erreur" };

export const TodayMarker = ({ runs, running }) => {
  const [cs, setCs] = useState(null);
  useEffect(() => { radar.cronStatus().then(setCs).catch(() => {}); }, []);
  if (!runs) return null;
  const today = runs.filter((r) => dayKey(r.at) === dayKey(new Date().toISOString()));
  const auto = today.find(isAuto);
  const manual = today.filter((r) => !isAuto(r)).length;
  const ok = today.length > 0;
  return (<>
    <div className={`mt-3 inline-flex flex-wrap items-center gap-2 rounded-full border px-3 py-1.5 text-xs ${ok ? "border-emerald-400/30 bg-emerald-500/10 text-emerald-200" : "border-amber-400/30 bg-amber-500/10 text-amber-200"}`} data-testid="radar-today-marker">
      {running ? <Clock className="h-3.5 w-3.5" /> : ok ? <CheckCircle2 className="h-3.5 w-3.5" /> : <CircleAlert className="h-3.5 w-3.5" />}
      {running ? "Recherche en cours…" : ok ? "Recherche effectuée aujourd'hui" : "Aucune recherche aujourd'hui"}
      <span className="text-slate-400" data-testid="radar-today-detail">
        · Automatique : {auto ? `faite à ${hour(auto.at)}` : "pas encore (prévue à 6 h, heure de l'Est)"}{manual ? ` · ${manual} manuelle(s)` : ""}</span>
    </div>
    {cs && <p className={`mt-2 text-[11px] ${cs.included ? "text-slate-500" : "text-rose-300"}`} data-testid="radar-cron-status">
      {cs.included ? "Votre compte est inclus dans la recherche automatique de 6 h." : `Votre compte n'est pas inclus dans la recherche automatique : ${cs.reason}`}
      {cs.last_auto ? ` Dernière recherche automatique : ${day(cs.last_auto.at)} à ${hour(cs.last_auto.at)}.` : " Aucune recherche automatique pour l'instant."}</p>}
  </>);
};

export const Num = ({ n, onClick, testid }) => (n ? (
  <button type="button" onClick={onClick} data-testid={testid} title="Afficher ces offres"
    className="rounded-md px-1.5 py-0.5 font-semibold text-indigo-300 underline decoration-indigo-400/40 underline-offset-2 transition-colors hover:bg-indigo-500/10 hover:text-indigo-200">{n}</button>
) : <span className="px-1.5">0</span>);

const RunRow = ({ r, onShow }) => {
  const bs = r.by_source || {};
  return (
    <tr className="border-t border-white/[0.05] text-slate-300" data-testid={`radar-run-${r.id}`}>
      <td className="py-2 pr-3 font-mono">{hour(r.at)}</td>
      <td className="pr-3"><span className={`rounded-full px-2 py-0.5 text-[11px] ${isAuto(r) ? "bg-indigo-500/15 text-indigo-200" : "bg-white/5 text-slate-300"}`}>{isAuto(r) ? "Automatique" : "Manuelle"}</span></td>
      <td className="pr-3">{STATUS[r.status] || r.status}</td>
      <td className="pr-3"><Num n={r.fetched} onClick={() => onShow(r, "found")} testid={`radar-run-found-${r.id}`} /></td>
      <td className="pr-3"><Num n={r.new} onClick={() => onShow(r, "new")} testid={`radar-run-new-${r.id}`} /></td>
      <td className="pr-3"><Num n={r.analyzed} onClick={() => onShow(r, "analyzed")} testid={`radar-run-analyzed-${r.id}`} />{r.skipped_limit ? <span className="text-slate-500"> (+<Num n={r.skipped_limit} onClick={() => onShow(r, "skipped")} testid={`radar-run-skipped-${r.id}`} /> reportées)</span> : ""}{r.out_zone ? <span className="text-amber-300/80"> (<Num n={r.out_zone} onClick={() => onShow(r, "out_zone")} testid={`radar-run-outzone-${r.id}`} /> hors zone)</span> : ""}</td>
      <td className="pr-3 text-slate-400">J <Num n={bs.jooble?.fetched} onClick={() => onShow(r, "src_jooble")} testid={`radar-run-src-jooble-${r.id}`} /> · W <Num n={bs.workday?.fetched} onClick={() => onShow(r, "src_workday")} testid={`radar-run-src-workday-${r.id}`} /> · S <Num n={bs.boards?.fetched} onClick={() => onShow(r, "src_boards")} testid={`radar-run-src-boards-${r.id}`} /></td>
    </tr>
  );
};

export const RadarHistory = ({ runs }) => {
  const [open, setOpen] = useState(0);
  const [sel, setSel] = useState(null);
  const onShow = (run, kind) => setSel({ run, kind, when: `${day(run.at)} à ${hour(run.at)}` });
  if (!runs) return null;
  const groups = Object.values(runs.reduce((g, r) => { (g[dayKey(r.at)] ||= { key: dayKey(r.at), label: day(r.at), runs: [] }).runs.push(r); return g; }, {}));
  return (
    <section data-testid="radar-history">
      <h2 className="mb-3 flex items-center gap-2 text-base font-semibold text-white md:text-lg"><CalendarClock className="h-4 w-4 text-indigo-300" />Historique des recherches (30 jours)</h2>
      {groups.length === 0 && <p className="text-sm text-slate-500" data-testid="radar-history-empty">Aucune recherche pour le moment.</p>}
      <div className="space-y-2">
        {groups.map((g, i) => (
          <div key={g.key} className="rounded-2xl border border-white/[0.07] bg-[#121520]/80" data-testid={`radar-history-day-${g.key}`}>
            <button onClick={() => setOpen(open === i ? -1 : i)} className="flex w-full items-center justify-between px-4 py-3 text-left text-sm" data-testid={`radar-history-toggle-${g.key}`}>
              <span className="font-medium capitalize text-slate-200">{g.label}</span>
              <span className="flex items-center gap-3 text-xs text-slate-400">
                Automatique : {g.runs.some(isAuto) ? "oui" : "non"} · {g.runs.length} recherche(s) · {g.runs.reduce((n, r) => n + (r.analyzed || 0), 0)} analysées
                <ChevronDown className={`h-4 w-4 transition-transform ${open === i ? "rotate-180" : ""}`} /></span>
            </button>
            {open === i && (
              <div className="overflow-x-auto px-4 pb-3">
                <table className="w-full min-w-[640px] text-left text-xs">
                  <thead className="text-slate-500"><tr><th className="py-1">Heure</th><th>Type</th><th>Statut</th><th>Trouvées</th><th>Nouvelles</th><th>Analysées</th><th>Par source</th></tr></thead>
                  <tbody>{g.runs.map((r) => <RunRow key={r.id} r={r} onShow={onShow} />)}</tbody>
                </table>
              </div>)}
          </div>
        ))}
      </div>
      <RunOffersDialog sel={sel} onClose={() => setSel(null)} />
    </section>
  );
};
