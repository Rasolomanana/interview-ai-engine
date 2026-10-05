import { Document, Packer, Paragraph, TextRun, BorderStyle, AlignmentType } from "docx";
import fs from "fs";

function inlineRuns(text, base = {}) {
  const runs = []; const re = /\*\*(.+?)\*\*/g; let last = 0, m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) runs.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    runs.push(new TextRun({ text: m[1], bold: true, ...base }));
    last = re.lastIndex;
  }
  if (last < text.length) runs.push(new TextRun({ text: text.slice(last), ...base }));
  if (!runs.length) runs.push(new TextRun({ text: "", ...base }));
  return runs;
}

const md = `## RÉSUMÉ PROFESSIONNEL
Superviseur d'opérations avec **8 ans** d'expérience. Titulaire d'une **Licence en Gestion**.

---

## EXPÉRIENCES PROFESSIONNELLES
### Superviseur des Opérations — Quart de Soir | Intelcom Dragonfly, Candiac, QC
- Encadrement de **20 opérateurs**, amélioration KPI de **15%** [à confirmer].
- Application du **lean 5S** et respect des délais.

## COMPÉTENCES
- Gestion d'équipe, SST, WMS`;

const lines = md.replace(/\r/g, "").split("\n");
const children = []; let first = true;
for (const raw of lines) {
  const line = raw.trim();
  if (!line) { children.push(new Paragraph({ spacing: { after: 40 } })); continue; }
  const h = line.match(/^(#{1,6})\s+(.*)$/);
  if (h) {
    const lvl = h[1].length; const txt = h[2].replace(/\*\*/g, "");
    if (lvl === 1) children.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 60 }, children: [new TextRun({ text: txt, bold: true, size: 32 })] }));
    else if (lvl === 2) children.push(new Paragraph({ spacing: { before: first ? 40 : 180, after: 60 }, border: { bottom: { color: "555555", size: 6, space: 2, style: BorderStyle.SINGLE } }, children: [new TextRun({ text: txt.toUpperCase(), bold: true, size: 24 })] }));
    else children.push(new Paragraph({ spacing: { before: 100, after: 40 }, children: [new TextRun({ text: txt, bold: true, size: 22 })] }));
    first = false; continue;
  }
  if (/^[-*_]{3,}$/.test(line)) continue;
  if (/^[-•*]\s+/.test(line)) { children.push(new Paragraph({ bullet: { level: 0 }, spacing: { after: 30 }, children: inlineRuns(line.replace(/^[-•*]\s+/, ""), { size: 21 }) })); first = false; continue; }
  children.push(new Paragraph({ spacing: { after: 40 }, children: inlineRuns(line, { size: 21 }) })); first = false;
}
const doc = new Document({ styles: { default: { document: { run: { font: "Calibri", size: 21 } } } }, sections: [{ properties: { page: { margin: { top: 700, bottom: 700, left: 720, right: 720 } } }, children }] });
const buf = await Packer.toBuffer(doc);
fs.writeFileSync("/tmp/test-cv.docx", buf);
console.log("OK docx bytes:", buf.length, "zip-magic:", buf.slice(0,2).toString());
