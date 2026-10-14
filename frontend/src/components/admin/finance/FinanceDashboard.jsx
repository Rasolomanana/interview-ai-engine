import { useCallback, useEffect, useState } from "react";
import { Loader2, PencilLine } from "lucide-react";
import { toast } from "sonner";
import { adminFinance } from "@/lib/api";
import { FinanceKpis, Answers } from "./FinanceKpis";
import { FinanceChart } from "./FinanceChart";
import { RevenueCosts, AiTables, PerMember, Alerts, Projections } from "./FinanceTables";
import { FinanceEditor } from "./FinanceEditor";
import { MembersPaid } from "./MembersPaid";
import { monthLabel } from "./fmt";

const thisMonth = () => new Date().toLocaleDateString("en-CA", { timeZone: "America/Toronto" }).slice(0, 7);

export const FinanceDashboard = () => {
  const [month, setMonth] = useState(thisMonth());
  const [s, setS] = useState(null);
  const [edit, setEdit] = useState(false);
  const load = useCallback(() => adminFinance(sessionStorage.getItem("adminPwd"), month).then(setS).catch((e) => toast.error(e.message)), [month]);
  useEffect(() => { setS(null); load(); }, [load]);
  return (
    <div className="space-y-4" data-testid="finance-dashboard">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-lg font-bold text-white">Rentabilité CareerOS</h2>
          <p className="text-xs text-slate-400">Toutes les valeurs en CAD · {s?.draft ? "mois non encore saisi (valeurs par défaut)" : "données saisies"}</p>
        </div>
        <div className="flex items-center gap-2">
          <input type="month" value={month} max={thisMonth()} onChange={(e) => e.target.value && setMonth(e.target.value)} className="rounded-lg border border-white/10 bg-slate-900 px-2.5 py-1.5 text-xs text-white" data-testid="finance-month" />
          <button onClick={() => setEdit(true)} disabled={!s} className="flex items-center gap-1.5 rounded-lg bg-emerald-500 px-3 py-1.5 text-xs font-semibold text-black hover:bg-emerald-400 disabled:opacity-50" data-testid="finance-edit-btn"><PencilLine className="h-3.5 w-3.5" />Saisir le mois</button>
        </div>
      </div>
      {!s ? <Loader2 className="h-5 w-5 animate-spin text-emerald-400" /> : <>
        <p className="text-sm capitalize text-slate-300" data-testid="finance-month-label">{monthLabel(s.month)}</p>
        <FinanceKpis s={s} />
        <Answers s={s} />
        <FinanceChart history={s.history} />
        <RevenueCosts s={s} />
        <AiTables s={s} />
        <PerMember s={s} />
        <Alerts s={s} />
        <Projections s={s} />
        <MembersPaid onChange={load} />
        {edit && <FinanceEditor open s={s} onClose={() => setEdit(false)} onSaved={() => { setEdit(false); load(); }} />}
      </>}
    </div>
  );
};
