import { motion } from "framer-motion";
import { AlertTriangle } from "lucide-react";
import { segmentsFor } from "@/lib/parse";

// Progressive reveal of the 3 telegraphic bullets (T2: puce 1 -> 2 -> 3).
export default function CandidateBullets({ parsed, streaming }) {
  const { alert, response, bullets } = parsed;
  return (
    <div className="space-y-2.5" data-testid="candidate-bullets">
      {alert && (
        <motion.div
          initial={{ opacity: 0, y: -6 }}
          animate={{ opacity: 1, y: 0 }}
          className="flex items-center gap-2 rounded-lg border border-amber-500/30 bg-amber-950/30 px-3 py-2 text-[13px] text-amber-200"
          data-testid="candidate-alert"
        >
          <AlertTriangle className="h-4 w-4 shrink-0" />
          <span>{alert}</span>
        </motion.div>
      )}
      {response && (
        <motion.div
          initial={{ opacity: 0, scale: 0.9 }}
          animate={{ opacity: 1, scale: 1 }}
          className="inline-flex items-center gap-2 rounded-md border border-emerald-500/40 bg-emerald-950/50 px-3 py-1.5 font-mono text-sm font-bold text-emerald-300"
          data-testid="vision-response"
        >
          RÉPONSE : {response}
        </motion.div>
      )}
      <ul className="space-y-2.5">
        {bullets.map((b, i) => (
          <motion.li
            key={i}
            initial={{ opacity: 0, x: -14 }}
            animate={{ opacity: 1, x: 0 }}
            transition={{ delay: streaming ? 0 : i * 0.14, duration: 0.28 }}
            className="flex items-start gap-3 rounded-xl border border-white/[0.06] bg-[#1a1e2e]/70 px-4 py-3"
            data-testid={`candidate-bullet-${i}`}
          >
            <span className="mt-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-emerald-500/15 font-mono text-xs font-bold text-emerald-400">
              {i + 1}
            </span>
            <p className="text-lg font-medium leading-snug tracking-wide text-slate-100">
              {segmentsFor(b).map((s, j) =>
                s.bold ? (
                  <strong
                    key={j}
                    className="rounded border border-amber-500/30 bg-amber-950/40 px-1 py-0.5 font-black text-amber-300"
                  >
                    {s.text}
                  </strong>
                ) : (
                  <span key={j}>{s.text}</span>
                )
              )}
            </p>
          </motion.li>
        ))}
        {streaming && bullets.length === 0 && (
          <li className="text-slate-500 text-sm">Génération…</li>
        )}
      </ul>
    </div>
  );
}
