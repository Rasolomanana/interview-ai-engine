import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { radar } from "@/lib/careeros";
import { CompanyManager } from "@/components/careeros/CompanyManager";
import { SOURCES } from "@/components/careeros/SourceStatus";

const inputCls = "w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/60";
const csv = (a) => (a || []).join(", ");
const list = (v) => v.split(",").map((x) => x.trim()).filter(Boolean);

export const RadarSettingsDialog = ({ onClose }) => {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  const [initial, setInitial] = useState("");
  useEffect(() => { radar.settings().then((r) => { setS(r); setInitial(JSON.stringify(r)); }).catch((e) => toast.error(e.message)); }, []);
  const close = () => {
    if (s && JSON.stringify(s) !== initial && !window.confirm("Vos modifications ne sont pas enregistrées. Fermer sans enregistrer ?")) return;
    onClose();
  };
  const save = async () => {
    setBusy(true);
    try {
      const { enabled, keywords, location, companies, sources } = s;
      const r = await radar.saveSettings({ enabled, keywords, location, companies: companies.filter((c) => c.name.trim()), sources });
      const n = (f) => r.companies.filter((c) => c.enabled && f(c)).length;
      const bad = r.companies.filter((c) => c.portal_url && !c.kind).map((c) => c.name);
      toast.success(`Réglages enregistrés : ${n((c) => c.kind === "workday")} portail(s) Workday, ${n((c) => c.kind && c.kind !== "workday")} autre(s) portail(s) employeur, ${n((c) => !c.kind)} entreprise(s) via Jooble.`);
      if (bad.length) toast.warning(`URL non reconnue pour : ${bad.join(", ")}. Ces entreprises sont suivies via Jooble.`, { duration: 9000 });
      onClose();
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  const toggleSrc = (k) => setS({ ...s, sources: s.sources.includes(k) ? s.sources.filter((x) => x !== k) : [...s.sources, k] });
  return (
    <Dialog open onOpenChange={close}>
      <DialogContent className="max-h-[85vh] overflow-y-auto border-white/10 bg-[#121520] text-slate-100 sm:max-w-2xl" data-testid="radar-settings-dialog">
        <DialogHeader><DialogTitle className="font-display">Réglages du Radar</DialogTitle>
          <DialogDescription className="text-xs text-slate-400">Sources officielles uniquement. Recherche quotidienne + à la demande.</DialogDescription></DialogHeader>
        {!s ? <Loader2 className="h-5 w-5 animate-spin text-indigo-400" /> : (
          <div className="space-y-4 text-xs">
            <label className="flex items-center gap-2 text-slate-300"><input type="checkbox" className="accent-indigo-500" checked={s.enabled} onChange={(e) => setS({ ...s, enabled: e.target.checked })} data-testid="radar-enabled-checkbox" />Recherche quotidienne automatique</label>
            <label className="block text-slate-400">Mots-clés / postes visés (virgules)<input defaultValue={csv(s.keywords)} onBlur={(e) => setS({ ...s, keywords: list(e.target.value) })} className={`${inputCls} mt-1`} data-testid="radar-keywords-input" /></label>
            <label className="block text-slate-400">Localisation<input value={s.location} onChange={(e) => setS({ ...s, location: e.target.value })} className={`${inputCls} mt-1`} data-testid="radar-location-input" /></label>
            <div className="flex flex-wrap gap-2" data-testid="radar-sources">
              {SOURCES.map(([k, l]) => {
                const off = !s.configured?.[k];
                return (
                  <button key={k} type="button" onClick={() => toggleSrc(k)} disabled={off} data-testid={`radar-source-${k}`} title={off ? "Clé API non configurée sur le serveur" : ""}
                    className={`rounded-full border px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-60 ${s.sources.includes(k) && !off ? "border-indigo-400/60 bg-indigo-500/15 text-white" : "border-white/10 text-slate-400"}`}>
                    {l}{off ? " · Non configuré" : ""}</button>);
              })}
            </div>
            <CompanyManager companies={s.companies} setCompanies={(companies) => setS({ ...s, companies })} />
            <div className="sticky bottom-0 -mx-1 bg-[#121520] px-1 pb-1 pt-2">
              <button onClick={save} disabled={busy} data-testid="radar-settings-save-btn" className="w-full rounded-xl bg-indigo-500 py-2.5 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60">{busy ? "Enregistrement…" : "Enregistrer"}</button>
            </div>
          </div>)}
      </DialogContent>
    </Dialog>
  );
};
