import { useRef, useState } from "react";
import { X } from "lucide-react";

const TONE = (c) => (c >= 0.75 ? "#10b981" : c >= 0.35 ? "#f59e0b" : "#f43f5e");
const ST = { ok: ["Couverte", "bg-emerald-500/15 text-emerald-300"], partiel: ["Partielle", "bg-amber-500/15 text-amber-300"], manquant: ["Manquante", "bg-rose-500/15 text-rose-300"] };

// Required-skills map of the job: same 3D bubble style; colour = how well the CV covers the domain.
export const JobMap = ({ domains, common }) => {
  const [sel, setSel] = useState(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const ref = useRef(null);
  if (!domains.length) return <p className="py-8 text-center text-xs text-slate-500" data-testid="job-map-empty">Aucune compétence reconnue dans la fiche emploi.</p>;
  const max = domains[0].weight;
  const size = (w) => Math.round(64 + 70 * Math.sqrt(w / max));
  const move = (e) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const pt = e.touches ? e.touches[0] : e;
    setTilt({ x: ((pt.clientY - r.top) / r.height - 0.5) * -14, y: ((pt.clientX - r.left) / r.width - 0.5) * 18 });
  };
  const g = domains.find((d) => d.name === sel);
  return (
    <div data-testid="job-map">
      <div ref={ref} onMouseMove={move} onTouchMove={move} onMouseLeave={() => setTilt({ x: 0, y: 0 })} className="overflow-hidden" style={{ perspective: 900 }}>
        <div className="flex flex-wrap items-center justify-center gap-3 py-4 transition-transform duration-300 ease-out" style={{ transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`, transformStyle: "preserve-3d" }}>
          {domains.map((d, i) => {
            const s = size(d.weight), c = TONE(d.coverage);
            return (
              <button key={d.name} type="button" onClick={() => setSel(sel === d.name ? null : d.name)} data-testid={`job-bubble-${i}`}
                className={`skill-bubble relative flex shrink-0 flex-col items-center justify-center rounded-full p-2 text-center text-white ${sel === d.name ? "ring-2 ring-white/80" : ""}`}
                style={{ width: s, height: s, animationDelay: `${(i % 5) * 0.6}s`, transform: `translateZ(${Math.round((d.weight / max) * 60)}px)`,
                  background: `radial-gradient(circle at 30% 28%, ${c}ee, ${c}88 55%, ${c}44)`, boxShadow: `0 ${8 + s / 10}px ${18 + s / 6}px -6px ${c}66, inset 0 -6px 14px rgba(0,0,0,.25)` }}>
                {common.includes(d.name) && <span className="absolute -left-1 top-1 h-3 w-3 rounded-full border-2 border-white bg-indigo-400" title="Domaine présent aussi dans votre carte" />}
                <span className="font-semibold leading-tight" style={{ fontSize: Math.max(10, s / 9) }}>{d.name}</span>
                <span className="mt-0.5 font-mono text-[10px] opacity-90">{Math.round(d.coverage * 100)} %</span>
              </button>);
          })}
        </div>
      </div>
      <div className="flex flex-wrap gap-3 text-[11px] text-slate-400">
        {[["#10b981", "Couverte par votre CV"], ["#f59e0b", "Partielle"], ["#f43f5e", "Manquante"]].map(([c, l]) => <span key={l} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />{l}</span>)}
        <span className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full border-2 border-white bg-indigo-400" />Domaine commun aux deux cartes</span>
      </div>
      {g && (
        <div className="mt-2 rounded-xl border border-white/10 p-3" data-testid="job-map-detail">
          <div className="mb-2 flex items-center justify-between"><p className="text-xs font-semibold text-slate-100">{g.name} · {g.skills.length} compétence(s) · couverture {Math.round(g.coverage * 100)} %</p>
            <button type="button" onClick={() => setSel(null)} className="text-slate-400 hover:text-white" aria-label="Fermer" data-testid="job-map-detail-close"><X className="h-4 w-4" /></button></div>
          <ul className="space-y-1.5">{g.skills.map((k, i) => (
            <li key={k.label} className="text-[12px]" data-testid={`job-skill-${i}`}>
              <div className="flex flex-wrap items-center gap-2"><span className="min-w-0 flex-1 text-slate-200">{k.label}</span>
                <span className="rounded-full bg-white/5 px-1.5 text-[10px] text-slate-400">{k.required ? "Requise" : "Souhaitée"} · {k.mentions} mention(s)</span>
                <span className={`rounded-full px-1.5 text-[10px] ${ST[k.status][1]}`}>{ST[k.status][0]}</span></div>
              <p className="text-[11px] text-slate-500">{k.evidence}</p>
            </li>))}</ul>
        </div>)}
    </div>
  );
};
