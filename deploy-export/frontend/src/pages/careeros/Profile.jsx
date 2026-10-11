import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { Shell } from "@/components/careeros/Shell";
import { careeros } from "@/lib/careeros";

const inputCls = "w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white outline-none focus:border-indigo-400/60";
const TEXT = [["full_name", "Nom complet"], ["headline", "Titre professionnel"], ["location", "Localisation"], ["target_roles", "Postes visés"], ["sectors", "Secteurs visés"], ["salary_expectation", "Attentes salariales"]];
const LISTS = [["skills", "Compétences"], ["certifications", "Certifications"], ["education", "Formations"], ["languages", "Langues"]];

export default function Profile() {
  const [p, setP] = useState(null);
  const [goals, setGoals] = useState([]);
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    careeros.getProfile().then(setP).catch((e) => toast.error(e.message));
    careeros.meta().then((m) => setGoals(m.goals)).catch(() => {});
  }, []);
  if (!p) return <Shell><Loader2 className="h-5 w-5 animate-spin text-indigo-400" /></Shell>;

  const set = (k) => (e) => setP({ ...p, [k]: e.target.value });
  const setList = (k) => (e) => setP({ ...p, [k]: e.target.value.split(",").map((s) => s.trim()).filter(Boolean) });
  const toggleGoal = (g) => setP({ ...p, goals: p.goals?.includes(g) ? p.goals.filter((x) => x !== g) : [...(p.goals || []), g] });
  const save = async () => {
    setBusy(true);
    try {
      const { user_id, updated_at, skills_detected, ...body } = p;
      setP(await careeros.saveProfile(body));
      toast.success("Career Memory mise à jour");
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };

  return (
    <Shell>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-indigo-300">Profil carrière vivant</p>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl">Career Memory</h1>
          <p className="mt-2 text-sm text-slate-400">CareerOS utilise ce profil pour chaque décision et chaque document.</p>
        </div>
        <button onClick={save} disabled={busy} data-testid="save-profile-btn" className="flex items-center gap-2 rounded-full bg-indigo-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Enregistrer
        </button>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-4">
          <div>
            <p className="mb-2 text-xs font-medium text-slate-300">Objectifs de carrière</p>
            <div className="flex flex-wrap gap-2" data-testid="goals-list">
              {goals.map((g) => (
                <button key={g} type="button" onClick={() => toggleGoal(g)} data-testid={`goal-${g.replace(/[^a-z]/gi, "-")}`}
                  className={`rounded-full border px-3 py-1.5 text-xs transition-colors ${p.goals?.includes(g) ? "border-indigo-400/60 bg-indigo-500/15 text-white" : "border-white/10 text-slate-400 hover:text-white"}`}>{g}</button>
              ))}
            </div>
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {TEXT.map(([k, l]) => <label key={k}><span className="mb-1 block text-xs text-slate-400">{l}</span><input value={p[k] || ""} onChange={set(k)} className={inputCls} data-testid={`profile-${k}-input`} /></label>)}
          </div>
          {LISTS.map(([k, l]) => <label key={k} className="block"><span className="mb-1 block text-xs text-slate-400">{l} (séparées par des virgules)</span><input defaultValue={(p[k] || []).join(", ")} onBlur={setList(k)} className={inputCls} data-testid={`profile-${k}-input`} /></label>)}
          <label className="block"><span className="mb-1 block text-xs text-slate-400">Promotions obtenues (12 derniers mois)</span><input type="number" min={0} max={50} value={p.promotions || 0} onChange={(e) => setP({ ...p, promotions: Math.max(0, Number(e.target.value) || 0) })} className={inputCls} data-testid="profile-promotions-input" /></label>
          <label className="block"><span className="mb-1 block text-xs text-slate-400">Réalisations clés</span><textarea rows={4} value={p.achievements || ""} onChange={set("achievements")} className={inputCls} data-testid="profile-achievements-input" /></label>
          {(p.skills_detected || []).length > 0 && (
            <div data-testid="skills-detected">
              <p className="mb-2 text-xs text-slate-400">Compétences détectées automatiquement par CareerOS</p>
              <div className="flex flex-wrap gap-1.5">{p.skills_detected.map((s) => <span key={s} className="rounded-md bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300">{s}</span>)}</div>
            </div>
          )}
        </section>
        <section>
          <label className="block"><span className="mb-1 block text-xs text-slate-400">CV maître (utilisé par défaut dans chaque pack)</span>
            <textarea rows={26} value={p.cv_text || ""} onChange={set("cv_text")} className={`${inputCls} font-mono text-xs`} data-testid="profile-cv-input" /></label>
        </section>
      </div>
    </Shell>
  );
}
