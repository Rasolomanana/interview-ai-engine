import { useCallback, useEffect, useState } from "react";
import { BadgeCheck, Undo2 } from "lucide-react";
import { toast } from "sonner";
import { radar } from "@/lib/careeros";

const ORIGIN = { annuaire: "vérifié dans l'annuaire CareerOS", "annuaire partagé": "vérifié dans l'annuaire CareerOS", "base commune": "déjà vérifié par CareerOS", site: "trouvé sur le site officiel de l'employeur" };

export const AutoNotices = ({ onChange, onEdit, refreshKey }) => {
  const [items, setItems] = useState([]);
  const load = useCallback(() => radar.notices().then((r) => setItems(r.items)).catch(() => {}), []);
  useEffect(() => { load(); const t = setInterval(load, 30000); return () => clearInterval(t); }, [load, refreshKey]);
  if (!items.length) return null;
  const act = async (n, undo) => {
    try {
      await (undo ? radar.undoNotice(n.id) : radar.ackNotice(n.id));
      if (undo) toast.success(`Association annulée : ${n.company} reste suivie via Jooble.`);
      setItems(items.filter((x) => x.id !== n.id));
      onChange?.();
    } catch (e) { toast.error(e.message); }
  };
  return (
    <section className="space-y-2 rounded-2xl border border-emerald-400/30 bg-emerald-500/[0.07] p-4" data-testid="radar-auto-notices">
      <p className="flex items-center gap-2 text-sm font-semibold text-emerald-200"><BadgeCheck className="h-4 w-4" />Portails associés automatiquement ({items.length})</p>
      {items.map((n) => (
        <div key={n.id} className="flex flex-wrap items-center gap-2 text-xs text-slate-200" data-testid={`auto-notice-${n.id}`}>
          <span className="min-w-0 flex-1"><b>{n.company}</b> → {n.kind_label} · {n.count} offre(s) visibles · {ORIGIN[n.origin] || "vérifié par CareerOS"}</span>
          <button type="button" onClick={() => act(n, false)} className="rounded-full bg-emerald-500 px-3 py-1 font-semibold text-emerald-950 hover:bg-emerald-400" data-testid={`auto-notice-ok-${n.id}`}>OK</button>
          <button type="button" onClick={onEdit} className="rounded-full border border-white/15 px-3 py-1 hover:text-white" data-testid={`auto-notice-edit-${n.id}`}>Modifier</button>
          <button type="button" onClick={() => act(n, true)} className="flex items-center gap-1 rounded-full border border-rose-400/40 px-3 py-1 text-rose-200 hover:bg-rose-500/10" data-testid={`auto-notice-undo-${n.id}`}><Undo2 className="h-3 w-3" />Annuler</button>
        </div>))}
    </section>
  );
};
