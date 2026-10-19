import { ConceptRow } from "@/components/careeros/guide/InfoTip";
import { useEffect, useState } from "react";
import { Loader2, Save } from "lucide-react";
import { toast } from "sonner";
import { Shell } from "@/components/careeros/Shell";
import { GoalsSelect } from "@/components/careeros/GoalsSelect";
import { careeros } from "@/lib/careeros";
import { usePageTitle } from "@/components/careeros/ThemeToggle";
import { SharingPanel } from "@/components/careeros/SharingPanel";
import { SkillMap } from "@/components/careeros/SkillMap";
import { Foldable } from "@/components/careeros/Foldable";
import { ProStrength } from "@/components/careeros/ProStrength";
import { SkillCompare } from "@/components/careeros/SkillCompare";

const inputCls = "w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white outline-none focus:border-indigo-400/60";
const TEXT = [["full_name", "Nom complet"], ["headline", "Titre professionnel"], ["location", "Localisation"], ["country", "Pays"], ["province", "Province / région"], ["city", "Ville"], ["target_roles", "Postes visés"], ["sectors", "Secteurs visés"], ["salary_expectation", "Attentes salariales"]];
const LISTS = [["skills", "Compétences"], ["certifications", "Certifications"], ["education", "Formations"], ["languages", "Langues"]];

export default function Profile() {
  usePageTitle("Career Memory");
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
      window.dispatchEvent(new Event("careeros:journey"));
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };

  return (
    <Shell>
      <div className="mb-8 flex flex-wrap items-end justify-between gap-4">
        <div>
          <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-indigo-300">Profil carrière vivant</p>
          <h1 className="mt-2 font-display text-4xl font-bold tracking-tight sm:text-5xl">Career Memory</h1>
          <p className="mt-2 text-sm text-slate-400">CareerOS utilise ce profil pour chaque décision et chaque document.</p>
          <ConceptRow keys={["memory", "career_score"]} />
        </div>
        <button onClick={save} disabled={busy} data-testid="save-profile-btn" className="flex items-center gap-2 rounded-full bg-indigo-500 px-5 py-2.5 text-sm font-semibold text-white hover:bg-indigo-400 disabled:opacity-60">
          {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />} Enregistrer
        </button>
      </div>
      <div className="grid gap-6 lg:grid-cols-2">
        <section className="space-y-4">
          <div>
            <p className="mb-2 text-xs font-medium text-slate-300">Objectifs de carrière</p>
            <GoalsSelect options={goals} value={p.goals || []} onToggle={toggleGoal} onClear={() => setP({ ...p, goals: [] })} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            {TEXT.map(([k, l]) => <label key={k}><span className="mb-1 block text-xs text-slate-400">{l}</span><input value={p[k] || ""} onChange={set(k)} className={inputCls} data-testid={`profile-${k}-input`} /></label>)}
          </div>
          <p className="text-[11px] text-slate-500" data-testid="profile-geo-note">Pays, province et ville restent modifiables. Ils servent au Radar et, uniquement de façon agrégée et anonyme, aux statistiques CareerOS.</p>
          {LISTS.map(([k, l]) => <label key={k} className="block"><span className="mb-1 block text-xs text-slate-400">{l} (séparées par des virgules)</span><input defaultValue={(p[k] || []).join(", ")} onBlur={setList(k)} className={inputCls} data-testid={`profile-${k}-input`} /></label>)}
          <label className="block"><span className="mb-1 block text-xs text-slate-400">Promotions obtenues (12 derniers mois)</span><input type="number" min={0} max={50} value={p.promotions || 0} onChange={(e) => setP({ ...p, promotions: Math.max(0, Number(e.target.value) || 0) })} className={inputCls} data-testid="profile-promotions-input" /></label>
          <label className="block"><span className="mb-1 block text-xs text-slate-400">Réalisations clés</span><textarea rows={4} value={p.achievements || ""} onChange={set("achievements")} className={inputCls} data-testid="profile-achievements-input" /></label>
          {(p.skills_detected || []).length > 0 && (
            <Foldable storageKey="cos.profile.skills.open" title="Compétences détectées automatiquement par CareerOS" hint={`${p.skills_detected.length} compétences`} testid="skills-detected">
              <div className="flex flex-wrap gap-1.5">{p.skills_detected.map((s) => <span key={s} className="rounded-md bg-emerald-500/10 px-2 py-1 text-xs text-emerald-300">{s}</span>)}</div>
            </Foldable>
          )}
        </section>
        <section>
          <Foldable storageKey="cos.profile.cv.open" initial={!(p.cv_text || "").trim()} title="CV maître (collez ici votre CV complet : il sert de base à chaque pack)" hint={`${(p.cv_text || "").length.toLocaleString("fr-CA")} caractères`} testid="profile-cv-block">
            <textarea rows={26} value={p.cv_text || ""} onChange={set("cv_text")} className={`${inputCls} font-mono text-xs`} data-testid="profile-cv-input" aria-label="CV maître" />
          </Foldable>
          <SkillMap profile={p} />
          <SkillCompare profile={p} />
          <ProStrength refreshKey={p.updated_at} />
        </section>
      </div>
      <SharingPanel />
    </Shell>
  );
}
