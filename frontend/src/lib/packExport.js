// Converts CareerOS pack parts to markdown (for copy / DOCX / PDF) + a jsPDF markdown renderer.
import { jsPDF } from "jspdf";

const VERDICT = { passe: "Passe", limite: "Limite", rejet: "Rejet" };
const QCATS = [["rh", "Questions RH"], ["gestionnaire", "Questions gestionnaire"], ["comportementales", "Questions comportementales"], ["techniques", "Questions techniques"]];
const list = (arr) => (arr || []).map((x) => `- ${x}`).join("\n");

export function decisionMd(d = {}, ips, reportMd = "") {
  const rows = (ips?.criteria || []).map((c) => `- **${c.label}** (poids ${c.weight}) : ${c.score}/10 → ${c.points} pts — ${c.justification}`).join("\n");
  return `# Décision CareerOS — ${d.poste || "Poste"}${d.entreprise ? ` · ${d.entreprise}` : ""}

## IPS ${ips?.score ?? "—"}/100 · Priorité ${ips?.priority ?? "—"}
${reportMd}

## Détail du calcul IPS
${rows}

${ips?.formula || ""}

## Pourquoi postuler
${list(d.reasons_apply)}

## Pourquoi éviter
${list(d.reasons_avoid)}

## Impact attendu
${d.expected_impact || ""}

## Potentiel salarial
${d.salary_potential || ""}

## Potentiel carrière
${d.career_potential || ""}`;
}

export function atsMd(d = {}) {
  const a = d.ats || {};
  return `# Analyse ATS — score ${a.score ?? "—"}/100

## Mots-clés présents
${list(a.keywords_found)}

## Mots-clés manquants
${list(a.keywords_missing)}

## Écarts
${list(a.gaps)}

## Améliorations
${list(a.improvements)}`;
}

export function simulationMd(d = {}) {
  const s = d.recruiter_simulation || {};
  const lanes = [["ats", "ATS"], ["ia_recruteur", "IA recruteur"], ["recruteur_humain", "Recruteur humain"], ["gestionnaire", "Gestionnaire recruteur"]];
  const sim = lanes.map(([k, l]) => `## ${l} — ${VERDICT[s[k]?.verdict] || s[k]?.verdict || "—"}\n${s[k]?.commentaire || ""}`).join("\n\n");
  const risks = (d.risks || []).map((r) => `- **${r.risque}**\n- Objection : ${r.objection}\n- Correction : ${r.correction}`).join("\n\n");
  return `# Simulation recruteur\n\n${sim}\n\n## Risques, objections et corrections\n${risks}`;
}

export function questionsMd(q = {}) {
  return "# Questions d'entrevue\n\n" + QCATS.map(([k, l]) =>
    `## ${l}\n` + (q[k] || []).map((x, i) => `**${i + 1}. ${x.question}**\n- Objectif : ${x.objectif}\n- Conseil : ${x.conseil}`).join("\n\n")
  ).join("\n\n");
}

export function starMd(s = {}) {
  return "# Réponses STAR\n\n" + (s.star || []).map((x, i) =>
    `## ${i + 1}. ${x.question}\n**Compétence : ${x.competence || ""}**\n- **Situation** : ${x.situation}\n- **Tâche** : ${x.tache}\n- **Action** : ${x.action}\n- **Résultat** : ${x.resultat}`
  ).join("\n\n");
}

const clean = (t) => t.replace(/\*\*/g, "").replace(/[^\u0000-\u00FF\u2013\u2014\u2018\u2019\u201C\u201D\u2022\u20AC\u2026]/g, "");

export function downloadPdf(markdown, filename, reference = "") {
  const doc = new jsPDF({ unit: "pt", format: "a4" });
  const W = doc.internal.pageSize.getWidth(), H = doc.internal.pageSize.getHeight(), M = 48;
  let y = M;
  const write = (text, size, style = "normal", indent = 0, gap = 4) => {
    doc.setFont("helvetica", style); doc.setFontSize(size);
    for (const ln of doc.splitTextToSize(clean(text), W - 2 * M - indent)) {
      if (y + size > H - M) { doc.addPage(); y = M; }
      doc.text(ln, M + indent, y); y += size * 1.3;
    }
    y += gap;
  };
  for (const raw of (markdown || "").replace(/\r/g, "").split("\n")) {
    const line = raw.trim();
    if (!line) { y += 6; continue; }
    if (/^[-*_]{3,}$/.test(line)) continue;
    const h = line.match(/^(#{1,6})\s+(.*)$/);
    if (h) { y += h[1].length === 1 ? 0 : 6; write(h[2], h[1].length === 1 ? 17 : h[1].length === 2 ? 12.5 : 11, "bold", 0, 2); continue; }
    const b = line.match(/^[-*•]\s+(.*)$/);
    if (b) { write(`•  ${b[1]}`, 10, "normal", 10, 1); continue; }
    write(line, 10, /^\*\*.*\*\*$/.test(line) ? "bold" : "normal");
  }
  if (reference) {
    const n = doc.getNumberOfPages();
    for (let i = 1; i <= n; i++) {
      doc.setPage(i); doc.setFont("helvetica", "normal"); doc.setFontSize(7.5); doc.setTextColor(130);
      doc.text(`Réf. CareerOS : ${reference}   ·   ${i}/${n}`, M, H - 22);
    }
  }
  doc.save(filename);
}
