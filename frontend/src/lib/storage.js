// Storage abstraction: chrome.storage.local in the extension, localStorage in dev/preview.
const hasChrome = typeof chrome !== "undefined" && chrome.storage && chrome.storage.local;

export async function get(key, def) {
  if (hasChrome) {
    return new Promise((r) => chrome.storage.local.get([key], (o) => r(o[key] === undefined ? def : o[key])));
  }
  try {
    const v = localStorage.getItem(key);
    return v ? JSON.parse(v) : def;
  } catch (e) { return def; }
}

export async function set(key, val) {
  if (hasChrome) return new Promise((r) => chrome.storage.local.set({ [key]: val }, r));
  localStorage.setItem(key, JSON.stringify(val));
}

export async function del(key) {
  if (hasChrome) return new Promise((r) => chrome.storage.local.remove([key], r));
  localStorage.removeItem(key);
}
