import { useState } from "react";

// Persisted open/closed state (localStorage), for collapsible panels.
export const usePersistedToggle = (key, initial = true) => {
  const [open, setOpen] = useState(() => {
    const v = localStorage.getItem(key);
    return v === null ? initial : v === "1";
  });
  const toggle = () => setOpen((o) => { localStorage.setItem(key, o ? "0" : "1"); return !o; });
  return [open, toggle];
};
