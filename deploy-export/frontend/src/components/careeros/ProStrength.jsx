import { useEffect, useState } from "react";
import { Gauge, Loader2 } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { careeros } from "@/lib/careeros";
import { usePersistedToggle } from "@/lib/usePersistedToggle";
import { Levers } from "@/components/careeros/Levers";

const tone = (r) => (r >= 0.8 ? "bg-emerald-400" : r >= 0.55 ? "bg-indigo-400" : r >= 0.35 ? "bg-amber-400" : "bg-rose-400");

const Spark = ({ hist }) => {
  if (hist.length < 2) return <p className="text-[11px] text-slate-500" data-testid="strength-history-empty">L'évolution s'affichera dès le prochain changement de votre profil.</p>;
  const w = 220, h = 44, xs = (i) => (i * w) / (hist.length - 1), ys = (s) => h - (s / 100) * h;
  return (
    <svg viewBox={`0 0 ${w} ${h}`} className="h-11 w-full max-w-[260px]" data-testid="strength-history-chart">
      <polyline fill="none" stroke="#818cf8" strokeWidth="2" points={hist.map((x, i) => `${xs(i)},${ys(x.score)}`).join(" ")} />
      {hist.map((x, i) => <circle key={x.day} cx={xs(i)} cy={ys(x.score)} r="2.5" fill="#c7d2fe"><title>{`${x.day} : ${x.score}/100`}</title></circle>)}
    </svg>
  );
};

const Detail = ({ d, onClose }) => (
  <Dialog open={!!d} onOpenChange={(o) => !o && onClose()}>
    <DialogContent className="max-h-[85vh] overflow-y-auto border-white/10 bg-[#121520] text-slate-100 sm:max-w-lg" data-testid="strength-detail-dialog">
      {d && <><DialogHeader><DialogTitle>{d.title}</DialogTitle><DialogDescription className="text-slate-400">{d.sub}</DialogDescription></DialogHeader>
        {d.rule && <p className="rounded-lg border border-white/10 bg-white/5 p-2.5 text-xs text-slate-300">Règle : {d.rule}</p>}
        {d.items?.length ? <ul className="space-y-1 text-xs text-slate-300">{d.items.map((x, i) => <li key={i} className="border-t border-white/5 pt-1">{x}</li>)}</ul> : <p className="text-xs text-slate-500">Aucun élément détecté.</p>}</>}
    </DialogContent>
  </Dialog>
);

const Chips = ({ title, items, testid, onPick }) => (
  <div data-testid={testid}><p className="mb-1.5 text-[11px] uppercase tracking-wider text-slate-500">{title}</p>
    <div className="flex flex-wrap gap-1.5">{items.map((x, i) => <button key={x.name || x} type="button" onClick={() => onPick(x)} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-xs text-slate-200 transition-colors hover:border-indigo-400/50" data-testid={`${testid}-${i}`}>{x.name || x}{x.share != null ? ` · ${x.share} %` : x.score != null ? ` · ${x.score}` : ""}</button>)}</div></div>
);

// Indice de Force Professionnelle: profile-only score, each figure opens its explanation.
export const ProStrength = ({ refreshKey }) => {
  const [s, setS] = useState(null);
  const [d, setD] = useState(null);
  const [open, toggle] = usePersistedToggle("cos.strength.open", true);
  const load = () => careeros.strength().then(setS).catch(() => setS({ error: true }));
  useEffect(() => { load(); }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!s) return <Loader2 className="mt-4 h-4 w-4 animate-spin text-indigo-400" />;
  if (s.error) return null;
  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-black/20 p-4" data-testid="pro-strength">
      <Detail d={d} onClose={() => setD(null)} />
      <div className="flex items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 text-xs text-slate-300"><Gauge className="h-3.5 w-3.5 text-indigo-300" />Indice de Force Professionnelle</p>
        <button type="button" onClick={toggle} className="text-[11px] text-indigo-300 hover:text-white" data-testid="pro-strength-toggle">{open ? "Masquer" : "Afficher"}</button>
      </div>
      {open && <div className="mt-3 space-y-4">
        <div className="flex flex-wrap items-end gap-4">
          <button type="button" onClick={() => setD({ title: `Indice global : ${s.score}/100`, sub: s.note, items: s.criteria.map((c) => `${c.label} : ${c.score}/${c.max} — ${c.summary}`) })} className="text-left" data-testid="pro-strength-score">
            <span className="font-display text-5xl font-bold tabular-nums text-white">{s.score}</span><span className="text-sm text-slate-500">/100</span>
            <span className="ml-2 rounded-full bg-indigo-500/15 px-2 py-0.5 text-[11px] text-indigo-200" data-testid="pro-strength-level">{s.level}</span>
          </button>
          <div className="min-w-[200px] flex-1"><p className="text-[11px] text-slate-500">Évolution</p><Spark hist={s.history || []} /></div>
        </div>
        <div className="grid gap-2 sm:grid-cols-2">
          {s.criteria.map((c) => (
            <button key={c.key} type="button" onClick={() => setD({ title: `${c.label} : ${c.score}/${c.max}`, sub: c.summary, rule: c.rule, items: c.evidence })} className="rounded-xl border border-white/[0.07] p-2.5 text-left transition-colors hover:border-indigo-400/40" data-testid={`strength-crit-${c.key}`}>
              <div className="flex justify-between text-xs"><span className="text-slate-300">{c.label}</span><span className="font-mono text-white">{c.score}/{c.max}</span></div>
              <div className="mt-1.5 h-1.5 rounded-full bg-white/5"><div className={`h-1.5 rounded-full ${tone(c.score / c.max)} transition-[width] duration-700`} style={{ width: `${(c.score / c.max) * 100}%` }} /></div>
            </button>))}
        </div>
        <Chips title="Domaines les plus forts" items={s.domains} testid="strength-domains" onPick={(x) => setD({ title: x.name, sub: `${x.share} % du poids des domaines forts · ${x.mentions} mention(s) dans le profil`, items: x.skills })} />
        <Levers s={s} setD={setD} onChange={load} />
        <Chips title="Postes les plus compatibles" items={s.roles} testid="strength-roles" onPick={(x) => setD({ title: x, sub: "Déduit de vos domaines les plus forts et de votre niveau de leadership (et de vos postes visés).", items: s.domains.map((m) => `${m.name} : ${m.share} %`) })} />
        <Chips title="Secteurs où le profil est le plus compétitif" items={s.sectors} testid="strength-sectors" onPick={(x) => setD({ title: x.name, sub: `Indice relatif ${x.score}/100 (100 = secteur le plus favorable pour votre profil).`, items: s.domains.map((m) => `${m.name} : ${m.share} %`) })} />
        <p className="text-[11px] text-slate-500">{s.note}</p>
      </div>}
    </div>
  );
};
