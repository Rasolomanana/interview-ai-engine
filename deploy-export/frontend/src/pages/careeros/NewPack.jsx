import { DateField } from "@/components/careeros/DateField";
import { ConceptRow } from "@/components/careeros/guide/InfoTip";
import { useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Loader2, ShieldCheck, Sparkles, Upload } from "lucide-react";
import { QuickVerdict } from "@/components/careeros/QuickVerdict";
import { toast } from "sonner";
import { Shell } from "@/components/careeros/Shell";
import { careeros, radar } from "@/lib/careeros";
import { extractPdf } from "@/lib/api";
import { usePageTitle } from "@/components/careeros/ThemeToggle";

const inputCls = "w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white outline-none transition-colors placeholder:text-slate-600 focus:border-indigo-400/60";
const Label = ({ children, hint }) => <div className="mb-1.5 flex items-baseline justify-between"><span className="text-xs font-medium text-slate-300">{children}</span>{hint && <span className="text-[11px] text-slate-600">{hint}</span>}</div>;
const OUTPUTS = ["Analyse ATS", "IPS + priorité A/B/C", "Pourquoi postuler / éviter", "CV ATS", "CV humain", "Lettre personnalisée", "Questions RH · gestionnaire · comportementales · techniques", "Réponses STAR", "Simulation recruteur", "Risques & objections"];

export default function NewPack() {
  usePageTitle("Pack candidature");
  const nav = useNavigate();
  const fileRef = useRef(null);
  const [f, setF] = useState({ offer_text: "", offer_url: "", company_url: "", cv_text: "", posted_date: "", network: "aucun", save_cv_to_memory: true });
  const [memoryCv, setMemoryCv] = useState(false);
  const [busy, setBusy] = useState(false);
  const [check, setCheck] = useState(null);
  const [checking, setChecking] = useState(false);
  const verify = async () => {
    setChecking(true);
    try { setCheck(await radar.external({ title: "", company: "", location: "", url: f.offer_url, text: f.offer_text })); } catch (err) { toast.error(err.message); } finally { setChecking(false); }
  };
  const set = (k) => (e) => setF({ ...f, [k]: e.target.type === "checkbox" ? e.target.checked : e.target.value });

  useEffect(() => {
    careeros.getProfile().then((p) => { if (p.cv_text) { setF((x) => ({ ...x, cv_text: p.cv_text })); setMemoryCv(true); } }).catch(() => {});
  }, []);

  const importPdf = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try { const t = await extractPdf(file); setF((x) => ({ ...x, cv_text: t })); toast.success("CV importé"); } catch (err) { toast.error(err.message); }
    e.target.value = "";
  };

  const submit = async (e) => {
    e.preventDefault();
    setBusy(true);
    try { const r = await careeros.createPack(f); nav(`/careeros/candidature/${r.id}`); } catch (err) { toast.error(err.message); setBusy(false); }
  };

  return (
    <Shell>
      <form onSubmit={submit} className="grid gap-8 lg:grid-cols-[1fr_320px]" data-testid="new-pack-form">
        <div className="space-y-6">
          <div>
            <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-indigo-300">Interview AI Engine</p>
            <h1 className="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl">Pack candidature en un clic</h1>
            <p className="mt-3 max-w-xl text-sm text-slate-400">Collez l'offre (ou son lien) : CareerOS décide s'il faut postuler, et prépare tout le reste.</p>
            <ConceptRow keys={["pack", "ips", "priorite"]} />
          </div>
          <div>
            <Label hint="texte complet recommandé">Offre d'emploi</Label>
            <textarea rows={8} value={f.offer_text} onChange={set("offer_text")} className={inputCls} placeholder="Collez ici le texte de l'offre…" data-testid="offer-text-input" />
          </div>
          <div className="grid gap-4 sm:grid-cols-2">
            <div><Label hint="optionnel">Lien de l'offre</Label><input value={f.offer_url} onChange={set("offer_url")} className={inputCls} placeholder="https://…" data-testid="offer-url-input" /></div>
            <div><Label hint="optionnel">Site de l'entreprise</Label><input value={f.company_url} onChange={set("company_url")} className={inputCls} placeholder="https://…" data-testid="company-url-input" /></div>
            <div><Label hint="fraîcheur de l'offre">Date de publication</Label><DateField value={f.posted_date} onChange={(v) => setF((x) => ({ ...x, posted_date: v }))} className={inputCls} testid="posted-date-input" /></div>
            <div>
              <Label hint="force du réseau">Contact dans l'entreprise</Label>
              <select value={f.network} onChange={set("network")} className={inputCls} data-testid="network-select">
                <option value="aucun">Aucun contact</option><option value="contact">Un contact</option><option value="recommandation">Recommandation interne</option>
              </select>
            </div>
          </div>
          <div>
            <Label hint={memoryCv ? "chargé depuis votre Career Memory" : ""}>Votre CV</Label>
            <textarea rows={8} value={f.cv_text} onChange={set("cv_text")} className={inputCls} placeholder="Collez votre CV ou importez un PDF…" data-testid="cv-text-input" />
            <div className="mt-2 flex flex-wrap items-center justify-between gap-2">
              <button type="button" onClick={() => fileRef.current?.click()} className="flex items-center gap-1.5 text-xs text-indigo-300 hover:text-indigo-200" data-testid="cv-import-pdf-btn"><Upload className="h-3.5 w-3.5" /> Importer un PDF</button>
              <input ref={fileRef} type="file" accept="application/pdf" className="hidden" onChange={importPdf} data-testid="cv-pdf-input" />
              <label className="flex items-center gap-2 text-xs text-slate-400"><input type="checkbox" checked={f.save_cv_to_memory} onChange={set("save_cv_to_memory")} data-testid="save-cv-memory-checkbox" className="accent-indigo-500" />Enregistrer ce CV dans ma Career Memory</label>
            </div>
          </div>
        </div>
        <aside className="h-fit space-y-4 rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-5 lg:sticky lg:top-24">
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-slate-500">Généré automatiquement</p>
          <ul className="space-y-2">{OUTPUTS.map((o) => <li key={o} className="flex gap-2 text-xs text-slate-300"><span className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-indigo-400" />{o}</li>)}</ul>
          <button type="button" onClick={verify} disabled={checking || (!f.offer_text.trim() && !f.offer_url.trim())} data-testid="verify-first-btn"
            className="flex w-full items-center justify-center gap-2 rounded-xl border border-emerald-400/40 bg-emerald-500/10 py-2.5 text-sm font-semibold text-emerald-200 transition-colors hover:bg-emerald-500/20 disabled:opacity-50">
            {checking ? <Loader2 className="h-4 w-4 animate-spin" /> : <ShieldCheck className="h-4 w-4" />} Vérifier d'abord (gratuit)
          </button>
          <p className="text-[11px] text-slate-500">IPS par règles, instantané, sans IA, calculé avec votre Career Memory, avant de lancer la génération IA.</p>
          {check && <QuickVerdict o={check} packLabel="Générer le pack complet" onPack={() => document.querySelector('[data-testid="generate-pack-btn"]')?.click()} />}
          <button disabled={busy} data-testid="generate-pack-btn"
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-500 py-3 text-sm font-semibold text-white shadow-lg shadow-indigo-500/20 transition-colors hover:bg-indigo-400 disabled:opacity-60">
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />} Générer le pack
          </button>
          <p className="text-[11px] text-slate-600">Environ 1 à 2 minutes. Les documents s'affichent au fur et à mesure et sont sauvegardés dans votre historique.</p>
        </aside>
      </form>
    </Shell>
  );
}
