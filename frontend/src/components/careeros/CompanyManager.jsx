import { KIND_LABEL } from "@/lib/portals";
import { useEffect, useState } from "react";
import { QuickAssociate, blockedKind, fromKnowledge } from "@/components/careeros/QuickAssociate";
import { Building2, CheckCircle2, Eye, EyeOff, Loader2, Plus, RefreshCw, Search, Trash2, Upload, Wand2 } from "lucide-react";
import { InfoTip } from "@/components/careeros/guide/InfoTip";
import { toast } from "sonner";
import { radar } from "@/lib/careeros";
import { CompanyCleanup } from "@/components/careeros/CompanyCleanup";
import { RemovedCompanies } from "@/components/careeros/RemovedCompanies";
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

const DOT = { new: "bg-sky-400", active: "bg-emerald-400", low: "bg-amber-400", inactive: "bg-rose-400" };
const CompanyRow = ({ c, i, onChange, onRemove, result, setResult, match, picked, onPick, act }) => {
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
    <div className="grid grid-cols-[auto_auto_1fr_1.4fr_auto_auto_auto_auto] items-center gap-2" data-testid={`radar-company-${i}`}>
      <input type="checkbox" className="h-3.5 w-3.5 accent-rose-500" checked={picked} onChange={onPick} title="Cocher pour retirer en groupe" aria-label={`Sélectionner ${c.name} pour la retirer`} data-testid={`radar-company-select-${i}`} />
      <button type="button" onClick={() => onChange({ enabled: !c.enabled })} title={c.enabled ? "Recherche active : cliquez pour mettre en pause" : "En pause : cliquez pour réactiver"} aria-pressed={c.enabled}
        className={`rounded-full border px-2 py-0.5 text-[10px] font-semibold ${c.enabled ? "border-emerald-400/40 bg-emerald-500/10 text-emerald-200" : "border-white/15 text-slate-400"}`} data-testid={`radar-company-enabled-${i}`}>{c.enabled ? "Active" : "En pause"}</button>
      <div className="relative"><input value={c.name} onChange={(e) => onChange({ name: e.target.value })} className={`${inputCls} pl-6`} data-testid={`radar-company-name-${i}`} />
        {act && <span className={`absolute left-2.5 top-1/2 h-2 w-2 -translate-y-1/2 rounded-full ${DOT[act.status]}`} title={`Dernière offre : ${act.last ? new Date(act.last).toLocaleDateString("fr-CA") : "jamais"}`} data-testid={`radar-company-activity-${i}`} />}</div>
      <input value={c.portal_url} onChange={(e) => onChange({ portal_url: e.target.value, kind: "", slug: "" })} placeholder="URL portail carrières (optionnel)" className={inputCls} data-testid={`radar-company-url-${i}`} />
      {c.kind ? <span className="flex items-center gap-1 whitespace-nowrap text-[11px] text-emerald-300" data-testid={`radar-company-kind-${i}`}><CheckCircle2 className="h-3.5 w-3.5" />{KIND[c.kind]}{c.auto && <span className="rounded border border-emerald-400/40 px-1 text-[9px] uppercase" title="Associé automatiquement : modifiable ou supprimable à tout moment" data-testid={`radar-company-auto-${i}`}>auto</span>}</span>
        : c.portal_url ? <button type="button" onClick={check} disabled={checking} className="whitespace-nowrap text-[11px] text-indigo-300" data-testid={`radar-company-check-${i}`}>{checking ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <span className="text-amber-300" title="Portail pas encore reconnu : cliquez pour vérifier">À vérifier</span>}</button>
          : blockedKind(c, match) ? <span /> : <span className="whitespace-nowrap text-[11px] text-slate-500" data-testid={`radar-company-kind-${i}`}>Jooble</span>}
      {!c.kind ? <QuickAssociate c={c} i={i} match={match} onPick={onChange} /> : <span />}
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
  const [showAssoc, setShowAssoc] = useState(false);
  const [kb, setKb] = useState({});
  const [sel, setSel] = useState(new Set());
  const [clean, setClean] = useState(null);
  const [act, setAct] = useState(null);
  const [showRemoved, setShowRemoved] = useState(false);
  const [rk, setRk] = useState(0);
  useEffect(() => { radar.companiesActivity().then(setAct).catch(() => {}); }, [rk]);
  const onRemoved = (names) => { const n = new Set(names); setCompanies(companies.filter((c) => !n.has(c.name))); setSel(new Set()); setResults({}); setRk((k) => k + 1); };
  const pick = (n) => setSel((s) => { const x = new Set(s); x.has(n) ? x.delete(n) : x.add(n); return x; });
  const pending = companies.filter((c) => !c.kind).map((c) => c.name).join("|");
  useEffect(() => {
    const names = pending ? pending.split("|") : [];
    if (!names.length) return undefined;
    const t = setTimeout(() => radar.knowledgeMatch(names).then((r) => setKb(r.items || {})).catch(() => {}), 400);
    return () => clearTimeout(t);
  }, [pending]);
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
  const add = async () => {
    const n = name.trim();
    if (!n) return;
    let extra = {};
    if (!url.trim()) {
      const m = (await radar.knowledgeMatch([n]).catch(() => ({ items: {} }))).items?.[n];
      if (m?.usable) { extra = fromKnowledge(m); toast.success(`${n} associée automatiquement à son portail déjà vérifié par CareerOS (${m.kind_label}). Modifiable à tout moment.`); }
      else if (m) extra = { detected: `Bloqué (anti-robot) : ${m.kind_label}` };
    }
    setCompanies(mergeCompanies(companies, [{ name: n, enabled: true, portal_url: url.trim(), kind: "", slug: "", ...extra }])); setName(""); setUrl("");
  };
  const doImport = () => { const items = parseImport(bulk); setCompanies(mergeCompanies(companies, items)); toast.success(`${items.length} entreprise(s) importée(s)`); setBulk(""); setImporting(false); };
  const active = companies.filter((c) => c.enabled).length;
  const redetectN = companies.filter((c) => c.enabled && !c.kind && REDETECT(c)).length;
  const assocN = companies.filter((c) => c.kind).length;
  const rows = companies.map((c, i) => [c, i]).filter(([c]) => showAssoc || !c.kind);
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
      <div className="flex flex-wrap items-center justify-between gap-2 rounded-lg border border-white/10 px-3 py-2 text-[11px]" data-testid="radar-company-filter">
        <span className="text-slate-400" data-testid="radar-company-filter-info">{showAssoc ? `Toutes les entreprises (${companies.length})` : `${companies.length - assocN} non associée(s) affichée(s) · ${assocN} associée(s) masquée(s)`}</span>
        <button type="button" onClick={() => setShowAssoc(!showAssoc)} className="flex items-center gap-1 text-indigo-300 hover:text-white" data-testid="radar-company-toggle-assoc">
          {showAssoc ? <EyeOff className="h-3.5 w-3.5" /> : <Eye className="h-3.5 w-3.5" />}{showAssoc ? "Masquer les associées" : `Afficher les associées (${assocN})`}
        </button>
      </div>
      <div className="flex flex-wrap items-center gap-2 rounded-lg border border-white/10 px-3 py-2 text-[11px]" data-testid="radar-company-bulk">
        <span className={`font-semibold ${companies.length >= 100 ? "text-rose-300" : "text-slate-200"}`} data-testid="radar-company-limit">Entreprises suivies : {companies.length} / 100</span>
        {act && <span className="text-slate-400" data-testid="radar-company-activity-counts"><span className="text-emerald-300">Actives (30 j) : {act.counts.active}</span> · <span className="text-amber-300">Peu actives : {act.counts.low}</span> · <span className="text-rose-300">Inactives (90 j) : {act.counts.inactive}</span></span>}
        <span className="ml-auto flex flex-wrap gap-2">
          <button type="button" onClick={() => setSel(new Set(rows.map(([c]) => c.name)))} className="text-indigo-300 hover:text-white" data-testid="radar-company-select-all">Tout sélectionner ({rows.length} affichées)</button>
          {sel.size > 0 && <button type="button" onClick={() => setSel(new Set())} className="text-slate-400 hover:text-white" data-testid="radar-company-select-none">Désélectionner</button>}
          <button type="button" onClick={() => setClean([...sel])} disabled={!sel.size} className="rounded-full bg-rose-600 px-3 py-0.5 font-semibold text-white disabled:opacity-40" data-testid="radar-company-remove-selected">Retirer la sélection ({sel.size})</button>
          <button type="button" onClick={() => setClean("inactive")} className="rounded-full border border-rose-400/40 px-3 py-0.5 text-rose-200" data-testid="radar-company-clean-inactive">Nettoyer les entreprises inactives</button>
          <button type="button" onClick={() => setClean("norel")} className="rounded-full border border-white/15 px-3 py-0.5 text-slate-300" data-testid="radar-company-clean-norel">Sans offre pertinente depuis 30 jours</button>
          <button type="button" onClick={() => setShowRemoved((v) => !v)} className="text-indigo-300 hover:text-white" data-testid="radar-company-show-removed">{showRemoved ? "Masquer" : "Afficher"} les entreprises retirées</button>
        </span>
      </div>
      <p className="text-[11px] text-slate-500">Retirer une entreprise arrête son suivi, mais ses offres déjà trouvées restent dans votre Radar et votre historique. Enregistrez vos autres modifications avant un retrait groupé.</p>
      {showRemoved && <RemovedCompanies refreshKey={rk} onRestored={async (n) => { const st = await radar.settings().catch(() => null); const c = st?.companies?.find((x) => x.name === n); setCompanies(mergeCompanies(companies, [c || { name: n, enabled: true, portal_url: "", kind: "", slug: "" }])); setRk((k) => k + 1); }} />}
      <CompanyCleanup open={!!clean} preset={clean} onClose={() => setClean(null)} onRemoved={onRemoved} />
      <div className="space-y-2">
        {rows.length === 0 && companies.length > 0 && <p className="text-[11px] text-emerald-300" data-testid="radar-company-all-assoc">Toutes vos entreprises sont associées à leur portail.</p>}
        {rows.map(([c, i]) => <CompanyRow key={i} c={c} i={i} match={kb[c.name]} picked={sel.has(c.name)} onPick={() => pick(c.name)} act={act?.items?.[c.name]} result={results[i]} setResult={(r) => { setResults((x) => ({ ...x, [i]: r })); if (r) update(i, { detected: detectedLabel(r) }); }} onChange={(p) => update(i, p)} onRemove={() => { setResults({}); setCompanies(companies.filter((_, j) => j !== i)); }} />)}
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
