import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ClipboardPaste, ExternalLink, GitCompare, TriangleAlert, Wrench, Zap, EyeOff, ListChecks, Loader2, Radar as RadarIcon, Settings2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Shell } from "@/components/careeros/Shell";
import { PriorityBadge } from "@/components/careeros/Ips";
import { RadarSettingsDialog } from "@/components/careeros/RadarSettings";
import { MoreMenu } from "@/components/careeros/guide/MoreMenu";
import { ConceptRow, InfoTip } from "@/components/careeros/guide/InfoTip";
import { PageTour, TourButton, usePageTour } from "@/components/careeros/guide/PageTour";

const RADAR_STEPS = [
  { target: "radar-settings-btn", title: "Réglages", text: "Postes visés, ville, sources et entreprises suivies. C'est ici que vous associez les portails employeurs." },
  { target: "radar-run-btn", title: "Rechercher maintenant", text: "Lance un passage immédiat. Le Radar tourne aussi automatiquement chaque matin." },
  { target: "radar-stats", title: "Compteurs", text: "Cliquez un chiffre pour filtrer la liste : analysées aujourd'hui, nouvelles, déjà connues, priorité A." },
  { target: "radar-source-status", title: "Sources", text: "Offres trouvées par source au dernier passage : Jooble, Workday, autres sites carrières, Adzuna." },
  { target: "radar-portal-health", title: "Portails employeurs", text: "Lecture de chaque portail : fiable, fragile, bloquée (403) ou repli Jooble. Survolez une ligne pour voir le détail." },
];
import { SourceStatus } from "@/components/careeros/SourceStatus";
import { PortalHealth } from "@/components/careeros/PortalHealth";
import { RadarHistory, TodayMarker } from "@/components/careeros/RadarHistory";
import { usePageTitle } from "@/components/careeros/ThemeToggle";
import { radar } from "@/lib/careeros";
import { FilterBanner, StatFilter } from "@/components/careeros/StatFilter";
import { ScoreExplain } from "@/components/careeros/explain/ScoreExplain";
import { ExternalOffer } from "@/components/careeros/explain/ExternalOffer";
import { CompareDialog } from "@/components/careeros/explain/CompareDialog";

const OfferCard = ({ o, onPack, onIgnore, onDeep, onExplain, deepId, busy }) => (
  <article className="rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-4 min-w-0 break-words" data-testid={`radar-offer-${o.id}`}>
    <div className="flex items-start gap-3">
      <PriorityBadge priority={o.ips?.priority} testid={`radar-priority-${o.id}`} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-white">{o.title}</p>
        <p className="truncate text-xs text-slate-500">{o.company} · {o.location} · {o.source}{o.posted_at ? ` · ${o.posted_at}` : ""}</p>
      </div>
      <span className="whitespace-nowrap font-mono text-xs text-slate-300" title="IPS Radar provisoire : 8 critères évaluables avant candidature. L'IPS officiel est recalculé dans le pack." data-testid={`radar-ips-${o.id}`}>IPS Radar {o.ips?.score ?? "—"}</span>
    </div>
    <div className="mt-2 flex flex-wrap gap-1.5">
      <span className={`inline-flex rounded-full border px-2 py-0.5 text-[11px] ${o.method === "ia" ? "border-indigo-400/30 bg-indigo-500/10 text-indigo-200" : "border-white/10 bg-white/5 text-slate-300"}`}
        title={o.method === "ia" ? "Analyse IA approfondie" : "Pré-analyse par règles CareerOS, sans IA"} data-testid={`radar-method-${o.id}`}>{o.method === "ia" ? "Analyse IA" : "Pré-analyse règles"}</span>
    {o.excerpt && <p className="inline-flex rounded-full border border-amber-400/30 bg-amber-500/10 px-2 py-0.5 text-[11px] text-amber-200" title="Jooble ne fournit qu'un extrait de l'offre : les critères non vérifiables sont notés de façon neutre." data-testid={`radar-excerpt-${o.id}`}>Analyse sur extrait{o.source === "jooble" ? " Jooble" : ""}</p>}
    </div>
    <p className="mt-3 text-xs leading-relaxed text-slate-300" data-testid={`radar-why-${o.id}`}>{o.decision_report?.summary}</p>
    {(o.reasons_apply?.length > 0 || o.reasons_avoid?.length > 0) && (
      <div className="mt-2 grid min-w-0 gap-2 text-[11px] sm:grid-cols-2">
        <ul className="space-y-0.5 text-emerald-300">{(o.reasons_apply || []).map((r, i) => <li key={i}>+ {r}</li>)}</ul>
        <ul className="space-y-0.5 text-rose-300">{(o.reasons_avoid || []).map((r, i) => <li key={i}>– {r}</li>)}</ul>
      </div>
    )}
    <div className="mt-3 flex flex-wrap gap-2">
      {o.status === "pack" ? <span className="text-xs text-indigo-300">Pack généré</span> : (
        <button onClick={() => onPack(o)} disabled={busy} data-testid={`radar-pack-btn-${o.id}`} className="flex items-center gap-1.5 rounded-full bg-indigo-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-50">
          <Sparkles className="h-3.5 w-3.5" />Générer le pack</button>)}
      {o.method !== "ia" && o.status !== "pack" && <button onClick={() => onDeep(o)} disabled={deepId === o.id} data-testid={`radar-deep-btn-${o.id}`} className="flex items-center gap-1.5 rounded-full border border-indigo-400/40 px-3 py-1.5 text-xs text-indigo-200 hover:bg-indigo-500/10 disabled:opacity-60">
        {deepId === o.id ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}Analyse approfondie</button>}
      {o.ips && <button onClick={() => onExplain(o)} data-testid={`radar-explain-btn-${o.id}`} className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:border-indigo-400/40 hover:text-white">
        <ListChecks className="h-3.5 w-3.5" />Pourquoi ce score ?</button>}
      <MoreMenu testid={`radar-more-${o.id}`} items={[
        o.url && { label: "Voir l'offre", icon: ExternalLink, href: o.url, testid: `radar-open-${o.id}` },
        o.status !== "ignoree" && o.status !== "pack" && { label: "Ignorer cette offre", icon: EyeOff, onClick: () => onIgnore(o), danger: true, testid: `radar-ignore-${o.id}` },
      ]} />
    </div>
  </article>
);

const TONES = {
  a: { box: "border-emerald-400/40 bg-emerald-500/10", bar: "bg-emerald-400", text: "text-emerald-200", chip: "bg-emerald-400 text-emerald-950", icon: Zap, cta: "Agir maintenant" },
  b: { box: "border-amber-400/30 bg-amber-500/[0.07]", bar: "bg-amber-400", text: "text-amber-200", chip: "bg-amber-400 text-amber-950", icon: Wrench, cta: "Optimiser puis postuler" },
  c: { box: "border-rose-400/25 bg-rose-500/[0.06]", bar: "bg-rose-400", text: "text-rose-200", chip: "bg-rose-400/80 text-rose-950", icon: TriangleAlert, cta: "À éviter" },
};

const SectionHead = ({ title, n, tone }) => {
  const t = TONES[tone];
  const urgent = tone === "a" && n > 0;
  return (
    <div className={`relative flex items-center gap-3 overflow-hidden rounded-xl border px-4 py-3 ${t.box} ${urgent ? "radar-urgent" : ""}`} data-testid={`radar-section-head-${tone}`}>
      <span className={`absolute inset-y-0 left-0 w-1 ${t.bar}`} />
      <span className="relative flex h-7 w-7 shrink-0 items-center justify-center">
        {urgent && <span className={`absolute inline-flex h-full w-full animate-ping rounded-full ${t.bar} opacity-40`} />}
        <t.icon className={`relative h-4 w-4 ${t.text}`} />
      </span>
      <h2 className={`min-w-0 flex-1 text-sm font-semibold ${t.text}`}>{title}</h2>
      <span className={`rounded-full px-2.5 py-0.5 text-xs font-bold tabular-nums ${t.chip} ${urgent ? "animate-pulse" : ""}`} data-testid={`radar-section-count-${tone}`}>{n}</span>
      {n > 0 && <span className={`hidden text-[11px] font-semibold uppercase tracking-wider sm:inline ${t.text}`}>{t.cta}</span>}
    </div>
  );
};

const Section = ({ title, items, testid, tone, ...p }) => (
  <section className="space-y-3" data-testid={testid}>
    {tone ? <SectionHead title={title} n={items.length} tone={tone} /> : <h2 className="text-sm font-semibold text-slate-200">{title} <span className="text-slate-500">({items.length})</span></h2>}
    {items.length === 0 ? <p className="text-xs text-slate-500">Aucune opportunité.</p> : <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">{items.map((o) => <OfferCard key={o.id} o={o} {...p} />)}</div>}
  </section>
);

export default function Radar() {
  usePageTitle("Radar");
  const nav = useNavigate();
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState(false);
  const tour = usePageTour("radarTourDone");
  const [explainId, setExplainId] = useState(null);
  const [ext, setExt] = useState(false);
  const [cmp, setCmp] = useState(false);
  const load = useCallback(() => radar.dashboard().then(setD).catch((e) => toast.error(e.message)), []);
  const running = d?.last_run?.status === "running";
  const [runs, setRuns] = useState(null);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!running) radar.runs(30).then(setRuns).catch(() => setRuns([])); }, [running, d?.last_run?.id]);
  useEffect(() => { if (!running) return undefined; const t = setTimeout(load, 4000); return () => clearTimeout(t); }, [running, d, load]);

  const runNow = async () => { try { await radar.run(); toast.success("Recherche lancée"); setTimeout(load, 1200); } catch (e) { toast.error(e.message); } };
  const onPack = async (o) => { setBusy(true); try { const r = await radar.pack(o.id); nav(`/careeros/candidature/${r.id}`); } catch (e) { toast.error(e.message); setBusy(false); } };
  const onIgnore = async (o) => { await radar.ignore(o.id); load(); };
  const [deepId, setDeepId] = useState(null);
  const onDeep = async (o) => {
    setDeepId(o.id);
    try { const r = await radar.deep(o.id); toast.success(`Analyse IA : IPS Radar ${r.ips?.score}/100 — priorité ${r.ips?.priority}`); load(); } catch (e) { toast.error(e.message); } finally { setDeepId(null); }
  };
  const [f, setF] = useState(null);
  const lr = d?.last_run;
  const FILTERS = d ? {
    analyzed: ["Analysées aujourd'hui", d.analyzed_today_list || []],
    new: ["Nouvelles (dernier passage)", d.new_today || []],
    known: ["Déjà connues (dernier passage)", d.known_last_run || []],
    a: ["Priorité A", d.top_a],
  } : {};
  const lastOffers = d ? [...new Map([...(d.new_today || []), ...(d.known_last_run || [])].map((o) => [o.id, o])).values()] : [];
  const SRC = { jooble: "Jooble", workday: "Workday", boards: "Sites carrières", adzuna: "Adzuna" };
  const srcOf = (o) => (["jooble", "workday", "adzuna"].includes(o.source) ? o.source : "boards");
  if (f?.startsWith("src:")) FILTERS[f] = [`Source : ${SRC[f.slice(4)]} (dernier passage)`, lastOffers.filter((o) => srcOf(o) === f.slice(4))];
  if (f?.startsWith("co:")) FILTERS[f] = [`Entreprise : ${f.slice(3)} (dernier passage)`, lastOffers.filter((o) => (o.company || "").toLowerCase() === f.slice(3).toLowerCase())];
  const pick = (k) => {
    setF((cur) => (cur === k ? null : k));
    if (k.includes(":")) setTimeout(() => document.querySelector('[data-testid="radar-filter-banner"]')?.scrollIntoView({ behavior: "smooth", block: "start" }), 50);
  };
  const errs = Object.entries(lr?.errors || {});

  return (
    <Shell>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-indigo-300">CareerOS Radar</p>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl">Vos meilleures opportunités</h1>
          <TodayMarker runs={runs} running={running} />
          <p className="mt-2 max-w-xl text-sm text-slate-400">CareerOS cherche chaque jour pour vous, pré-analyse chaque offre par règles (sans IA), fait confirmer par l'IA les 5 meilleures du jour, et classe les offres par IPS Radar (provisoire, sur les critères évaluables avant candidature). L'IPS officiel est recalculé dans le pack complet, qui n'est généré que si vous le demandez.</p>
          <ConceptRow keys={["ips_radar", "priorite", "regles", "deep", "extrait"]} />
        </div>
        <div className="flex flex-wrap gap-2">
          <TourButton onClick={tour.open} testid="radar-tour-btn" />
          <button type="button" onClick={() => { tour.close(); setExt(true); }} className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-2 text-xs text-slate-300 hover:text-white" data-testid="radar-external-btn"><ClipboardPaste className="h-3.5 w-3.5" />Analyser une offre externe</button>
          <button type="button" onClick={() => { tour.close(); setCmp(true); }} className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-2 text-xs text-slate-300 hover:text-white" data-testid="radar-compare-btn"><GitCompare className="h-3.5 w-3.5" />Comparer avec LinkedIn</button>
          <button onClick={() => { tour.close(); setSettings(true); }} data-testid="radar-settings-btn" className="flex items-center gap-1.5 rounded-full border border-white/10 px-4 py-2 text-xs text-slate-300 hover:text-white"><Settings2 className="h-4 w-4" />Réglages</button>
          <button onClick={runNow} disabled={running} data-testid="radar-run-btn" className="flex items-center gap-2 rounded-full bg-indigo-500 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60">
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <RadarIcon className="h-4 w-4" />}{running ? "Recherche en cours…" : "Rechercher maintenant"}</button>
        </div>
      </div>
      {!d ? <Loader2 className="h-5 w-5 animate-spin text-indigo-400" /> : (
        <div className="space-y-8">
          <div className="relative grid grid-cols-2 gap-3 md:grid-cols-4" data-testid="radar-stats">
            <span className="absolute -top-5 right-0"><InfoTip k="compteurs" /></span>
            <StatFilter label="Analysées aujourd'hui (règles · IA)" value={`${d.analyzed_today} · ${d.ai_today ?? 0}/${d.deep_limit ?? 0}`} testid="radar-stat-analyzed" active={f === "analyzed"} onClick={() => pick("analyzed")} />
            <StatFilter label="Nouvelles (dernier passage)" value={lr?.new ?? 0} testid="radar-stat-new" active={f === "new"} onClick={() => pick("new")} />
            <StatFilter label="Déjà connues" value={lr?.known ?? 0} testid="radar-stat-known" active={f === "known"} onClick={() => pick("known")} />
            <StatFilter label="Priorité A" value={d.top_a.length} testid="radar-stat-a" active={f === "a"} onClick={() => pick("a")} />
          </div>
          <SourceStatus status={d.sources_status} run={lr} active={f?.startsWith("src:") ? f.slice(4) : null} onPick={(k) => pick(`src:${k}`)} />
          <PortalHealth status={d.sources_status} run={lr} active={f?.startsWith("co:") ? f.slice(3) : null} onPick={(n) => pick(`co:${n}`)} />
          {lr && <p className="text-xs text-slate-500" data-testid="radar-last-run">Dernier passage : {new Date(lr.at).toLocaleString("fr-CA")} ({lr.trigger}) · {lr.fetched} offres trouvées{lr.skipped_limit ? ` · ${lr.skipped_limit} reportées (limite quotidienne)` : ""}{d.pending ? ` · ${d.pending} en attente d'analyse` : ""}</p>}
          {errs.length > 0 && <div className="rounded-xl border border-amber-400/20 bg-amber-500/5 p-3 text-xs text-amber-200" data-testid="radar-errors">{errs.map(([k, v]) => <p key={k}>{k} : {v}</p>)}</div>}
          {f ? <>
            <FilterBanner label={FILTERS[f][0]} count={FILTERS[f][1].length} onClear={() => setF(null)} testid="radar-filter-banner" />
            <Section title={FILTERS[f][0]} items={FILTERS[f][1]} testid="radar-filtered" onPack={onPack} onIgnore={onIgnore} onDeep={onDeep} onExplain={(o) => setExplainId(o.id)} deepId={deepId} busy={busy} />
          </> : <>
            <Section title="Top priorité A — postuler en premier" items={d.top_a} testid="radar-top-a" tone="a" onPack={onPack} onIgnore={onIgnore} onDeep={onDeep} onExplain={(o) => setExplainId(o.id)} deepId={deepId} busy={busy} />
            <Section title="Top priorité B — postuler après optimisation" items={d.top_b} testid="radar-top-b" tone="b" onPack={onPack} onIgnore={onIgnore} onDeep={onDeep} onExplain={(o) => setExplainId(o.id)} deepId={deepId} busy={busy} />
            <Section title="Opportunités ignorées ou à éviter (C)" items={d.ignored} testid="radar-ignored" tone="c" onPack={onPack} onIgnore={onIgnore} onDeep={onDeep} onExplain={(o) => setExplainId(o.id)} deepId={deepId} busy={busy} />
          </>}
          <RadarHistory runs={runs} />
        </div>
      )}
      {d && !settings && <PageTour tour={tour} steps={RADAR_STEPS} label="Visite du Radar" testid="radar-tour" />}
      <ScoreExplain id={explainId} onClose={() => { setExplainId(null); load(); }} onDeep={load} />
      <CompareDialog open={cmp} onClose={() => setCmp(false)} onExplain={(id) => { setCmp(false); setExplainId(id); }} />
      <ExternalOffer open={ext} onClose={() => setExt(false)} onDone={(o) => { setExt(false); load(); setExplainId(o.id); }} />
      {settings && <RadarSettingsDialog onClose={() => { setSettings(false); load(); }} />}
    </Shell>
  );
}
