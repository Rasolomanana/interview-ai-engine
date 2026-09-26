import { useState, useEffect } from "react";
import { motion, AnimatePresence } from "framer-motion";
import { X, FileText, Briefcase, Building2, Layers, Save } from "lucide-react";

const SECTEURS = ["Logistique", "Tech", "Finance", "Autre"];

export default function ContextPanel({ open, session, onClose, onSave }) {
  const [form, setForm] = useState({ title: "", cv: "", poste: "", entreprise: "", secteur: "Autre" });

  useEffect(() => {
    if (session) {
      setForm({
        title: session.title || "",
        cv: session.context?.cv || "",
        poste: session.context?.poste || "",
        entreprise: session.context?.entreprise || "",
        secteur: session.context?.secteur || "Autre",
      });
    }
  }, [session, open]);

  const field = (key, val) => setForm((f) => ({ ...f, [key]: val }));

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}
        >
          <div className="absolute inset-0 bg-black/70 backdrop-blur-sm" onClick={onClose} />
          <motion.div
            initial={{ opacity: 0, y: 24, scale: 0.97 }}
            animate={{ opacity: 1, y: 0, scale: 1 }}
            exit={{ opacity: 0, y: 24, scale: 0.97 }}
            className="glass relative z-10 flex max-h-[88vh] w-full max-w-2xl flex-col overflow-hidden rounded-2xl"
            data-testid="context-panel"
          >
            <div className="flex items-center justify-between border-b border-white/[0.06] px-6 py-4">
              <div>
                <h2 className="font-display text-lg font-bold text-white">Contexte de session</h2>
                <p className="font-mono text-[10px] uppercase tracking-widest text-slate-500">Injecté à chaque tour · BLOC 2.2</p>
              </div>
              <button onClick={onClose} data-testid="context-close-btn" className="rounded-lg p-2 text-slate-400 hover:bg-white/5 hover:text-white">
                <X className="h-5 w-5" />
              </button>
            </div>

            <div className="space-y-5 overflow-y-auto px-6 py-5">
              <Group icon={<FileText className="h-4 w-4" />} label="Titre de la session">
                <input
                  data-testid="ctx-title"
                  value={form.title}
                  onChange={(e) => field("title", e.target.value)}
                  className="input"
                  placeholder="ex. Simulation Lead Dev — Acme"
                />
              </Group>

              <Group icon={<FileText className="h-4 w-4" />} label="Profil candidat (CV)">
                <textarea data-testid="ctx-cv" value={form.cv} onChange={(e) => field("cv", e.target.value)} rows={4} className="input resize-none" placeholder="Expérience, compétences, outils maîtrisés…" />
              </Group>

              <Group icon={<Briefcase className="h-4 w-4" />} label="Poste (fiche, missions, exigences)">
                <textarea data-testid="ctx-poste" value={form.poste} onChange={(e) => field("poste", e.target.value)} rows={3} className="input resize-none" placeholder="Intitulé, missions clés, stack requise…" />
              </Group>

              <Group icon={<Building2 className="h-4 w-4" />} label="Info entreprise & actualité">
                <textarea data-testid="ctx-entreprise" value={form.entreprise} onChange={(e) => field("entreprise", e.target.value)} rows={3} className="input resize-none" placeholder="Culture, produits, concurrents, actus récentes…" />
              </Group>

              <Group icon={<Layers className="h-4 w-4" />} label="Secteur">
                <div className="flex flex-wrap gap-2">
                  {SECTEURS.map((sec) => (
                    <button
                      key={sec}
                      data-testid={`ctx-secteur-${sec}`}
                      onClick={() => field("secteur", sec)}
                      className={`rounded-lg border px-3 py-1.5 text-sm transition-all ${
                        form.secteur === sec
                          ? "border-indigo-500/60 bg-indigo-500/15 text-indigo-200"
                          : "border-white/10 bg-white/[0.03] text-slate-400 hover:text-white"
                      }`}
                    >
                      {sec}
                    </button>
                  ))}
                </div>
              </Group>
            </div>

            <div className="flex justify-end gap-3 border-t border-white/[0.06] px-6 py-4">
              <button onClick={onClose} className="rounded-xl px-4 py-2 text-sm text-slate-400 hover:text-white">Annuler</button>
              <button
                onClick={() => onSave(form)}
                data-testid="context-save-btn"
                className="flex items-center gap-2 rounded-xl bg-indigo-500 px-5 py-2 text-sm font-semibold text-white shadow-lg shadow-indigo-500/30 transition-all hover:bg-indigo-400"
              >
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
