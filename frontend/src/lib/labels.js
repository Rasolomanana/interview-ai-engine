// Member-facing labels shared by Radar views (never show raw technical source keys).
const SOURCE_LABEL = { jooble: "Jooble", adzuna: "Adzuna", google_jobs: "Google Emplois", externe: "Offre ajoutée par vous" };
export const sourceLabel = (s) => SOURCE_LABEL[s] || "Site officiel de l'employeur";
export const metaLine = (o) => [o.company, o.location, sourceLabel(o.source)].filter(Boolean).join(" · ");
// Team-only debug tools (localStorage careeros:dev = "1").
export const DEV = (() => { try { return localStorage.getItem("careeros:dev") === "1"; } catch { return false; } })();
