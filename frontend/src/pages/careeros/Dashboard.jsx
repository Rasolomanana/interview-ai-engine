import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Plus, Brain, ChevronRight } from "lucide-react";
import { Shell } from "@/components/careeros/Shell";
import { PriorityBadge } from "@/components/careeros/Ips";
import { useAuth } from "@/components/careeros/AuthProvider";
import { careeros, PIPELINE_LABELS } from "@/lib/careeros";

const Stat = ({ label, value, testid }) => (
  <div className="rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-4" data-testid={testid}>
    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">{label}</p>
    <p className="mt-2 font-display text-3xl font-bold text-white">{value}</p>
  </div>
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
      <ChevronRight className="h-4 w-4 text-slate-600 transition-transform group-hover:translate-x-0.5" />
    </div>
  </Link>
);

export default function Dashboard() {
  const { user } = useAuth();
  const [apps, setApps] = useState(null);
  useEffect(() => { careeros.list().then(setApps).catch(() => setApps([])); }, []);
  const list = apps || [];
  const count = (fn) => list.filter(fn).length;

  return (
    <Shell>
      <div className="mb-10 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-indigo-300">Directeur de carrière</p>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl" data-testid="dashboard-title">Bonjour{user?.name ? `, ${user.name}` : ""}.</h1>
          <p className="mt-2 text-sm text-slate-400">Vos opportunités, classées par probabilité réelle d'obtenir une entrevue.</p>
        </div>
        <Link to="/careeros/nouveau" data-testid="dashboard-new-pack-btn" className="flex items-center gap-2 rounded-full bg-indigo-500 px-5 py-2.5 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 hover:bg-indigo-400">
          <Plus className="h-4 w-4" /> Nouveau pack candidature
        </Link>
      </div>
      <div className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-4">
        <Stat label="Opportunités" value={list.length} testid="stat-total" />
        <Stat label="Priorité A" value={count((a) => a.priority === "A")} testid="stat-priority-a" />
        <Stat label="Entrevues" value={count((a) => a.pipeline_status === "entrevue")} testid="stat-interviews" />
        <Stat label="Offres" value={count((a) => a.pipeline_status === "offre")} testid="stat-offers" />
      </div>
      <section className="rounded-2xl border border-white/[0.07] bg-[#121520]/60 p-3 sm:p-5">
        <h2 className="mb-2 px-2 text-sm font-semibold text-slate-200">Historique des candidatures</h2>
        {apps === null ? <p className="px-2 py-6 text-sm text-slate-500">Chargement…</p> : list.length === 0 ? (
          <div className="flex flex-col items-start gap-3 px-2 py-10" data-testid="empty-history">
            <Brain className="h-6 w-6 text-indigo-300" />
            <p className="text-sm text-slate-400">Aucune candidature pour l'instant. Commencez par une offre qui vous intéresse.</p>
          </div>
        ) : <div data-testid="applications-list">{[...list].sort((x, y) => (x.priority || "Z").localeCompare(y.priority || "Z") || (y.ips || 0) - (x.ips || 0)).map((a) => <Row key={a.id} a={a} />)}</div>}
      </section>
    </Shell>
  );
}
