// CV <-> offer optimisation helpers (rules, free): payload for the server, CV assembly, diff, impact breakdown.
import { DOMAINS, N, buildSkillMap } from "@/lib/skillMap";
import { compareSkills } from "@/lib/skillMatch";

const KEY_LINE = "Compétences clés pour ce poste : ";
const EXTRA_LINE = "Compétences complémentaires : ";

export const jobPayload = (r) => r.job.map((s) => ({ label: s.label, aliases: s.aliases, status: s.status, weight: s.weight,
  domain_keys: (DOMAINS.find(([n]) => n === s.domain) || [null, []])[1] }));

// Original CV wording for an alias (same-length normalisation so the slice maps back to the CV text).
const flat = (s) => s.normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9+#]/g, " ");
export const cvWord = (cv, alias) => {
  const src = String(cv || "").normalize("NFC"), f = flat(src), a = alias.trim();
  const i = ` ${f}`.indexOf(` ${a}`);
  if (i < 0 || !a) return "";
  let j = i + a.length; while (j < f.length && /[a-z0-9]/.test(f[j])) j += 1;
  return src.slice(i, j);
};

// Guaranteed rule-based highlight: job skills already proven in the CV, in the CV's own words, gathered near the top.
export const keySkillsItem = (r, cv) => {
  const words = r.job.filter((s) => s.status === "ok" && ["skill", "tool"].includes(s.cat)).sort((a, b) => b.weight - a.weight)
    .map((s) => s.aliases.map((a) => cvWord(cv, a)).find(Boolean)).filter(Boolean);
  const ok = [...new Map(words.map((w) => [N(w), w.charAt(0).toUpperCase() + w.slice(1)])).values()].slice(0, 8);
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
// Evidence = the original CV line (never the name/title line), shortened, one per line.
const evidence = (cv, keys) => {
  const lines = String(cv || "").split("\n").map((l) => l.trim()).filter(Boolean).slice(2).filter((l) => !(/\b(19|20)\d{2}\b|aujourd/i.test(l) && l.length < 90));
  return [...new Set(lines.filter((l) => keys.some((k) => ` ${N(l)} `.includes(` ${k}`))).map((l) => l.replace(/^[-•*●▪–]\s*/, "").replace(/\.$/, "")))]
    .slice(0, 3).map((l) => (l.length > 70 ? `${l.slice(0, 67)}…` : l));
};

// Skills of the offer not proven in the CV: never added unless the member confirms them.
export const toConfirm = (r, profile, covered) => {
  const mine = buildSkillMap(profile);
  return r.gaps.filter((s) => !covered.has(s.label)).slice(0, 10).map((s) => {
    const g = mine.find((d) => d.name === s.domain);
    const ev = evidence(profile.cv_text, RELATED[s.label] || []);
    const related = ev.length ? ev : (g?.skills || []).slice(0, 3).map((x) => x.label);
    const confidence = ev.length >= 2 ? "élevée" : ev.length || s.status === "partiel" ? "moyenne" : "faible";
    return { id: `c:${s.label}`, type: "a_confirmer", label: s.label, required: s.required, confidence, related, domain: s.domain, after: s.label };
  });
};

// After the name/title block: before the first section header, else after the 2nd non-empty line.
const keyAt = (lines) => {
  const ne = lines.map((l, i) => [l.trim(), i]).filter(([l]) => l);
  const hdr = ne.find(([l], k) => k > 0 && l.length < 40 && l === l.toUpperCase() && /[A-ZÀ-Ý]{4}/.test(l));
  return hdr ? hdr[1] : (ne[1] ? ne[1][1] + 1 : lines.length);
};

export const buildCv = (cv, items, sel) => {
  const lines = cv.split("\n");
  items.filter((x) => x.type === "reformulation" && sel.has(x.id)).forEach((x) => { lines[x.line] = lines[x.line].replace(x.before.trim(), x.after.trim()); });
  const key = items.find((x) => x.id === "key" && sel.has(x.id));
  if (key) lines.splice(keyAt(lines), 0, key.after);
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
  if (key) rows.splice(keyAt(before), 0, { tag: "added", text: key.after });
  const extra = items.filter((x) => x.type === "a_confirmer" && sel.has(x.id)).map((x) => x.label);
  if (extra.length) rows.push({ tag: "added", text: EXTRA_LINE + extra.join(" · ") });
  return rows;
};

export const matchOf = (profile, cv, offer) => compareSkills({ ...profile, cv_text: cv }, offer.text, offer.title).score;
export const coveredBy = (items) => new Set(items.filter((x) => x.type === "reformulation").flatMap((x) => x.skills || []));
export const isNorm = (a, b) => N(a) === N(b);
