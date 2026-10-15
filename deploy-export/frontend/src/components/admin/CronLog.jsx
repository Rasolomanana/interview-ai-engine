import { useEffect, useState } from "react";
import { Clock } from "lucide-react";
import { toast } from "sonner";
import { adminCronLog } from "@/lib/api";

const ST = { done: ["Terminé", "text-emerald-300"], started: ["En cours", "text-sky-300"], interrompu: ["Interrompu (processus arrêté avant la fin)", "text-rose-300"] };
const t = (iso) => new Date(iso).toLocaleString("fr-CA", { timeZone: "America/Toronto", dateStyle: "short", timeStyle: "medium" });

export const CronLog = () => {
  const [rows, setRows] = useState(null);
  useEffect(() => { adminCronLog(sessionStorage.getItem("adminPwd")).then((r) => setRows(r.items)).catch((e) => toast.error(e.message)); }, []);
  return (
    <section className="min-w-0 rounded-2xl border border-white/10 bg-slate-900/60 p-4 sm:p-5" data-testid="admin-cron-log">
      <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-200"><Clock className="h-4 w-4 text-emerald-400" />Journal du passage quotidien (cron Radar)</h3>
      <p className="mb-3 text-[11px] text-slate-500">Chaque appel reçu de cron-job.org est enregistré dès réception, puis chaque membre traité (Radar, puis détection des portails). Heure de Toronto.</p>
      {!rows ? <p className="text-xs text-slate-500">Chargement…</p> : rows.length === 0 ? <p className="text-xs text-amber-300" data-testid="cron-log-empty">Aucun appel reçu depuis la mise en place du journal.</p> : (
        <div className="space-y-2">{rows.map((r) => {
          const [l, c] = ST[r.status] || ST.started;
          return (
            <details key={r.id} className="rounded-xl border border-white/5 bg-black/20 p-3 text-xs" data-testid={`cron-log-${r.id}`}>
              <summary className="cursor-pointer text-slate-200">{t(r.at)} · <span className={c}>{l}</span> · {r.members} membre(s) traité(s){r.inactive_skipped ? ` · ${r.inactive_skipped} inactif(s) ignoré(s)` : ""} · {r.steps.filter((s) => !s.ok).length} erreur(s)</summary>
              <ul className="mt-2 space-y-1 text-slate-400">{r.steps.map((s, i) => (
                <li key={i} className={s.ok ? "" : "text-rose-300"}>{t(s.at)} · membre {s.member} · {s.step === "radar" ? "Radar" : "Détection portails"} · {s.ok ? (s.step === "radar" ? `${s.fetched} trouvées, ${s.new} nouvelles, ${s.analyzed} analysées` : `${s.checked} vérifiée(s)${s.associated?.length ? `, associé(s) : ${s.associated.join(", ")}` : ""}`) : s.error}</li>))}
                {r.steps.length === 0 && <li>Aucune étape enregistrée.</li>}
              </ul>
            </details>);
        })}</div>)}
    </section>
  );
};
