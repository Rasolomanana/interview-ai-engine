import { useState } from "react";
import { Database, Link2, Loader2, ShieldAlert } from "lucide-react";
import { toast } from "sonner";
import { discoverFor } from "@/components/careeros/PortalSuggest";

const CONF = { elevee: "élevée", moyenne: "moyenne", faible: "faible" };

export const fromKnowledge = (k) => ({ kind: k.kind, slug: k.slug, portal_url: k.portal_url, auto: true, detected: `Associé automatiquement · Base commune · ${k.kind_label}` });

// One-click association for a company without a portal: shared knowledge first, then the loupe's best readable candidate.
export const blockedKind = (c, match) => (match && !match.usable ? match.kind_label : (c.detected || "").startsWith("Bloqué (anti-robot) : ") ? c.detected.slice(22) : "");

export const QuickAssociate = ({ c, i, match, onPick }) => {
  const [busy, setBusy] = useState(false);
  const blocked = blockedKind(c, match);
  if (blocked) {
    return <span className="flex items-center gap-1 whitespace-nowrap text-[11px] text-rose-300" title="Portail protégé volontairement par l'employeur : CareerOS ne le contourne pas et suit l'entreprise via Jooble" data-testid={`radar-company-blocked-${i}`}><ShieldAlert className="h-3.5 w-3.5" />{blocked} · bloqué · suivi via Jooble</span>;
  }
  const go = async () => {
    if (match) { onPick(fromKnowledge(match)); toast.success(`${c.name} associée via la base commune CareerOS (${match.kind_label}).`); return; }
    setBusy(true);
    try {
      const r = await discoverFor(c);
      const best = (r.candidates || []).find((p) => p.ok && p.count);
      if (!best) { toast.message(`${c.name} : ${r.message || "aucun portail lisible trouvé"} Ouvrez la loupe ou collez l'URL du portail.`); return; }
      onPick({ kind: best.kind, slug: best.slug, portal_url: best.portal_url, auto: false, detected: "" });
      toast.success(`${c.name} associée à son portail ${best.kind_label} (${best.count} offre(s) visibles).`);
    } catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  return (
    <button type="button" onClick={go} disabled={busy} className="flex items-center gap-1 whitespace-nowrap rounded-full border border-indigo-400/40 px-2 py-0.5 text-[11px] text-indigo-200 hover:bg-indigo-500/20 disabled:opacity-60"
      title={match ? `Base commune : ${match.kind_label}, confiance ${CONF[match.confidence]}, ${match.validations} validation(s)` : "Cherche et associe le meilleur portail lisible"} data-testid={`radar-company-quick-${i}`}>
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : match ? <Database className="h-3.5 w-3.5" /> : <Link2 className="h-3.5 w-3.5" />}
      {match ? `Associer · ${match.kind_label}` : "Associer"}
    </button>
  );
};
