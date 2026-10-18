import { useEffect, useState } from "react";
import { Download, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { skillMatch } from "@/lib/careeros";

// Prefill the copilot context from Career Memory, a pack or a Radar offer (no retyping).
export const CopilotImport = ({ onImport }) => {
  const [open, setOpen] = useState(false);
  const [src, setSrc] = useState(null);
  const [busy, setBusy] = useState("");
  useEffect(() => { if (open && !src) skillMatch.sources().then(setSrc).catch(() => setSrc({ radar: [], packs: [] })); }, [open, src]);
  const pick = async (kind, id = "") => {
    setBusy(kind + id);
    try { onImport(await skillMatch.copilot(kind, id)); toast.success("Contexte importé depuis CareerOS"); setOpen(false); } catch (e) { toast.error(e.message); } finally { setBusy(""); }
  };
  const Chip = ({ kind, x }) => (
    <button type="button" onClick={() => pick(kind, x.id)} disabled={!!busy} className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-left text-xs text-slate-200 hover:border-indigo-400/50" data-testid={`ctx-import-${kind}-${x.id}`}>
      {busy === kind + x.id ? <Loader2 className="mr-1 inline h-3 w-3 animate-spin" /> : null}{x.priority ? <b className="mr-1 text-indigo-300">{x.priority}</b> : null}{x.title}{x.company ? ` · ${x.company}` : ""}
    </button>);
  return (
    <div className="rounded-xl border border-indigo-400/30 bg-indigo-500/5 p-3" data-testid="ctx-import">
      <div className="flex flex-wrap items-center gap-2">
        <button type="button" onClick={() => setOpen((v) => !v)} className="flex items-center gap-1.5 rounded-full bg-indigo-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-400" data-testid="ctx-import-btn"><Download className="h-3.5 w-3.5" />Importer depuis un pack / le Radar</button>
        <button type="button" onClick={() => pick("memoire")} disabled={!!busy} className="rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:text-white" data-testid="ctx-import-memoire">CV maître (Career Memory)</button>
      </div>
      {open && (!src ? <Loader2 className="mt-2 h-4 w-4 animate-spin text-indigo-400" /> : (
        <div className="mt-2 space-y-2">
          <div><p className="mb-1 text-[11px] text-slate-500">Packs ({src.packs.length})</p><div className="flex max-h-28 flex-wrap gap-1.5 overflow-y-auto">{src.packs.map((x) => <Chip key={x.id} kind="pack" x={x} />)}</div></div>
          <div><p className="mb-1 text-[11px] text-slate-500">Offres du Radar A/B ({src.radar.length})</p><div className="flex max-h-28 flex-wrap gap-1.5 overflow-y-auto">{src.radar.map((x) => <Chip key={x.id} kind="radar" x={x} />)}</div></div>
        </div>))}
    </div>
  );
};
