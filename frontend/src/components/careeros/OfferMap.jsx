import "leaflet/dist/leaflet.css";
import { Circle, CircleMarker, MapContainer, Popup, TileLayer } from "react-leaflet";
import { Map as MapIcon } from "lucide-react";
import { Foldable } from "@/components/careeros/Foldable";

const COLOR = { A: "#10b981", B: "#f59e0b", C: "#64748b" };

const Legend = ({ n }) => (
  <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px] text-slate-400" data-testid="radar-map-legend">
    {Object.entries(COLOR).map(([k, c]) => <span key={k} className="flex items-center gap-1"><span className="h-2.5 w-2.5 rounded-full" style={{ background: c }} />Priorité {k}</span>)}
    <span>· {n} offre(s) localisée(s) · les offres sans ville reconnue n'apparaissent pas sur la carte</span>
  </div>
);

// OpenStreetMap view: member zones as circles, offers as A/B/C dots with distance on click.
export const OfferMap = ({ zone, points }) => {
  const zones = (zone?.zones || []).filter((z) => z.lat != null);
  const center = zones[0] ? [zones[0].lat, zones[0].lon] : points[0] ? [points[0].lat, points[0].lon] : [45.5, -73.57];
  // Offers sharing a city are spread slightly so each dot stays clickable.
  const seen = {};
  const spread = points.map((p) => { const k = `${p.lat},${p.lon}`; const i = (seen[k] = (seen[k] || 0) + 1) - 1; const a = i * 2.4; return { ...p, y: p.lat + Math.sin(a) * 0.004 * Math.sqrt(i), x: p.lon + Math.cos(a) * 0.006 * Math.sqrt(i) }; });
  return (
    <Foldable storageKey="cos.radar.map.open" title={<span className="inline-flex items-center gap-1.5 text-sm font-semibold text-slate-200"><MapIcon className="h-4 w-4 text-indigo-300" />Carte des offres</span>} hint={`${points.length} offre(s)`} testid="radar-map">
      <div className="h-[380px] overflow-hidden rounded-2xl border border-white/[0.07]" data-testid="radar-map-canvas">
        <MapContainer center={center} zoom={zones[0]?.radius === "province" ? 6 : zones[0]?.radius === "country" ? 4 : 9} scrollWheelZoom={false} className="h-full w-full">
          <TileLayer attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>' url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
          {zones.map((z) => /^\d+$/.test(z.radius) && <Circle key={z.location} center={[z.lat, z.lon]} radius={Number(z.radius) * 1000} pathOptions={{ color: "#818cf8", weight: 1.5, fillOpacity: 0.06 }} />)}
          {zones.map((z) => <CircleMarker key={`c-${z.location}`} center={[z.lat, z.lon]} radius={5} pathOptions={{ color: "#c7d2fe", fillColor: "#6366f1", fillOpacity: 1 }}><Popup>{z.location} · {z.label}</Popup></CircleMarker>)}
          {spread.map((p) => (
            <CircleMarker key={p.id} center={[p.y, p.x]} radius={7} pathOptions={{ color: "#0b0d14", weight: 1, fillColor: COLOR[p.priority] || COLOR.C, fillOpacity: 0.9 }}>
              <Popup><div data-testid={`radar-map-popup-${p.id}`}><b>{p.title}</b><br />{p.company} · {p.location}<br />Priorité {p.priority} · IPS {p.score}<br />{p.distance_km != null ? `${p.distance_km} km de ${p.from}` : "Distance inconnue"}{p.url ? <><br /><a href={p.url} target="_blank" rel="noreferrer">Voir l'offre</a></> : null}</div></Popup>
            </CircleMarker>
          ))}
        </MapContainer>
      </div>
      <Legend n={points.length} />
    </Foldable>
  );
};
