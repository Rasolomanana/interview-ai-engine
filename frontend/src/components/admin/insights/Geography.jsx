import { useState } from "react";
import { adminInsights } from "@/lib/api";
import { DetailDialog } from "@/components/admin/DetailDialog";
import { RankList, Spinner, pwd, useAdminData } from "./ui";

export const Geography = () => {
  const [detail, setDetail] = useState(null);
  const d = useAdminData(() => adminInsights(pwd(), "geo"));
  if (!d) return <Spinner />;
  const total = d.countries.reduce((s, r) => s + r.count, 0);
  const pick = (level) => (r) => setDetail({ title: `${level} · ${r.label}`, cols: [["k", "Élément"], ["v", "Valeur"]],
    rows: [{ k: "Membres", v: r.count }, { k: "Part des membres", v: `${total ? Math.round((100 * r.count) / total) : 0} %` }], note: "Statistique agrégée : aucun membre identifiable." });
  return (
    <div className="space-y-4" data-testid="admin-geo">
      <DetailDialog detail={detail} onClose={() => setDetail(null)} />
      <p className="text-[11px] text-slate-500" data-testid="geo-note">{d.note}{d.merged ? " Les groupes de moins de 3 membres sont regroupés pour votre rôle." : ""}</p>
      <div className="grid gap-4 lg:grid-cols-3">
        <RankList title="Membres par pays" rows={d.countries} testid="geo-countries" onPick={pick("Pays")} />
        <RankList title="Membres par province / région" rows={d.provinces} testid="geo-provinces" onPick={pick("Province / région")} />
        <RankList title="Membres par ville" rows={d.cities} testid="geo-cities" onPick={pick("Ville")} />
      </div>
    </div>
  );
};
