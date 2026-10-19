import { useEffect, useState } from "react";
import { cvOptimize } from "@/lib/careeros";
import { buildCv, matchOf } from "@/lib/cvOptimize";

const r1 = (n) => Math.round(n * 10) / 10;
const labelOf = (x) => x.label || (x.type === "ajout" ? `Compétences clés regroupées en haut du CV (${x.skills.length})`
  : x.skills?.length ? `Reformulation : ${x.skills.slice(0, 3).join(", ")}` : "Reformulation d'une expérience");

// Simulates compatibility (browser rules) and Pro strength (server rules) for the current selection, guaranteed vs potential.
export const useImpact = (profile, offer, cv, items, sel) => {
  const [sim, setSim] = useState(null);
  const key = [...sel].sort().join("|");
  useEffect(() => {
    if (!profile || !items) return undefined;
    const t = setTimeout(async () => {
      const confirmIds = items.filter((x) => x.type === "a_confirmer").map((x) => x.id);
      const pot = new Set([...sel, ...confirmIds]);
      const singles = items.filter((x) => sel.has(x.id) || x.type === "a_confirmer");
      const variants = { base: cv, after: buildCv(cv, items, sel), potential: buildCv(cv, items, pot) };
      const keyOf = Object.fromEntries(singles.map((x, i) => [x.id, `i${i}`]));  // short keys (ids can be long skill labels)
      singles.forEach((x) => { variants[keyOf[x.id]] = buildCv(cv, items, new Set([x.id])); });
      try {
        const s = await cvOptimize.simulate(variants);
        const m = (v) => matchOf(profile, variants[v], offer);
        const base = m("base");
        const parts = singles.map((x) => ({ id: x.id, label: labelOf(x), potential: x.type === "a_confirmer", match: m(keyOf[x.id]) - base, ifp: r1(s[keyOf[x.id]].score - s.base.score) }))
          .filter((p) => p.match > 0 || p.ifp > 0).sort((a, b) => Number(a.potential) - Number(b.potential) || b.match - a.match || b.ifp - a.ifp);
        const criteria = Object.keys(s.base.criteria).map((k) => ({ label: s.base.labels[k], delta: r1(s.after.criteria[k] - s.base.criteria[k]) })).filter((c) => c.delta);
        setSim({ match: { before: base, after: m("after"), potential: m("potential") }, ifp: { before: s.base.score, after: s.after.score, potential: s.potential.score }, parts, criteria });
      } catch { setSim({ error: true }); }
    }, 350);
    return () => clearTimeout(t);
  }, [profile, offer, cv, items, key]); // eslint-disable-line react-hooks/exhaustive-deps
  return sim;
};
