import { Copy, FileDown, FileText } from "lucide-react";
import { toast } from "sonner";
import { downloadAtsCvDocx, downloadCoverLetterDocx } from "@/lib/docxExport";
import { downloadPdf } from "@/lib/packExport";

const bold = (t, k) => t.split(/(\*\*[^*]+\*\*)/g).map((p, i) =>
  p.startsWith("**") && p.endsWith("**") ? <strong key={`${k}-${i}`} className="font-semibold text-white">{p.slice(2, -2)}</strong> : p);

export const Markdown = ({ text, testid }) => (
  <div className="space-y-1.5 text-sm leading-relaxed text-slate-300" data-testid={testid}>
    {(text || "").replace(/\r/g, "").split("\n").map((raw, i) => {
      const line = raw.trim();
      if (!line || /^[-*_]{3,}$/.test(line)) return <div key={i} className="h-2" />;
      const h = line.match(/^(#{1,6})\s+(.*)$/);
      if (h) {
        const cls = h[1].length === 1 ? "font-display text-2xl font-bold text-white" : h[1].length === 2 ? "mt-4 border-b border-white/10 pb-1 text-xs font-semibold uppercase tracking-[0.15em] text-indigo-300" : "mt-2 font-semibold text-white";
        return <div key={i} className={cls}>{bold(h[2], i)}</div>;
      }
      const b = line.match(/^[-*•]\s+(.*)$/);
      if (b) return <div key={i} className="flex gap-2 pl-1"><span className="mt-2 h-1 w-1 shrink-0 rounded-full bg-indigo-400" /><span>{bold(b[1], i)}</span></div>;
      return <p key={i}>{bold(line, i)}</p>;
    })}
  </div>
);

const Btn = ({ onClick, icon: Icon, children, testid }) => (
  <button onClick={onClick} data-testid={testid}
    className="flex items-center gap-1.5 rounded-full border border-white/10 bg-white/[0.03] px-3 py-1.5 text-xs text-slate-300 transition-colors hover:border-indigo-400/40 hover:text-white">
    <Icon className="h-3.5 w-3.5" />{children}
  </button>
);

export const DocActions = ({ markdown, name, kind = "md", testid }) => {
  const copy = async () => {
    await navigator.clipboard.writeText((markdown || "").replace(/\*\*/g, ""));
    toast.success("Copié dans le presse-papiers");
  };
  const docx = () => (kind === "letter" ? downloadCoverLetterDocx(markdown, `${name}.docx`) : downloadAtsCvDocx(markdown, `${name}.docx`));
  return (
    <div className="flex flex-wrap gap-2" data-testid={`${testid}-actions`}>
      <Btn onClick={copy} icon={Copy} testid={`${testid}-copy-btn`}>Copier</Btn>
      <Btn onClick={docx} icon={FileText} testid={`${testid}-docx-btn`}>DOCX</Btn>
      <Btn onClick={() => downloadPdf(markdown, `${name}.pdf`)} icon={FileDown} testid={`${testid}-pdf-btn`}>PDF</Btn>
    </div>
  );
};
