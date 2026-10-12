import { useCallback, useEffect, useState } from "react";
import { CalendarPlus, Copy, Loader2, Mail, Send } from "lucide-react";
import { toast } from "sonner";
import { careeros, followup } from "@/lib/careeros";

const inputCls = "w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/60";
const card = "rounded-2xl border border-white/[0.07] bg-[#121520]/80 p-5";
const KINDS = [["confirmation", "Confirmation d'entrevue"], ["remerciement", "Remerciement"], ["relance", "Relance"]];
const STATUS = { brouillon: "Brouillon", pret: "Validé", envoye: "Envoyé" };

const Draft = ({ e, app, reload }) => {
  const [f, setF] = useState({ to: e.to, subject: e.subject, body: e.body });
  const save = (changes) => followup.patch(app.id, "emails", e.id, changes).then(reload).catch((x) => toast.error(x.message));
  const mailto = `mailto:${encodeURIComponent(f.to)}?subject=${encodeURIComponent(f.subject)}&body=${encodeURIComponent(f.body)}`;
  return (
    <div className="space-y-2 rounded-xl border border-white/10 p-3" data-testid={`email-draft-${e.id}`}>
      <div className="flex items-center justify-between text-xs"><span className="font-semibold text-slate-200">{KINDS.find((k) => k[0] === e.kind)?.[1]}</span>
        <span className="rounded bg-white/5 px-2 py-0.5 text-slate-400" data-testid={`email-status-${e.id}`}>{STATUS[e.status]}</span></div>
      <input value={f.to} onChange={(x) => setF({ ...f, to: x.target.value })} placeholder="Destinataire (courriel)" className={inputCls} data-testid={`email-to-${e.id}`} />
      <input value={f.subject} onChange={(x) => setF({ ...f, subject: x.target.value })} className={inputCls} data-testid={`email-subject-${e.id}`} />
      <textarea rows={7} value={f.body} onChange={(x) => setF({ ...f, body: x.target.value })} className={inputCls} data-testid={`email-body-${e.id}`} />
      <div className="flex flex-wrap gap-2 text-xs">
        <button onClick={() => save({ ...f, status: "pret" })} data-testid={`email-validate-${e.id}`} className="rounded-full bg-indigo-500 px-3 py-1.5 font-semibold text-white hover:bg-indigo-400">Valider le brouillon</button>
        <button onClick={() => { navigator.clipboard.writeText(`${f.subject}\n\n${f.body}`); toast.success("Copié"); }} className="flex items-center gap-1 rounded-full border border-white/10 px-3 py-1.5 text-slate-300"><Copy className="h-3.5 w-3.5" />Copier</button>
        {e.status !== "brouillon" && <a href={mailto} data-testid={`email-open-${e.id}`} className="flex items-center gap-1 rounded-full border border-white/10 px-3 py-1.5 text-slate-300"><Mail className="h-3.5 w-3.5" />Ouvrir dans ma messagerie</a>}
        {e.status === "pret" && <button onClick={() => window.confirm("Confirmez-vous avoir envoyé ce courriel ?") && save({ status: "envoye" })} data-testid={`email-mark-sent-${e.id}`} className="flex items-center gap-1 rounded-full border border-white/10 px-3 py-1.5 text-slate-300"><Send className="h-3.5 w-3.5" />Marquer comme envoyé</button>}
      </div>
    </div>
  );
};

export const FollowupPanel = ({ app }) => {
  const [d, setD] = useState(null);
  const [iv, setIv] = useState({ stage: "rh", scheduled_at: "", mode: "visio", location: "" });
  const [ctx, setCtx] = useState({ recruiter_name: "", to: "" });
  const [busy, setBusy] = useState("");
  const reload = useCallback(() => careeros.dossier(app.id).then(setD), [app.id]);
  useEffect(() => { reload(); }, [reload]);

  const addInterview = async () => {
    if (!iv.scheduled_at) return toast.error("Indiquez la date et l'heure");
    await followup.addInterview(app.id, { ...iv, scheduled_at: new Date(iv.scheduled_at).toISOString() });
    toast.success("Entrevue ajoutée au dossier"); reload();
  };
  const draft = async (kind) => {
    setBusy(kind);
    const next = (d?.interviews || []).find((i) => i.scheduled_at);
    try { await followup.draft(app.id, { kind, ...ctx, interview_at: next ? new Date(next.scheduled_at).toLocaleString("fr-CA") : "" }); reload(); }
    catch (e) { toast.error(e.message); } finally { setBusy(""); }
  };
  if (!d) return <Loader2 className="h-5 w-5 animate-spin text-indigo-400" />;
  return (
    <div className="grid gap-4 lg:grid-cols-2" data-testid="followup-panel">
      <section className={card}>
        <h3 className="mb-3 text-sm font-semibold text-white">Entrevues · {app.code}</h3>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <select value={iv.stage} onChange={(e) => setIv({ ...iv, stage: e.target.value })} className={inputCls} data-testid="interview-stage-select">
            {["rh", "gestionnaire", "technique", "panel", "final"].map((s) => <option key={s} value={s}>{s}</option>)}</select>
          <input type="datetime-local" value={iv.scheduled_at} onChange={(e) => setIv({ ...iv, scheduled_at: e.target.value })} className={inputCls} data-testid="interview-datetime-input" />
          <select value={iv.mode} onChange={(e) => setIv({ ...iv, mode: e.target.value })} className={inputCls}><option value="visio">Visio</option><option value="telephone">Téléphone</option><option value="presentiel">Présentiel</option></select>
          <input value={iv.location} onChange={(e) => setIv({ ...iv, location: e.target.value })} placeholder="Lien ou adresse" className={inputCls} />
        </div>
        <button onClick={addInterview} data-testid="interview-add-btn" className="mt-2 rounded-full bg-indigo-500 px-3 py-1.5 text-xs font-semibold text-white hover:bg-indigo-400">Ajouter l'entrevue</button>
        <ul className="mt-4 space-y-2">
          {(d.interviews || []).map((i) => (
            <li key={i.id} className="flex items-center justify-between rounded-lg bg-black/30 px-3 py-2 text-xs" data-testid={`interview-${i.id}`}>
              <span className="text-slate-200">{i.stage.toUpperCase()} · {i.scheduled_at ? new Date(i.scheduled_at).toLocaleString("fr-CA") : "—"} · {i.mode}</span>
              <button onClick={() => followup.downloadIcs(app.id, i.id, app.code).catch((e) => toast.error(e.message))} data-testid={`interview-ics-${i.id}`} className="flex items-center gap-1 text-indigo-300"><CalendarPlus className="h-3.5 w-3.5" />.ics (Google, Outlook, Apple)</button>
            </li>))}
        </ul>
        <p className="mt-3 text-[11px] text-slate-500">Le fichier .ics s'importe d'un clic dans votre agenda. Rien n'est ajouté sans votre action.</p>
      </section>
      <section className={card}>
        <h3 className="mb-3 text-sm font-semibold text-white">Courriels de suivi (validation obligatoire)</h3>
        <div className="grid grid-cols-2 gap-2">
          <input value={ctx.recruiter_name} onChange={(e) => setCtx({ ...ctx, recruiter_name: e.target.value })} placeholder="Nom du recruteur" className={inputCls} data-testid="email-recruiter-input" />
          <input value={ctx.to} onChange={(e) => setCtx({ ...ctx, to: e.target.value })} placeholder="Courriel du recruteur" className={inputCls} />
        </div>
        <div className="mt-2 flex flex-wrap gap-2">
          {KINDS.map(([k, l]) => <button key={k} onClick={() => draft(k)} disabled={!!busy} data-testid={`email-generate-${k}`} className="flex items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-200 hover:text-white disabled:opacity-50">{busy === k && <Loader2 className="h-3.5 w-3.5 animate-spin" />}{l}</button>)}
        </div>
        <div className="mt-4 space-y-3">{(d.emails || []).slice().reverse().map((e) => <Draft key={e.id} e={e} app={app} reload={reload} />)}</div>
        <p className="mt-3 text-[11px] text-slate-500">Aucun courriel n'est envoyé automatiquement : vous validez, puis l'envoyez depuis votre messagerie.</p>
      </section>
    </div>
  );
};
