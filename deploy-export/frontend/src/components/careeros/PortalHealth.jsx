import { useState } from "react";
import { ArrowDownUp, TriangleAlert } from "lucide-react";
import { InfoTip } from "@/components/careeros/guide/InfoTip";
import { KIND_LABEL, QUALITY, qualityOf } from "@/lib/portals";

const tid = (n) => n.replace(/[^a-z0-9]/gi, "-");
const COLS = [["name", "Entreprise"], ["kind", "Plateforme"], ["quality", "Qualité"], ["fetched", "Lues"], ["matched", "Retenues"], ["note", "État"]];

const note = (p) => {
  if (p.blocked) return "Bloqué par l'employeur (anti-robot) · repli Jooble";
  if (!p.ok) return `Échec de lecture · repli Jooble${p.error ? ` (${p.error.slice(0, 80)})` : ""}`;
  if (!p.fetched) return "Aucune offre publiée actuellement";
  if (!p.matched) return "Aucune offre ne correspond à vos postes / ville";
  return qualityOf(p) === "fragile" ? "Lecture au mieux : résultats possiblement partiels" : "OK";
};

const QualityBadge = ({ p }) => {
  const q = QUALITY[qualityOf(p)];
  return <span className={`inline-flex items-center gap-1.5 whitespace-nowrap ${q.text}`}><span className={`h-2 w-2 rounded-full ${q.dot}`} />{q.label.replace("Lecture ", "")}</span>;
};

const Row = ({ p, active, onPick }) => (
  <tr onClick={() => onPick?.(p.name)} className={`cursor-pointer border-t border-white/[0.05] transition-colors hover:bg-indigo-500/5 ${active ? "bg-indigo-500/10" : ""}`} data-testid={`portal-row-${tid(p.name)}`} title="Afficher les offres de cette entreprise">
    <td className="py-2 pl-2 pr-3 font-medium text-slate-100">{p.name}</td>
    <td className="py-2 pr-3 text-slate-400">{KIND_LABEL[p.kind] || p.kind}</td>
    <td className="py-2 pr-3"><QualityBadge p={p} /></td>
    <td className="py-2 pr-3 text-right tabular-nums text-slate-300">{p.fetched || 0}</td>
    <td className="py-2 pr-3 text-right tabular-nums font-semibold text-white">{p.matched ?? 0}</td>
    <td className={`py-2 pr-2 ${p.ok && p.matched ? "text-slate-500" : "text-amber-300/90"}`}>{note(p)}</td>
  </tr>
);

const Card = ({ p, active, onPick }) => (
  <button type="button" onClick={() => onPick?.(p.name)} className={`w-full rounded-xl border p-3 text-left text-xs ${active ? "border-indigo-400/60 bg-indigo-500/10" : "border-white/[0.06] bg-black/20"}`} data-testid={`portal-card-${tid(p.name)}`}>
    <div className="flex items-center justify-between gap-2"><span className="font-semibold text-slate-100">{p.name}</span><QualityBadge p={p} /></div>
    <div className="mt-1 flex justify-between text-slate-400"><span>{KIND_LABEL[p.kind] || p.kind}</span><span>{p.fetched || 0} lues · <b className="text-white">{p.matched ?? 0}</b> retenues</span></div>
    {(!p.ok || !p.matched) && <p className="mt-1 flex items-center gap-1 text-amber-300/90"><TriangleAlert className="h-3 w-3" />{note(p)}</p>}
  </button>
);

export const PortalHealth = ({ status, run, active, onPick }) => {
  const [qf, setQf] = useState(null);
  const [sort, setSort] = useState(["matched", -1]);
  const all = Object.entries(run?.portals || {}).map(([name, p]) => ({ ...p, name, quality: qualityOf(p), note: note(p) }));
  const configured = (status?.portals?.workday || 0) + (status?.portals?.boards || 0);
  const ok = all.filter((p) => p.ok).length;
  const rate = all.length ? Math.round((ok * 100) / all.length) : null;
  const counts = all.reduce((a, p) => ({ ...a, [p.quality]: (a[p.quality] || 0) + 1 }), {});
  const [key, dir] = sort;
  const rows = all.filter((p) => !qf || p.quality === qf).sort((a, b) => {
    const x = a[key] ?? 0, y = b[key] ?? 0;
    return (typeof x === "number" ? x - y : String(x).localeCompare(String(y), "fr")) * dir;
  });
  const sortBy = (k) => setSort(([c, d]) => [k, c === k ? -d : ["fetched", "matched"].includes(k) ? -1 : 1]);
  return (
    <section className="rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-4" data-testid="radar-portal-health">
      <div className="mb-3 flex flex-wrap items-baseline gap-x-5 gap-y-1">
        <p className="flex items-center font-mono text-[10px] uppercase tracking-[0.18em] text-slate-500">Portails employeurs<InfoTip k="portails" /></p>
        <span className="text-xs text-slate-300" data-testid="portal-configured">{configured} configuré(s)</span>
        <span className="text-xs text-slate-300" data-testid="portal-success-rate">Lecture réussie : {rate === null ? "—" : `${ok}/${all.length} (${rate} %)`}</span>
        <span className="text-xs text-slate-300">Offres : {all.reduce((a, p) => a + (p.fetched || 0), 0)} lues · {all.reduce((a, p) => a + (p.matched || 0), 0)} retenues</span>
      </div>
      {all.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2" data-testid="portal-quality-summary">
          {Object.entries(QUALITY).map(([k, q]) => (
            <button type="button" key={k} disabled={!counts[k]} onClick={() => setQf((c) => (c === k ? null : k))}
              className={`flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-[11px] text-slate-300 transition-colors enabled:hover:border-indigo-400/40 disabled:opacity-50 ${qf === k ? "border-indigo-400/60 bg-indigo-500/15" : "border-white/[0.07] bg-black/20"}`} data-testid={`portal-quality-${k}`}>
              <span className={`h-2 w-2 rounded-full ${q.dot}`} />{q.label} : <b className="text-white">{counts[k] || 0}</b></button>))}
          {qf && <button type="button" onClick={() => setQf(null)} className="text-[11px] text-indigo-300 hover:text-white" data-testid="portal-quality-clear">Tout afficher</button>}
          <InfoTip k="qualite" className="self-center" />
        </div>)}
      {all.length === 0 ? <p className="text-xs text-slate-500" data-testid="portal-none">Aucun portail lu au dernier passage. Ajoutez des entreprises depuis l'annuaire ou « Trouver le portail » dans les réglages.</p> : (<>
        <div className="hidden overflow-x-auto md:block">
          <table className="w-full text-xs" data-testid="portal-table">
            <thead><tr className="text-left text-[10px] uppercase tracking-wider text-slate-500">
              {COLS.map(([k, l]) => <th key={k} className={`pb-2 pr-3 font-medium ${["fetched", "matched"].includes(k) ? "text-right" : ""} ${k === "name" ? "pl-2" : ""}`}>
                <button type="button" onClick={() => sortBy(k)} className={`inline-flex items-center gap-1 hover:text-white ${key === k ? "text-indigo-300" : ""}`} data-testid={`portal-sort-${k}`}>{l}<ArrowDownUp className="h-3 w-3" /></button></th>)}
            </tr></thead>
            <tbody>{rows.map((p) => <Row key={p.name} p={p} active={active === p.name} onPick={onPick} />)}</tbody>
          </table>
        </div>
        <div className="grid gap-2 md:hidden" data-testid="portal-cards">{rows.map((p) => <Card key={p.name} p={p} active={active === p.name} onPick={onPick} />)}</div>
        <p className="mt-2 text-[11px] text-slate-500">Cliquez une entreprise pour afficher ses offres retenues · cliquez une pastille pour filtrer le tableau.</p>
      </>)}
    </section>
  );
};
