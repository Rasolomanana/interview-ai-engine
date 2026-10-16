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
      {cs.included ? "Votre compte est inclus dans le passage automatique de 6 h." : `Votre compte n'est pas inclus dans le passage automatique : ${cs.reason}`}
      {cs.last_auto ? ` Dernier passage automatique : ${day(cs.last_auto.at)} à ${hour(cs.last_auto.at)}.` : " Aucun passage automatique enregistré pour votre compte."}
      {cs.last_daily ? <span data-testid="radar-cron-last-daily"> Dernier démarrage du passage quotidien : {day(cs.last_daily.at)} à {hour(cs.last_daily.at)} ({cs.last_daily.trigger || "cron"}, {cs.last_daily.members} membre(s), {cs.last_daily.status === "done" ? "terminé" : cs.last_daily.status === "error" ? "erreur" : "en cours"}).</span> : null}
      {" "}Le serveur démarre lui-même le passage chaque jour dès 6 h (heure de Toronto) ; s'il dormait, il le rattrape dès son réveil.</p>}
  </>);
};

export const Num = ({ n, onClick, testid }) => (n ? (
  <button type="button" onClick={onClick} data-testid={testid} title="Afficher ces offres"
    className="rounded-md px-1.5 py-0.5 font-semibold text-indigo-300 underline decoration-indigo-400/40 underline-offset-2 transition-colors hover:bg-indigo-500/10 hover:text-indigo-200">{n}</button>
) : <span className="px-1.5">0</span>);

const ERR = (k) => (k === "limite" ? "Limite quotidienne d'analyses" : k === "cv" ? "Career Memory incomplète" : k === "ia" ? "Service IA"
  : k.startsWith("jooble") ? `Jooble · recherche « ${k.split(":")[1]?.split("#")[0] || ""} »` : k.startsWith("adzuna") ? "Adzuna"
  : k.includes(":") ? `Portail employeur · ${k.split(":").slice(1).join(":")}` : k);
const TODO = (k) => (k === "limite" ? "Rien à faire : les offres reportées seront analysées au prochain passage (les plus proches de vos postes d'abord). Vous pouvez aussi lancer une « Analyse approfondie » sur une offre précise."
  : k === "cv" ? "Ajoutez votre CV dans la Career Memory." : k === "ia" ? "Les offres restent notées par règles ; réessayez plus tard." : "Source momentanément indisponible : l'entreprise reste couverte par Jooble.");

const AlertsDialog = ({ run, onClose }) => (
  <Dialog open={!!run} onOpenChange={(o) => !o && onClose()}>
    <DialogContent className="max-h-[85vh] max-w-xl overflow-y-auto border-white/10 bg-[#121520] text-slate-100" data-testid="run-alerts-dialog">
      <DialogHeader><DialogTitle>Alertes · {run && `${day(run.at)} à ${hour(run.at)}`}</DialogTitle>
        <DialogDescription className="text-slate-400">{run && Object.keys(run.errors || {}).length} alerte(s) enregistrée(s) pendant ce passage</DialogDescription></DialogHeader>
      <ul className="space-y-2">{run && Object.entries(run.errors || {}).map(([k, v]) => (
        <li key={k} className="rounded-xl border border-amber-400/20 bg-amber-500/5 p-3 text-xs" data-testid={`run-alert-${k.replace(/[^a-z0-9]/gi, "-")}`}>
          <p className="font-semibold text-amber-200">{ERR(k)}</p>
          <p className="mt-1 text-slate-300">{/403|forbidden/i.test(String(v)) ? "Accès refusé par le portail (HTTP 403 : protection anti-robot)." : String(v).replace(/\s*For more information check:.*$/i, "")}</p>
          <p className="mt-1 text-slate-500">Que faire : {/403|forbidden|anti-robot/i.test(String(v)) ? "Portail protégé volontairement par l'employeur (anti-robot) : aucune action requise, l'entreprise reste suivie via Jooble." : TODO(k)}</p>
        </li>))}</ul>
    </DialogContent>
  </Dialog>
);

const RunRow = ({ r, onShow, onAlerts }) => {
  const bs = r.by_source || {};
  const errs = Object.keys(r.errors || {}).length;
  return (
    <tr className="border-t border-white/[0.05] text-slate-300" data-testid={`radar-run-${r.id}`}>
      <td className="py-2 pr-3 font-mono">{hour(r.at)}</td>
      <td className="pr-3"><span className={`rounded-full px-2 py-0.5 text-[11px] ${isAuto(r) ? "bg-indigo-500/15 text-indigo-200" : "bg-white/5 text-slate-300"}`}>{isAuto(r) ? "Automatique" : "Manuelle"}</span></td>
      <td className="pr-3">{STATUS[r.status] || r.status}</td>
      <td className="pr-3"><Num n={r.fetched} onClick={() => onShow(r, "found")} testid={`radar-run-found-${r.id}`} /></td>
      <td className="pr-3"><Num n={r.new} onClick={() => onShow(r, "new")} testid={`radar-run-new-${r.id}`} /></td>
      <td className="pr-3"><Num n={r.analyzed} onClick={() => onShow(r, "analyzed")} testid={`radar-run-analyzed-${r.id}`} />{r.skipped_limit ? <span className="text-slate-500"> (+<Num n={r.skipped_limit} onClick={() => onShow(r, "skipped")} testid={`radar-run-skipped-${r.id}`} /> reportées)</span> : ""}</td>
      <td className="pr-3 text-slate-400">J <Num n={bs.jooble?.fetched} onClick={() => onShow(r, "src_jooble")} testid={`radar-run-src-jooble-${r.id}`} /> · W <Num n={bs.workday?.fetched} onClick={() => onShow(r, "src_workday")} testid={`radar-run-src-workday-${r.id}`} /> · S <Num n={bs.boards?.fetched} onClick={() => onShow(r, "src_boards")} testid={`radar-run-src-boards-${r.id}`} /></td>
      <td>{errs ? <button type="button" onClick={() => onAlerts(r)} className="rounded-md px-1.5 py-0.5 font-semibold text-amber-300 underline decoration-amber-400/40 underline-offset-2 hover:bg-amber-500/10" data-testid={`radar-run-alerts-${r.id}`}>{errs} alerte(s)</button> : <span className="text-slate-500">—</span>}</td>
    </tr>
  );
};

export const RadarHistory = ({ runs }) => {
  const [open, setOpen] = useState(0);
  const [sel, setSel] = useState(null);
  const [alerts, setAlerts] = useState(null);
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
                  <thead className="text-slate-500"><tr><th className="py-1">Heure</th><th>Type</th><th>Statut</th><th>Trouvées</th><th>Nouvelles</th><th>Analysées</th><th>Par source</th><th>Alertes</th></tr></thead>
                  <tbody>{g.runs.map((r) => <RunRow key={r.id} r={r} onShow={onShow} onAlerts={setAlerts} />)}</tbody>
                </table>
              </div>)}
          </div>
        ))}
      </div>
      <RunOffersDialog sel={sel} onClose={() => setSel(null)} />
      <AlertsDialog run={alerts} onClose={() => setAlerts(null)} />
    </section>
  );
};
