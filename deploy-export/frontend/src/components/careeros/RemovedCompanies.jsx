import { useEffect, useState } from "react";
import { RotateCcw } from "lucide-react";
import { toast } from "sonner";
import { radar } from "@/lib/careeros";

const date = (s) => (s ? new Date(s).toLocaleDateString("fr-CA") : "—");

// « Entreprises retirées » and « Entreprises bloquées » with restore.
export const RemovedCompanies = ({ refreshKey, onRestored }) => {
  const [items, setItems] = useState(null);
  const load = () => radar.removedCompanies().then((r) => setItems(r.items)).catch(() => setItems([]));
  useEffect(() => { load(); }, [refreshKey]); // eslint-disable-line react-hooks/exhaustive-deps
  if (!items) return null;
  const restore = async (n) => { try { await radar.restoreCompany(n); toast.success(`${n} est de nouveau suivie.`); load(); onRestored?.(n); } catch (e) { toast.error(e.message.replace(/^LIMIT:/, "")); } };
  const Group = ({ mode, title }) => {
    const list = items.filter((x) => x.mode === mode);
    return (
      <div data-testid={`removed-${mode}`}><p className="mb-1 text-[11px] uppercase tracking-wider text-slate-500">{title} ({list.length})</p>
        {!list.length ? <p className="text-[11px] text-slate-500">Aucune.</p> : <ul className="space-y-1">{list.map((x, i) => (
          <li key={x.name} className="flex flex-wrap items-center gap-2 text-xs" data-testid={`removed-${mode}-${i}`}>
            <span className="text-slate-200">{x.name}</span><span className="text-slate-500">· {date(x.at)}{x.reason ? ` · ${x.reason}` : ""}</span>
            <button type="button" onClick={() => restore(x.name)} className="ml-auto flex items-center gap-1 text-indigo-300 hover:text-white" data-testid={`removed-restore-${mode}-${i}`}><RotateCcw className="h-3 w-3" />Restaurer</button>
          </li>))}</ul>}
      </div>);
  };
  return (
    <div className="space-y-3 rounded-xl border border-white/10 p-3" data-testid="removed-companies">
      <Group mode="retire" title="Entreprises retirées" />
      <Group mode="bloque" title="Entreprises bloquées définitivement" />
    </div>
  );
};
