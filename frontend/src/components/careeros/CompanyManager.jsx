import { KIND_LABEL } from "@/lib/portals";
import { useState } from "react";
import { Building2, CheckCircle2, Loader2, Plus, RefreshCw, Search, Trash2, Upload, Wand2 } from "lucide-react";
import { InfoTip } from "@/components/careeros/guide/InfoTip";
import { toast } from "sonner";
import { radar } from "@/lib/careeros";
import { PortalSuggest, discoverFor } from "@/components/careeros/PortalSuggest";
import { EmployerDirectory } from "@/components/careeros/EmployerDirectory";
import { CompanySummary, detectedLabel } from "@/components/careeros/CompanySummary";

const inputCls = "w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/60";
const KIND = KIND_LABEL;
const REDETECT = (c) => /^(Non pris en charge|Illisible)/.test(c.detected || "");

export const parseImport = (text) => text.split("\n").flatMap((l) => (/https?:|\|/.test(l) ? [l] : l.split(","))).map((l) => l.trim()).filter(Boolean).map((l) => {
  const [name, url = ""] = l.split(/\s*[|\t;]\s*/);
  return { name: name.trim(), enabled: true, portal_url: url.trim(), kind: "", slug: "" };
}).filter((c) => c.name);

export const mergeCompanies = (list, added) => {
  const out = [...list];
  added.forEach((c) => {
    const i = out.findIndex((x) => x.name.toLowerCase() === c.name.toLowerCase());
    if (i < 0) out.push(c);
    else if (c.portal_url) out[i] = { ...out[i], portal_url: c.portal_url, kind: "", slug: "" };
  });
  return out;
};

const CompanyRow = ({ c, i, onChange, onRemove, result, setResult }) => {
  const [checking, setChecking] = useState(false);
  const [open, setOpen] = useState(false);
  const check = async () => {
    setChecking(true);
    try {
      const r = await radar.detectPortal({ url: c.portal_url, name: c.name });
      onChange({ kind: r.kind, slug: r.slug });
      (r.ok ? toast.success : toast.message)(`${c.name} : ${r.message}${r.ok ? ` ${r.count} offre(s) visibles.` : ""}`);
    } catch (e) { toast.error(e.message); } finally { setChecking(false); }
  };
  const show = open || !!result;
  return (
    <div className="space-y-1.5">
    <div className="grid grid-cols-[auto_1fr_1.4fr_auto_auto_auto] items-center gap-2" data-testid={`radar-company-${i}`}>
      <input type="checkbox" className="accent-indigo-500" checked={c.enabled} onChange={(e) => onChange({ enabled: e.target.checked })} title="Surveillance active" data-testid={`radar-company-enabled-${i}`} />
      <input value={c.name} onChange={(e) => onChange({ name: e.target.value })} className={inputCls} data-testid={`radar-company-name-${i}`} />
      <input value={c.portal_url} onChange={(e) => onChange({ portal_url: e.target.value, kind: "", slug: "" })} placeholder="URL portail carrières (optionnel)" className={inputCls} data-testid={`radar-company-url-${i}`} />
      {c.kind ? <span className="flex items-center gap-1 whitespace-nowrap text-[11px] text-emerald-300" data-testid={`radar-company-kind-${i}`}><CheckCircle2 className="h-3.5 w-3.5" />{KIND[c.kind]}</span>
        : c.portal_url ? <button type="button" onClick={check} disabled={checking} className="whitespace-nowrap text-[11px] text-indigo-300" data-testid={`radar-company-check-${i}`}>{checking ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <span className="text-amber-300" title="Portail pas encore reconnu : cliquez pour vérifier">À vérifier</span>}</button>
          : <span className="whitespace-nowrap text-[11px] text-slate-500" data-testid={`radar-company-kind-${i}`}>Jooble</span>}
      <button type="button" onClick={() => setOpen(!show)} title="Trouver le portail" className="p-1.5 text-indigo-300 hover:text-white" data-testid={`radar-company-find-${i}`}><Search className="h-4 w-4" /></button>
      <button type="button" onClick={onRemove} className="p-1.5 text-slate-500 hover:text-rose-300" data-testid={`radar-company-remove-${i}`}><Trash2 className="h-4 w-4" /></button>
    </div>
    {show && <PortalSuggest c={c} i={i} auto={open && !result} result={result} onResult={setResult} onClose={() => { setOpen(false); setResult(null); }}
      onPick={(p) => { onChange({ ...p, detected: "" }); setOpen(false); setResult(null); toast.success(`${c.name} associée à son portail ${KIND[p.kind]}.`); }} />}
    </div>
  );
};

export const CompanyManager = ({ companies, setCompanies }) => {
  const [name, setName] = useState("");
  const [url, setUrl] = useState("");
  const [importing, setImporting] = useState(false);
  const [bulk, setBulk] = useState("");
  const [results, setResults] = useState({});
  const [dir, setDir] = useState(false);
  const [scan, setScan] = useState(null);
  const detectAll = async (only) => {
    const todo = companies.map((c, i) => [c, i]).filter(([c]) => c.enabled && !c.kind && (!only || only(c)));
    if (!todo.length) { toast.message(only ? "Aucune entreprise non prise en charge ou illisible à re-détecter." : "Toutes les entreprises actives ont déjà un portail."); return; }
    let found = 0;
    const det = {};
    for (let k = 0; k < todo.length; k++) {
      const [c, i] = todo[k];
      setScan(`${k + 1}/${todo.length} · ${c.name}`);
      try {
        const r = await discoverFor(c);
        setResults((x) => ({ ...x, [i]: r }));
        det[i] = detectedLabel(r);
        if (r.candidates?.some((p) => p.ok)) found += 1;
      } catch { /* keep going */ }
    }
    setScan(null);
    setCompanies(companies.map((c, i) => (i in det ? { ...c, detected: det[i] } : c)));
    toast.success(`Détection terminée : ${found} portail(s) proposé(s) sur ${todo.length} entreprise(s). Validez chaque suggestion avec « Associer ».`);
  };
  const addFromDirectory = (d) => {
    setCompanies(mergeCompanies(companies, [{ name: d.name, enabled: true, portal_url: d.ok ? d.portal_url : "", kind: d.ok ? d.kind : "", slug: d.ok ? d.slug : "", website: "",
      detected: d.ok ? "" : d.blocked ? `Bloqué (anti-robot) : ${d.kind_label}` : d.kind ? `Illisible : ${d.kind_label}` : `Non pris en charge : ${d.ats || "non identifié"}` }]));
    toast.success(d.ok ? `${d.name} ajoutée avec son portail ${d.kind_label}.` : `${d.name} ajoutée : suivie via Jooble.`);
  };
  const update = (i, patch) => setCompanies(companies.map((c, j) => (j === i ? { ...c, ...patch } : c)));
  const add = () => { if (!name.trim()) return; setCompanies(mergeCompanies(companies, [{ name: name.trim(), enabled: true, portal_url: url.trim(), kind: "", slug: "" }])); setName(""); setUrl(""); };
  const doImport = () => { const items = parseImport(bulk); setCompanies(mergeCompanies(companies, items)); toast.success(`${items.length} entreprise(s) importée(s)`); setBulk(""); setImporting(false); };
  const active = companies.filter((c) => c.enabled).length;
  const redetectN = companies.filter((c) => c.enabled && !c.kind && REDETECT(c)).length;
  return (
    <div className="space-y-2" data-testid="radar-company-manager">
      <div className="flex items-center justify-between">
        <p className="flex items-center text-slate-300">Entreprises suivies<InfoTip k="loupe" /><span className="ml-1 text-slate-500" data-testid="radar-company-count">({active}/{companies.length} actives)</span></p>
        <div className="flex flex-wrap items-center gap-3">
          <button type="button" onClick={() => setDir(!dir)} className="flex items-center gap-1 text-indigo-300" data-testid="radar-directory-toggle"><Building2 className="h-3.5 w-3.5" />Annuaire</button>
          <button type="button" onClick={() => detectAll()} disabled={!!scan} className="flex items-center gap-1 text-indigo-300 disabled:opacity-60" data-testid="radar-detect-all-btn">{scan ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Wand2 className="h-3.5 w-3.5" />}{scan ? `Détection ${scan}` : "Tout détecter"}</button>
          <button type="button" onClick={() => detectAll(REDETECT)} disabled={!!scan || !redetectN} className="flex items-center gap-1 text-indigo-300 disabled:opacity-40" data-testid="radar-redetect-btn" title="Relance la loupe sur les entreprises non prises en charge ou illisibles"><RefreshCw className="h-3.5 w-3.5" />Re-détecter ({redetectN})</button>
          <InfoTip k="detection" />
          <button type="button" onClick={() => setImporting(!importing)} className="flex items-center gap-1 text-indigo-300" data-testid="radar-import-toggle"><Upload className="h-3.5 w-3.5" />Importer une liste</button>
        </div>
      </div>
      <p className="text-[11px] text-slate-500">Ajoutez simplement le nom : la loupe propose le portail compatible (Workday, SuccessFactors, Oracle Recruiting, iCIMS, UKG, Taleo, Avature, Phenom, SmartRecruiters, Greenhouse, Lever…). Sans portail lisible, l'entreprise reste suivie via Jooble.</p>
      <CompanySummary companies={companies} />
      {dir && <EmployerDirectory companies={companies} onAdd={addFromDirectory} />}
      {importing && (
        <div className="space-y-2 rounded-xl border border-white/10 p-3" data-testid="radar-import-panel">
          <textarea value={bulk} onChange={(e) => setBulk(e.target.value)} rows={5} placeholder={"Une entreprise par ligne, URL optionnelle après |\nExemple : Desjardins | https://desjardins.wd10.myworkdayjobs.com/Desjardins"} className={inputCls} data-testid="radar-import-textarea" />
          <button type="button" onClick={doImport} disabled={!bulk.trim()} className="rounded-full bg-indigo-500 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-50" data-testid="radar-import-btn">Importer</button>
        </div>)}
      <div className="space-y-2">
        {companies.map((c, i) => <CompanyRow key={i} c={c} i={i} result={results[i]} setResult={(r) => { setResults((x) => ({ ...x, [i]: r })); if (r) update(i, { detected: detectedLabel(r) }); }} onChange={(p) => update(i, p)} onRemove={() => { setResults({}); setCompanies(companies.filter((_, j) => j !== i)); }} />)}
        {companies.length === 0 && <p className="text-[11px] text-slate-500" data-testid="radar-company-empty">Aucune entreprise suivie. Ajoutez-en une ou importez une liste.</p>}
      </div>
      <div className="grid grid-cols-[1fr_1.4fr_auto] gap-2">
        <input value={name} onChange={(e) => setName(e.target.value)} onKeyDown={(e) => e.key === "Enter" && add()} placeholder="Nouvelle entreprise" className={inputCls} data-testid="radar-company-add-name" />
        <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="URL portail (optionnel)" className={inputCls} data-testid="radar-company-add-url" />
        <button type="button" onClick={add} className="flex items-center gap-1 rounded-xl border border-indigo-400/40 px-3 text-indigo-300" data-testid="radar-company-add-btn"><Plus className="h-3.5 w-3.5" />Ajouter</button>
      </div>
    </div>
  );
};
