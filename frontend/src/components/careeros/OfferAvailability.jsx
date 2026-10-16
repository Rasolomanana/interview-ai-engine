import { useEffect, useRef, useState } from "react";
import { AlertTriangle, CheckCircle2, ExternalLink, HelpCircle, Loader2, RefreshCw, Search, Timer } from "lucide-react";
import { toast } from "sonner";
import { careeros } from "@/lib/careeros";

const ST = {
  available: [CheckCircle2, "text-emerald-300", "Offre disponible"],
  expired: [AlertTriangle, "text-rose-300", "Offre expirée sur ce site"],
  expired_likely: [AlertTriangle, "text-amber-300", "Offre probablement retirée"],
  unknown: [HelpCircle, "text-slate-300", "Disponibilité impossible à vérifier"],
};
const ago = (iso) => Math.floor((Date.now() - new Date(iso).getTime()) / 864e5);
const STALE_MS = 6 * 36e5;
const CACHE_MS = 12 * 36e5;

export const OfferAvailability = ({ a, onChange }) => {
  const [busy, setBusy] = useState("");
  const av = a.availability;
  const run = async (search, auto = false) => {
    setBusy(search ? "search" : "check");
    try {
      const r = await careeros.checkAvailability(a.id, search, auto);
      onChange({ availability: r.availability, alternatives: r.alternatives, alternatives_at: r.alternatives_at, google_jobs: r.google_jobs || a.google_jobs });
      if (search && !auto) toast.message(r.alternatives?.length ? `${r.alternatives.length} annonce(s) correspondante(s) trouvée(s) ailleurs.` : "Aucune annonce correspondante trouvée automatiquement : utilisez les recherches rapides.");
    } catch (e) { toast.error(e.message); } finally { setBusy(""); }
  };
  const todo = a.pipeline_status === "a_postuler";
  const started = useRef("");
  useEffect(() => {
    if (started.current === a.id) return;
    started.current = a.id;
    if (todo && (!a.alternatives_at || Date.now() - new Date(a.alternatives_at).getTime() > CACHE_MS)) run(true, true);  // automatic search, cached 12 h
    else if (todo && a.offer_link && (!av?.checked_at || Date.now() - new Date(av.checked_at).getTime() > STALE_MS)) run(false);
  }, [a.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const use = async (alt) => {
    try { const r = await careeros.setOfferLink(a.id, alt.url, alt.source); onChange({ offer_link: r.offer_link, offer_source: alt.source, availability: r.availability, alternatives: r.alternatives }); toast.success("Lien du dossier remplacé : vous pouvez postuler."); }
    catch (e) { toast.error(e.message); }
  };
  const covered = new Set((a.alternatives || []).map((x) => (x.source || "").toLowerCase()));
  const hasOfficial = (a.alternatives || []).some((x) => x.official);
  const manual = (a.search_links || []).filter((l) => ![...covered].some((c) => c.includes(l.label.toLowerCase())) && !(hasOfficial && l.label.startsWith("Site carrière")));
  const openAll = () => {
    const links = manual;
    const blocked = links.filter((l) => { const w = window.open(l.url, "_blank"); if (w) w.opener = null; return !w; }).length;
    if (blocked && links.length) toast.message(`${blocked} onglet(s) bloqué(s) par le navigateur : autorisez les fenêtres surgissantes pour ce site, ou cliquez sur chaque lien.`);
  };
  const prio = a.ips?.priority;
  const age = ago(a.created_at);
  const urgent = todo && ["A", "B"].includes(prio) && age >= 3;
  const [Icon, tone, label] = ST[av?.status] || ST.unknown;
  const bad = ["expired", "expired_likely"].includes(av?.status);
  const alts = a.alternatives || [];
  return (
    <div className="mt-4 space-y-3 border-t border-white/10 pt-4" data-testid="offer-availability">
      {urgent && <p className="flex items-center gap-2 rounded-lg border border-amber-400/40 bg-amber-500/10 px-3 py-2 text-xs text-amber-200" data-testid="apply-urgent">
        <Timer className="h-4 w-4" />Offre prioritaire {prio} à postuler rapidement : dossier créé il y a {age} jour(s). Les bonnes offres se ferment vite.</p>}
      <div className="flex flex-wrap items-center gap-2 text-xs">
        {a.offer_link && (busy === "check" ? <span className="flex items-center gap-1.5 text-slate-300"><Loader2 className="h-4 w-4 animate-spin" />Vérification de l'offre…</span>
          : <span className={`flex items-center gap-1.5 font-medium ${tone}`} data-testid="availability-status"><Icon className="h-4 w-4" />{av ? label : "Disponibilité non vérifiée"}</span>)}
        {av?.detail && busy !== "check" && <span className="text-slate-400" data-testid="availability-detail">{av.detail}{av.checked_at ? ` · vérifié ${new Date(av.checked_at).toLocaleString("fr-CA", { dateStyle: "short", timeStyle: "short" })}` : ""}</span>}
        {a.offer_link && <button type="button" onClick={() => run(false)} disabled={!!busy} className="flex items-center gap-1 rounded-full border border-white/10 px-2.5 py-1 text-slate-300 hover:text-white disabled:opacity-50" data-testid="availability-check-btn"><RefreshCw className="h-3.5 w-3.5" />Vérifier maintenant</button>}
        <button type="button" onClick={() => run(true)} disabled={!!busy} className="flex items-center gap-1 rounded-full border border-indigo-400/40 px-2.5 py-1 text-indigo-200 hover:bg-indigo-500/10 disabled:opacity-50" data-testid="availability-search-btn">
          {busy === "search" ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}{busy === "search" ? "Recherche sur tous les sites…" : "Trouver l'offre partout"}</button>
      </div>
      {(bad || alts.length > 0 || a.alternatives_at) && <div className={`rounded-xl border p-3 ${bad ? "border-rose-400/30 bg-rose-500/5" : "border-white/10"}`} data-testid="alternatives">
        <p className="mb-2 text-xs font-semibold text-slate-200">{alts.length ? `Offre trouvée sur ${new Set(alts.map((x) => x.source)).size} site(s) · ${alts.length} lien(s)` : `Aucune copie trouvée automatiquement (${(a.auto_sources || ["Portail officiel"]).join(", ")})`}
          {a.alternatives_at && <span className="ml-2 font-normal text-slate-500">recherche du {new Date(a.alternatives_at).toLocaleString("fr-CA", { dateStyle: "short", timeStyle: "short" })}</span>}</p>
        {alts.map((x, i) => (
          <div key={x.url} className="flex flex-wrap items-center gap-2 border-t border-white/5 py-1.5 text-xs" data-testid={`alternative-${i}`}>
            <span className={`rounded px-1.5 py-0.5 text-[10px] font-semibold ${x.official ? "bg-emerald-500/20 text-emerald-300" : "bg-white/10 text-slate-300"}`} data-testid={`alternative-source-${i}`}>{x.source}{x.via ? <span className="ml-1 font-normal text-slate-500">via {x.via}</span> : null}</span>
            <span className="min-w-[60%] flex-1 break-words text-slate-200 sm:min-w-0">{x.title} · {x.company}{x.location ? ` · ${x.location}` : ""}{x.posted_at ? ` · ${x.posted_at}` : ""}</span>
            <span className="font-mono text-[10px] text-slate-400" data-testid={`alternative-match-${i}`}>{x.match} %</span>
            <a href={x.url} target="_blank" rel="noopener noreferrer" className="flex items-center gap-1 text-indigo-300 hover:text-white" data-testid={`alternative-open-${i}`}><ExternalLink className="h-3.5 w-3.5" />Ouvrir</a>
            <button type="button" onClick={() => use(x)} className="rounded-full border border-emerald-400/40 px-2 py-0.5 text-emerald-200 hover:bg-emerald-500/10" data-testid={`alternative-use-${i}`}>Utiliser ce lien</button>
          </div>))}
      </div>}
      <p className="text-[11px] text-slate-500" data-testid="auto-sources">Recherche automatique à l'ouverture (résultats gardés 12 h) : {(a.auto_sources || ["Portail officiel"]).join(" · ")}.
        {a.google_jobs?.enabled ? <span data-testid="google-jobs-budget"> Google Jobs (Indeed, LinkedIn, Glassdoor…) : {a.google_jobs.used}/{a.google_jobs.cap} recherches ce mois, réservé aux offres A en priorité.</span>
          : <span data-testid="google-jobs-off"> Google Jobs (liens Indeed, LinkedIn, Glassdoor…) s'activera avec la clé SerpApi.</span>}</p>
      <details className="text-[11px]" data-testid="manual-sites">
        <summary className="cursor-pointer text-slate-400 hover:text-white" data-testid="manual-sites-toggle">Autres sites (recherche manuelle) · {manual.length}</summary>
        <div className="mt-2 flex flex-wrap items-center gap-2" data-testid="search-links">
          {manual.map((l, i) => <a key={l.label} href={l.url} target="_blank" rel="noopener noreferrer" className={`rounded-full border px-2.5 py-1 hover:text-white ${l.quebec ? "border-sky-400/30 text-sky-200" : "border-white/10 text-slate-300"} hover:border-white/25`} data-testid={`search-link-${i}`}>{l.label}</a>)}
          <button type="button" onClick={openAll} className="rounded-full border border-emerald-400/40 px-2.5 py-1 text-emerald-200 hover:bg-emerald-500/10" data-testid="search-links-open-all">Tout ouvrir ({manual.length})</button>
        </div>
        <p className="mt-1 text-[10px] text-slate-600">Sites non couverts par la recherche automatique (ils interdisent la lecture automatique). En bleu : sites québécois.</p>
      </details>
    </div>
  );
};
