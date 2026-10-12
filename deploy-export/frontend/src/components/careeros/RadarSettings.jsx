import { useEffect, useState } from "react";
import { Loader2, Plus, Trash2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { radar } from "@/lib/careeros";

const inputCls = "w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/60";
const csv = (a) => (a || []).join(", ");
const list = (v) => v.split(",").map((x) => x.trim()).filter(Boolean);

export const RadarSettingsDialog = ({ onClose }) => {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  useEffect(() => { radar.settings().then(setS).catch((e) => toast.error(e.message)); }, []);
  const save = async () => {
    setBusy(true);
    try {
      const { enabled, keywords, location, companies, boards, sources } = s;
      await radar.saveSettings({ enabled, keywords, location, companies, boards, sources });
      toast.success("Réglages Radar enregistrés"); onClose();
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  const toggleSrc = (k) => setS({ ...s, sources: s.sources.includes(k) ? s.sources.filter((x) => x !== k) : [...s.sources, k] });
  const setBoard = (i, k, v) => setS({ ...s, boards: s.boards.map((b, j) => (j === i ? { ...b, [k]: v } : b)) });
  return (
    <Dialog open onOpenChange={onClose}>
      <DialogContent className="max-h-[85vh] overflow-y-auto border-white/10 bg-[#121520] text-slate-100 sm:max-w-xl" data-testid="radar-settings-dialog">
        <DialogHeader><DialogTitle className="font-display">Réglages du Radar</DialogTitle>
          <DialogDescription className="text-xs text-slate-400">Sources officielles uniquement. Recherche quotidienne + à la demande.</DialogDescription></DialogHeader>
        {!s ? <Loader2 className="h-5 w-5 animate-spin text-indigo-400" /> : (
          <div className="space-y-4 text-xs">
            <label className="flex items-center gap-2 text-slate-300"><input type="checkbox" className="accent-indigo-500" checked={s.enabled} onChange={(e) => setS({ ...s, enabled: e.target.checked })} data-testid="radar-enabled-checkbox" />Recherche quotidienne automatique</label>
            <label className="block text-slate-400">Mots-clés / postes visés (virgules)<input defaultValue={csv(s.keywords)} onBlur={(e) => setS({ ...s, keywords: list(e.target.value) })} className={`${inputCls} mt-1`} data-testid="radar-keywords-input" /></label>
            <label className="block text-slate-400">Localisation<input value={s.location} onChange={(e) => setS({ ...s, location: e.target.value })} className={`${inputCls} mt-1`} data-testid="radar-location-input" /></label>
            <label className="block text-slate-400">Entreprises suivies (recherche ciblée Adzuna / Jooble)<input defaultValue={csv(s.companies)} onBlur={(e) => setS({ ...s, companies: list(e.target.value) })} className={`${inputCls} mt-1`} data-testid="radar-companies-input" /></label>
            <div className="flex flex-wrap gap-2" data-testid="radar-sources">
              {[["adzuna", "Adzuna"], ["jooble", "Jooble"], ["boards", "Sites carrières"]].map(([k, l]) => (
                <button key={k} type="button" onClick={() => toggleSrc(k)} data-testid={`radar-source-${k}`}
                  className={`rounded-full border px-3 py-1.5 ${s.sources.includes(k) ? "border-indigo-400/60 bg-indigo-500/15 text-white" : "border-white/10 text-slate-400"}`}>
                  {l}{k !== "boards" && !s.configured?.[k] ? " · clé manquante" : ""}</button>))}
            </div>
            <div className="space-y-2">
              <p className="text-slate-400">Sites carrières (Greenhouse, Lever, Ashby) — identifiant visible dans l'adresse de la page carrière</p>
              {s.boards.map((b, i) => (
                <div key={i} className="grid grid-cols-[1fr_110px_1fr_auto] gap-2" data-testid={`radar-board-${i}`}>
                  <input value={b.company} onChange={(e) => setBoard(i, "company", e.target.value)} placeholder="Entreprise" className={inputCls} />
                  <select value={b.kind} onChange={(e) => setBoard(i, "kind", e.target.value)} className={inputCls}><option value="greenhouse">Greenhouse</option><option value="lever">Lever</option><option value="ashby">Ashby</option></select>
                  <input value={b.slug} onChange={(e) => setBoard(i, "slug", e.target.value)} placeholder="identifiant" className={inputCls} />
                  <button type="button" onClick={() => setS({ ...s, boards: s.boards.filter((_, j) => j !== i) })} className="p-2 text-slate-500 hover:text-rose-300"><Trash2 className="h-4 w-4" /></button>
                </div>))}
              <button type="button" onClick={() => setS({ ...s, boards: [...s.boards, { company: "", kind: "greenhouse", slug: "" }] })} data-testid="radar-add-board-btn" className="flex items-center gap-1 text-indigo-300"><Plus className="h-3.5 w-3.5" />Ajouter un site carrière</button>
            </div>
            <button onClick={save} disabled={busy} data-testid="radar-settings-save-btn" className="w-full rounded-xl bg-indigo-500 py-2.5 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60">Enregistrer</button>
          </div>)}
      </DialogContent>
    </Dialog>
  );
};
