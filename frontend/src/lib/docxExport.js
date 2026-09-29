// Export the ATS-optimized CV (markdown) to a formatted Word .docx.
// Compact margins/sizes so a typical ATS CV fits within ~2 pages.
import { Document, Packer, Paragraph, TextRun, BorderStyle, AlignmentType } from "docx";

// Split a line on **bold** markers into docx TextRuns.
function inlineRuns(text, base = {}) {
  const runs = [];
  const re = /\*\*(.+?)\*\*/g;
  let last = 0;
  let m;
  while ((m = re.exec(text)) !== null) {
    if (m.index > last) runs.push(new TextRun({ text: text.slice(last, m.index), ...base }));
    runs.push(new TextRun({ text: m[1], bold: true, ...base }));
    last = re.lastIndex;
  }
  if (last < text.length) runs.push(new TextRun({ text: text.slice(last), ...base }));
  if (!runs.length) runs.push(new TextRun({ text: "", ...base }));
  return runs;
}

// Export a cover letter (plain prose) to a clean one-page Word .docx.
export async function downloadCoverLetterDocx(text, filename = "Lettre-de-motivation.docx") {
  const lines = (text || "").replace(/\r/g, "").split("\n");
  const children = [];
  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { children.push(new Paragraph({ spacing: { after: 120 } })); continue; }
    children.push(new Paragraph({
      spacing: { after: 120, line: 276 },
      alignment: AlignmentType.JUSTIFIED,
      children: inlineRuns(line, { size: 22 }),
    }));
  }
  const doc = new Document({
    styles: { default: { document: { run: { font: "Calibri", size: 22 } } } },
    sections: [{
      properties: { page: { margin: { top: 1134, bottom: 1134, left: 1134, right: 1134 } } },
      children,
    }],
  });
  const blob = await Packer.toBlob(doc);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}

// docx `size` is in half-points (20 = 10pt).
export async function downloadAtsCvDocx(markdown, filename = "CV-optimise-ATS.docx") {
  const lines = (markdown || "").replace(/\r/g, "").split("\n");
  const children = [];
  let first = true;

  for (const raw of lines) {
    const line = raw.trim();
    if (!line) { children.push(new Paragraph({ spacing: { after: 40 } })); continue; }

    const hMatch = line.match(/^(#{1,6})\s+(.*)$/);
    if (hMatch) {
      const level = hMatch[1].length;
      const txt = hMatch[2].replace(/\*\*/g, "");
      // H1 = name (centered, large), H2 = section (bold + underline rule), H3 = sub.
      if (level === 1) {
        children.push(new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { after: 60 },
          children: [new TextRun({ text: txt, bold: true, size: 32 })],
        }));
      } else if (level === 2) {
        children.push(new Paragraph({
          spacing: { before: first ? 40 : 180, after: 60 },
          border: { bottom: { color: "555555", size: 6, space: 2, style: BorderStyle.SINGLE } },
          children: [new TextRun({ text: txt.toUpperCase(), bold: true, size: 24, color: "1a1a1a" })],
        }));
      } else {
        children.push(new Paragraph({
          spacing: { before: 100, after: 40 },
          children: [new TextRun({ text: txt, bold: true, size: 22 })],
        }));
      }
      first = false;
      continue;
    }

    if (/^[-*_]{3,}$/.test(line)) continue; // markdown horizontal rule -> skip

    if (/^[-•*]\s+/.test(line)) {
      const txt = line.replace(/^[-•*]\s+/, "");
      children.push(new Paragraph({
        bullet: { level: 0 },
        spacing: { after: 30 },
        children: inlineRuns(txt, { size: 21 }),
      }));
      first = false;
      continue;
    }

    children.push(new Paragraph({ spacing: { after: 40 }, children: inlineRuns(line, { size: 21 }) }));
    first = false;
  }

  const doc = new Document({
    styles: { default: { document: { run: { font: "Calibri", size: 21 } } } },
    sections: [{
      properties: { page: { margin: { top: 700, bottom: 700, left: 720, right: 720 } } },
      children,
    }],
  });

  const blob = await Packer.toBlob(doc);
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
