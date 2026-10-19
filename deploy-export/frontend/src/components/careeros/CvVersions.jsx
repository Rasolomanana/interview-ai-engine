import { useEffect, useState } from "react";
import { History, RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { cvOptimize } from "@/lib/careeros";
import { CvDiff } from "@/components/careeros/optimize/CvDiff";

const fr = (n) => (n == null ? "—" : String(n).replace(".", ","));
const rows = (a, b) => { const prev = a.split("\n"), set = new Set(prev); return b.split("\n").map((t, i) => (set.has(t) ? { tag: "same", text: t } : prev.length === b.split("\n").length ? { tag: "improved", text: t, prev: prev[i] } : { tag: "added", text: t })); };

// Master CV versions: date, offer, estimated vs real gain, differences, restore.
export const CvVersions = ({ onRestored }) => {
  const [items, setItems] = useState(null);
  const [view, setView] = useState(null);
  const load = () => cvOptimize.versions().then((r) => setItems(r.items)).catch(() => setItems([]));
  useEffect(() => { load(); const h = () => load(); window.addEventListener("careeros:cv-updated", h); return () => window.removeEventListener("careeros:cv-updated", h); }, []);
  const restore = async (v) => {
    if (!window.confirm("Remettre le CV maître tel qu'il était avant cette version ? Le CV actuel restera dans l'historique.")) return;
    try { await cvOptimize.restore(v.id); toast.success("Ancienne version restaurée."); load(); onRestored?.(); } catch (e) { toast.error(e.message); }
  };
  if (!items?.length) return null;
  return (
    <section className="mt-4 rounded-2xl border border-white/[0.07] p-4" data-testid="cv-versions">
      <p className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-white"><History className="h-4 w-4 text-indigo-300" />Historique des versions du CV maître</p>
      <ul className="space-y-1.5">{items.map((v, i) => (
        <li key={v.id} className="rounded-xl border border-white/[0.07] p-2.5 text-xs" data-testid={`cv-version-${i}`}>
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-slate-300">{new Date(v.at).toLocaleString("fr-CA", { dateStyle: "medium", timeStyle: "short" })}</span>
            <span className="text-slate-500">{v.kind === "restauration" ? "Restauration" : `Optimisation · ${v.offer?.title || "offre"}${v.offer?.company ? ` · ${v.offer.company}` : ""}`}</span>
            <span className="ml-auto flex gap-2">
              <button type="button" onClick={() => setView(view === v.id ? null : v.id)} className="text-indigo-300 hover:text-white" data-testid={`cv-version-diff-${i}`}>Différences</button>
              <button type="button" onClick={() => restore(v)} className="flex items-center gap-1 text-indigo-300 hover:text-white" data-testid={`cv-version-restore-${i}`}><RotateCcw className="h-3 w-3" />Restaurer l'avant</button></span>
          </div>
          {v.kind !== "restauration" && <p className="mt-1 text-[11px] text-slate-400" data-testid={`cv-version-gains-${i}`}>
            Estimé : compatibilité {fr(v.estimated?.match_before)} % → {fr(v.estimated?.match_after)} %, indice {fr(v.estimated?.ifp_before)} → {fr(v.estimated?.ifp_after)} ·
            Réel : compatibilité {fr(v.real?.match_after)} %, indice {fr(v.real?.ifp_before)} → {fr(v.real?.ifp_after)}</p>}
          {view === v.id && <div className="mt-2"><CvDiff cv={v.cv_before} rows={v.diff?.length ? v.diff : rows(v.cv_before, v.cv_after)} /></div>}
        </li>))}</ul>
    </section>
  );
};
