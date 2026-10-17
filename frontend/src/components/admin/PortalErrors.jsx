import { useCallback, useEffect, useState } from "react";
import { Loader2, Trash2, Undo2, Wrench } from "lucide-react";
import { toast } from "sonner";
import { adminPortalErrors, adminPortalErrorStatus, adminPortalErrorFix, adminPortalErrorUndo } from "@/lib/api";
import { ClickNum, DetailDialog } from "./DetailDialog";

const ST = { ouverte: ["Ouverte", "text-rose-300"], resolue: ["Résolue", "text-emerald-300"], ignore: ["Ignorée", "text-slate-400"] };
const date = (s) => (s ? new Date(s).toLocaleString("fr-CA", { dateStyle: "medium", timeStyle: "short" }) : "—");
const LBL = { "statut : ouverte": "Rouverte", "statut : resolue": "Marquée résolue", "statut : ignore": "Ignorée" };
const pwd = () => sessionStorage.getItem("adminPwd");

const FixRow = ({ r, onDone }) => {
  const [url, setUrl] = useState(r.portal_url || "");
  const [busy, setBusy] = useState(false);
  const fix = async () => {
    setBusy(true);
    try { const x = await adminPortalErrorFix(pwd(), r.id, url); toast.success(`Portail corrigé : ${x.fix.offers} offre(s) lue(s), appliqué à ${x.fix.members} membre(s).`); onDone(); } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <div className="flex gap-2">
      <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="URL publique du portail carrières" className="min-w-0 flex-1 rounded-lg border border-white/10 bg-black/40 px-2 py-1 text-xs text-white" data-testid={`perr-url-${r.id}`} />
      <button type="button" onClick={fix} disabled={busy || url.length < 8} className="flex items-center gap-1 rounded-lg bg-emerald-600 px-2.5 py-1 text-xs font-semibold text-white disabled:opacity-50" data-testid={`perr-fix-${r.id}`}>
        {busy ? <Loader2 className="h-3 w-3 animate-spin" /> : <Wrench className="h-3 w-3" />}Tester et corriger</button>
    </div>
  );
};

export const PortalErrors = () => {
  const [d, setD] = useState(null);
  const [filter, setFilter] = useState("ouverte");
  const [detail, setDetail] = useState(null);
  const load = useCallback(() => adminPortalErrors(pwd()).then(setD).catch((e) => toast.error(e.message)), []);
  useEffect(() => { load(); }, [load]);
  if (!d) return <Loader2 className="h-5 w-5 animate-spin text-emerald-400" />;
  const act = async (fn, ok) => { try { await fn(); toast.success(ok); load(); } catch (e) { toast.error(e.message); } };
  const rows = d.items.filter((r) => !filter || r.status === filter);
  return (
    <section className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-4 sm:p-5" data-testid="admin-portal-errors">
      <DetailDialog detail={detail} onClose={() => setDetail(null)} />
      <div>
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-200"><Trash2 className="h-4 w-4 text-rose-400" />Journal des erreurs</h3>
        <p className="text-[11px] text-slate-500">Toutes les erreurs techniques du système (portails, Jooble, Adzuna, IA, packs), masquées aux membres. Une fiche par source et type d'erreur, tous membres confondus. Aucune donnée personnelle : seuls le nombre de membres touchés et les dates sont conservés. Une correction est testée avant d'être appliquée, et peut être annulée.</p>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-4">
        {[["ouverte", "Ouvertes"], ["resolue", "Résolues"], ["ignore", "Ignorées"], ["", "Toutes"]].map(([k, l]) => (
          <div key={l} role="button" tabIndex={0} onClick={() => setFilter(k)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); setFilter(k); } }}
            className={`cursor-pointer rounded-xl border p-3 ${filter === k ? "border-emerald-400/50" : "border-white/10 hover:border-emerald-400/30"}`} data-testid={`perr-kpi-${k || "all"}`}>
            <p className="text-[11px] text-slate-500">{l}</p><p className="font-mono text-xl font-bold text-white">{k ? d.stats[k] : d.stats.total}</p>
          </div>))}
      </div>
      <p className="text-[11px] text-slate-500" data-testid="perr-members">Membres touchés par une erreur ouverte : {d.stats.members}</p>
      {rows.length === 0 ? <p className="text-xs text-slate-500" data-testid="perr-empty">Aucune erreur dans cette catégorie.</p> : (
        <div className="space-y-2">{rows.map((r) => (
          <article key={r.id} className="space-y-2 rounded-xl border border-white/10 p-3 text-xs" data-testid={`perr-row-${r.id}`}>
            <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
              <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] uppercase tracking-wider text-slate-400" data-testid={`perr-cat-${r.id}`}>{r.category_label}</span><span className="font-semibold text-white">{r.name}</span><span className="text-slate-400">{r.kind_label}</span>
              <span className="text-amber-300">{r.type_label}</span><span className={ST[r.status]?.[1]} data-testid={`perr-status-${r.id}`}>{ST[r.status]?.[0]}</span>
              <span className="ml-auto text-slate-500">Dernière : {date(r.last_seen)}</span>
            </div>
            <p className="break-all text-slate-400">{r.message}</p>
            <p className="text-slate-500">
              <ClickNum testid={`perr-occ-${r.id}`} onClick={() => setDetail({ title: `${r.name} · historique`, cols: [["at", "Date"], ["action", "Action"], ["detail", "Détail"]],
                rows: [{ at: r.first_seen, action: "Première occurrence", detail: r.type_label }, ...(r.history || []).map((h) => ({ ...h, action: LBL[h.action] || h.action })), { at: r.last_seen, action: "Dernière occurrence", detail: r.message }]
                  .sort((a, b) => (a.at || "").localeCompare(b.at || "")).map((x) => ({ ...x, at: date(x.at) })) })}>{r.occurrences} occurrence(s)</ClickNum>
              {" · "}{r.members} membre(s) touché(s) · depuis {date(r.first_seen)}
              {r.fix && !r.fix.undone && <span className="text-emerald-300"> · corrigé le {date(r.fix.at)} ({r.fix.offers} offre(s), {r.fix.members} membre(s))</span>}
            </p>
            {r.fixable && r.status !== "resolue" && <FixRow r={r} onDone={load} />}
            <div className="flex flex-wrap gap-2">
              {r.status !== "resolue" && <button type="button" onClick={() => act(() => adminPortalErrorStatus(pwd(), r.id, "resolue"), "Marquée résolue")} className="rounded-full border border-white/10 px-2.5 py-0.5 hover:text-white" data-testid={`perr-resolve-${r.id}`}>Marquer résolue</button>}
              {r.status !== "ignore" && <button type="button" onClick={() => act(() => adminPortalErrorStatus(pwd(), r.id, "ignore"), "Erreur ignorée")} className="rounded-full border border-white/10 px-2.5 py-0.5 hover:text-white" data-testid={`perr-ignore-${r.id}`}>Ignorer</button>}
              {r.status !== "ouverte" && <button type="button" onClick={() => act(() => adminPortalErrorStatus(pwd(), r.id, "ouverte"), "Erreur rouverte")} className="rounded-full border border-white/10 px-2.5 py-0.5 hover:text-white" data-testid={`perr-reopen-${r.id}`}>Rouvrir</button>}
              {r.fix && !r.fix.undone && <button type="button" onClick={() => act(() => adminPortalErrorUndo(pwd(), r.id), "Correction annulée")} className="flex items-center gap-1 rounded-full border border-amber-400/30 px-2.5 py-0.5 text-amber-200" data-testid={`perr-undo-${r.id}`}><Undo2 className="h-3 w-3" />Annuler la correction</button>}
            </div>
          </article>))}</div>)}
    </section>
  );
};
