export const cad = (n) => (n === null || n === undefined ? "—" : new Intl.NumberFormat("fr-CA", { style: "currency", currency: "CAD", minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(n));
export const cadFine = (n) => (n === null || n === undefined ? "—" : new Intl.NumberFormat("fr-CA", { style: "currency", currency: "CAD", minimumFractionDigits: 2, maximumFractionDigits: Math.abs(n) < 1 ? 4 : 2 }).format(n));
export const usd = (n) => `${(Number(n) || 0).toLocaleString("fr-CA", { minimumFractionDigits: 2, maximumFractionDigits: Math.abs(n) < 1 ? 4 : 2 })} USD`;
export const pct = (n) => (n === null || n === undefined ? "—" : `${n.toLocaleString("fr-CA")} %`);
export const num = (n) => (Number(n) || 0).toLocaleString("fr-CA");
export const tone = (n) => (n === null || n === undefined ? "text-white" : n < 0 ? "text-rose-400" : "text-emerald-400");
export const monthLabel = (m) => new Date(`${m}-15T12:00:00`).toLocaleDateString("fr-CA", { month: "long", year: "numeric" });
export const panel = "min-w-0 rounded-2xl border border-white/10 bg-slate-900/60 p-4 sm:p-5";

export const Panel = ({ title, icon: Icon, children, testid, right }) => (
  <section className={panel} data-testid={testid}>
    <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
      <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-200">{Icon && <Icon className="h-4 w-4 text-emerald-400" />}{title}</h3>
      {right}
    </div>
    {children}
  </section>
);

export const Row = ({ label, value, strong, testid, hint }) => (
  <div className={`flex items-baseline justify-between gap-3 border-t border-white/[0.06] py-2 text-sm first:border-t-0 ${strong ? "font-semibold text-white" : "text-slate-300"}`} data-testid={testid}>
    <span>{label}{hint && <span className="ml-1 text-[11px] font-normal text-slate-500">{hint}</span>}</span>
    <span className="font-mono tabular-nums">{value}</span>
  </div>
);
