import { useEffect, useRef, useState } from "react";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { CheckCircle2, Link2, Loader2, Search, TriangleAlert } from "lucide-react";
import { radar } from "@/lib/careeros";

const inputCls = "w-full rounded-lg border border-white/10 bg-black/40 px-2.5 py-1.5 text-xs text-white outline-none focus:border-indigo-400/60";
const ORIGIN = { annuaire: "annuaire", site: "site carrières", devinette: "détection automatique" };

export const discoverFor = (c) => radar.discoverPortal({ name: c.name, website: c.website || "" });

const useMobile = () => {
  const [m, setM] = useState(() => window.matchMedia("(max-width: 639px)").matches);
  useEffect(() => {
    const q = window.matchMedia("(max-width: 639px)");
    const f = (e) => setM(e.matches);
    q.addEventListener("change", f);
    return () => q.removeEventListener("change", f);
  }, []);
  return m;
};

export const PortalSuggest = (props) => {
  const mobile = useMobile();
  if (!mobile) return <SuggestBox {...props} />;
  return (
    <Sheet open onOpenChange={(o) => !o && props.onClose()}>
      <SheetContent side="bottom" className="max-h-[85vh] overflow-y-auto rounded-t-2xl border-white/10 bg-[#121520] text-slate-100" data-testid={`portal-sheet-${props.i}`}>
        <SheetHeader className="mb-3 text-left"><SheetTitle className="text-white">Portail de {props.c.name}</SheetTitle>
          <SheetDescription className="text-xs text-slate-400">Choisissez le portail à associer. Rien n'est associé sans votre clic.</SheetDescription></SheetHeader>
        <SuggestBox {...props} />
      </SheetContent>
    </Sheet>
  );
};

const SuggestBox = ({ c, i, result, onResult, onPick, onClose, auto }) => {
  const [busy, setBusy] = useState(false);
  const [site, setSite] = useState(c.website || "");
  const box = useRef(null);
  const run = async () => {
    setBusy(true);
    try { onResult(await radar.discoverPortal({ name: c.name, website: site })); } catch (e) { onResult({ candidates: [], message: e.message }); } finally { setBusy(false); }
  };
  useEffect(() => { if (auto) run(); }, []); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { box.current?.scrollIntoView({ block: "nearest", behavior: "smooth" }); }, [busy, result]);
  return (
    <div ref={box} className="space-y-2 rounded-xl border border-indigo-400/20 bg-indigo-500/5 p-2.5" data-testid={`portal-suggest-${i}`}>
      <div className="flex gap-2">
        <input value={site} onChange={(e) => setSite(e.target.value)} placeholder="Site web de l'entreprise (facultatif, ex. desjardins.com)" className={inputCls} data-testid={`portal-website-${i}`} />
        <button type="button" onClick={run} disabled={busy} className="flex shrink-0 items-center gap-1 rounded-lg bg-indigo-500 px-2.5 text-[11px] font-semibold text-white disabled:opacity-60" data-testid={`portal-discover-run-${i}`}>
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Search className="h-3.5 w-3.5" />}{result ? "Relancer" : "Chercher"}</button>
        <button type="button" onClick={onClose} className="shrink-0 text-[11px] text-slate-500 hover:text-white">Fermer</button>
      </div>
      {busy && <p className="text-[11px] text-slate-400">Recherche du portail (annuaire, site carrières, portails publics)… jusqu'à 30 secondes.</p>}
      {result && !busy && <>
        {(result.candidates || []).length > 0 && <p className="text-[11px] text-slate-400" data-testid={`portal-count-${i}`}>{result.candidates.length} proposition(s) · {result.candidates.filter((p) => p.ok).length} lisible(s)</p>}
        <div className="max-h-64 space-y-1.5 overflow-y-auto pr-1" data-testid={`portal-results-${i}`}>
        {(result.candidates || []).map((p, k) => (
          <div key={`${p.kind}-${p.slug}`} className="flex flex-wrap items-center gap-2 rounded-lg border border-white/[0.06] bg-black/20 p-2 text-[11px] sm:flex-nowrap" data-testid={`portal-candidate-${i}-${p.kind}${k ? `-${k}` : ""}`}>
            {p.ok ? <CheckCircle2 className="h-3.5 w-3.5 shrink-0 text-emerald-400" /> : <TriangleAlert className="h-3.5 w-3.5 shrink-0 text-amber-400" />}
            <span className="min-w-0 flex-1"><b className="text-slate-100">{p.kind_label}</b> <span className="text-slate-500">· {ORIGIN[p.origin]}</span>
              <span className="block text-slate-400">{p.ok ? `${p.count} offre(s) visibles` : p.message}</span>
              <span className="block break-all text-slate-500">{p.portal_url}</span></span>
            {p.ok && <button type="button" onClick={() => onPick({ portal_url: p.portal_url, kind: p.kind, slug: p.slug, website: site })} className="flex shrink-0 items-center gap-1 rounded-full border border-emerald-400/40 px-2.5 py-1 text-emerald-300 hover:bg-emerald-500/10" data-testid={`portal-associate-${i}-${p.kind}${k ? `-${k}` : ""}`}><Link2 className="h-3 w-3" />Associer</button>}
          </div>))}
        </div>
        {result.message && <p className="flex items-center gap-1.5 text-[11px] text-amber-300" data-testid={`portal-message-${i}`}><TriangleAlert className="h-3.5 w-3.5" />{result.message}</p>}
      </>}
    </div>
  );
};
