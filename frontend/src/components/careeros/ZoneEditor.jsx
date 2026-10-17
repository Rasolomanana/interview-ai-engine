import { Plus, X } from "lucide-react";

export const RADII = [["25", "25 km"], ["50", "50 km"], ["100", "100 km"], ["200", "200 km"], ["province", "Toute la province"], ["country", "Tout le pays"]];
const inputCls = "min-w-0 flex-1 rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/60";
const selCls = "w-36 shrink-0 rounded-xl border border-white/10 bg-black/40 px-2 py-2 text-sm text-white outline-none focus:border-indigo-400/60";

const ZoneRow = ({ loc, radius, onLoc, onRadius, onRemove, i }) => (
  <div className="flex items-center gap-2" data-testid={`radar-zone-row-${i}`}>
    <input value={loc} onChange={(e) => onLoc(e.target.value)} placeholder={i ? "Ville (ex. Québec, Québec)" : "Ville principale"} className={inputCls} data-testid={i ? `radar-zone-location-${i}` : "radar-location-input"} />
    <select value={radius} onChange={(e) => onRadius(e.target.value)} className={selCls} aria-label="Rayon" data-testid={i ? `radar-zone-radius-${i}` : "radar-radius-select"}>
      {RADII.map(([k, l]) => <option key={k} value={k} className="bg-[#121520]">{l}</option>)}
    </select>
    {onRemove ? <button type="button" onClick={onRemove} className="rounded-full p-1.5 text-slate-500 hover:bg-white/5 hover:text-rose-300" title="Retirer cette zone" data-testid={`radar-zone-remove-${i}`}><X className="h-4 w-4" /></button> : <span className="w-7" />}
  </div>
);

// Main Radar location + radius, plus up to 2 extra cities — side by side.
export const ZoneEditor = ({ s, setS }) => {
  const extra = s.extra_zones || [];
  const setExtra = (z) => setS({ ...s, extra_zones: z });
  const upd = (i, k, v) => setExtra(extra.map((z, j) => (j === i ? { ...z, [k]: v } : z)));
  return (
    <div className="space-y-2" data-testid="radar-zones">
      <div className="flex items-center justify-between text-slate-400"><span>Localisation et rayon de recherche</span><span className="text-[11px] text-slate-500">jusqu'à 3 villes</span></div>
      <ZoneRow i={0} loc={s.location} radius={s.radius || "100"} onLoc={(v) => setS({ ...s, location: v })} onRadius={(v) => setS({ ...s, radius: v })} />
      {extra.map((z, i) => <ZoneRow key={i} i={i + 1} loc={z.location} radius={z.radius || "100"} onLoc={(v) => upd(i, "location", v)} onRadius={(v) => upd(i, "radius", v)} onRemove={() => setExtra(extra.filter((_, j) => j !== i))} />)}
      {extra.length < 2 && <button type="button" onClick={() => setExtra([...extra, { location: "", radius: "100" }])} className="flex items-center gap-1 text-[11px] text-indigo-300 hover:text-indigo-200" data-testid="radar-zone-add-btn"><Plus className="h-3.5 w-3.5" />Ajouter une ville</button>}
      <p className="text-[11px] text-slate-500">Une offre est gardée si elle se trouve dans l'une de vos zones. Les offres sans lieu, en télétravail ou « Canada » sont gardées. Les autres sont masquées (consultables via « hors zone »). Jooble cherche dans chaque ville.</p>
    </div>
  );
};
