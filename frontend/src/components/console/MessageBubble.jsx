import { motion } from "framer-motion";
import { parseCandidate, stripDebugLine } from "@/lib/parse";
import CandidateBullets from "./CandidateBullets";
import { User, MessageCircleQuestion } from "lucide-react";

const RECRUITER_AVATAR =
  "https://images.unsplash.com/photo-1544723495-432537d12f6c?crop=entropy&cs=srgb&fm=jpg&w=120&q=80";

export default function MessageBubble({ msg, streaming }) {
  if (msg.role === "user") {
    return (
      <motion.div initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} className="flex justify-end" data-testid="user-message">
        <div className="flex max-w-[80%] items-start gap-2.5">
          <div className="rounded-2xl rounded-tr-sm border border-white/[0.08] bg-[#1a1e2e] px-4 py-2.5 text-[15px] text-slate-200">
            {msg.content}
          </div>
          <div className="mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-slate-700 text-slate-300">
            <User className="h-3.5 w-3.5" />
          </div>
        </div>
      </motion.div>
    );
  }

  const { debug, body } = stripDebugLine(msg.content);

  return (
    <motion.div initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} className="flex flex-col gap-1.5" data-testid={`assistant-message-${msg.mode}`}>
      {debug && (
        <div className="self-start rounded-md border border-red-500/30 bg-red-950/30 px-2.5 py-1 font-mono text-[10px] text-red-300">{debug}</div>
      )}

      {msg.mode === "CANDIDAT" && (
        <div className="max-w-[92%]">
          <ModeTag color="emerald" label="COPILOTE" modules={msg.modules} />
          <CandidateBullets parsed={parseCandidate(body)} streaming={streaming} />
        </div>
      )}

      {msg.mode === "RECRUTEUR" && (
        <div className="flex max-w-[85%] items-start gap-3">
          <img src={RECRUITER_AVATAR} alt="Recruteur" className="mt-0.5 h-9 w-9 shrink-0 rounded-full border border-violet-500/40 object-cover" />
          <div>
            <ModeTag color="violet" label="RECRUTEUR" />
            <div className="rounded-2xl rounded-tl-sm border border-violet-500/25 bg-violet-950/20 px-4 py-3 text-[15px] leading-relaxed text-slate-200">
              {body}
              {streaming && <span className="caret h-4" />}
            </div>
          </div>
        </div>
      )}

      {msg.mode === "NEUTRE" && (
        <div className="flex max-w-[80%] items-center gap-3 rounded-2xl border border-slate-600/40 bg-slate-800/30 px-4 py-3">
          <MessageCircleQuestion className="h-5 w-5 shrink-0 text-slate-400" />
          <p className="text-[15px] text-slate-200">{body}{streaming && <span className="caret h-4" />}</p>
        </div>
      )}
    </motion.div>
  );
}

function ModeTag({ color, label, modules }) {
  const map = {
    emerald: "border-emerald-500/40 bg-emerald-950/50 text-emerald-400",
    violet: "border-violet-500/40 bg-violet-950/50 text-violet-400",
  };
  return (
    <div className="mb-1.5 flex items-center gap-2">
      <span className={`rounded-md border px-2 py-0.5 font-mono text-[9px] font-bold uppercase tracking-widest ${map[color]}`}>{label}</span>
      {modules && modules.length > 0 && modules[0] !== "—" && (
        <span className="font-mono text-[9px] text-slate-500">{modules.join(" · ")}</span>
      )}
    </div>
  );
}
