import { useState } from "react";
import { Stethoscope, Loader2 } from "lucide-react";
import { streamGemini, describeGeminiError } from "@/lib/gemini";

const readLast = () => { try { return JSON.parse(localStorage.getItem("geminiLastError") || "null"); } catch { return null; } };

const ErrorBox = ({ info, testid }) => (
  <div data-testid={testid} className="rounded-lg border border-red-500/30 bg-red-950/30 p-2 text-[11px] text-red-200">
    <div className="font-semibold text-red-300">{info.label}{info.status ? ` (HTTP ${info.status})` : ""}</div>
    <div className="mt-1 whitespace-pre-wrap break-all font-mono text-[10px] text-red-200/80">{info.detail}</div>
    <div className="mt-1 text-[10px] text-slate-500">{info.model} · {(info.at || "").replace("T", " ").slice(0, 19)}</div>
  </div>
);

export const GeminiDiagnostic = ({ apiKey, model }) => {
  const [last, setLast] = useState(readLast);
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState(null);

  const test = async () => {
    setBusy(true); setResult(null);
    const t0 = performance.now();
    let text = "";
    try {
      if (!apiKey) throw Object.assign(new Error("aucune clé saisie"), { kind: "KEY_INVALID", kindLabel: "Clé API manquante", detail: "Collez une clé Gemini puis relancez le test." });
      await streamGemini({ apiKey, model, systemMessage: "Réponds en un mot.", userText: "Dis OK.", onDelta: (c) => { text += c; } });
      setResult({ ok: true, ms: Math.round(performance.now() - t0), text: text.slice(0, 60) });
    } catch (e) {
      const info = describeGeminiError(e, model);
      console.warn("[Test Gemini]", info, e);
      setResult({ ok: false, info });
    } finally { setBusy(false); }
  };

  return (
    <div className="space-y-2 rounded-xl border border-white/10 bg-black/30 p-3" data-testid="gemini-diagnostic">
      <button type="button" onClick={test} disabled={busy} data-testid="gemini-test-btn"
        className="flex items-center gap-2 rounded-lg border border-indigo-500/40 bg-indigo-500/10 px-3 py-1.5 text-xs text-indigo-100 hover:bg-indigo-500/20 disabled:opacity-50">
        {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Stethoscope className="h-3.5 w-3.5" />} Tester Gemini ({model})
      </button>
      {result?.ok && <div data-testid="gemini-test-ok" className="text-[11px] text-emerald-300">OK — premier résultat en {result.ms} ms : « {result.text} »</div>}
      {result && !result.ok && <ErrorBox info={result.info} testid="gemini-test-error" />}
      {last && (
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px] uppercase tracking-widest text-slate-500">
            Dernière erreur Gemini (bascule Serveur)
            <button type="button" data-testid="gemini-last-error-clear" onClick={() => { localStorage.removeItem("geminiLastError"); setLast(null); }} className="normal-case text-slate-400 hover:text-white">effacer</button>
          </div>
          <ErrorBox info={last} testid="gemini-last-error" />
        </div>
      )}
    </div>
  );
};
