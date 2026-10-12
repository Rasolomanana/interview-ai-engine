// CareerOS theme: "light" | "dark". Default = OS preference, else light.
// Saved locally (instant, pre-login) and in the member profile (restored on login).
const KEY = "careeros.theme";

export function systemTheme() {
  try { return window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light"; } catch { return "light"; }
}

export function currentTheme() {
  const t = localStorage.getItem(KEY);
  return t === "dark" || t === "light" ? t : systemTheme();
}

export function applyTheme(t) {
  const root = document.documentElement;
  root.classList.toggle("light", t === "light");
  root.classList.toggle("dark", t === "dark");
  root.style.colorScheme = t;
  localStorage.setItem(KEY, t);
  window.dispatchEvent(new CustomEvent("careeros-theme", { detail: t }));
}

export function setPageTitle(page) {
  document.title = page ? `CareerOS | ${page}` : "CareerOS | Directeur de carrière IA";
}
