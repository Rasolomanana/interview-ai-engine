import { useEffect, useState } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

export const ClickNum = ({ children, onClick, testid, className = "" }) => (
  <button type="button" onClick={onClick} data-testid={testid} title="Afficher le détail"
    className={`rounded-md text-left underline decoration-current/30 underline-offset-4 transition-colors hover:bg-white/5 hover:decoration-current ${className}`}>{children}</button>
);

export const DetailDialog = ({ detail: current, onClose }) => {
  const [last, setLast] = useState(current);
  useEffect(() => { if (current) setLast(current); }, [current]);
  const detail = current || last;  // keep content while the close animation runs
  return (
  <Dialog open={!!current} onOpenChange={(o) => !o && onClose()}>
    <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto border-white/10 bg-slate-900 text-slate-100" data-testid="admin-detail-dialog">
      <DialogHeader><DialogTitle data-testid="admin-detail-title">{detail?.title}</DialogTitle>
        <DialogDescription className="text-slate-400">{detail?.note || `${detail?.rows.length ?? 0} ligne(s)`}</DialogDescription></DialogHeader>
      {detail && (detail.rows.length === 0 ? <p className="text-sm text-slate-500" data-testid="admin-detail-empty">Aucune donnée à afficher.</p> : (
        <div className="overflow-x-auto"><table className="w-full text-left text-xs" data-testid="admin-detail-table">
          <thead className="text-slate-500"><tr>{detail.cols.map(([k, l]) => <th key={k} className="py-1.5 pr-3 font-medium">{l}</th>)}</tr></thead>
          <tbody>{detail.rows.map((r, i) => <tr key={i} className="border-t border-white/5">{detail.cols.map(([k]) => <td key={k} className="py-1.5 pr-3 text-slate-300">{r[k] ?? "—"}</td>)}</tr>)}</tbody>
        </table></div>))}
    </DialogContent>
  </Dialog>
  );
};
