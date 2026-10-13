import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ExternalLink, EyeOff, Loader2, Radar as RadarIcon, Settings2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Shell } from "@/components/careeros/Shell";
import { PriorityBadge } from "@/components/careeros/Ips";
import { RadarSettingsDialog } from "@/components/careeros/RadarSettings";
import { SourceStatus } from "@/components/careeros/SourceStatus";
import { RadarHistory, TodayMarker } from "@/components/careeros/RadarHistory";
import { usePageTitle } from "@/components/careeros/ThemeToggle";
import { radar } from "@/lib/careeros";

const Stat = ({ label, value, testid }) => (
  <div className="rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-4" data-testid={testid}>
    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
    <p className="mt-1 font-display text-2xl font-bold text-white">{value}</p>
  </div>
);

const OfferCard = ({ o, onPack, onIgnore, busy }) => (
  <article className="rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-4 min-w-0 break-words" data-testid={`radar-offer-${o.id}`}>
    <div className="flex items-start gap-3">
      <PriorityBadge priority={o.ips?.priority} testid={`radar-priority-${o.id}`} />
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-semibold text-white">{o.title}</p>
        <p className="truncate text-xs text-slate-500">{o.company} · {o.location} · {o.source}{o.posted_at ? ` · ${o.posted_at}` : ""}</p>
      </div>
      <span className="font-mono text-xs text-slate-300" data-testid={`radar-ips-${o.id}`}>IPS {o.ips?.score ?? "—"}</span>
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
      {o.url && <a href={o.url} target="_blank" rel="noreferrer" data-testid={`radar-open-${o.id}`} className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:text-white"><ExternalLink className="h-3.5 w-3.5" />Voir l'offre</a>}
      {o.status !== "ignoree" && o.status !== "pack" && <button onClick={() => onIgnore(o)} data-testid={`radar-ignore-${o.id}`} className="flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs text-slate-500 hover:text-slate-200"><EyeOff className="h-3.5 w-3.5" />Ignorer</button>}
    </div>
  </article>
);

const Section = ({ title, items, testid, ...p }) => (
  <section className="space-y-3" data-testid={testid}>
    <h2 className="text-sm font-semibold text-slate-200">{title} <span className="text-slate-500">({items.length})</span></h2>
    {items.length === 0 ? <p className="text-xs text-slate-500">Aucune opportunité.</p> : <div className="grid grid-cols-1 gap-3 lg:grid-cols-2">{items.map((o) => <OfferCard key={o.id} o={o} {...p} />)}</div>}
  </section>
);

export default function Radar() {
  usePageTitle("Radar");
  const nav = useNavigate();
  const [d, setD] = useState(null);
  const [busy, setBusy] = useState(false);
  const [settings, setSettings] = useState(false);
  const load = useCallback(() => radar.dashboard().then(setD).catch((e) => toast.error(e.message)), []);
  const running = d?.last_run?.status === "running";
  const [runs, setRuns] = useState(null);
  useEffect(() => { load(); }, [load]);
  useEffect(() => { if (!running) radar.runs(30).then(setRuns).catch(() => setRuns([])); }, [running, d?.last_run?.id]);
  useEffect(() => { if (!running) return undefined; const t = setTimeout(load, 4000); return () => clearTimeout(t); }, [running, d, load]);

  const runNow = async () => { try { await radar.run(); toast.success("Recherche lancée"); setTimeout(load, 1200); } catch (e) { toast.error(e.message); } };
  const onPack = async (o) => { setBusy(true); try { const r = await radar.pack(o.id); nav(`/careeros/candidature/${r.id}`); } catch (e) { toast.error(e.message); setBusy(false); } };
  const onIgnore = async (o) => { await radar.ignore(o.id); load(); };
  const lr = d?.last_run;
  const errs = Object.entries(lr?.errors || {});

  return (
    <Shell>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-indigo-300">CareerOS Radar</p>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl">Vos meilleures opportunités</h1>
          <TodayMarker runs={runs} running={running} />
          <p className="mt-2 max-w-xl text-sm text-slate-400">CareerOS cherche chaque jour pour vous et classe les offres par IPS officiel. Le pack complet n'est généré que si vous le demandez.</p>
        </div>
        <div className="flex gap-2">
          <button onClick={() => setSettings(true)} data-testid="radar-settings-btn" className="flex items-center gap-1.5 rounded-full border border-white/10 px-4 py-2 text-xs text-slate-300 hover:text-white"><Settings2 className="h-4 w-4" />Réglages</button>
          <button onClick={runNow} disabled={running} data-testid="radar-run-btn" className="flex items-center gap-2 rounded-full bg-indigo-500 px-5 py-2 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60">
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <RadarIcon className="h-4 w-4" />}{running ? "Recherche en cours…" : "Rechercher maintenant"}</button>
        </div>
      </div>
      {!d ? <Loader2 className="h-5 w-5 animate-spin text-indigo-400" /> : (
        <div className="space-y-8">
          <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
            <Stat label="Analysées aujourd'hui" value={`${d.analyzed_today}/${d.daily_limit}`} testid="radar-stat-analyzed" />
            <Stat label="Nouvelles (dernier passage)" value={lr?.new ?? 0} testid="radar-stat-new" />
            <Stat label="Déjà connues" value={lr?.known ?? 0} testid="radar-stat-known" />
            <Stat label="Priorité A" value={d.top_a.length} testid="radar-stat-a" />
          </div>
          <SourceStatus status={d.sources_status} run={lr} />
          {lr && <p className="text-xs text-slate-500" data-testid="radar-last-run">Dernier passage : {new Date(lr.at).toLocaleString("fr-CA")} ({lr.trigger}) · {lr.fetched} offres trouvées{lr.skipped_limit ? ` · ${lr.skipped_limit} reportées (limite quotidienne)` : ""}{d.pending ? ` · ${d.pending} en attente d'analyse` : ""}</p>}
          {errs.length > 0 && <div className="rounded-xl border border-amber-400/20 bg-amber-500/5 p-3 text-xs text-amber-200" data-testid="radar-errors">{errs.map(([k, v]) => <p key={k}>{k} : {v}</p>)}</div>}
          <Section title="Top priorité A — postuler en premier" items={d.top_a} testid="radar-top-a" onPack={onPack} onIgnore={onIgnore} busy={busy} />
          <Section title="Top priorité B — postuler après optimisation" items={d.top_b} testid="radar-top-b" onPack={onPack} onIgnore={onIgnore} busy={busy} />
          <Section title="Opportunités ignorées ou à éviter (C)" items={d.ignored} testid="radar-ignored" onPack={onPack} onIgnore={onIgnore} busy={busy} />
          <RadarHistory runs={runs} />
        </div>
      )}
      {settings && <RadarSettingsDialog onClose={() => { setSettings(false); load(); }} />}
    </Shell>
  );
}
