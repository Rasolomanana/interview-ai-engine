import { MoreMenu } from "@/components/careeros/guide/MoreMenu";
import { ApplyBar } from "@/components/careeros/ApplyBar";
import { ConceptRow, InfoTip } from "@/components/careeros/guide/InfoTip";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Archive, GitCompareArrows, Mic, RefreshCw } from "lucide-react";
import { toast } from "sonner";
import { Shell } from "@/components/careeros/Shell";
import { PriorityBadge } from "@/components/careeros/Ips";
import { careeros, PIPELINE_LABELS } from "@/lib/careeros";
import { PackRef } from "@/components/careeros/DocTools";
import { VersionBar, ReanalyzeDialog, CompareDialog } from "@/components/careeros/Versions";
import { Pending, DecisionPanel, AtsPanel, SimulationPanel, QuestionsPanel, StarPanel, DocPanel } from "@/components/careeros/PackSections";
import { usePageTitle } from "@/components/careeros/ThemeToggle";
import { FollowupPanel } from "@/components/careeros/Followup";

const TABS = [
  ["decision", "Décision & IPS"], ["ats", "Analyse ATS"], ["cv_ats", "CV ATS"], ["cv_humain", "CV humain"],
  ["letter", "Lettre"], ["questions", "Questions"], ["star", "Réponses STAR"], ["simulation", "Simulation recruteur"], ["suivi", "Suivi & agenda"],
];
const PART_OF = { decision: "decision", ats: "decision", simulation: "decision", cv_ats: "cv_ats", cv_humain: "cv_humain", letter: "letter", questions: "questions", star: "star" };

function TabBody({ tab, a, app, onRetry }) {
  const p = a.parts || {};
  if (tab === "suivi") return <FollowupPanel app={app} />;
  const part = PART_OF[tab];
  if (!p[part]) return <Pending label={TABS.find((t) => t[0] === tab)[1]} error={a.errors?.[part] || a.errors?.pack || (a.status !== "generating" ? "génération échouée" : "")} onRetry={onRetry} />;
  const d = p.decision || {};
  switch (tab) {
    case "decision": return <DecisionPanel d={d} ips={a.ips} report={a.decision_report} />;
    case "ats": return <AtsPanel d={d} />;
    case "simulation": return <SimulationPanel d={d} />;
    case "questions": return <QuestionsPanel q={p.questions} />;
    case "star": return <StarPanel s={p.star} />;
    case "letter": return <DocPanel text={p.letter} name="Lettre-de-motivation" kind="letter" testid="letter" />;
    default: return <DocPanel text={p[tab]} name={tab === "cv_ats" ? "CV-ATS" : "CV-humain"} testid={tab} />;
  }
}

export default function PackView() {
  const { id } = useParams();
  const nav = useNavigate();
  const [a, setA] = useState(null);
  const [tab, setTab] = useState("decision");
  usePageTitle(a?.code ? `Pack candidature · ${a.code}` : "Pack candidature");
  const [viewing, setViewing] = useState(null);
  const [older, setOlder] = useState(null);
  const [dialog, setDialog] = useState("");
  const [tick, setTick] = useState(0);

  useEffect(() => {
    let alive = true, timer;
    const load = async () => {
      try {
        const d = await careeros.get(id);
        if (!alive) return;
        setA(d);
        if (d.status === "generating") timer = setTimeout(load, 2500);
        else window.dispatchEvent(new Event("careeros:journey"));
      } catch (e) { toast.error(e.message); }
    };
    load();
    return () => { alive = false; clearTimeout(timer); };
  }, [id, tick]);

  const view = async (v) => {
    if (v === a.current_version) { setViewing(null); setOlder(null); return; }
    try { setOlder(await careeros.getVersion(id, v)); setViewing(v); } catch (e) { toast.error(e.message); }
  };

  const changeStatus = async (s) => {
    await careeros.setStatus(id, s);
    setA({ ...a, pipeline_status: s, apply_opened_at: null, applied_at: a.applied_at || (s === "postule" ? new Date().toISOString() : a.applied_at) });
    toast.success(`Statut : ${PIPELINE_LABELS[s]}`);
  };
  const retry = async () => {
    try { await careeros.retry(id); toast.success("Régénération des sections manquantes lancée"); setTick((t) => t + 1); } catch (e) { toast.error(e.message); }
  };
  const remove = async () => {
    if (!window.confirm("Archiver cette candidature ? Elle disparaîtra du tableau de bord mais son historique complet reste conservé.")) return;
    await careeros.remove(id);
    nav("/careeros");
  };

  if (!a) return <Shell><Pending label="Chargement" /></Shell>;
  const shown = older && viewing ? older : a;
  const shownVersion = viewing || a.current_version;
  const d = shown.parts?.decision || a.parts?.decision || {};
  const done = Object.values(a.parts || {}).filter(Boolean).length;
  const comparable = (a.versions || []).filter((v) => v.ips != null).length >= 2;

  return (
    <Shell>
      <button onClick={() => nav("/careeros")} className="mb-6 flex items-center gap-1.5 text-xs text-slate-500 hover:text-white" data-testid="back-to-dashboard"><ArrowLeft className="h-3.5 w-3.5" /> Tableau de bord</button>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-indigo-300"><span data-testid="application-code" className="text-white">{a.code}</span> · Dossier de candidature · v{shownVersion}</p>
          <h1 className="mt-2 font-display text-3xl font-bold tracking-tight sm:text-4xl" data-testid="pack-title">{d.poste || (a.status === "error" ? "Pack à relancer" : "Analyse en cours…")}</h1>
          <p className="mt-1 text-sm text-slate-400">{d.entreprise}</p>
          <ConceptRow keys={["ips", "priorite", "pack", "suivi", "ics"]} />
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {shown.ips && <><PriorityBadge priority={shown.ips.priority} testid="header-priority" /><span className="font-mono text-sm text-slate-300" data-testid="header-ips">IPS {shown.ips.score}</span></>}
          <select value={a.pipeline_status} onChange={(e) => changeStatus(e.target.value)} data-testid="pipeline-status-select"
            className="rounded-full border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-slate-200 outline-none">
            {Object.entries(PIPELINE_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          {a.status === "done" && <Link to={`/careeros/copilote?pack=${a.id}`} title="Ouvre le Copilote avec le CV, l'offre, le CV ATS et la lettre de ce pack déjà remplis" data-testid="prepare-interview-btn" className="flex items-center gap-1.5 rounded-full bg-indigo-500 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-400"><Mic className="h-3.5 w-3.5" />Préparer l'entrevue</Link>}
          <MoreMenu testid="pack-more-btn" items={[
            { label: "Comparer les versions", icon: GitCompareArrows, onClick: () => comparable && setDialog("compare"), testid: "compare-versions-btn" },
            { label: "Archiver la candidature", icon: Archive, onClick: remove, danger: true, testid: "delete-application-btn" },
          ]} />
        </div>
      </div>
      <ApplyBar a={a} d={d} onChange={(p) => setA((x) => ({ ...x, ...p }))} />
      <div className="mb-6 flex flex-wrap items-center justify-between gap-3 rounded-2xl border border-white/[0.07] bg-[#121520]/60 px-4 py-3" data-testid="versions-panel">
        <div className="flex flex-wrap items-center gap-3">
          <span className="flex items-center font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">Historique IPS<InfoTip k="versions" /></span>
          <VersionBar versions={a.versions || []} viewing={shownVersion} onView={view} />
        </div>
        <div className="flex gap-2">
          <button onClick={() => setDialog("reanalyze")} disabled={a.status === "generating"} data-testid="reanalyze-btn" className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:text-white disabled:opacity-40"><RefreshCw className="h-3.5 w-3.5" />Réanalyser</button>
        </div>
      </div>
      {viewing && <p className="mb-4 rounded-lg border border-amber-400/20 bg-amber-500/5 px-3 py-2 text-xs text-amber-200" data-testid="viewing-old-version">Vous consultez la version v{viewing} (archivée, non modifiable) — {older?.change_note}. <button className="underline" onClick={() => view(a.current_version)}>Revenir à la version actuelle</button></p>}
      {dialog === "reanalyze" && <ReanalyzeDialog open onOpenChange={() => setDialog("")} app={a} onStarted={() => { setViewing(null); setOlder(null); setTick((t) => t + 1); }} />}
      {dialog === "compare" && <CompareDialog open onOpenChange={() => setDialog("")} app={a} />}
      {a.status === "generating" && (
        <div className="mb-6" data-testid="pack-progress">
          <div className="mb-1.5 flex justify-between text-xs text-slate-400"><span>CareerOS prépare votre pack…</span><span>{done}/6 documents</span></div>
          <div className="h-1 rounded-full bg-white/5"><div className="h-full rounded-full bg-indigo-400 transition-[width] duration-700" style={{ width: `${(done / 6) * 100}%` }} /></div>
        </div>
      )}
      <div className="mb-6 flex gap-1 overflow-x-auto border-b border-white/5 pb-px" data-testid="pack-tabs">
        {TABS.map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`pack-tab-${k}`}
            className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-xs font-medium transition-colors ${tab === k ? "border-indigo-400 text-white" : "border-transparent text-slate-500 hover:text-slate-200"}`}>
            {l}{k === "suivi" || shown.parts?.[PART_OF[k]] ? "" : " ·"}
          </button>
        ))}
      </div>
      <PackRef.Provider value={`${a.code} · v${shownVersion}`}>
        <TabBody tab={tab} a={shown} app={a} onRetry={!viewing && a.status !== "generating" ? retry : null} />
      </PackRef.Provider>
    </Shell>
  );
}
