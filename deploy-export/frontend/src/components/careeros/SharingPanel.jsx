import { useEffect, useState } from "react";
import { Eye, Loader2, Lock, Trash2, UserPlus } from "lucide-react";
import { toast } from "sonner";
import { sharing } from "@/lib/careeros";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "@/components/ui/dialog";

const SCOPES = { cv: "CV", memory: "Career Memory", applications: "Candidatures" };
const REL = { conseiller: "Conseiller carrière", proche: "Proche" };
const inputCls = "w-full rounded-xl border border-white/10 bg-black/40 px-3 py-2 text-sm text-white outline-none focus:border-indigo-400/60";
const date = (s) => (s ? new Date(s).toLocaleDateString("fr-CA", { day: "numeric", month: "long", year: "numeric" }) : "jamais");

const SharedView = ({ id, onClose }) => {
  const [d, setD] = useState(null);
  useEffect(() => { if (id) sharing.view(id).then(setD).catch((e) => { toast.error(e.message); onClose(); }); }, [id]); // eslint-disable-line react-hooks/exhaustive-deps
  return (
    <Dialog open={!!id} onOpenChange={(o) => !o && onClose()}>
      <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto" data-testid="shared-view-dialog">
        <DialogHeader><DialogTitle>{d ? `Partagé par ${d.owner_name || d.owner_email}` : "Chargement…"}</DialogTitle></DialogHeader>
        {!d ? <Loader2 className="h-5 w-5 animate-spin" /> : (
          <div className="space-y-4 text-sm">
            <p className="text-[11px] text-slate-500">Lecture seule, autorisée explicitement par le membre et révocable à tout moment.</p>
            {d.memory && <section data-testid="shared-view-memory"><h4 className="mb-1 font-semibold">Career Memory</h4>
              <dl className="grid gap-1 text-xs sm:grid-cols-2">{Object.entries(d.memory).map(([k, v]) => <div key={k}><dt className="text-slate-500">{k}</dt><dd>{Array.isArray(v) ? v.join(", ") : String(v)}</dd></div>)}</dl></section>}
            {d.cv_text !== undefined && <section data-testid="shared-view-cv"><h4 className="mb-1 font-semibold">CV</h4><pre className="max-h-64 overflow-y-auto whitespace-pre-wrap rounded-lg bg-black/30 p-3 font-mono text-[11px]">{d.cv_text || "Aucun CV."}</pre></section>}
            {d.applications && <section data-testid="shared-view-apps"><h4 className="mb-1 font-semibold">Candidatures ({d.applications.length})</h4>
              <ul className="space-y-1 text-xs">{d.applications.map((a) => <li key={a.id} className="rounded border border-white/10 px-2 py-1">{a.poste || "Poste"} · {a.entreprise || "—"} · IPS {a.ips ?? "—"} ({a.priority || "—"}) · {a.pipeline_status}</li>)}</ul></section>}
          </div>)}
      </DialogContent>
    </Dialog>
  );
};

export const SharingPanel = () => {
  const [d, setD] = useState(null);
  const [form, setForm] = useState({ email: "", relation: "conseiller", scopes: [] });
  const [busy, setBusy] = useState(false);
  const [viewing, setViewing] = useState(null);
  const load = () => sharing.list().then(setD).catch((e) => toast.error(e.message));
  useEffect(() => { load(); }, []);
  const toggle = (s) => setForm({ ...form, scopes: form.scopes.includes(s) ? form.scopes.filter((x) => x !== s) : [...form.scopes, s] });
  const grant = async () => {
    setBusy(true);
    try { await sharing.grant(form); toast.success(`Accès accordé à ${form.email}.`); setForm({ email: "", relation: "conseiller", scopes: [] }); load(); }
    catch (e) { toast.error(e.message); } finally { setBusy(false); }
  };
  const revoke = async (g) => { try { await sharing.revoke(g.id); toast.success(`Accès de ${g.grantee_email} révoqué.`); load(); } catch (e) { toast.error(e.message); } };
  if (!d) return null;
  return (
    <section className="mt-8 space-y-4 rounded-2xl border border-white/10 p-5" data-testid="sharing-panel">
      <div>
        <h2 className="flex items-center gap-2 text-base font-semibold md:text-lg"><Lock className="h-4 w-4 text-indigo-300" />Partage et accompagnement</h2>
        <p className="text-xs text-slate-400">Par défaut, personne (ni l'équipe CareerOS) ne voit votre CV, votre Career Memory ou vos candidatures. Vous pouvez autoriser un conseiller ou un proche, information par information, et révoquer à tout moment. La personne doit se connecter avec un compte CareerOS à cette adresse.</p>
      </div>
      <div className="grid gap-2 sm:grid-cols-[1.4fr_1fr]">
        <input type="email" value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} placeholder="E-mail de la personne" className={inputCls} data-testid="sharing-email-input" />
        <select value={form.relation} onChange={(e) => setForm({ ...form, relation: e.target.value })} className={inputCls} data-testid="sharing-relation-select">
          {Object.entries(REL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}
        </select>
      </div>
      <div className="flex flex-wrap items-center gap-4 text-sm">
        {Object.entries(SCOPES).map(([k, l]) => <label key={k} className="flex items-center gap-1.5"><input type="checkbox" className="accent-indigo-500" checked={form.scopes.includes(k)} onChange={() => toggle(k)} data-testid={`sharing-scope-${k}`} />{l}</label>)}
        <button type="button" onClick={grant} disabled={busy || !form.email || !form.scopes.length} className="ml-auto flex items-center gap-1.5 rounded-full bg-indigo-500 px-4 py-2 text-xs font-semibold text-white disabled:opacity-50" data-testid="sharing-grant-btn">
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <UserPlus className="h-3.5 w-3.5" />}Autoriser
        </button>
      </div>
      <div data-testid="sharing-given">
        <p className="mb-1 text-xs font-medium text-slate-300">Accès que vous avez accordés ({d.given.length})</p>
        {d.given.length === 0 ? <p className="text-[11px] text-slate-500" data-testid="sharing-given-empty">Aucun : rien n'est partagé.</p> : d.given.map((g, i) => (
          <div key={g.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 py-2 text-xs" data-testid={`sharing-given-${i}`}>
            <span><b>{g.grantee_email}</b> · {REL[g.relation]} · {g.scopes.map((s) => SCOPES[s]).join(", ")} · consulté {g.views} fois (dernier : {date(g.last_viewed_at)})</span>
            <button type="button" onClick={() => revoke(g)} className="flex items-center gap-1 text-rose-300 hover:text-rose-200" data-testid={`sharing-revoke-${i}`}><Trash2 className="h-3.5 w-3.5" />Révoquer</button>
          </div>))}
      </div>
      {d.received.length > 0 && <div data-testid="sharing-received">
        <p className="mb-1 text-xs font-medium text-slate-300">Partagés avec moi ({d.received.length})</p>
        {d.received.map((g, i) => (
          <div key={g.id} className="flex flex-wrap items-center justify-between gap-2 border-b border-white/5 py-2 text-xs" data-testid={`sharing-received-${i}`}>
            <span><b>{g.owner_name || g.owner_email}</b> · {g.scopes.map((s) => SCOPES[s]).join(", ")}</span>
            <button type="button" onClick={() => setViewing(g.id)} className="flex items-center gap-1 text-indigo-300 hover:text-white" data-testid={`sharing-view-${i}`}><Eye className="h-3.5 w-3.5" />Consulter</button>
          </div>))}
      </div>}
      <SharedView id={viewing} onClose={() => setViewing(null)} />
    </section>
  );
};
