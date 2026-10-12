import { useEffect, useState } from "react";
import { Moon, Sun } from "lucide-react";
import { applyTheme, currentTheme, setPageTitle } from "@/lib/theme";
import { call, tokens } from "@/lib/careeros";

export function useTheme() {
  const [theme, setTheme] = useState(currentTheme);
  useEffect(() => {
    const on = (e) => setTheme(e.detail);
    window.addEventListener("careeros-theme", on);
    return () => window.removeEventListener("careeros-theme", on);
  }, []);
  return theme;
}

export function usePageTitle(page) {
  useEffect(() => { setPageTitle(page); }, [page]);
}

export const ThemeToggle = ({ className = "" }) => {
  const theme = useTheme();
  const next = theme === "dark" ? "light" : "dark";
  const toggle = () => {
    applyTheme(next);
    if (tokens.get()) call("/auth/preferences", { method: "PATCH", body: { theme: next } }).catch(() => {});
  };
  const label = next === "light" ? "Activer le mode clair" : "Activer le mode sombre";
  return (
    <button type="button" onClick={toggle} title={label} aria-label={label} data-testid="theme-toggle-btn"
      className={`rounded-full border border-white/10 p-2 text-slate-300 transition-colors hover:text-white ${className}`}>
      {theme === "dark" ? <Sun className="h-4 w-4" data-testid="theme-icon-sun" /> : <Moon className="h-4 w-4" data-testid="theme-icon-moon" />}
    </button>
  );
};
