import { useEffect, useState } from "react";
import { ArrowRight, GitCompareArrows, History, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { careeros, skillMatch } from "@/lib/careeros";
import { compareSkills } from "@/lib/skillMatch";
import { SkillMap } from "@/components/careeros/SkillMap";
import { JobMap } from "@/components/careeros/JobMap";

const TABS = [["radar", "Offre du Radar"], ["pack", "Pack existant"], ["texte", "Texte collé"], ["hist", "Historique"]];
const FIELDS = [["offre", "Offre d'emploi"], ["description", "Description du poste"], ["linkedin", "Profil LinkedIn du recruteur"]];
const area = "w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-xs text-white outline-none focus:border-indigo-400/60";

const Picker = ({ tab, src, onPick, texts, setTexts, onText, hist, onHist }) => {
  if (tab === "texte") return (
    <div className="grid gap-2 md:grid-cols-3">
      {FIELDS.map(([k, l]) => <label key={k} className="text-[11px] text-slate-400">{l}<textarea rows={5} value={texts[k] || ""} onChange={(e) => setTexts({ ...texts, [k]: e.target.value })} className={`${area} mt-1`} data-testid={`compare-text-${k}`} /></label>)}
      <button type="button" onClick={onText} disabled={!Object.values(texts).join("").trim()} className="rounded-full bg-indigo-500 px-4 py-2 text-xs font-semibold text-white disabled:opacity-40 md:col-span-3 md:justify-self-start" data-testid="compare-text-btn">Comparer</button>
    </div>);
  const items = tab === "hist" ? hist : src?.[tab === "radar" ? "radar" : "packs"];
  if (!items) return <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />;
  if (!items.length) return <p className="text-xs text-slate-500" data-testid="compare-empty">Aucun élément disponible.</p>;
  return (
    <div className="flex max-h-40 flex-wrap gap-1.5 overflow-y-auto">
      {items.map((x) => (
        <button key={x.id} type="button" onClick={() => (tab === "hist" ? onHist(x) : onPick(tab, x))} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-left text-xs text-slate-200 hover:border-indigo-400/50" data-testid={`compare-pick-${x.id}`}>
          {x.priority ? <b className="mr-1 text-indigo-300">{x.priority}</b> : null}{x.title}{x.company ? ` · ${x.company}` : ""}{tab === "hist" ? ` · ${x.score} % · ${new Date(x.at).toLocaleDateString("fr-CA")}` : ""}
        </button>))}
    </div>);
};

const Center = ({ r }) => (
  <div className="space-y-3" data-testid="compare-center">
    <div className="rounded-2xl border border-indigo-400/30 bg-indigo-500/10 p-4 text-center">
      <p className="text-[11px] uppercase tracking-wider text-indigo-200">Score de concordance</p>
      <p className="font-display text-5xl font-bold tabular-nums text-white" data-testid="compare-score">{r.score} %</p>
      <p className="text-[11px] text-slate-400" data-testid="compare-counts">{r.counts.ok} couverte(s) · {r.counts.partiel} partielle(s) · {r.counts.manquant} manquante(s) · {r.counts.required} requise(s)</p>
    </div>
    <div><p className="mb-1 text-[11px] uppercase tracking-wider text-slate-500">Compétences manquantes (par importance)</p>
      {r.gaps.length ? <ul className="space-y-1">{r.gaps.slice(0, 8).map((g, i) => (
        <li key={g.label} className="text-xs" data-testid={`compare-gap-${i}`}><div className="flex items-center gap-2"><span className="min-w-0 flex-1 text-slate-200">{g.label}{g.required ? "" : " (souhaitée)"}</span>
          <span className="h-1.5 w-20 overflow-hidden rounded bg-white/10"><span className={`block h-full ${g.status === "partiel" ? "bg-amber-400" : "bg-rose-400"}`} style={{ width: `${Math.min(100, (g.weight / r.gaps[0].weight) * 100)}%` }} /></span></div></li>))}</ul>
        : <p className="text-xs text-emerald-300">Toutes les compétences reconnues sont couvertes.</p>}</div>
    {r.recos.length > 0 && <div><p className="mb-1 text-[11px] uppercase tracking-wider text-slate-500">Recommandations</p>
      <ul className="space-y-1.5">{r.recos.map((x, i) => (
        <li key={i} className="rounded-lg border border-white/[0.07] p-2 text-xs" data-testid={`compare-reco-${i}`}><p className="text-slate-100">{x.title}</p><p className="text-[11px] text-slate-500">{x.why}</p>
          {x.lever && <p className="mt-0.5 text-[11px] text-emerald-300" data-testid={`compare-reco-lever-${i}`}>Lié au levier « {x.lever.title} » : +{String(x.lever.gain).replace(".", ",")} pt(s) sur votre Indice de Force Professionnelle</p>}</li>))}</ul></div>}
    {r.common.length > 0 && <p className="text-[11px] text-slate-400" data-testid="compare-common"><ArrowRight className="mr-1 inline h-3 w-3 text-indigo-300" />Domaines communs : {r.common.join(" · ")}</p>}
    <p className="rounded-xl bg-white/[0.04] p-2.5 text-xs font-medium text-slate-100" data-testid="compare-verdict">Constat : {r.verdict}</p>
  </div>
);

// Enlarged view: real CV skill map (unchanged) | score & gaps | required-skills map of the job.
export const SkillCompare = ({ profile }) => {
  const [open, setOpen] = useState(false);
  const [tab, setTab] = useState("radar");
  const [src, setSrc] = useState(null);
  const [hist, setHist] = useState(null);
  const [texts, setTexts] = useState({});
  const [res, setRes] = useState(null);
  const [busy, setBusy] = useState(false);
  const [levers, setLevers] = useState([]);
  useEffect(() => {
    if (!open) return;
    skillMatch.sources().then(setSrc).catch(() => setSrc({ radar: [], packs: [] }));
    skillMatch.history().then(setHist).catch(() => setHist([]));
    careeros.strength().then((s) => setLevers(s.levers?.items || [])).catch(() => {});
  }, [open]);
  const run = async (meta, text) => {
    const r = compareSkills(profile, text, meta.title, levers);
    setRes({ ...meta, r });
    try { await skillMatch.save({ ...meta, score: r.score, result: r }); skillMatch.history().then(setHist); } catch (e) { toast.error(e.message); }
  };
  const onPick = async (kind, x) => {
    setBusy(true);
    try { const s = await skillMatch.source(kind, x.id); await run({ title: s.title, company: s.company, source_kind: kind, source_id: x.id }, s.text); } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  const onText = () => run({ title: (texts.offre || texts.description || "").split("\n")[0].slice(0, 120) || "Texte collé", company: "", source_kind: "texte", texts }, Object.values(texts).join("\n"));
  const onHist = async (x) => { try { const h = await skillMatch.get(x.id); setRes({ title: h.title, company: h.company, at: h.at, r: h.result }); } catch (e) { toast.error(e.message); } };
  return (
    <>
      <button type="button" onClick={() => setOpen(true)} className="group mt-3 flex w-full items-center gap-3 rounded-2xl border border-dashed border-indigo-400/40 bg-indigo-500/5 p-4 text-left transition-colors hover:bg-indigo-500/10" data-testid="skill-compare-open">
        <GitCompareArrows className="h-5 w-5 shrink-0 text-indigo-300 transition-transform group-hover:scale-110" />
        <span><span className="block text-sm font-semibold text-white">Comparer ma carte avec une fiche emploi</span>
          <span className="text-[11px] text-slate-400">Compétences réelles (CV) vs compétences requises : score de concordance, compétences manquantes et recommandations.</span></span>
      </button>
      <Dialog open={open} onOpenChange={setOpen}>
        <DialogContent className="max-h-[92vh] w-[96vw] max-w-7xl overflow-y-auto border-white/10 bg-[#0d1018] text-slate-100" data-testid="skill-compare-dialog">
          <DialogHeader><DialogTitle>Carte des compétences réelles vs compétences requises</DialogTitle>
            <DialogDescription className="text-slate-400">Comparaison par règles CareerOS, gratuite et instantanée. Chaque comparaison est enregistrée dans l'historique.</DialogDescription></DialogHeader>
          <div className="flex flex-wrap gap-1.5">{TABS.map(([k, l]) => <button key={k} type="button" onClick={() => setTab(k)} className={`flex items-center gap-1 rounded-full px-3 py-1 text-xs ${tab === k ? "bg-indigo-500 text-white" : "border border-white/10 text-slate-300"}`} data-testid={`compare-tab-${k}`}>{k === "hist" && <History className="h-3 w-3" />}{l}</button>)}</div>
          <Picker tab={tab} src={src} onPick={onPick} texts={texts} setTexts={setTexts} onText={onText} hist={hist} onHist={onHist} />
          {busy && <Loader2 className="h-4 w-4 animate-spin text-indigo-400" />}
          {res && (
            <div className="grid gap-4 lg:grid-cols-[1fr_320px_1fr]" data-testid="compare-result">
              <section className="min-w-0 rounded-2xl border border-sky-400/20 p-3"><p className="text-xs font-semibold uppercase tracking-wider text-sky-300">Carte des compétences réelles (du CV)</p><SkillMap profile={profile} /></section>
              <Center r={res.r} />
              <section className="min-w-0 rounded-2xl border border-orange-400/25 p-3"><p className="text-xs font-semibold uppercase tracking-wider text-orange-300">Carte des compétences requises</p>
                <p className="mb-1 text-sm font-semibold text-white" data-testid="compare-job-title">{res.title}{res.company ? ` · ${res.company}` : ""}</p>
                <JobMap domains={res.r.domains} common={res.r.common} /></section>
            </div>)}
        </DialogContent>
      </Dialog>
    </>
  );
};
