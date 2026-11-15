import { useEffect, useState, useCallback } from "react";

const KEY = "careeros_mic_lang";
const EVT = "careeros-mic-lang";

export const readMicLang = () => (localStorage.getItem(KEY) === "en-US" ? "en-US" : "fr-FR");

// Shared FR/EN language for live listening and dictation, remembered between interviews.
export function useMicLang() {
  const [lang, setLangState] = useState(readMicLang);
  useEffect(() => {
    const sync = () => setLangState(readMicLang());
    window.addEventListener(EVT, sync);
    return () => window.removeEventListener(EVT, sync);
  }, []);
  const setLang = useCallback((v) => {
    localStorage.setItem(KEY, v);
    window.dispatchEvent(new Event(EVT));
  }, []);
  return [lang, setLang];
}
