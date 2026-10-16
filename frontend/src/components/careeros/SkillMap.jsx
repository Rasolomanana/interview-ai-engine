import { useMemo, useRef, useState } from "react";
import { Sparkles, X } from "lucide-react";
import { buildSkillMap } from "@/lib/skillMap";
import { usePersistedToggle } from "@/lib/usePersistedToggle";

// Floating bubbles with 3D depth: the cloud tilts with the pointer, bigger domains sit closer.
export const SkillMap = ({ profile }) => {
  const groups = useMemo(() => buildSkillMap(profile), [profile]);
  const [sel, setSel] = useState(null);
  const [tilt, setTilt] = useState({ x: 0, y: 0 });
  const [open, toggle] = usePersistedToggle("cos.skillmap.open", true);
  const ref = useRef(null);
  if (!groups.length) return null;
  const max = groups[0].weight;
  const size = (w) => Math.round(64 + 76 * Math.sqrt(w / max));
  const move = (e) => {
    const r = ref.current?.getBoundingClientRect();
    if (!r) return;
    const pt = e.touches ? e.touches[0] : e;
    setTilt({ x: ((pt.clientY - r.top) / r.height - 0.5) * -14, y: ((pt.clientX - r.left) / r.width - 0.5) * 18 });
  };
  const g = groups.find((x) => x.name === sel);
  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4" data-testid="skill-map">
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs text-slate-300"><Sparkles className="h-3.5 w-3.5 text-emerald-400" />Carte de compétences · {groups.length} domaine(s)</p>
        <button type="button" onClick={toggle} className="text-[11px] text-indigo-300 hover:text-white" data-testid="skill-map-toggle">{open ? "Masquer la carte" : "Afficher la carte"}</button>
      </div>
      {open && <>
        <p className="mt-1 text-[11px] text-slate-500">Taille = poids du domaine (nombre de compétences + mentions dans votre CV et votre Career Memory). Cliquez sur une bulle pour voir son détail.</p>
        <div ref={ref} onMouseMove={move} onTouchMove={move} onMouseLeave={() => setTilt({ x: 0, y: 0 })} className="mt-3 overflow-hidden" style={{ perspective: 900 }} data-testid="skill-map-cloud">
          <div className="flex flex-wrap items-center justify-center gap-3 py-4 transition-transform duration-300 ease-out" style={{ transform: `rotateX(${tilt.x}deg) rotateY(${tilt.y}deg)`, transformStyle: "preserve-3d" }}>
            {groups.map((d, i) => {
              const s = size(d.weight);
              return (
                <button key={d.name} type="button" onClick={() => setSel(sel === d.name ? null : d.name)} data-testid={`skill-bubble-${i}`}
                  className={`skill-bubble flex shrink-0 flex-col items-center justify-center rounded-full p-2 text-center text-white ${sel === d.name ? "ring-2 ring-white/80" : ""}`}
                  style={{ width: s, height: s, animationDelay: `${(i % 5) * 0.7}s`, transform: `translateZ(${Math.round((d.weight / max) * 60)}px)`,
                    background: `radial-gradient(circle at 30% 28%, ${d.color}ee, ${d.color}88 55%, ${d.color}44)`, boxShadow: `0 ${8 + s / 10}px ${18 + s / 6}px -6px ${d.color}66, inset 0 -6px 14px rgba(0,0,0,.25)` }}>
                  <span className="text-[11px] font-semibold leading-tight" style={{ fontSize: Math.max(10, s / 9) }}>{d.name}</span>
                  <span className="mt-0.5 font-mono text-[10px] opacity-80">{d.skills.length} · {d.weight}</span>
                </button>);
            })}
          </div>
        </div>
        {g && (
          <div className="mt-2 rounded-xl border border-white/10 p-3" data-testid="skill-map-detail">
            <div className="mb-2 flex items-center justify-between"><p className="text-xs font-semibold" style={{ color: g.color }}>{g.name} · {g.skills.length} compétence(s) · poids {g.weight}</p>
              <button type="button" onClick={() => setSel(null)} className="text-slate-400 hover:text-white" aria-label="Fermer" data-testid="skill-map-detail-close"><X className="h-4 w-4" /></button></div>
            <ul className="space-y-1">{g.skills.map((k, i) => (
              <li key={k.label} className="flex items-center gap-2 text-[12px]" data-testid={`skill-map-skill-${i}`}>
                <span className="min-w-0 flex-1 text-slate-200">{k.label}{k.variants > 1 ? <span className="text-slate-500"> (+{k.variants - 1} formulation(s) proche(s))</span> : null}</span>
                <span className="h-2 w-24 overflow-hidden rounded bg-white/10"><span className="block h-full rounded" style={{ width: `${(k.weight / g.skills[0].weight) * 100}%`, background: g.color }} /></span>
                <span className="w-24 text-right font-mono text-[10px] text-slate-400">{k.mentions} mention(s)</span>
              </li>))}</ul>
          </div>)}
      </>}
    </div>
  );
};
