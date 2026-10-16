import { useEffect, useState } from "react";
import { BellRing, CheckCircle2, Copy, ExternalLink, Link2, Send } from "lucide-react";
import { toast } from "sonner";
import { careeros } from "@/lib/careeros";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const host = (u) => { try { return new URL(u).hostname.replace(/^www\./, ""); } catch { return ""; } };
const LATER = (id) => `cos.applyLater.${id}`;

// Follow-up reminder 7 days later, as a downloadable .ics (nothing is added to a calendar automatically).
const relanceIcs = (a, d) => {
  const day = new Date(Date.now() + 7 * 864e5);
  const ymd = day.toISOString().slice(0, 10).replace(/-/g, "");
  const esc = (s) => String(s || "").replace(/[,;\\]/g, (c) => `\\${c}`).replace(/\n/g, "\\n");
  const ics = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//CareerOS//Relance//FR", "BEGIN:VEVENT", `UID:relance-${a.id}@careeros`,
    `DTSTAMP:${new Date().toISOString().replace(/[-:]/g, "").slice(0, 15)}Z`, `DTSTART;VALUE=DATE:${ymd}`, `SUMMARY:${esc(`Relancer ${d.entreprise || "l'employeur"} — ${d.poste || "candidature"}`)}`,
    `DESCRIPTION:${esc(`Candidature ${a.code} envoyée il y a 7 jours. ${a.offer_link || ""}`)}`, "END:VEVENT", "END:VCALENDAR"].join("\r\n");
  Object.assign(document.createElement("a"), { href: URL.createObjectURL(new Blob([ics], { type: "text/calendar" })), download: `${a.code}_relance.ics` }).click();
};

const Step = ({ n, label, on, done }) => (
  <span className={`flex items-center gap-1.5 text-[11px] ${done ? "text-emerald-300" : on ? "text-white" : "text-slate-500"}`}>
    <span className={`flex h-5 w-5 items-center justify-center rounded-full border text-[10px] ${done ? "border-emerald-400 bg-emerald-500/20" : on ? "border-indigo-400 bg-indigo-500/20" : "border-white/15"}`}>{done ? "✓" : n}</span>{label}
  </span>
);

export const ApplyBar = ({ a, d, onChange }) => {
  const [url, setUrl] = useState("");
  const [ask, setAsk] = useState(false);
  const [justApplied, setJustApplied] = useState(false);
  const applied = a.pipeline_status !== "a_postuler";
  useEffect(() => { if (a.apply_opened_at && !applied && !sessionStorage.getItem(LATER(a.id))) setAsk(true); }, [a.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const open = () => {
    window.open(a.offer_link, "_blank", "noopener");
    if (!applied) careeros.applyOpened(a.id).then(() => onChange({ apply_opened_at: new Date().toISOString() })).catch(() => {});
    if (!applied) { sessionStorage.removeItem(LATER(a.id)); const back = () => { if (document.visibilityState === "visible") { setAsk(true); document.removeEventListener("visibilitychange", back); } }; document.addEventListener("visibilitychange", back); }
  };
  const confirm = async () => {
    try { const r = await careeros.applied(a.id); onChange({ pipeline_status: "postule", applied_at: r.applied_at, apply_opened_at: null }); setAsk(false); setJustApplied(true); toast.success("Candidature confirmée : statut « Postulé », date enregistrée dans le dossier."); }
    catch (e) { toast.error(e.message); }
  };
  const notYet = async () => { await careeros.applyNotYet(a.id).catch(() => {}); onChange({ apply_opened_at: null }); setAsk(false); };
  const later = () => { sessionStorage.setItem(LATER(a.id), "1"); setAsk(false); toast.message("D'accord, je vous le redemanderai à votre prochaine visite de ce dossier."); };
  const save = async () => {
    try { const r = await careeros.setOfferLink(a.id, url); onChange({ offer_link: r.offer_link }); setUrl(""); toast.success("Lien de l'offre enregistré."); } catch (e) { toast.error(e.message); }
  };
  const copy = () => navigator.clipboard.writeText(a.offer_link).then(() => toast.success("Lien copié."));
  const optimized = a.status === "done";
  return (
    <section className="mb-6 rounded-2xl border border-emerald-400/25 bg-emerald-500/[0.06] p-4 sm:p-5" data-testid="apply-bar">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2" data-testid="apply-steps">
        <Step n={1} label="Optimiser le CV (onglets CV ATS / CV humain)" on={!optimized} done={optimized} />
        <span className="text-slate-600">→</span>
        <Step n={2} label="Postuler sur le site de l'offre" on={optimized && !applied && !a.apply_opened_at} done={applied || !!a.apply_opened_at} />
        <span className="text-slate-600">→</span>
        <Step n={3} label="Confirmer « J'ai postulé »" on={!!a.apply_opened_at && !applied} done={applied} />
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {a.offer_link ? <>
          <button type="button" onClick={open} className="flex items-center gap-2 rounded-full bg-emerald-500 px-5 py-2.5 text-sm font-semibold text-black hover:bg-emerald-400" data-testid="apply-open-offer-btn">
            <ExternalLink className="h-4 w-4" />{applied ? "Revoir l'offre" : "Postuler sur le site de l'offre"}
          </button>
          <span className="text-xs text-slate-300" data-testid="apply-offer-host">{host(a.offer_link)}{a.offer_source ? ` · via ${a.offer_source}` : ""}</span>
          <button type="button" onClick={copy} className="flex items-center gap-1 rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:text-white" data-testid="apply-copy-link-btn"><Copy className="h-3.5 w-3.5" />Copier le lien</button>
        </> : (
          <div className="flex w-full flex-wrap items-center gap-2 sm:w-auto" data-testid="apply-add-link">
            <Link2 className="h-4 w-4 text-amber-300" /><span className="text-xs text-amber-200">Aucun lien d'offre enregistré pour ce dossier.</span>
            <input value={url} onChange={(e) => setUrl(e.target.value)} placeholder="https://… (adresse de l'annonce)" className="min-w-[240px] flex-1 rounded-full border border-white/10 bg-black/40 px-3 py-1.5 text-xs text-white outline-none" data-testid="apply-link-input" />
            <button type="button" onClick={save} disabled={!url.trim()} className="rounded-full border border-emerald-400/40 px-3 py-1.5 text-xs text-emerald-200 disabled:opacity-40" data-testid="apply-link-save-btn">Enregistrer le lien</button>
          </div>)}
        {applied ? (
          <span className="ml-auto flex items-center gap-1.5 text-xs text-emerald-300" data-testid="apply-done">
            <CheckCircle2 className="h-4 w-4" />{a.applied_at ? `Postulé le ${new Date(a.applied_at).toLocaleDateString("fr-CA", { day: "numeric", month: "long", year: "numeric" })}` : "Candidature envoyée"}
            <button type="button" onClick={() => relanceIcs(a, d)} className="ml-2 flex items-center gap-1 rounded-full border border-white/10 px-2.5 py-1 text-slate-300 hover:text-white" data-testid="apply-relance-ics-btn"><BellRing className="h-3.5 w-3.5" />Rappel de relance J+7 (.ics)</button>
          </span>
        ) : (
          <button type="button" onClick={confirm} className="ml-auto flex items-center gap-1.5 rounded-full border border-emerald-400/50 px-4 py-2 text-xs font-semibold text-emerald-200 hover:bg-emerald-500/10" data-testid="apply-confirm-btn"><Send className="h-3.5 w-3.5" />J'ai postulé</button>
        )}
      </div>
      {justApplied && <p className="mt-3 text-[11px] text-slate-400" data-testid="apply-relance-hint">Conseil : relancez l'employeur dans 7 jours si vous n'avez pas de réponse. Le rappel .ics se télécharge ; rien n'est ajouté à votre calendrier sans votre action.</p>}
      <Dialog open={ask} onOpenChange={(o) => !o && later()}>
        <DialogContent className="max-w-md border-white/10 bg-[#121520] text-slate-100" data-testid="apply-ask-dialog">
          <DialogHeader><DialogTitle>Avez-vous postulé ?</DialogTitle>
            <DialogDescription className="text-slate-400">{d.poste || "Cette offre"}{d.entreprise ? ` · ${d.entreprise}` : ""} — vous avez ouvert l'offre{a.apply_opened_at ? ` le ${new Date(a.apply_opened_at).toLocaleDateString("fr-CA", { day: "numeric", month: "long" })}` : ""}.</DialogDescription></DialogHeader>
          <div className="flex flex-col gap-2">
            <button type="button" onClick={confirm} className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-semibold text-black" data-testid="apply-ask-yes">Oui, j'ai postulé</button>
            <button type="button" onClick={notYet} className="rounded-full border border-white/10 px-4 py-2 text-sm text-slate-200" data-testid="apply-ask-not-yet">Pas encore</button>
            <button type="button" onClick={later} className="text-xs text-slate-400 hover:text-white" data-testid="apply-ask-later">Me le rappeler plus tard</button>
          </div>
        </DialogContent>
      </Dialog>
    </section>
  );
};
