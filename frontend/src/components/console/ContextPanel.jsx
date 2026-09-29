import { useState, useEffect, useRef } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { toast } from "sonner";
import { X, FileText, Briefcase, Building2, Layers, Save, Upload, Loader2, Globe, Sparkles, Gauge, AlertTriangle, KeyRound, Target, FileDown } from "lucide-react";
import { extractPdf, analyzeApplication } from "@/lib/api";
import { downloadAtsCvDocx } from "@/lib/docxExport";

const SECTEURS = ["Logistique", "Tech", "Finance", "Autre"];
const EMPTY = { title: "", cv: "", poste: "", entreprise: "", secteur: "Autre", atsCv: "", score: null, gaps: [], missingKeywords: [], redFlags: [] };

export default function ContextPanel({ open, session, onClose, onSave }) {
  const [form, setForm] = useState(EMPTY);
  const [importing, setImporting] = useState(false);
  const [companyUrl, setCompanyUrl] = useState("");
  const [analyzing, setAnalyzing] = useState(false);
  const pdfRef = useRef(null);

  useEffect(() => {
    if (session) {
      const c = session.context || {};
      setForm({
        title: session.title || "",
        cv: c.cv || "", poste: c.poste || "", entreprise: c.entreprise || "", secteur: c.secteur || "Autre",
        atsCv: c.atsCv || "", score: c.score ?? null, gaps: c.gaps || [], missingKeywords: c.missingKeywords || [], redFlags: c.redFlags || [],
      });
    }
  }, [session, open]);

  const field = (key, val) => setForm((f) => ({ ...f, [key]: val }));

  const runAnalysis = async () => {
    if (!form.cv.trim()) { toast.error("Ajoutez d'abord votre CV (import PDF ou collé)"); return; }
    setAnalyzing(true);
    try {
      const r = await analyzeApplication({ cv: form.cv, poste: form.poste, url: companyUrl.trim() });
      setForm((f) => ({
        ...f,
        atsCv: r.ats_cv || "",
        score: typeof r.score === "number" ? r.score : parseInt(r.score, 10) || 0,
        gaps: r.gaps || [], missingKeywords: r.missing_keywords || [], redFlags: r.red_flags || [],
        entreprise: r.company ? (companyUrl ? `— ${companyUrl} —\n` : "") + r.company : f.entreprise,
      }));
      toast.success("Analyse terminée — CV ATS, score et lacunes générés");
    } catch (err) {
      toast.error("Analyse échouée : " + err.message);
    } finally {
      setAnalyzing(false);
    }
  };

  const importPdf = async (e) => {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    setImporting(true);
    try {
      const text = await extractPdf(file);
      field("cv", text);
      toast.success("CV importé depuis le PDF");
    } catch (err) {
      toast.error("Import PDF échoué : " + err.message);
    } finally {
      setImporting(false);
    }
  };

  const scoreColor = form.score == null ? "text-slate-400" : form.score >= 75 ? "text-emerald-400" : form.score >= 50 ? "text-amber-400" : "text-rose-400";

  return (
    <AnimatePresence>
      {open && (
        <motion.div className="fixed inset-0 z-50 flex items-center justify-center p-2 sm:p-4" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
          <div className="absolute inset-0 bg-black/80 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            initial={{ opacity: 0, scale: 0.98 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.98 }}
            className="glass relative z-10 flex h-[96vh] w-full max-w-[1500px] flex-col overflow-hidden rounded-2xl"
            data-testid="context-panel"
          >
            <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-3">
              <div>
                <h2 className="font-display text-lg font-bold text-white">Contexte & Analyse de candidature</h2>
                <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">CV · Offre · Site → CV ATS · Score · Lacunes</p>
              </div>
              <button onClick={onClose} data-testid="context-close-btn" className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="grid flex-1 grid-cols-1 overflow-hidden lg:grid-cols-2">
              {/* LEFT — inputs */}
              <div className="space-y-5 overflow-y-auto border-white/[0.06] px-6 py-5 lg:border-r">
                <Group icon={<FileText className="h-4 w-4" />} label="Titre de la session">
                  <input data-testid="ctx-title" value={form.title} onChange={(e) => field("title", e.target.value)} className="input" placeholder="ex. Superviseur — Pratt & Whitney" />
                </Group>

                <Group icon={<FileText className="h-4 w-4" />} label="Profil candidat (CV actuel)">
                  <div className="mb-2 flex items-center gap-2">
                    <button type="button" data-testid="import-pdf-btn" onClick={() => pdfRef.current?.click()} disabled={importing}
                      className="flex items-center gap-2 rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-3 py-1.5 text-xs font-semibold text-indigo-200 hover:bg-indigo-500/20 disabled:opacity-50">
                      {importing ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Upload className="h-3.5 w-3.5" />}
                      {importing ? "Lecture du PDF…" : "Importer un PDF (CV)"}
                    </button>
                    <span className="text-[11px] text-slate-500">ou collez le texte</span>
                    <input ref={pdfRef} type="file" accept=".pdf,application/pdf" className="hidden" onChange={importPdf} data-testid="pdf-input" />
                  </div>
                  <textarea data-testid="ctx-cv" value={form.cv} onChange={(e) => field("cv", e.target.value)} rows={6} className="input resize-y" placeholder="Expérience, compétences, outils…" />
                </Group>

                <Group icon={<Briefcase className="h-4 w-4" />} label="Poste (offre d'emploi)">
                  <textarea data-testid="ctx-poste" value={form.poste} onChange={(e) => field("poste", e.target.value)} rows={5} className="input resize-y" placeholder="Intitulé, missions clés, exigences…" />
                </Group>

                <Group icon={<Building2 className="h-4 w-4" />} label="Site entreprise (optionnel)">
                  <div className="flex items-center gap-2 rounded-lg border border-white/10 bg-black/40 px-2.5 py-1.5">
                    <Globe className="h-3.5 w-3.5 shrink-0 text-indigo-400" />
                    <input data-testid="company-url-input" value={companyUrl} onChange={(e) => setCompanyUrl(e.target.value)}
                      onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); runAnalysis(); } }}
                      placeholder="https://careers.exemple.com …" className="flex-1 bg-transparent text-sm text-slate-100 outline-none placeholder:text-slate-600" />
                  </div>
                </Group>

                <button type="button" data-testid="analyze-company-btn" onClick={runAnalysis} disabled={analyzing}
                  className="flex w-full items-center justify-center gap-2 rounded-xl border border-emerald-500/40 bg-emerald-500/15 px-4 py-2.5 text-sm font-semibold text-emerald-100 hover:bg-emerald-500/25 disabled:opacity-50">
                  {analyzing ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  {analyzing ? "Analyse en cours…" : "Analyser (CV + offre + site)"}
                </button>
                <p className="text-[11px] text-slate-500">Génère à droite un CV optimisé ATS, un score de compatibilité, les lacunes, 5 mots-clés manquants et les signaux d'alerte. Le CV amélioré est ensuite utilisé pour tes réponses STAR en entretien.</p>

                <Group icon={<Layers className="h-4 w-4" />} label="Secteur">
                  <div className="flex flex-wrap gap-2">
                    {SECTEURS.map((sec) => (
                      <button key={sec} data-testid={`ctx-secteur-${sec}`} onClick={() => field("secteur", sec)}
                        className={`rounded-lg border px-3 py-1.5 text-sm transition-all ${form.secteur === sec ? "border-indigo-500/60 bg-indigo-500/15 text-indigo-200" : "border-white/10 bg-white/[0.03] text-slate-400 hover:text-white"}`}>
                        {sec}
                      </button>
                    ))}
                  </div>
                </Group>

                <Group icon={<Building2 className="h-4 w-4" />} label="Info entreprise (valeurs, questions probables)">
                  <textarea data-testid="ctx-entreprise" value={form.entreprise} onChange={(e) => field("entreprise", e.target.value)} rows={4} className="input resize-y" placeholder="Rempli automatiquement par l'analyse du site…" />
                </Group>
              </div>

              {/* RIGHT — analysis results */}
              <div className="space-y-5 overflow-y-auto bg-black/20 px-6 py-5" data-testid="analysis-column">
                <div className="flex items-center justify-between">
                  <span className="flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-slate-400"><Gauge className="h-4 w-4 text-emerald-400" /> Score de compatibilité</span>
                  <span data-testid="ats-score" className={`font-display text-3xl font-black ${scoreColor}`}>{form.score == null ? "—" : `${form.score}/100`}</span>
                </div>

                <Group icon={<Target className="h-4 w-4" />} label="CV optimisé ATS (modifiable — rectifie les chiffres)">
                  <textarea data-testid="ats-cv" value={form.atsCv} onChange={(e) => field("atsCv", e.target.value)} rows={14} className="input resize-y font-mono text-[12.5px] leading-relaxed" placeholder="Clique « Analyser » pour générer un CV optimisé ATS avec des réalisations chiffrées. Les valeurs [à confirmer] sont à rectifier." />
                  <button
                    data-testid="download-ats-word-btn"
                    onClick={async () => {
                      if (!form.atsCv.trim()) { toast.error("Aucun CV ATS à télécharger — lance d'abord l'analyse."); return; }
                      try {
                        const name = (form.title || form.poste || "CV").replace(/[^\w\s-]/g, "").trim().replace(/\s+/g, "-").slice(0, 40) || "CV";
                        await downloadAtsCvDocx(form.atsCv, `CV-ATS-${name}.docx`);
                        toast.success("CV Word téléchargé.");
                      } catch (e) { toast.error("Export Word impossible : " + (e.message || e)); }
                    }}
                    disabled={!form.atsCv.trim()}
                    className="mt-2 flex items-center gap-2 rounded-lg border border-sky-500/40 bg-sky-500/10 px-3 py-2 text-xs font-semibold text-sky-200 transition-colors hover:bg-sky-500/20 disabled:opacity-40"
                  >
                    <FileDown className="h-4 w-4" /> Télécharger en Word (mis en forme, ~2 pages)
                  </button>
                </Group>

                <Group icon={<KeyRound className="h-4 w-4" />} label="5 mots-clés manquants">
                  <div className="flex flex-wrap gap-2" data-testid="missing-keywords">
                    {(form.missingKeywords || []).length === 0 ? <span className="text-[12px] text-slate-600">—</span> :
                      form.missingKeywords.map((k, i) => (
                        <span key={i} className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1 text-xs text-amber-200">{k}</span>
                      ))}
                  </div>
                </Group>

                <Group icon={<AlertTriangle className="h-4 w-4" />} label="Signaux d'alerte (vus par un recruteur)">
                  <ul className="space-y-1.5" data-testid="red-flags">
                    {(form.redFlags || []).length === 0 ? <li className="text-[12px] text-slate-600">—</li> :
                      form.redFlags.map((r, i) => (
                        <li key={i} className="flex gap-2 text-[13px] text-rose-200"><AlertTriangle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-rose-400" />{r}</li>
                      ))}
                  </ul>
                </Group>

                <Group icon={<Briefcase className="h-4 w-4" />} label="Lacunes vs l'offre">
                  <ul className="space-y-1.5" data-testid="gaps-list">
                    {(form.gaps || []).length === 0 ? <li className="text-[12px] text-slate-600">—</li> :
                      form.gaps.map((g, i) => (
                        <li key={i} className="flex gap-2 text-[13px] text-slate-300"><span className="text-slate-500">•</span>{g}</li>
                      ))}
                  </ul>
                </Group>
              </div>
            </div>

            <div className="flex justify-end gap-3 border-t border-white/[0.06] px-6 py-3">
              <button onClick={onClose} className="rounded-xl px-4 py-2 text-sm text-slate-400 hover:text-white">Annuler</button>
              <button onClick={() => onSave(form)} data-testid="context-save-btn"
                className="flex items-center gap-2 rounded-xl bg-indigo-500 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 hover:bg-indigo-400">
                <Save className="h-4 w-4" /> Enregistrer
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
      <style>{`.input{width:100%;border-radius:0.75rem;border:1px solid var(--border);background:rgba(9,10,15,0.6);padding:0.6rem 0.8rem;font-size:0.9rem;color:var(--fg);outline:none;transition:border-color .15s}.input:focus{border-color:rgba(99,102,241,0.6)}`}</style>
    </AnimatePresence>
  );
}

function Group({ icon, label, children }) {
  return (
    <div>
      <label className="mb-2 flex items-center gap-2 font-mono text-[11px] uppercase tracking-widest text-slate-400">
        <span className="text-indigo-400">{icon}</span>
        {label}
      </label>
      {children}
    </div>
  );
}
