import { useEffect, useState } from "react";
import { Loader2, PlugZap, Puzzle } from "lucide-react";
import { toast } from "sonner";
import { adminConnectors } from "@/lib/api";

const panel = "min-w-0 rounded-2xl border border-white/10 bg-slate-900/60 p-4 sm:p-5";
const PRIO = { "Élevée": "text-rose-300", Moyenne: "text-amber-300", Faible: "text-slate-400", "Aucune (protection)": "text-slate-500" };
const Th = ({ children, left }) => <th className={`py-2 pr-3 font-medium ${left ? "" : "text-right"}`}>{children}</th>;
const Td = ({ children, left, className = "" }) => <td className={`border-b border-white/5 py-2 pr-3 ${left ? "" : "text-right font-mono tabular-nums"} ${className}`}>{children}</td>;

export const Connectors = () => {
  const [d, setD] = useState(null);
  useEffect(() => { adminConnectors(sessionStorage.getItem("adminPwd")).then(setD).catch((e) => toast.error(e.message)); }, []);
  if (!d) return <Loader2 className="h-5 w-5 animate-spin text-emerald-400" />;
  return (
    <div className="space-y-4" data-testid="admin-connectors">
      <section className={panel} data-testid="connectors-backlog">
        <h3 className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-200"><Puzzle className="h-4 w-4 text-emerald-400" />Connecteurs à prévoir (classés par impact)</h3>
        <p className="mb-3 text-[11px] text-slate-500">Agrégé de façon anonyme sur les entreprises suivies par tous les membres. Offres = offres Jooble des 30 derniers jours pour ces entreprises (potentiellement récupérables à la source).</p>
        {d.backlog.length === 0 ? <p className="text-xs text-slate-500" data-testid="connectors-backlog-empty">Aucun portail non pris en charge détecté pour l'instant. Les membres doivent lancer la loupe ou « Tout détecter ».</p> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[720px] text-left text-[12px]">
              <thead className="text-slate-500"><tr className="border-b border-white/10"><Th left>Portail</Th><Th>Entreprises</Th><Th>Membres</Th><Th>Offres (30 j)</Th><Th left>Exemples</Th><Th left>Difficulté</Th><Th left>Priorité</Th></tr></thead>
              <tbody>{d.backlog.map((r) => (
                <tr key={r.connector} data-testid={`connector-row-${r.connector.replace(/[^a-z0-9]/gi, "-")}`}>
                  <Td left className="font-semibold text-white">{r.connector}</Td><Td>{r.companies}</Td><Td>{r.members}</Td><Td>{r.offers_30d}</Td>
                  <Td left className="text-slate-400">{r.examples.join(", ")}</Td><Td left>{r.difficulty}</Td><Td left className={`font-semibold ${PRIO[r.priority] || ""}`}>{r.priority}</Td>
                </tr>))}</tbody>
            </table>
          </div>)}
      </section>
      <section className={panel} data-testid="connectors-supported">
        <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200"><PlugZap className="h-4 w-4 text-emerald-400" />Connecteurs actifs (dernier passage de chaque membre)</h3>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[820px] text-left text-[12px]">
            <thead className="text-slate-500"><tr className="border-b border-white/10"><Th left>Portail</Th><Th>Entreprises</Th><Th>Membres</Th><Th>Offres lues</Th><Th>Retenues</Th><Th>Lecture réussie</Th><Th>Fiable</Th><Th>Fragile</Th><Th>Bloquée</Th><Th>Repli Jooble</Th></tr></thead>
            <tbody>{d.supported.map((r) => (
              <tr key={r.kind} data-testid={`connector-active-${r.kind}`}>
                <Td left className="font-semibold text-white">{r.label}{r.fragile_kind && <span className="ml-1.5 rounded-full border border-sky-400/30 px-1.5 text-[10px] font-normal text-sky-300" data-testid={`connector-fragile-${r.kind}`}>au mieux</span>}</Td><Td>{r.companies}</Td><Td>{r.members}</Td><Td>{r.fetched}</Td><Td>{r.matched}</Td>
                <Td className={r.success_pct !== null && r.success_pct < 100 ? "text-amber-300" : ""}>{r.success_pct === null ? "—" : `${r.success_pct} %`}</Td>
                <Td className="text-emerald-300">{r.reliable}</Td><Td className="text-sky-300">{r.fragile}</Td><Td className="text-rose-300">{r.blocked}</Td>
                <Td className="text-amber-300">{r.fallback - r.blocked}</Td>
              </tr>))}</tbody>
          </table>
        </div>
        <p className="mt-2 text-[11px] text-slate-500">Fiable = API ou flux structuré · Fragile = lecture « au mieux » d'une page web · Bloquée = protection volontaire de l'employeur (403 / anti-robot) · Repli Jooble = échec de lecture.</p>
        {Object.keys(d.redetect || {}).length > 0 && <p className="mt-1 text-[11px] text-sky-300" data-testid="connectors-redetect">Désormais pris en charge, à re-détecter par les membres (loupe ou « Tout détecter ») : {Object.entries(d.redetect).map(([k, v]) => `${k} (${v})`).join(", ")}.</p>}
      </section>
    </div>
  );
};
