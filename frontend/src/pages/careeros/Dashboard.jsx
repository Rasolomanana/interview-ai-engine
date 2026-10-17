import { ConceptRow } from "@/components/careeros/guide/InfoTip";
import { useGuide } from "@/components/careeros/guide/GuideProvider";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Brain, ChevronRight } from "lucide-react";
import { Shell } from "@/components/careeros/Shell";
import { PriorityBadge } from "@/components/careeros/Ips";
import { useAuth } from "@/components/careeros/AuthProvider";
import { careeros, radar, PIPELINE_LABELS } from "@/lib/careeros";
import { usePageTitle } from "@/components/careeros/ThemeToggle";
import { FilterBanner, StatFilter } from "@/components/careeros/StatFilter";

const FILTERS = {
  a: ["Priorité A (candidatures + Radar)", (a) => a.priority === "A"],
  entrevue: ["Entrevues obtenues", (a) => a.pipeline_status === "entrevue" || (a.interviews_count || 0) > 0],
  offre: ["Offres d'emploi reçues", (a) => a.pipeline_status === "offre"],
  saved: ["Offres sauvegardées", (a) => a.radar && a.saved],
};

const fromRadar = (o) => ({ id: `radar-${o.id}`, radar: true, saved: !!o.saved, priority: o.ips?.priority, ips: o.ips?.score, poste: o.title, entreprise: o.company, created_at: o.first_seen, location: o.location });

const RadarRow = ({ a }) => (
  <Link to={`/careeros/radar?offer=${a.id.replace("radar-", "")}`} data-testid={`dashboard-radar-row-${a.id}`} className="group grid grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-white/5 px-2 py-3.5 transition-colors hover:bg-white/[0.02]">
    <PriorityBadge priority={a.priority} testid={`row-priority-${a.id}`} />
    <div className="min-w-0">
      <p className="truncate text-sm font-medium text-white"><span className="mr-2 rounded bg-indigo-500/15 px-1.5 py-0.5 font-mono text-[10px] text-indigo-200">RADAR</span>{a.poste}</p>
      <p className="truncate text-xs text-slate-500">{a.entreprise || "—"} · {a.location || ""} · {a.saved ? "Sauvegardée" : "Priorité A détectée par le Radar"} · pas encore de pack</p>
    </div>
    <div className="flex items-center gap-4"><span className="hidden font-mono text-xs text-slate-400 sm:block">IPS Radar {a.ips ?? "—"}</span><ChevronRight className="h-4 w-4 text-slate-600 transition-transform group-hover:translate-x-0.5" /></div>
  </Link>
);

const Row = ({ a }) => (
  <Link to={`/careeros/candidature/${a.id}`} data-testid={`application-row-${a.id}`}
    className="group grid grid-cols-[auto_1fr_auto] items-center gap-4 border-b border-white/5 px-2 py-3.5 transition-colors hover:bg-white/[0.02]">
    <PriorityBadge priority={a.priority} testid={`row-priority-${a.id}`} />
    <div className="min-w-0">
      <p className="truncate text-sm font-medium text-white"><span className="mr-2 font-mono text-[11px] text-indigo-300" data-testid={`row-code-${a.id}`}>{a.code}</span>{a.poste || "Analyse en cours…"}</p>
      <p className="truncate text-xs text-slate-500">{a.entreprise || "—"} · {new Date(a.created_at).toLocaleDateString("fr-CA")} · {PIPELINE_LABELS[a.pipeline_status]}{a.version > 1 ? ` · v${a.version}` : ""}</p>
      {a.why && <p className="mt-0.5 truncate text-[11px] text-slate-400" data-testid={`row-why-${a.id}`}>{a.why}</p>}
    </div>
    <div className="flex items-center gap-4">
      <span className="hidden font-mono text-xs text-slate-400 sm:block">IPS {(a.ips_history || []).map((h) => h.score).join(" → ") || "—"} · ATS {a.ats ?? "—"}</span>
      {a.status === "generating" && <span className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] text-indigo-300">génération</span>}
      {a.apply_urgent && <span className="rounded-full border border-orange-400/40 bg-orange-500/10 px-2 py-0.5 text-[10px] text-orange-300" data-testid={`row-apply-urgent-${a.id}`}>À postuler rapidement</span>}
      {["expired", "expired_likely"].includes(a.availability) && <span className="rounded-full border border-rose-400/40 bg-rose-500/10 px-2 py-0.5 text-[10px] text-rose-300" data-testid={`row-expired-${a.id}`}>Offre expirée · voir ailleurs</span>}
      {a.apply_pending && <span className="rounded-full border border-amber-400/40 bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-300" data-testid={`row-apply-pending-${a.id}`}>Candidature à confirmer</span>}
      <ChevronRight className="h-4 w-4 text-slate-600 transition-transform group-hover:translate-x-0.5" />
    </div>
  </Link>
);

export default function Dashboard() {
  usePageTitle("Tableau de bord");
  const { user } = useAuth();
  const { beginner } = useGuide();
  const [apps, setApps] = useState(null);
  const [rd, setRd] = useState(null);
  useEffect(() => { careeros.list().then(setApps).catch(() => setApps([])); radar.dashboard().then(setRd).catch(() => setRd({})); }, []);
  const radarItems = rd ? [...new Map([...(rd.radar_a || rd.top_a || []), ...(rd.saved || [])].filter((o) => o.status !== "pack").map((o) => [o.id, fromRadar(o)])).values()] : [];
  const list = [...(apps || []), ...radarItems];
  const nApps = (apps || []).length;
  const count = (fn) => list.filter(fn).length;
  const [f, setF] = useState(null);
  const pick = (k) => setF((cur) => (cur === k ? null : k));
  const shown = f ? list.filter(FILTERS[f][1]) : list;

  return (
    <Shell>
      <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-indigo-300">Directeur de carrière</p>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl" data-testid="dashboard-title">Bonjour{user?.name ? `, ${user.name}` : ""}.</h1>
          <p className="mt-2 text-sm text-slate-400">Vos opportunités, classées par probabilité réelle d'obtenir une entrevue.</p>
          <ConceptRow keys={["ips", "priorite", "career_score", "suivi"]} />
        </div>
        <Link to="/careeros/nouveau" data-testid="dashboard-new-pack-btn" className={beginner ? "flex items-center gap-2 rounded-full border border-white/15 px-5 py-2.5 text-sm font-medium text-slate-200 hover:bg-white/5" : "flex items-center gap-2 rounded-full bg-indigo-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-400"}>
          <Plus className="h-4 w-4" /> Nouveau pack candidature
        </Link>
      </div>
      <p className="mb-2 text-[11px] text-slate-500" data-testid="dashboard-breakdown">{nApps} candidature(s) · {radarItems.filter((x) => x.priority === "A").length} priorité(s) A du Radar sans pack · {count(FILTERS.saved[1])} offre(s) sauvegardée(s)</p>
      <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-5">
        <StatFilter label="Opportunités" value={list.length} testid="stat-total" active={!f} onClick={() => setF(null)} />
        <StatFilter label="Sauvegardées" value={count(FILTERS.saved[1])} testid="stat-saved" active={f === "saved"} onClick={() => pick("saved")} />
        <StatFilter label="Priorité A" value={count(FILTERS.a[1])} testid="stat-priority-a" active={f === "a"} onClick={() => pick("a")} />
        <StatFilter label="Entrevues" value={count(FILTERS.entrevue[1])} testid="stat-interviews" active={f === "entrevue"} onClick={() => pick("entrevue")} />
        <StatFilter label="Offres" value={count(FILTERS.offre[1])} testid="stat-offers" active={f === "offre"} onClick={() => pick("offre")} />
      </div>
      <section className="rounded-2xl border border-white/[0.07] bg-[#121520]/60 p-3 sm:p-5">
        <h2 className="mb-2 px-2 text-sm font-semibold text-slate-200">Candidatures et opportunités</h2>
        {f && <div className="mb-3"><FilterBanner label={FILTERS[f][0]} count={shown.length} onClear={() => setF(null)} testid="dashboard-filter-banner" /></div>}
        {apps === null ? <p className="px-2 py-6 text-sm text-slate-500">Chargement…</p> : list.length === 0 ? (
          <div className="flex flex-col items-start gap-3 px-2 py-10" data-testid="empty-history">
            <Brain className="h-6 w-6 text-indigo-300" />
            <p className="text-sm text-slate-400">Aucune candidature pour l'instant. Commencez par une offre qui vous intéresse.</p>
          </div>
        ) : shown.length === 0 ? <p className="px-2 py-6 text-sm text-slate-500" data-testid="filter-empty">Aucune candidature pour ce filtre.</p> : <div data-testid="applications-list">{[...shown].sort((x, y) => (x.priority || "Z").localeCompare(y.priority || "Z") || (y.ips || 0) - (x.ips || 0)).map((a) => (a.radar ? <RadarRow key={a.id} a={a} /> : <Row key={a.id} a={a} />))}</div>}
      </section>
    </Shell>
  );
}
