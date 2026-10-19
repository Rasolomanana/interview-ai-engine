import { MapPin } from "lucide-react";
import { N } from "@/lib/skillMap";

// Tells the member when a zone city is unknown (radius impossible) or was read with a spelling correction.
export const ZoneNotice = ({ zones, onFix }) => {
  const unknown = zones.filter((z) => /^\d+$/.test(z.radius) && z.lat == null);
  const fixed = zones.filter((z) => z.city && !N(z.location).startsWith(N(z.city)));
  if (!unknown.length && !fixed.length) return null;
  return (
    <div className="flex flex-wrap items-center gap-2 rounded-xl border border-amber-400/30 bg-amber-500/5 px-3 py-2 text-xs text-amber-100" data-testid="radar-zone-notice">
      <MapPin className="h-3.5 w-3.5 shrink-0" />
      <span className="flex-1">
        {unknown.map((z) => <span key={z.location} className="block" data-testid="radar-zone-unknown">Ville non reconnue : « {z.location} ». Le rayon de {z.label} ne peut pas s'appliquer : vérifiez l'orthographe.</span>)}
        {fixed.map((z) => <span key={z.location} className="block" data-testid="radar-zone-fixed">« {z.location} » est lu comme {z.city} (rayon {z.label}). Corrigez l'orthographe dans les réglages si besoin.</span>)}
      </span>
      <button type="button" onClick={onFix} className="rounded-full border border-amber-400/40 px-3 py-1 font-semibold hover:bg-amber-500/10" data-testid="radar-zone-fix-btn">Corriger mes zones</button>
    </div>
  );
};
