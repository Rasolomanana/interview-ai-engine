import { useState } from "react";
import { Check, Flag, TrendingUp } from "lucide-react";
import { toast } from "sonner";
import { careeros } from "@/lib/careeros";

const ROI = { Excellent: "text-emerald-300 border-emerald-400/30", "Très bon": "text-emerald-200 border-emerald-400/20", Bon: "text-indigo-200 border-indigo-400/30", Modéré: "text-slate-300 border-white/15" };
const fmt = (g) => `+${String(g).replace(".", ",")} pt${g >= 2 ? "s" : ""}`;

const Lever = ({ it, rank, onOpen, onFollow }) => (
  <li className="rounded-xl border border-white/[0.07] p-3" data-testid={`lever-${it.id}`}>
    <div className="flex flex-wrap items-start gap-2">
      {rank && <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-indigo-500/20 text-[11px] font-bold text-indigo-200">{rank}</span>}
      <button type="button" onClick={() => onOpen(it)} className="min-w-0 flex-1 text-left text-sm text-slate-100 hover:text-white" data-testid={`lever-open-${it.id}`}>{it.title}</button>
      <span className="font-mono text-sm font-bold text-emerald-300" data-testid={`lever-gain-${it.id}`}>{fmt(it.gain)}</span>
    </div>
    <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
      <span className="rounded-full border border-white/10 px-2 py-0.5 text-slate-300">Difficulté : {it.difficulty}</span>
      <span className="rounded-full border border-white/10 px-2 py-0.5 text-slate-300">Effort : {it.effort}</span>
      <span className={`rounded-full border px-2 py-0.5 ${ROI[it.roi]}`} data-testid={`lever-roi-${it.id}`}>Retour sur effort : {it.roi}</span>
      <button type="button" onClick={() => onFollow(it)} className={`ml-auto flex items-center gap-1 rounded-full border px-2 py-0.5 ${it.followed ? "border-emerald-400/40 text-emerald-200" : "border-white/10 text-slate-400 hover:text-white"}`} data-testid={`lever-follow-${it.id}`}>
        {it.followed ? <Check className="h-3 w-3" /> : <Flag className="h-3 w-3" />}{it.followed ? "Je m'y mets" : "Suivre ce levier"}</button>
    </div>
  </li>
);

// « Comment gagner des points ? » : rule-based levers sorted by simulated gain, milestones 85 / 90 / 95.
export const Levers = ({ s, setD, onChange }) => {
  const [busy, setBusy] = useState("");
  const lv = s.levers;
  if (!lv || !lv.items.length) return <p className="text-xs text-slate-500" data-testid="levers-empty">Aucun levier simple détecté : votre profil est déjà très complet.</p>;
  const by = Object.fromEntries(lv.items.map((x) => [x.id, x]));
  const open = (it) => setD({ title: `${it.title} · ${fmt(it.gain)}`, sub: it.why, rule: `Gain estimé en recalculant l'indice avec cette action. Effet : ${it.impact.join(" ; ").replace(/(\d)\.(\d)/g, "$1,$2") || "—"}. Difficulté ${it.difficulty}, effort ${it.effort}, retour sur effort ${it.roi}.`,
    items: [...it.evidence.map((e) => `Preuve : ${e}`), "N'ajoutez que ce que vous avez réellement vécu ou obtenu."] });
  const follow = async (it) => {
    if (busy) return;
    setBusy(it.id);
    try { const r = await careeros.followLever(it.id); toast.success(r.followed ? "Levier suivi : CareerOS mesurera son effet sur votre indice." : "Levier retiré."); onChange(); } catch (e) { toast.error(e.message); } finally { setBusy(""); }
  };
  return (
    <div className="space-y-3" data-testid="strength-levers">
      <p className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-slate-500"><TrendingUp className="h-3.5 w-3.5 text-emerald-400" />Comment gagner des points ?</p>
      <p className="text-xs text-slate-400">Indice actuel : <b className="text-white">{s.score}/100</b> · Niveau : {s.level}. Les 3 leviers les plus impactants :</p>
      <ol className="space-y-2">{lv.top3.map((id, i) => <Lever key={id} it={by[id]} rank={i + 1} onOpen={open} onFollow={follow} />)}</ol>
      {lv.milestones.map((m) => (
        <div key={m.target} className="rounded-xl bg-white/[0.02] p-2.5" data-testid={`milestone-${m.target}`}>
          <p className="text-xs font-semibold text-slate-200">Pour atteindre {m.target} {m.reachable ? "" : <span className="font-normal text-slate-500">(atteignable jusqu'à {String(m.reach).replace(".", ",")} avec ces leviers)</span>}</p>
          <ul className="mt-1 space-y-0.5 text-xs">{m.levers.map((id) => <li key={id}><button type="button" onClick={() => open(by[id])} className="text-left text-slate-300 hover:text-white" data-testid={`milestone-${m.target}-${id}`}><span className="font-mono text-emerald-300">{fmt(by[id].gain)}</span> : {by[id].title}</button></li>)}
            {!m.levers.length && <li className="text-slate-500">Déjà couvert par les leviers précédents.</li>}</ul>
        </div>))}
      {lv.items.length > 3 && <details className="text-xs text-slate-400"><summary className="cursor-pointer" data-testid="levers-more">Autres leviers ({lv.items.length - 3})</summary>
        <ul className="mt-2 space-y-2">{lv.items.slice(3).map((it) => <Lever key={it.id} it={it} onOpen={open} onFollow={follow} />)}</ul></details>}
    </div>
  );
};
