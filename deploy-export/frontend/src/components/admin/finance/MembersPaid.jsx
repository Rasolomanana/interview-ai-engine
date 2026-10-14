import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import { toast } from "sonner";
import { Switch } from "@/components/ui/switch";
import { adminMembers, adminSetPaid } from "@/lib/api";
import { Panel } from "./fmt";

const pwd = () => sessionStorage.getItem("adminPwd");

export const MembersPaid = ({ onChange }) => {
  const [list, setList] = useState(null);
  const [q, setQ] = useState("");
  useEffect(() => { adminMembers(pwd()).then(setList).catch((e) => toast.error(e.message)); }, []);
  const toggle = async (m, paid) => {
    try { await adminSetPaid(pwd(), m.id, paid); setList(list.map((x) => (x.id === m.id ? { ...x, paid } : x))); onChange(); } catch (e) { toast.error(e.message); }
  };
  const shown = (list || []).filter((m) => `${m.email} ${m.name || ""}`.toLowerCase().includes(q.toLowerCase())).slice(0, 100);
  return (
    <Panel title="Membres payants" icon={Users} testid="finance-members"
      right={<input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Rechercher…" className="w-44 rounded-lg border border-white/10 bg-slate-950 px-2.5 py-1 text-xs text-white outline-none" data-testid="finance-members-search" />}>
      {!list ? <p className="text-xs text-slate-500">Chargement…</p> : (
        <div className="max-h-72 overflow-y-auto">
          {shown.map((m) => (
            <div key={m.id} className="flex items-center justify-between gap-3 border-t border-white/[0.06] py-2 text-sm first:border-t-0" data-testid={`member-${m.id}`}>
              <div className="min-w-0">
                <p className="truncate text-slate-200">{m.name || m.email}</p>
                <p className="truncate text-[11px] text-slate-500">{m.email} · {m.active_month ? "actif ce mois" : "inactif ce mois"}</p>
              </div>
              <label className="flex shrink-0 items-center gap-2 text-xs text-slate-400">Payant<Switch checked={m.paid} onCheckedChange={(v) => toggle(m, v)} data-testid={`member-paid-${m.id}`} /></label>
            </div>))}
        </div>)}
      <p className="mt-2 text-[11px] text-slate-500">Les membres cochés servent au calcul des « actifs payants ». Le nombre de payants peut aussi être forcé dans « Saisir le mois ».</p>
    </Panel>
  );
};
