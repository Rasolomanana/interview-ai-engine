import { useEffect, useState } from "react";
import { Loader2 } from "lucide-react";
import { toast } from "sonner";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { radar } from "@/lib/careeros";
import { CompanyManager } from "@/components/careeros/CompanyManager";
import { SOURCES } from "@/components/careeros/SourceStatus";
import { PageTour, TourButton, usePageTour } from "@/components/careeros/guide/PageTour";

const SETTINGS_STEPS = [
  { target: "company-summary", title: "Couverture", text: "Combien d'entreprises sont lues à la source, suivies via Jooble, non prises en charge ou bloquées. Cliquez une case pour la liste." },
  { target: "radar-directory-toggle", title: "Annuaire", text: "Grands employeurs du Québec et du Canada dont le portail est déjà vérifié : ajout en un clic." },
  { target: "radar-detect-all-btn", title: "Tout détecter / Re-détecter", text: "Lance la loupe sur toutes les entreprises sans portail, ou seulement sur celles non prises en charge (après l'arrivée d'un nouveau connecteur)." },
  { target: "radar-company-find-0", title: "Loupe et Associer", text: "La loupe propose le portail officiel d'une entreprise. Cliquez « Associer » pour le relier : rien n'est associé sans votre clic." },
  { target: "radar-settings-save-btn", title: "Enregistrer", text: "Vos associations sont prises en compte au prochain passage du Radar, une fois enregistrées." },
];

const inputCls = "w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/60";
const csv = (a) => (a || []).join(", ");
const list = (v) => v.split(",").map((x) => x.trim()).filter(Boolean);

export const RadarSettingsDialog = ({ onClose }) => {
  const [s, setS] = useState(null);
  const [busy, setBusy] = useState(false);
  const [initial, setInitial] = useState("");
  const tour = usePageTour("radarSettingsTourDone");
  useEffect(() => { radar.settings().then((r) => { setS(r); setInitial(JSON.stringify(r)); }).catch((e) => toast.error(e.message)); }, []);
  const close = () => {
    if (s && JSON.stringify(s) !== initial && !window.confirm("Vos modifications ne sont pas enregistrées. Fermer sans enregistrer ?")) return;
    onClose();
  };
  const save = async () => {
    setBusy(true);
    try {
      const { enabled, keywords, location, companies, sources, expand } = s;
      const r = await radar.saveSettings({ enabled, keywords, location, companies: companies.filter((c) => c.name.trim()), sources, expand: expand !== false });
      const n = (f) => r.companies.filter((c) => c.enabled && f(c)).length;
      const bad = r.companies.filter((c) => c.portal_url && !c.kind).map((c) => c.name);
      toast.success(`Réglages enregistrés : ${n((c) => c.kind === "workday")} portail(s) Workday, ${n((c) => c.kind && c.kind !== "workday")} autre(s) portail(s) employeur, ${n((c) => !c.kind)} entreprise(s) via Jooble.`);
      if (r.auto_detecting?.length) toast.message(`Détection automatique lancée pour ${r.auto_detecting.length} entreprise(s) : les portails vérifiés avec certitude seront associés et signalés sur la page Radar.`, { duration: 8000 });
      if (bad.length) toast.warning(`URL non reconnue pour : ${bad.join(", ")}. Ces entreprises sont suivies via Jooble.`, { duration: 9000 });
      onClose();
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  const toggleSrc = (k) => setS({ ...s, sources: s.sources.includes(k) ? s.sources.filter((x) => x !== k) : [...s.sources, k] });
  return (
    <Dialog open onOpenChange={close}>
      <DialogContent className="flex max-h-[94vh] flex-col gap-0 overflow-hidden border-white/10 bg-[#121520] p-0 text-slate-100 sm:max-w-3xl" data-testid="radar-settings-dialog">
        <DialogHeader className="shrink-0 border-b border-white/[0.06] px-5 pb-3 pt-5 sm:px-6"><DialogTitle className="flex flex-wrap items-center gap-3 pr-6 font-display">Réglages du Radar<TourButton onClick={tour.open} testid="radar-settings-tour-btn">Visite</TourButton></DialogTitle>
          <DialogDescription className="text-xs text-slate-400">Sources officielles uniquement. Recherche quotidienne + à la demande.</DialogDescription></DialogHeader>
        {!s ? <Loader2 className="m-6 h-5 w-5 animate-spin text-indigo-400" /> : (<>
          <div className="min-h-0 flex-1 space-y-4 overflow-y-auto px-5 py-4 text-xs sm:px-6" data-testid="radar-settings-body">
            <label className="flex items-center gap-2 text-slate-300"><input type="checkbox" className="accent-indigo-500" checked={s.enabled} onChange={(e) => setS({ ...s, enabled: e.target.checked })} data-testid="radar-enabled-checkbox" />Recherche quotidienne automatique</label>
            <label className="block text-slate-400">Mots-clés / postes visés (virgules)<input defaultValue={csv(s.keywords)} onBlur={(e) => setS({ ...s, keywords: list(e.target.value) })} className={`${inputCls} mt-1`} data-testid="radar-keywords-input" /></label>
            <div className="rounded-xl border border-white/[0.07] bg-black/20 p-3" data-testid="radar-expand-box">
              <label className="flex items-center gap-2 text-slate-300"><input type="checkbox" className="accent-indigo-500" checked={s.expand !== false} onChange={(e) => setS({ ...s, expand: e.target.checked })} data-testid="radar-expand-checkbox" />
                Recherche élargie : titres équivalents en français et en anglais (jusqu'à 8 recherches Jooble, 2 pages chacune)</label>
              {s.expand !== false && s.expanded?.length > 0 && <p className="mt-2 flex flex-wrap gap-1" data-testid="radar-expanded-terms">{s.expanded.map((t) => <span key={t} className="rounded-full border border-white/10 px-2 py-0.5 text-[11px] text-slate-300">{t}</span>)}</p>}
              <p className="mt-1 text-[11px] text-slate-500">Calculé à partir de vos mots-clés enregistrés. Seules les 50 offres aux titres les plus proches de vos postes visés sont analysées chaque jour.</p>
            </div>
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
          </div>
          <PageTour tour={tour} steps={SETTINGS_STEPS} label="Visite des réglages" testid="radar-settings-tour" className="absolute bottom-20 right-4 z-[70]" />
          <div className="shrink-0 border-t border-white/[0.06] bg-[#121520] px-5 py-3 sm:px-6" data-testid="radar-settings-footer">
            <button onClick={save} disabled={busy} data-testid="radar-settings-save-btn" className="w-full rounded-xl bg-indigo-500 py-2.5 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60">{busy ? "Enregistrement…" : "Enregistrer"}</button>
          </div>
        </>)}
      </DialogContent>
    </Dialog>
  );
};
