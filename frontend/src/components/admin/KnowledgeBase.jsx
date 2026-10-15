import { useEffect, useState } from "react";
import { Database, Loader2 } from "lucide-react";
import { toast } from "sonner";
import { adminKnowledge } from "@/lib/api";
import { ClickNum, DetailDialog } from "./DetailDialog";

const ST = { fiable: ["Fiable", "text-emerald-300"], fragile: ["Fragile", "text-amber-300"], bloque: ["Bloqué par l'employeur (403)", "text-rose-300"] };
const CONF = { elevee: ["Élevée", "text-emerald-300"], moyenne: ["Moyenne", "text-amber-300"], faible: ["Faible", "text-slate-400"] };
const date = (s) => (s ? new Date(s).toLocaleDateString("fr-CA", { day: "numeric", month: "long", year: "numeric" }) : "—");
const KPIS = [["total", "Fiches employeurs", null], ["fiable", "Fiables", (r) => r.status === "fiable"], ["fragile", "Fragiles", (r) => r.status === "fragile"],
  ["bloque", "Bloquées (403)", (r) => r.status === "bloque"], ["elevee", "Confiance élevée", (r) => r.confidence === "elevee"]];

export const KnowledgeBase = () => {
  const [d, setD] = useState(null);
  const [detail, setDetail] = useState(null);
  useEffect(() => { adminKnowledge(sessionStorage.getItem("adminPwd")).then(setD).catch((e) => toast.error(e.message)); }, []);
  if (!d) return <Loader2 className="h-5 w-5 animate-spin text-emerald-400" />;
  const open = (label, f) => setDetail({ title: `Base commune · ${label}`, cols: [["name", "Entreprise"], ["kind_label", "Portail"], ["s", "Statut"], ["d", "Dernière validation"]],
    rows: d.items.filter((r) => !f || f(r)).map((r) => ({ ...r, s: ST[r.status]?.[0], d: date(r.last_validated) })), note: "Aucune donnée membre : nom, portail public, type, statut et dates uniquement." });
  return (
    <section className="space-y-4 rounded-2xl border border-white/10 bg-slate-900/60 p-4 sm:p-5" data-testid="admin-knowledge">
      <DetailDialog detail={detail} onClose={() => setDetail(null)} />
      <div>
        <h3 className="flex items-center gap-2 text-sm font-semibold text-slate-200"><Database className="h-4 w-4 text-emerald-400" />Base commune CareerOS</h3>
        <p className="text-[11px] text-slate-500">Portails confirmés (lecture réussie + au moins une offre) par l'utilisation de la plateforme, partagés avec tous les membres. Aucune donnée personnelle.</p>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {KPIS.map(([k, label, f]) => (
          <div key={k} role="button" tabIndex={0} onClick={() => open(label, f)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); open(label, f); } }}
            className="cursor-pointer rounded-xl border border-white/10 p-3 hover:border-emerald-400/40" data-testid={`knowledge-kpi-${k}`}>
            <p className="text-[11px] text-slate-500">{label}</p><p className="font-mono text-xl font-bold text-white">{d.stats[k]}</p>
          </div>))}
      </div>
      {d.items.length === 0 ? <p className="text-xs text-slate-500" data-testid="knowledge-empty">Aucune fiche pour l'instant : elles se créent automatiquement aux prochains passages du Radar.</p> : (
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-[12px]">
            <thead className="text-slate-500"><tr className="border-b border-white/10">{["Entreprise", "Portail", "Statut", "Confiance", "Validations", "Offres lues", "Dernière validation"].map((h) => <th key={h} className="py-2 pr-3 font-medium">{h}</th>)}</tr></thead>
            <tbody>{d.items.map((r, i) => (
              <tr key={r.name} className="border-b border-white/5" data-testid={`knowledge-row-${i}`}>
                <td className="py-2 pr-3 font-semibold text-white">{r.portal_url ? <a href={r.portal_url} target="_blank" rel="noreferrer" className="hover:underline" data-testid={`knowledge-link-${i}`}>{r.name}</a> : r.name}</td>
                <td className="pr-3">{r.kind_label}</td>
                <td className={`pr-3 ${ST[r.status]?.[1]}`} data-testid={`knowledge-status-${i}`}>{ST[r.status]?.[0]}</td>
                <td className={`pr-3 ${CONF[r.confidence][1]}`} data-testid={`knowledge-conf-${i}`}>{CONF[r.confidence][0]}</td>
                <td className="pr-3 font-mono"><ClickNum testid={`knowledge-validations-${i}`} onClick={() => setDetail({ title: `${r.name} · indice de confiance`, cols: [["k", "Élément"], ["v", "Valeur"]],
                  rows: [{ k: "Validations (jours distincts)", v: r.validations }, { k: "Dernière validation réussie", v: date(r.last_success) }, { k: "Offres lues au dernier passage", v: r.recent_offers }, { k: "Dernier contrôle", v: date(r.last_validated) }] })}>{r.validations}</ClickNum></td>
                <td className="pr-3 font-mono">{r.recent_offers}</td>
                <td className="pr-3">{date(r.last_validated)}</td>
              </tr>))}</tbody>
          </table>
        </div>)}
    </section>
  );
};
