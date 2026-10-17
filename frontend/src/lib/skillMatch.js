// Rule-based CV vs job skill comparison (free, instant). Domains = the same as the CV skill map.
import { DOMAINS, N, OTHER, buildSkillMap } from "@/lib/skillMap";

// [label, category, aliases (normalised)]
const LEX = [
  ["Supervision d'équipe", "skill", ["supervis", "superviseur", "encadrement", "encadrer", "team lead", "chef d equipe"]],
  ["Leadership", "skill", ["leadership", "leader"]],
  ["Gestion du personnel", "skill", ["gestion du personnel", "gestion de personnel", "gestion des employes", "people management"]],
  ["Coaching et formation des employés", "skill", ["coach", "former les", "formation des employes", "mentor", "training"]],
  ["Relations de travail / milieu syndiqué", "skill", ["syndic", "convention collective", "relations de travail", "union"]],
  ["Gestion des opérations", "skill", ["gestion des operations", "operations management", "operations"]],
  ["Planification et ordonnancement", "skill", ["planification", "planifier", "ordonnancement", "scheduling", "horaires"]],
  ["Gestion de quarts", "skill", ["quart", "shift"]],
  ["Amélioration continue", "skill", ["amelioration continue", "continuous improvement", "kaizen", "5s"]],
  ["Indicateurs de performance (KPI)", "skill", ["kpi", "indicateurs de performance", "indicateurs", "performance metrics"]],
  ["Résolution de problèmes", "skill", ["resolution de problemes", "problem solving", "resoudre"]],
  ["Gestion des priorités", "skill", ["priorit"]],
  ["Logistique", "skill", ["logistique", "logistics"]],
  ["Réception et expédition", "skill", ["reception", "expedition", "shipping", "receiving"]],
  ["Gestion d'entrepôt", "skill", ["entrepot", "warehouse", "entreposage"]],
  ["Gestion des stocks et inventaires", "skill", ["inventaire", "stocks", "inventory"]],
  ["Chaîne d'approvisionnement", "skill", ["chaine d approvisionnement", "supply chain", "approvisionnement"]],
  ["Distribution", "skill", ["distribution", "centre de distribution", "distribution center"]],
  ["Transport et livraison", "skill", ["transport", "livraison", "delivery", "dernier kilometre", "last mile"]],
  ["Répartition / dispatch", "skill", ["repartition", "dispatch", "repartiteur"]],
  ["Gestion de flotte", "skill", ["flotte", "fleet"]],
  ["Chariot élévateur", "cert", ["chariot elevateur", "cariste", "forklift"]],
  ["Santé et sécurité au travail (SST)", "skill", ["sst", "sante et securite", "health and safety", "securite au travail"]],
  ["CNESST", "skill", ["cnesst", "csst"]],
  ["Premiers secours", "cert", ["premiers secours", "premier secours", "premiers soins", "first aid", "secouriste"]],
  ["Prévention des incidents", "skill", ["prevention", "incident", "enquete d accident"]],
  ["SIMDUT / WHMIS", "cert", ["simdut", "whmis"]],
  ["Conformité et normes", "skill", ["conformite", "compliance", "normes", "reglementation"]],
  ["Assurance qualité", "skill", ["assurance qualite", "controle qualite", "quality assurance", "qualite"]],
  ["SQF / HACCP", "cert", ["sqf", "haccp", "salubrite"]],
  ["ISO", "cert", ["iso 9001", "iso 14001", "iso 45001", "norme iso", "normes iso"]],
  ["Lean Six Sigma", "cert", ["lean", "six sigma", "green belt", "yellow belt"]],
  ["Gestion de projet", "skill", ["gestion de projet", "project management", "chargé de projet", "charge de projet"]],
  ["PMP / CAPM", "cert", ["pmp", "capm"]],
  ["Agile / Scrum", "skill", ["agile", "scrum", "kanban"]],
  ["Gestion du changement", "skill", ["gestion du changement", "change management"]],
  ["Gestion budgétaire", "skill", ["budget", "budgetaire", "budgeting"]],
  ["Contrôle des coûts", "skill", ["controle des couts", "reduction des couts", "cost control", "couts"]],
  ["Analyse de données", "skill", ["analyse de donnees", "data analysis", "analytique", "analytics"]],
  ["Reporting et tableaux de bord", "skill", ["reporting", "tableau de bord", "tableaux de bord", "dashboard", "rapports"]],
  ["Service à la clientèle", "skill", ["service a la clientele", "service client", "customer service", "relation client"]],
  ["Communication", "skill", ["communication", "communiquer"]],
  ["Travail d'équipe", "skill", ["travail d equipe", "esprit d equipe", "teamwork", "collaboration"]],
  ["Gestion des conflits", "skill", ["gestion des conflits", "conflict"]],
  ["Recrutement et intégration", "skill", ["recrutement", "embauche", "onboarding", "integration des employes"]],
  ["Bilinguisme français / anglais", "lang", ["bilingue", "bilinguisme", "francais et anglais", "anglais", "english", "bilingual"]],
  ["Microsoft Excel", "tool", ["excel"]],
  ["Suite Microsoft Office", "tool", ["microsoft office", "suite office", "office 365", "microsoft 365", "word", "outlook"]],
  ["Power BI", "tool", ["power bi"]],
  ["SQL", "tool", ["sql"]],
  ["SAP", "tool", ["sap"]],
  ["Oracle", "tool", ["oracle"]],
  ["WMS (système de gestion d'entrepôt)", "tool", ["wms", "systeme de gestion d entrepot", "manhattan", "blue yonder"]],
  ["ERP", "tool", ["erp", "progiciel de gestion"]],
  ["Dayforce / Kronos / UKG", "tool", ["dayforce", "kronos", "ukg", "horasphere"]],
  ["Jira", "tool", ["jira"]],
  ["Python", "tool", ["python"]],
  ["Salesforce", "tool", ["salesforce"]],
  ["Permis de conduire", "cert", ["permis de conduire", "permis classe", "driver s license", "driver license"]],
  ["Diplôme d'études collégiales / universitaires", "cert", ["dec ", "baccalaureat", "bachelor", "diplome", "degree", "aec "]],
];
const DESIRED = /\b(atout|souhait|un plus|serait un|seraient un|preferred|nice to have|asset|ideal|idealement|bonus)\b/;

const domainOf = (label, aliases) => (DOMAINS.find(([, keys]) => keys.some((k) => ` ${N(`${label} ${aliases.join(" ")}`)} `.includes(k))) || OTHER);
const W = (a) => ` ${a}`; // aliases match from a word start ("lean" ≠ "clean")
const count = (t, a) => (a.trim() ? t.split(W(a)).length - 1 : 0);

export const extractJobSkills = (text, title = "") => {
  const t = ` ${N(text)} `, tt = ` ${N(title)} `;
  const sentences = String(text || "").split(/[.\n;•●▪\-–]\s*/).map((s) => ` ${N(s)} `);
  return LEX.map(([label, cat, aliases]) => {
    const mentions = aliases.reduce((n, a) => n + count(t, a), 0);
    if (!mentions) return null;
    const desired = sentences.filter((s) => aliases.some((a) => s.includes(W(a)))).every((s) => DESIRED.test(s));
    const inTitle = aliases.some((a) => tt.includes(W(a)));
    const d = domainOf(label, aliases);
    return { label, cat, aliases, mentions, inTitle, required: !desired, domain: d[0], color: d[2],
      weight: Math.round(((desired ? 1 : 2) * (1 + Math.min(3, mentions - 1) * 0.25 + (inTitle ? 0.5 : 0))) * 100) / 100 };
  }).filter(Boolean);
};

const LEVER_OF = { "Supervision d'équipe": "lead", Leadership: "lead", "Gestion du personnel": "lead", "Coaching et formation des employés": "lead",
  "Gestion de projet": "cert_pm", "PMP / CAPM": "cert_pm", "Lean Six Sigma": "cert_lean", "Amélioration continue": "cert_lean",
  "Santé et sécurité au travail (SST)": "cert_sst", CNESST: "cert_sst", "Premiers secours": "cert_sst", "Gestion budgétaire": "budget", "Contrôle des coûts": "budget",
  "Relations de travail / milieu syndiqué": "union", "Indicateurs de performance (KPI)": "kpi" };

const reco = (s) => {
  const need = s.required ? "exigée par l'offre" : "présentée comme un atout";
  if (s.status === "partiel") return [`Renforcer la preuve de « ${s.label} »`, `Votre domaine « ${s.domain} » est déjà présent : citez un exemple précis (contexte, action, résultat chiffré) qui montre cette compétence ${need}.`];
  if (s.cat === "cert") return [`${s.required ? "Obtenir" : "Envisager"} : ${s.label}`, `Certification ${need} : si vous l'avez déjà, ajoutez-la dans vos certifications (souvent un filtre ATS éliminatoire).`];
  if (s.cat === "tool") return [`Se former à ${s.label}`, `Logiciel ${need} : une formation en ligne courte permet de l'ajouter honnêtement au CV ; les ATS le cherchent mot pour mot.`];
  if (s.cat === "lang") return [`Préciser votre niveau : ${s.label}`, "Indiquez votre niveau (courant, intermédiaire) et un contexte d'usage professionnel."];
  return [s.required ? `Compétence requise à expliciter ou à développer : ${s.label}` : `Atout à mentionner si vous l'avez : ${s.label}`,
    s.required ? "Si vous l'avez déjà pratiquée, nommez-la explicitement dans le CV maître ; sinon, c'est une priorité de développement pour ce type de poste."
      : "Pas éliminatoire, mais la mentionner peut vous départager des autres candidats."];
};

export const compareSkills = (profile, text, title = "", levers = []) => {
  const mine = buildSkillMap(profile);
  const corpus = ` ${N([profile.cv_text, profile.achievements, profile.headline, (profile.skills_detected || []).join(" "), (profile.skills || []).join(" "), (profile.certifications || []).join(" ")].join(" "))} `;
  const myDom = Object.fromEntries(mine.map((g) => [g.name, g.weight]));
  const job = extractJobSkills(text, title).map((s) => {
    const hit = s.aliases.find((a) => corpus.includes(W(a)));
    const status = hit ? "ok" : (myDom[s.domain] || 0) >= 3 ? "partiel" : "manquant";
    const evidence = hit ? `Trouvé dans votre profil : « ${hit.trim()} »` : status === "partiel" ? `Domaine « ${s.domain} » présent dans votre carte (poids ${myDom[s.domain]}), mais pas cette compétence précise` : "Aucune mention dans le CV ni la Career Memory";
    return { ...s, status, evidence };
  });
  const total = job.reduce((n, s) => n + s.weight, 0);
  const score = total ? Math.round((100 * job.reduce((n, s) => n + s.weight * (s.status === "ok" ? 1 : s.status === "partiel" ? 0.5 : 0), 0)) / total) : 0;
  const domains = Object.values(job.reduce((g, s) => { (g[s.domain] ||= { name: s.domain, color: s.color, skills: [], weight: 0 }).skills.push(s); g[s.domain].weight += s.weight; return g; }, {}))
    .map((d) => ({ ...d, coverage: d.skills.reduce((n, s) => n + (s.status === "ok" ? 1 : s.status === "partiel" ? 0.5 : 0), 0) / d.skills.length })).sort((a, b) => b.weight - a.weight);
  const gaps = job.filter((s) => s.status !== "ok").sort((a, b) => b.weight - a.weight || (a.status === "manquant" ? -1 : 1));
  const recos = gaps.slice(0, 6).map((s) => {
    const [t, why] = reco(s);
    const lv = LEVER_OF[s.label] || (s.cat === "tool" ? "tools" : "");
    const l = levers.find((x) => x.id === lv);
    return { skill: s.label, title: t, why, lever: l ? { id: l.id, title: l.title, gain: l.gain } : null };
  });
  const common = domains.filter((d) => myDom[d.name]).map((d) => d.name);
  const weak = domains.filter((d) => d.coverage < 0.5).slice(0, 2).map((d) => d.name);
  const verdict = !job.length ? "Aucune compétence reconnue dans ce texte : collez l'offre complète (exigences et responsabilités)."
    : score >= 80 ? `Très bonne adéquation${weak.length ? `, à consolider sur ${weak.join(" et ")}` : ""}.`
    : score >= 60 ? `Bonne adaptation globale, à renforcer sur ${weak.join(" et ") || "les compétences manquantes"}.`
    : `Adéquation partielle : priorité à ${weak.join(" et ") || "les compétences requises manquantes"} avant de postuler.`;
  return { score, job, domains, gaps, recos, common, verdict, counts: { ok: job.filter((s) => s.status === "ok").length, partiel: job.filter((s) => s.status === "partiel").length, manquant: job.filter((s) => s.status === "manquant").length, required: job.filter((s) => s.required).length } };
};
