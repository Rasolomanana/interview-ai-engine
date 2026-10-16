// Deterministic skill grouping (free, instant): domain keywords, near-duplicate merge, weight = mentions in CV + Career Memory.
const N = (s) => (s || "").normalize("NFKD").replace(/[\u0300-\u036f]/g, "").toLowerCase().replace(/[^a-z0-9+#]+/g, " ").trim();

export const DOMAINS = [
  ["Données et analyse", ["donnee", "data", "analyse", "analyt", "power bi", "dax", "sql", "python", "tableau de bord", "dashboard", "reporting", "rapport", "statisti", "bi ", "kpi", "excel avance", "modelis"], "#06b6d4"],
  ["Gestion de projet", ["projet", "partie prenante", "parties prenantes", "stakeholder", "agile", "scrum", "pmp", "changement", "deploiement", "jalons"], "#8b5cf6"],
  ["Finance et budget", ["budget", "financ", "comptab", "cout", "rentabilit", "factur", "prevision"], "#eab308"],
  ["Technologies et développement", ["developp", "programm", "cloud", "azure", "aws", "java", "api", "automatis", "devops", "reseau", "cyber"], "#3b82f6"],
  ["Ressources humaines", ["recrut", "rh ", "ressources humaines", "paie", "formation du personnel", "onboard", "talent"], "#f97316"],
  ["Marketing et ventes", ["marketing", "vente", "commercial", "seo", "campagne", "marque", "prospect"], "#d946ef"],
  ["Santé et sécurité", ["sst", "cnesst", "securit", "secours", "soins", "prevention", "urgence", "incident", "risque", "ergonom"], "#f43f5e"],
  ["Conformité et qualité", ["sqf", "conformit", "qualit", "norme", "iso", "haccp", "audit", "politique", "procedure", "rigueur"], "#a855f7"],
  ["Leadership", ["supervis", "encadr", "leadership", "equipe", "discipline", "gestion de personnel", "mentor", "coach", "motiv", "multiculturel"], "#6366f1"],
  ["Logistique", ["logisti", "reception", "expedition", "entrepos", "inventaire", "stock", "flux", "repartition", "chariot", "manutention"], "#10b981"],
  ["Transport", ["transport", "livraison", "route", "flotte", "camion", "dispatch", "geobus", "chauffeur"], "#0ea5e9"],
  ["Distribution", ["distribution", "centre de distribution", "approvisionnement", "chaine", "supply"], "#14b8a6"],
  ["Gestion des opérations", ["operation", "quart", "priorit", "planif", "coordination", "production", "amelioration", "kpi", "performance", "imprevu", "resolution"], "#f59e0b"],
  ["Logiciels et outils", ["logiciel", "oracle", "progression", "horasphere", "dayforce", "jira", "excel", "sap", "erp", "wms", "office", "progiciel", "microsoft"], "#0284c7"],
  ["Langues et communication", ["bilingu", "francais", "anglais", "communication", "langue", "redaction"], "#ec4899"],
  ["Service client", ["client", "service", "relation"], "#84cc16"],
  ["Certifications", ["certif", "pl 300", "attestation", "diplom"], "#22c55e"],
];
const OTHER = ["Autres compétences", [], "#64748b"];

const tokens = (s) => new Set(N(s).split(" ").filter((t) => t.length > 2));
const jaccard = (a, b) => { const x = tokens(a), y = tokens(b); const i = [...x].filter((t) => y.has(t)).length; return x.size && y.size ? i / (x.size + y.size - i) : 0; };

export const buildSkillMap = (p) => {
  const raw = [...(p.skills_detected || []), ...(p.skills || []), ...(p.certifications || [])].map((s) => String(s).trim()).filter(Boolean);
  const merged = [];
  raw.forEach((s) => {
    const twin = merged.find((m) => jaccard(m.label, s) >= 0.6 || N(m.label) === N(s));
    if (twin) { twin.variants.push(s); if (s.length > twin.label.length) twin.label = s; } else merged.push({ label: s, variants: [s] });
  });
  const corpus = N([p.cv_text, p.achievements, p.headline, p.target_roles, (p.goals || []).join(" ")].join(" "));
  const count = (k) => (k ? corpus.split(k).length - 1 : 0);
  const groups = new Map();
  merged.forEach((m) => {
    const n = ` ${N(m.variants.join(" "))} `;
    const dom = DOMAINS.find(([, keys]) => keys.some((k) => n.includes(k))) || OTHER;
    const mentions = Math.min(10, [...tokens(m.label)].reduce((a, t) => a + Math.min(3, count(t)), 0));
    const weight = m.variants.length + mentions;
    if (!groups.has(dom[0])) groups.set(dom[0], { name: dom[0], color: dom[2], weight: 0, skills: [] });
    const g = groups.get(dom[0]);
    g.weight += weight;
    g.skills.push({ label: m.label, weight, variants: m.variants.length, mentions });
  });
  return [...groups.values()].map((g) => ({ ...g, skills: g.skills.sort((a, b) => b.weight - a.weight) })).sort((a, b) => b.weight - a.weight);
};
