export const pwd = () => sessionStorage.getItem("adminPwd");
export const inp = "rounded-lg border border-white/10 bg-slate-950 px-2.5 py-1.5 text-sm text-white outline-none focus:border-emerald-400/60";

export const StatusBadge = ({ archived, suspended }) => (
  <span className={`rounded-full border px-2 py-px text-[10px] font-semibold ${archived ? "border-slate-500/40 text-slate-400" : suspended ? "border-amber-400/40 text-amber-300" : "border-emerald-400/40 text-emerald-300"}`}>
    {archived ? "Archivé" : suspended ? "Suspendu" : "Actif"}
  </span>
);

export const IconBtn = ({ icon: Icon, label, onClick, disabled, danger, testid }) => (
  <button type="button" onClick={onClick} disabled={disabled} title={label} aria-label={label} data-testid={testid}
    className={`rounded-md p-1.5 transition-colors disabled:cursor-not-allowed disabled:opacity-30 ${danger ? "text-slate-500 hover:text-rose-400" : "text-slate-400 hover:bg-white/5 hover:text-white"}`}>
    <Icon className="h-4 w-4" />
  </button>
);
