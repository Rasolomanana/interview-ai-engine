// CV <-> offer optimisation helpers (rules, free): payload for the server, CV assembly, diff, impact breakdown.
import { DOMAINS, N, buildSkillMap } from "@/lib/skillMap";
import { compareSkills } from "@/lib/skillMatch";

const KEY_LINE = "Compétences clés pour ce poste : ";
const EXTRA_LINE = "Compétences complémentaires : ";

export const jobPayload = (r) => r.job.map((s) => ({ label: s.label, aliases: s.aliases, status: s.status, weight: s.weight,
  domain_keys: (DOMAINS.find(([n]) => n === s.domain) || [null, []])[1] }));

// Guaranteed rule-based highlight: job skills already proven in the CV, gathered in one line near the top.
export const keySkillsItem = (r, cv) => {
  const ok = r.job.filter((s) => s.status === "ok").sort((a, b) => b.weight - a.weight).slice(0, 8).map((s) => s.label);
  if (ok.length < 2 || cv.includes(KEY_LINE)) return null;
  return { id: "key", type: "ajout", after: KEY_LINE + ok.join(" · "), skills: ok, reason: "Ces compétences demandées par l'offre sont déjà prouvées dans votre CV : les regrouper en haut les rend visibles du recruteur et des logiciels de tri (ATS)." };
};

// Practices that, when present in the CV, make a missing skill plausible (evidence shown to the member, never added automatically).
const RELATED = {
  "Amélioration continue": ["optimisation", "optimise", "processus", "reduction des pertes", "pertes", "efficacite", "gaspillage", "5s", "kaizen"],
  "Lean Six Sigma": ["amelioration continue", "optimisation", "processus", "reduction des pertes", "pertes", "gaspillage", "5s", "kaizen"],
  "Indicateurs de performance (KPI)": ["indicateurs", "rendement", "performance", "tableau de bord", "tableaux de bord", "objectifs"],
  "Santé et sécurité au travail (SST)": ["securite", "accident", "prevention", "epi", "risque"],
  "Gestion du personnel": ["equipe", "employes", "supervis", "encadr"], "Leadership": ["supervis", "encadr", "equipe", "chef d equipe"],
  "Coaching et formation des employés": ["formation", "former", "accueil des nouveaux", "integration"],
  "Gestion budgétaire": ["budget", "couts", "depenses"], "Contrôle des coûts": ["couts", "budget", "reduction", "pertes"],
  "Gestion de projet": ["projet", "implantation", "deploiement", "migration"], "Analyse de données": ["donnees", "rapports", "tableaux de bord", "excel"],
};
const snippet = (cv, key) => { const m = ` ${N(cv)} `.match(new RegExp(` ((?:[a-z0-9]+ ){0,2}${key.trim().replace(/\s+/g, " ")}[a-z0-9]*(?: [a-z0-9]+){0,2}) `)); return m ? m[1] : ""; };

// Skills of the offer not proven in the CV: never added unless the member confirms them.
export const toConfirm = (r, profile, covered) => {
  const mine = buildSkillMap(profile);
  return r.gaps.filter((s) => !covered.has(s.label)).slice(0, 10).map((s) => {
    const g = mine.find((d) => d.name === s.domain);
    const ev = [...new Set((RELATED[s.label] || []).map((k) => snippet(profile.cv_text || "", k)).filter(Boolean))].slice(0, 3);
    const related = ev.length ? ev : (g?.skills || []).slice(0, 3).map((x) => x.label);
    const confidence = s.status === "partiel" || ev.length >= 2 ? "élevée" : related.length ? "moyenne" : "faible";
    return { id: `c:${s.label}`, type: "a_confirmer", label: s.label, required: s.required, confidence, related, domain: s.domain, after: s.label };
  });
};

export const buildCv = (cv, items, sel) => {
  const lines = cv.split("\n");
  items.filter((x) => x.type === "reformulation" && sel.has(x.id)).forEach((x) => { lines[x.line] = lines[x.line].replace(x.before.trim(), x.after.trim()); });
  const key = items.find((x) => x.id === "key" && sel.has(x.id));
  if (key) { const at = Math.max(0, lines.findIndex((l) => l.trim())) + 1; lines.splice(at, 0, key.after); }
  const extra = items.filter((x) => x.type === "a_confirmer" && sel.has(x.id)).map((x) => x.label);
  if (extra.length) lines.push("", EXTRA_LINE + extra.join(" · "));
  return lines.join("\n");
};

// Rows of the optimised CV: same | improved (with previous text) | added.
export const diffRows = (cv, items, sel) => {
  const before = cv.split("\n");
  const after = buildCv(cv, items.filter((x) => x.type === "reformulation"), sel).split("\n");
  const rows = before.map((l, i) => (after[i] !== l ? { tag: "improved", text: after[i], prev: l } : { tag: "same", text: l }));
  const key = items.find((x) => x.id === "key" && sel.has(x.id));
  if (key) rows.splice(Math.max(0, before.findIndex((l) => l.trim())) + 1, 0, { tag: "added", text: key.after });
  const extra = items.filter((x) => x.type === "a_confirmer" && sel.has(x.id)).map((x) => x.label);
  if (extra.length) rows.push({ tag: "added", text: EXTRA_LINE + extra.join(" · ") });
  return rows;
};

export const matchOf = (profile, cv, offer) => compareSkills({ ...profile, cv_text: cv }, offer.text, offer.title).score;
export const coveredBy = (items) => new Set(items.filter((x) => x.type === "reformulation").flatMap((x) => x.skills || []));
export const isNorm = (a, b) => N(a) === N(b);
