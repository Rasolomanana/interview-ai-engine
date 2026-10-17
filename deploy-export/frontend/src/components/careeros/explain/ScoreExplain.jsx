import { useFullscreen } from "@/components/careeros/Fullscreen";
import { useEffect, useState } from "react";
import { Loader2, Sparkles, TriangleAlert } from "lucide-react";
import { toast } from "sonner";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { PriorityBadge } from "@/components/careeros/Ips";
import { radar } from "@/lib/careeros";
import { Criteria } from "./Criteria";
import { Requirements } from "./Requirements";

const GapToA = ({ ips }) => {
  if (ips.priority === "A") return <p className="text-xs text-emerald-300" data-testid="explain-gap">Priorité A atteinte (IPS ≥ 70 et objectifs ≥ 6/10).</p>;
  const items = [
    ips.knockout && `Exigence éliminatoire à lever : ${ips.knockout_detail || "voir ci-dessous"} (IPS plafonné à 40)`,
    ips.score < 70 && `+${70 - ips.score} point(s) d'IPS (actuel ${ips.score}, requis 70)`,
    ips.goal_fit < 6 && `Objectifs ${ips.goal_fit}/10 → 6/10 requis (titre plus proche de vos postes visés dans la Career Memory)`,
  ].filter(Boolean);
  return (
    <div className="rounded-xl border border-amber-400/20 bg-amber-500/5 p-3" data-testid="explain-gap">
      <p className="mb-1 text-xs font-semibold text-amber-200">Ce qu'il manque pour la priorité A</p>
      <ul className="list-inside list-disc space-y-0.5 text-xs text-slate-300">{items.map((x) => <li key={x}>{x}</li>)}</ul>
    </div>
  );
};

export const ScoreExplain = ({ id, onClose, onDeep }) => {
  const [o, setO] = useState(null);
  const [deep, setDeep] = useState(false);
  const [read, setRead] = useState(() => { try { return JSON.parse(localStorage.getItem("explainReading")) || { light: true, big: false }; } catch { return { light: true, big: false }; } });
  const setReading = (v) => { setRead(v); try { localStorage.setItem("explainReading", JSON.stringify(v)); } catch { /* ignore */ } };
  useEffect(() => { if (id) { setO(null); radar.explain(id).then(setO).catch((e) => toast.error(e.message)); } }, [id]);
  const runDeep = async () => {
    setDeep(true);
    try { setO(await radar.deep(o.id)); setO(await radar.explain(o.id)); onDeep?.(); toast.success("Analyse approfondie IA terminée"); } catch (e) { toast.error(e.message); } finally { setDeep(false); }
  };
  const ia = o?.method === "ia";
  const [full, fsButton] = useFullscreen("explain-fullscreen");
  return (
    <Sheet open={!!id} onOpenChange={(v) => !v && onClose()}>
      <SheetContent side="right" className={`w-full overflow-y-auto border-white/10 bg-[#121520] text-slate-100 ${full ? "sm:!max-w-none" : "sm:!max-w-2xl"} ${read.light ? "reading-light" : "reading-dark"}`} style={read.big ? { zoom: 1.15 } : undefined} data-testid="explain-panel">
        <SheetHeader><div className="flex flex-wrap items-center gap-3 pr-8"><SheetTitle className="text-left font-display text-white">Pourquoi ce score ?</SheetTitle>{fsButton}</div></SheetHeader>
        <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px]" data-testid="explain-reading">
          <span className="text-slate-500">Lecture :</span>
          {[[true, "Fond clair"], [false, "Fond sombre"]].map(([v, l]) => (
            <button key={l} type="button" onClick={() => setReading({ ...read, light: v })} className={`rounded-full border px-2.5 py-1 ${read.light === v ? "border-indigo-400 bg-indigo-500/15 font-semibold text-indigo-300" : "border-white/10 text-slate-400"}`} data-testid={`explain-reading-${v ? "light" : "dark"}`}>{l}</button>))}
          <button type="button" onClick={() => setReading({ ...read, big: !read.big })} className={`rounded-full border px-2.5 py-1 ${read.big ? "border-indigo-400 bg-indigo-500/15 font-semibold text-indigo-300" : "border-white/10 text-slate-400"}`} data-testid="explain-reading-big">A+ Texte agrandi</button>
        </div>
        {!o ? <Loader2 className="mx-auto mt-10 h-5 w-5 animate-spin text-slate-500" /> : (
          <div className="mt-4 space-y-5">
            <div className="flex items-start gap-3">
              <PriorityBadge priority={o.ips?.priority} testid="explain-priority" />
              <div className="min-w-0 flex-1"><p className="text-sm font-semibold text-white">{o.title}</p><p className="text-xs text-slate-500">{o.company} · {o.location} · {o.source}</p></div>
              <span className="font-mono text-sm text-white" data-testid="explain-ips">IPS {o.ips?.score}</span>
            </div>
            <p className={`rounded-xl border px-3 py-2 text-xs ${ia ? "border-indigo-400/30 bg-indigo-500/10 text-indigo-100" : "border-white/10 bg-white/5 text-slate-300"}`} data-testid="explain-method">
              {ia ? "Analyse approfondie IA : critères notés par l'IA à partir de l'offre complète et de votre CV ; IPS calculé par la formule officielle CareerOS."
                : "Analyse par règles (gratuite, sans IA) : comparaison automatique de votre Career Memory et du texte de l'offre. Les critères non vérifiables valent 5/10 (neutre)."}
              {o.excerpt && " Offre disponible en extrait seulement : plusieurs critères restent neutres."}</p>
            <GapToA ips={o.ips} />
            {o.ips?.knockout && <p className="flex items-start gap-2 rounded-xl border border-rose-400/30 bg-rose-500/10 p-3 text-xs text-rose-200" data-testid="explain-knockout"><TriangleAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />Éliminatoire : {o.ips.knockout_detail}</p>}
            <section><p className="mb-2 text-xs font-semibold text-slate-200">Critères, du plus pénalisant au moins pénalisant <span className="font-normal text-slate-500">(points sur 100)</span></p><Criteria ips={o.ips} /></section>
            <Requirements items={o.requirements_ai} title="Exigences de l'offre" badge="border-indigo-400/30 text-indigo-200" testid="explain-req-ai" />
            <Requirements items={o.requirements_rules} title={o.requirements_ai?.length ? "Exigences détectées par règles" : "Exigences de l'offre"} badge="border-white/10 text-slate-400" testid="explain-req-rules" />
            <p className="text-[11px] text-slate-500">✓ couvert par votre Career Memory · ✗ absent du CV · ? à vérifier (non mentionné). Comparaison LinkedIn : LinkedIn vérifie surtout les qualifications ; l'IPS mesure en plus la concurrence, la fraîcheur, la qualité du CV et vos objectifs.</p>
            {!ia && <button type="button" onClick={runDeep} disabled={deep} className="flex items-center gap-1.5 rounded-full bg-indigo-500 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-60" data-testid="explain-deep-btn">
              {deep ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}Lancer l'analyse approfondie IA</button>}
          </div>)}
      </SheetContent>
    </Sheet>
  );
};
