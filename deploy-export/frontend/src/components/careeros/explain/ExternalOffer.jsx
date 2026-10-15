import { useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { radar } from "@/lib/careeros";

const F = ({ k, label, v, set, ph }) => (
  <label className="block text-xs text-slate-400">{label}
    <input value={v[k]} onChange={(e) => set({ ...v, [k]: e.target.value })} placeholder={ph} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/50" data-testid={`external-${k}`} />
  </label>
);

export const ExternalOffer = ({ open, onClose, onDone }) => {
  const [v, setV] = useState({ title: "", company: "", location: "", url: "", text: "" });
  const [busy, setBusy] = useState(false);
  const submit = async () => {
    setBusy(true);
    try { const o = await radar.external(v); toast.success(`Offre analysée : IPS ${o.ips?.score}`); onDone(o); setV({ title: "", company: "", location: "", url: "", text: "" }); } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <Dialog open={open} onOpenChange={(x) => !x && onClose()}>
      <DialogContent className="max-h-[90vh] overflow-y-auto border-white/10 bg-[#121520] text-slate-100 sm:max-w-xl" data-testid="external-dialog">
        <DialogHeader><DialogTitle className="font-display">Analyser une offre externe</DialogTitle></DialogHeader>
        <DialogDescription className="text-xs text-slate-400">Collez le texte d'une offre vue ailleurs (LinkedIn, Indeed, site employeur…). CareerOS ne lit jamais LinkedIn automatiquement. Analyse par règles gratuite, puis analyse approfondie IA si vous le souhaitez.</DialogDescription>
        <div className="grid gap-3 sm:grid-cols-3">
          <F k="title" label="Titre" v={v} set={setV} ph="Chefs des opérations" />
          <F k="company" label="Entreprise" v={v} set={setV} ph="RONA" />
          <F k="location" label="Lieu" v={v} set={setV} ph="Boucherville, QC" />
        </div>
        <F k="url" label="Lien (facultatif ; lu seulement si le site publie des données d'offre)" v={v} set={setV} ph="https://…" />
        <label className="block text-xs text-slate-400">Texte de l'offre (exigences, responsabilités…)
          <textarea value={v.text} onChange={(e) => setV({ ...v, text: e.target.value })} rows={9} className="mt-1 w-full rounded-lg border border-white/10 bg-black/30 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/50" data-testid="external-text" />
        </label>
        <div className="flex justify-end gap-2">
          <button type="button" onClick={onClose} className="rounded-full px-4 py-2 text-xs text-slate-400 hover:text-white" data-testid="external-cancel">Annuler</button>
          <button type="button" onClick={submit} disabled={busy || (!v.text.trim() && !v.url.trim())} className="flex items-center gap-1.5 rounded-full bg-indigo-500 px-4 py-2 text-xs font-semibold text-white hover:bg-indigo-400 disabled:opacity-50" data-testid="external-submit">
            {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />}Analyser</button>
        </div>
      </DialogContent>
    </Dialog>
  );
};
