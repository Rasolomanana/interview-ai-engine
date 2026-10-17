import { useEffect, useState } from "react";
import { Maximize2, Minimize2 } from "lucide-react";

// Browser fullscreen (no browser bars); Échap exits. Returns [isFull, button].
export const useFullscreen = (testid) => {
  const [full, setFull] = useState(false);
  useEffect(() => {
    const on = () => setFull(!!document.fullscreenElement);
    document.addEventListener("fullscreenchange", on);
    return () => { document.removeEventListener("fullscreenchange", on); if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {}); };
  }, []);
  const toggle = async () => {
    try {
      if (document.fullscreenElement) await document.exitFullscreen();
      else if (document.documentElement.requestFullscreen) await document.documentElement.requestFullscreen();
      else setFull((v) => !v);
    } catch { setFull((v) => !v); }
  };
  const button = (
    <button type="button" onClick={toggle} title={full ? "Quitter le plein écran (Échap)" : "Plein écran"} data-testid={testid}
      className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-1 text-xs text-slate-300 transition-colors hover:bg-white/5 hover:text-white">
      {full ? <Minimize2 className="h-3.5 w-3.5" /> : <Maximize2 className="h-3.5 w-3.5" />}{full ? "Quitter" : "Plein écran"}
    </button>
  );
  return [full, button];
};
