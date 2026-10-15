import { adminInsights } from "@/lib/api";
import { useTrace } from "@/components/admin/TraceDialog";
import { RankList, Spinner, pwd, useAdminData } from "./ui";

export const Geography = () => {
  const [traceNode, trace] = useTrace();
  const d = useAdminData(() => adminInsights(pwd(), "geo"));
  if (!d) return <Spinner />;
  const pick = (metric) => (r) => trace(metric, r.label);
  return (
    <div className="space-y-4" data-testid="admin-geo">
      {traceNode}
      <p className="text-[11px] text-slate-500" data-testid="geo-note">{d.note}{d.merged ? " Les groupes de moins de 3 membres sont regroupés pour votre rôle." : ""}</p>
      <div className="grid gap-4 lg:grid-cols-3">
        <RankList title="Membres par pays" rows={d.countries} testid="geo-countries" onPick={pick("g_country")} />
        <RankList title="Membres par province / région" rows={d.provinces} testid="geo-provinces" onPick={pick("g_province")} />
        <RankList title="Membres par ville" rows={d.cities} testid="geo-cities" onPick={pick("g_city")} />
      </div>
    </div>
  );
};
