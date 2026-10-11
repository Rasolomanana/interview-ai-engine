import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { ArrowLeft, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Shell } from "@/components/careeros/Shell";
import { PriorityBadge } from "@/components/careeros/Ips";
import { careeros, PIPELINE_LABELS } from "@/lib/careeros";
import { Pending, DecisionPanel, AtsPanel, SimulationPanel, QuestionsPanel, StarPanel, DocPanel } from "@/components/careeros/PackSections";

const TABS = [
  ["decision", "Décision & IPS"], ["ats", "Analyse ATS"], ["cv_ats", "CV ATS"], ["cv_humain", "CV humain"],
  ["letter", "Lettre"], ["questions", "Questions"], ["star", "Réponses STAR"], ["simulation", "Simulation recruteur"],
];
const PART_OF = { decision: "decision", ats: "decision", simulation: "decision", cv_ats: "cv_ats", cv_humain: "cv_humain", letter: "letter", questions: "questions", star: "star" };

function TabBody({ tab, a }) {
  const p = a.parts || {};
  const part = PART_OF[tab];
  if (!p[part]) return <Pending label={TABS.find((t) => t[0] === tab)[1]} error={a.errors?.[part] || (a.status !== "generating" ? "génération échouée" : "")} />;
  const d = p.decision || {};
  switch (tab) {
    case "decision": return <DecisionPanel d={d} ips={a.ips} />;
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

  useEffect(() => {
    let alive = true, timer;
    const load = async () => {
      try {
        const d = await careeros.get(id);
        if (!alive) return;
        setA(d);
        if (d.status === "generating") timer = setTimeout(load, 2500);
      } catch (e) { toast.error(e.message); }
    };
    load();
    return () => { alive = false; clearTimeout(timer); };
  }, [id]);

  const changeStatus = async (s) => {
    await careeros.setStatus(id, s);
    setA({ ...a, pipeline_status: s });
    toast.success(`Statut : ${PIPELINE_LABELS[s]}`);
  };
  const remove = async () => {
    if (!window.confirm("Supprimer définitivement cette candidature et ses documents ?")) return;
    await careeros.remove(id);
    nav("/careeros");
  };

  if (!a) return <Shell><Pending label="Chargement" /></Shell>;
  const d = a.parts?.decision || {};
  const done = Object.values(a.parts || {}).filter(Boolean).length;

  return (
    <Shell>
      <button onClick={() => nav("/careeros")} className="mb-6 flex items-center gap-1.5 text-xs text-slate-500 hover:text-white" data-testid="back-to-dashboard"><ArrowLeft className="h-3.5 w-3.5" /> Tableau de bord</button>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-indigo-300">Pack candidature</p>
          <h1 className="mt-2 font-display text-3xl font-bold tracking-tight sm:text-4xl" data-testid="pack-title">{d.poste || "Analyse en cours…"}</h1>
          <p className="mt-1 text-sm text-slate-400">{d.entreprise}</p>
        </div>
        <div className="flex items-center gap-3">
          {a.ips && <><PriorityBadge priority={a.ips.priority} testid="header-priority" /><span className="font-mono text-sm text-slate-300" data-testid="header-ips">IPS {a.ips.score}</span></>}
          <select value={a.pipeline_status} onChange={(e) => changeStatus(e.target.value)} data-testid="pipeline-status-select"
            className="rounded-full border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-slate-200 outline-none">
            {Object.entries(PIPELINE_LABELS).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
          </select>
          <button onClick={remove} className="rounded-full p-2 text-slate-500 hover:bg-rose-500/10 hover:text-rose-300" data-testid="delete-application-btn" title="Supprimer"><Trash2 className="h-4 w-4" /></button>
        </div>
      </div>
      {a.status === "generating" && (
        <div className="mb-6" data-testid="pack-progress">
          <div className="mb-1.5 flex justify-between text-xs text-slate-400"><span>Interview AI Engine génère votre pack…</span><span>{done}/6 documents</span></div>
          <div className="h-1 rounded-full bg-white/5"><div className="h-full rounded-full bg-indigo-400 transition-[width] duration-700" style={{ width: `${(done / 6) * 100}%` }} /></div>
        </div>
      )}
      <div className="mb-6 flex gap-1 overflow-x-auto border-b border-white/5 pb-px" data-testid="pack-tabs">
        {TABS.map(([k, l]) => (
          <button key={k} onClick={() => setTab(k)} data-testid={`pack-tab-${k}`}
            className={`whitespace-nowrap border-b-2 px-3 py-2.5 text-xs font-medium transition-colors ${tab === k ? "border-indigo-400 text-white" : "border-transparent text-slate-500 hover:text-slate-200"}`}>
            {l}{a.parts?.[PART_OF[k]] ? "" : " ·"}
          </button>
        ))}
      </div>
      <TabBody tab={tab} a={a} />
    </Shell>
  );
}
