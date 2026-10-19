import { useEffect, useState } from "react";
import { CheckCircle2, Loader2, Sparkles } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { careeros, cvOptimize, skillMatch } from "@/lib/careeros";
import { compareSkills } from "@/lib/skillMatch";
import { buildCv, coveredBy, diffRows, jobPayload, keySkillsItem, matchOf, toConfirm } from "@/lib/cvOptimize";
import { useFullscreen } from "@/components/careeros/Fullscreen";
import { ImpactPanel } from "@/components/careeros/optimize/ImpactPanel";
import { ProposalList } from "@/components/careeros/optimize/ProposalList";
import { CvDiff } from "@/components/careeros/optimize/CvDiff";
import { ApplyBar, RealResult } from "@/components/careeros/optimize/ApplyBar";
import { useImpact } from "@/components/careeros/optimize/useImpact";

const load = async (offer) => {
  const profile = await careeros.getProfile();
  const src = offer.text ? offer : { ...offer, ...(await skillMatch.source(offer.kind, offer.id)) };
  const r = compareSkills(profile, src.text, src.title);
  const res = await cvOptimize.propose({ title: src.title || "", offer_text: src.text.slice(0, 30000), skills: jobPayload(r) });
  const items = [keySkillsItem(r, res.cv_text), ...res.items, ...toConfirm(r, profile, coveredBy(res.items))].filter(Boolean);
  return { profile, src, cv: res.cv_text, items, rejected: res.rejected, ai: res.ai };
};

// Same optimisation screen everywhere (Radar card, pack, CV <-> job comparison). Nothing is saved without explicit validation.
export const CvOptimizer = ({ offer, open, onClose }) => {
  const [d, setD] = useState(null);
  const [sel, setSel] = useState(new Set());
  const [tab, setTab] = useState("props");
  const [done, setDone] = useState(null);
  const [full, fsButton] = useFullscreen("cv-optimizer-fullscreen");
  useEffect(() => {
    if (!open) return;
    setD(null); setDone(null); setTab("props");
    load(offer).then((x) => { setD(x); setSel(new Set(x.items.filter((i) => i.type !== "a_confirmer").map((i) => i.id))); })
      .catch((e) => { toast.error(e.message); onClose(); });
  }, [open]); // eslint-disable-line react-hooks/exhaustive-deps
  const sim = useImpact(d?.profile, d?.src, d?.cv, d?.items, sel);
  const toggle = (id) => setSel((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });
  const setAll = (on) => setSel((s) => { const n = new Set([...s].filter((id) => id.startsWith("c:"))); if (on) d.items.filter((x) => x.type !== "a_confirmer").forEach((x) => n.add(x.id)); return n; });
  const apply = async () => {
    const cv = buildCv(d.cv, d.items, sel);
    const v = await cvOptimize.apply({ cv_text: cv, offer: { title: d.src.title, company: d.src.company, kind: offer.kind || "texte", id: offer.id || "" }, accepted: [...sel], diff: diffRows(d.cv, d.items, sel),
      estimated: { match_before: sim?.match.before, match_after: sim?.match.after, match_potential: sim?.match.potential, ifp_before: sim?.ifp.before, ifp_after: sim?.ifp.after } });
    const p2 = await careeros.getProfile();
    const realMatch = matchOf(p2, p2.cv_text || "", d.src);
    await cvOptimize.real(v.id, realMatch).catch(() => {});
    careeros.strength().catch(() => {});
    window.dispatchEvent(new Event("careeros:journey"));
    window.dispatchEvent(new Event("careeros:cv-updated"));
    setDone({ match_before: sim?.match.before, match_after: realMatch, ifp_before: v.real.ifp_before, ifp_after: v.real.ifp_after });
    toast.success("CV maître mis à jour. L'ancienne version reste disponible dans l'historique de la Career Memory.");
  };
  return (
    <Dialog open={open} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className={`overflow-y-auto border-white/10 bg-[#121520] text-slate-100 ${full ? "h-screen max-h-screen w-screen max-w-none rounded-none sm:rounded-none" : "max-h-[92vh] w-[96vw] max-w-6xl"}`} data-testid="cv-optimizer-dialog">
        <DialogHeader><div className="flex flex-wrap items-center gap-3 pr-8"><DialogTitle className="flex items-center gap-2"><Sparkles className="h-5 w-5 text-amber-300" />Optimiser mon CV pour cette offre</DialogTitle>{fsButton}</div>
          <DialogDescription className="text-slate-400">{offer.title}{offer.company ? ` · ${offer.company}` : ""} — CareerOS reformule uniquement ce qui est déjà dans votre CV. Rien n'est modifié avant votre validation.</DialogDescription></DialogHeader>
        {!d ? <p className="flex items-center gap-2 text-sm text-slate-400" data-testid="cv-optimizer-loading"><Loader2 className="h-4 w-4 animate-spin text-indigo-400" />Analyse de votre CV et de l'offre (30 secondes environ)…</p>
          : done ? <RealResult done={done} onClose={onClose} />
          : <div className="space-y-4">
            <ImpactPanel sim={sim} />
            <div className="flex gap-1.5">{[["props", "Modifications proposées"], ["diff", "Comparer CV actuel | CV optimisé"]].map(([k, l]) => (
              <button key={k} type="button" onClick={() => setTab(k)} className={`rounded-full px-3 py-1 text-xs ${tab === k ? "bg-indigo-500 text-white" : "border border-white/10 text-slate-300"}`} data-testid={`cv-optimizer-tab-${k}`}>{l}</button>))}</div>
            {tab === "props" ? <ProposalList items={d.items} sel={sel} toggle={toggle} setAll={setAll} rejected={d.rejected} ai={d.ai} /> : <CvDiff cv={d.cv} rows={diffRows(d.cv, d.items, sel)} />}
            <ApplyBar count={sel.size} sim={sim} onApply={apply} />
          </div>}
        {done && <p className="flex items-center gap-1.5 text-[11px] text-emerald-300"><CheckCircle2 className="h-3.5 w-3.5" />Version enregistrée.</p>}
      </DialogContent>
    </Dialog>
  );
};
