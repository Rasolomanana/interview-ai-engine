import { useMemo, useState } from "react";
import { ArrowUpDown, Download, Loader2, Search } from "lucide-react";
import { toast } from "sonner";
import { adminTrace } from "@/lib/api";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const csv = (t, rows) => {
  const esc = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
  const body = [t.cols.map(([, l]) => esc(l)).join(";"), ...rows.map((r) => t.cols.map(([k]) => esc(r[k])).join(";"))].join("\n");
  const a = document.createElement("a");
  a.href = URL.createObjectURL(new Blob([`\ufeff${body}`], { type: "text/csv;charset=utf-8" }));
  a.download = `${t.title.replace(/[^\w-]+/g, "_").slice(0, 60)}.csv`;
  document.body.appendChild(a); a.click(); a.remove();
};

const TraceTable = ({ t }) => {
  const [q, setQ] = useState("");
  const [sort, setSort] = useState(null);
  const rows = useMemo(() => {
    const f = t.rows.filter((r) => !q || t.cols.some(([k]) => String(r[k] ?? "").toLowerCase().includes(q.toLowerCase())));
    if (!sort) return f;
    const [k, dir] = sort;
    return [...f].sort((a, b) => (typeof a[k] === "number" && typeof b[k] === "number" ? a[k] - b[k] : String(a[k] ?? "").localeCompare(String(b[k] ?? ""), "fr")) * dir);
  }, [t, q, sort]);
  return (
    <>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex flex-1 items-center gap-2 rounded-lg border border-white/10 bg-black/30 px-2.5"><Search className="h-3.5 w-3.5 text-slate-500" />
          <input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher dans la trace…" className="w-full bg-transparent py-1.5 text-xs text-white outline-none" data-testid="trace-search" /></label>
        <span className="text-[11px] text-slate-400" data-testid="trace-count">{rows.length} / {t.total} ligne(s){t.truncated ? " (limité aux 1000 plus récentes)" : ""}</span>
        <button type="button" onClick={() => csv(t, rows)} disabled={!rows.length} className="flex items-center gap-1 rounded-lg border border-emerald-400/30 px-2.5 py-1 text-[11px] text-emerald-200 disabled:opacity-40" data-testid="trace-csv"><Download className="h-3.5 w-3.5" />CSV</button>
      </div>
      {rows.length === 0 ? <p className="py-6 text-center text-sm text-slate-500" data-testid="trace-empty">Aucun élément : ce chiffre vaut 0 ou rien ne correspond à la recherche.</p> : (
        <div className="max-h-[55vh] overflow-auto"><table className="w-full text-left text-xs" data-testid="trace-table">
          <thead className="sticky top-0 bg-slate-900 text-slate-500"><tr>{t.cols.map(([k, l]) => (
            <th key={k} className="py-1.5 pr-3 font-medium"><button type="button" onClick={() => setSort(sort?.[0] === k ? [k, -sort[1]] : [k, 1])} className="flex items-center gap-1 hover:text-white" data-testid={`trace-sort-${k}`}>{l}<ArrowUpDown className="h-3 w-3" /></button></th>))}</tr></thead>
          <tbody>{rows.map((r, i) => <tr key={i} className="border-t border-white/5" data-testid={`trace-row-${i}`}>{t.cols.map(([k]) => <td key={k} className="py-1.5 pr-3 text-slate-300">{r[k] ?? "—"}</td>)}</tr>)}</tbody>
        </table></div>)}
    </>
  );
};

// Opens the real records behind any admin number: const [traceNode, openTrace] = useTrace(); openTrace("m_total")
export const useTrace = () => {
  const [state, setState] = useState(null);
  const open = async (metric, key = "", days) => {
    setState({ loading: true, metric });
    try { setState({ t: await adminTrace(sessionStorage.getItem("adminPwd"), metric, key, days) }); }
    catch (e) { toast.error(e.message); setState(null); }
  };
  const node = (
    <Dialog open={!!state} onOpenChange={(o) => !o && setState(null)}>
      <DialogContent className="max-h-[90vh] max-w-5xl overflow-hidden border-white/10 bg-slate-900 text-slate-100" data-testid="trace-dialog">
        <DialogHeader><DialogTitle data-testid="trace-title">{state?.t?.title || "Chargement de la trace…"}</DialogTitle>
          <DialogDescription className="text-slate-400">{state?.t?.note || "Éléments réels qui composent ce chiffre."}</DialogDescription></DialogHeader>
        <div className="space-y-3">{state?.loading ? <Loader2 className="h-5 w-5 animate-spin text-emerald-400" /> : state?.t && <TraceTable t={state.t} />}</div>
      </DialogContent>
    </Dialog>
  );
  return [node, open];
};
