export const KIND_LABEL = { workday: "Workday", successfactors: "SuccessFactors", oracle: "Oracle Recruiting", icims: "iCIMS", ukg: "UKG", taleo: "Taleo", avature: "Avature", phenom: "Phenom", schema: "Site carrières (schema.org)", taleobe: "Taleo Business Edition", greenhouse: "Greenhouse", lever: "Lever", ashby: "Ashby", smartrecruiters: "SmartRecruiters", amazon: "amazon.jobs" };
export const QUALITY = {
  fiable: { label: "Lecture fiable", dot: "bg-emerald-400", text: "text-emerald-300" },
  fragile: { label: "Lecture fragile", dot: "bg-sky-400", text: "text-sky-300" },
  bloquee: { label: "Lecture bloquée", dot: "bg-rose-400", text: "text-rose-300" },
  repli: { label: "Repli Jooble", dot: "bg-amber-400", text: "text-amber-300" },
};
export const FRAGILE = new Set(["icims", "avature", "phenom", "taleobe"]);
export const qualityOf = (p) => p.quality || (p.blocked ? "bloquee" : !p.ok ? "repli" : FRAGILE.has(p.kind) ? "fragile" : "fiable");
