// CareerOS client: Bearer-token auth (cross-site safe) + Career Memory / Pack / History API.
const BASE = () => `${process.env.REACT_APP_BACKEND_URL}/api`;
const KEY = "careeros.tokens";

export const tokens = {
  get: () => { try { return JSON.parse(localStorage.getItem(KEY) || "null"); } catch { return null; } },
  set: (t) => localStorage.setItem(KEY, JSON.stringify(t)),
  clear: () => localStorage.removeItem(KEY),
};

export function formatApiError(detail) {
  if (detail == null) return "Une erreur est survenue. Réessayez.";
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((e) => (e && typeof e.msg === "string" ? e.msg : JSON.stringify(e))).join(" ");
  if (typeof detail.msg === "string") return detail.msg;
  return String(detail);
}

async function raw(path, { method = "GET", body, auth = true } = {}) {
  const headers = { "Content-Type": "application/json" };
  const t = tokens.get();
  if (auth && t?.access_token) headers.Authorization = `Bearer ${t.access_token}`;
  return fetch(`${BASE()}${path}`, { method, headers, body: body ? JSON.stringify(body) : undefined });
}

async function tryRefresh() {
  const t = tokens.get();
  if (!t?.refresh_token) return false;
  const r = await raw("/auth/refresh", { method: "POST", body: { refresh_token: t.refresh_token }, auth: false });
  if (!r.ok) { tokens.clear(); return false; }
  const { access_token } = await r.json();
  tokens.set({ ...t, access_token });
  return true;
}

export async function call(path, opts = {}) {
  let r = await raw(path, opts);
  if (r.status === 401 && opts.auth !== false && (await tryRefresh())) r = await raw(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) {
    const err = new Error(formatApiError(data.detail) || `HTTP ${r.status}`);
    err.status = r.status;
    throw err;
  }
  return data;
}

export const auth = {
  async login(email, password) {
    const d = await call("/auth/login", { method: "POST", body: { email, password }, auth: false });
    tokens.set({ access_token: d.access_token, refresh_token: d.refresh_token });
    return d.user;
  },
  async register(email, password, name) {
    const d = await call("/auth/register", { method: "POST", body: { email, password, name }, auth: false });
    tokens.set({ access_token: d.access_token, refresh_token: d.refresh_token });
    return d.user;
  },
  me: () => call("/auth/me"),
  logout: () => tokens.clear(),
};

export const careeros = {
  meta: () => call("/careeros/meta", { auth: false }),
  getProfile: () => call("/careeros/profile"),
  saveProfile: (p) => call("/careeros/profile", { method: "PUT", body: p }),
  createPack: (b) => call("/careeros/packs", { method: "POST", body: b }),
  list: () => call("/careeros/applications"),
  get: (id) => call(`/careeros/applications/${id}`),
  setStatus: (id, pipeline_status) => call(`/careeros/applications/${id}/status`, { method: "PATCH", body: { pipeline_status } }),
  remove: (id) => call(`/careeros/applications/${id}`, { method: "DELETE" }),
  reanalyze: (id, b) => call(`/careeros/applications/${id}/reanalyze`, { method: "POST", body: b }),
  retry: (id) => call(`/careeros/applications/${id}/retry`, { method: "POST" }),
  getVersion: (id, v) => call(`/careeros/applications/${id}/versions/${v}`),
  compare: (id, a, b) => call(`/careeros/applications/${id}/compare?a=${a}&b=${b}`),
  dossier: (id) => call(`/careeros/applications/${id}/dossier`),
};

export const radar = {
  settings: () => call("/careeros/radar/settings"),
  saveSettings: (b) => call("/careeros/radar/settings", { method: "PUT", body: b }),
  run: () => call("/careeros/radar/run", { method: "POST" }),
  runs: (days = 30) => call(`/careeros/radar/runs?days=${days}`),
  runOffers: (id, kind) => call(`/careeros/radar/runs/${id}/offers?kind=${kind}`),
  dashboard: () => call("/careeros/radar/dashboard"),
  ignore: (id) => call(`/careeros/radar/offers/${id}/ignore`, { method: "POST" }),
  pack: (id) => call(`/careeros/radar/offers/${id}/pack`, { method: "POST" }),
  deep: (id) => call(`/careeros/radar/offers/${id}/deep`, { method: "POST" }),
  explain: (id) => call(`/careeros/radar/offers/${id}/explain`),
  external: (b) => call("/careeros/radar/external", { method: "POST", body: b }),
  detectPortal: (b) => call("/careeros/radar/portal/detect", { method: "POST", body: b }),
  discoverPortal: (b) => call("/careeros/radar/portal/discover", { method: "POST", body: b }),
  directory: () => call("/careeros/radar/directory"),
};

export const followup = {
  draft: (appId, b) => call(`/careeros/applications/${appId}/emails/draft`, { method: "POST", body: b }),
  addInterview: (appId, b) => call(`/careeros/applications/${appId}/interviews`, { method: "POST", body: b }),
  patch: (appId, entity, id, changes) => call(`/careeros/applications/${appId}/${entity}/${id}`, { method: "PATCH", body: { changes } }),
  async downloadIcs(appId, interviewId, code) {
    const t = tokens.get();
    const r = await fetch(`${BASE()}/careeros/applications/${appId}/interviews/${interviewId}/ics`, { headers: { Authorization: `Bearer ${t?.access_token}` } });
    if (!r.ok) throw new Error("Fichier .ics indisponible");
    const url = URL.createObjectURL(await r.blob());
    Object.assign(document.createElement("a"), { href: url, download: `${code}_entrevue.ics` }).click();
    URL.revokeObjectURL(url);
  },
};

export const PIPELINE_LABELS = {
  a_postuler: "À postuler", postule: "Postulé", entrevue: "Entrevue", offre: "Offre", refuse: "Refusé", abandonne: "Abandonné",
};
