import { useEffect, useState } from "react";
import { BellRing, ExternalLink, Loader2, Wallet } from "lucide-react";
import { toast } from "sonner";
import { adminCredits, adminSaveAlert, adminTestAlert } from "@/lib/api";

const pwd = () => sessionStorage.getItem("adminPwd");
const usd = (n) => `${(Number(n) || 0).toFixed(2)} $`;

const Balance = ({ o, threshold }) => {
  if (!o?.configured) return <p className="text-xs text-amber-300" data-testid="admin-credit-none">OpenRouter non configuré (OPENROUTER_API_KEY absente sur le serveur).</p>;
  if (o.error) return <p className="text-xs text-red-400" data-testid="admin-credit-error">{o.error}</p>;
  const pct = o.remaining_pct ?? 0;
  const low = pct <= threshold;
  return (
    <div data-testid="admin-credit-balance">
      <div className="flex flex-wrap items-baseline gap-2">
        <span className={`text-3xl font-bold ${low ? "text-red-400" : "text-white"}`} data-testid="admin-credit-remaining">{usd(o.remaining)}</span>
        <span className="text-sm text-slate-400">restants sur {usd(o.total)} achetés · {usd(o.used)} utilisés</span>
        <span className={`rounded-full px-2 py-0.5 text-xs ${low ? "bg-red-500/15 text-red-300" : "bg-emerald-500/15 text-emerald-300"}`} data-testid="admin-credit-pct">{pct} %</span>
      </div>
      <div className="mt-2 h-2 w-full overflow-hidden rounded-full bg-white/10"><div className={`h-full ${low ? "bg-red-400" : "bg-emerald-400"}`} style={{ width: `${Math.min(100, pct)}%` }} /></div>
    </div>
  );
};

export const CreditCard = () => {
  const [c, setC] = useState(null);
  const [email, setEmail] = useState("");
  const [threshold, setThreshold] = useState(20);
  const [busy, setBusy] = useState("");
  const load = () => adminCredits(pwd()).then((r) => { setC(r); setEmail(r.alert.email); setThreshold(r.alert.threshold); }).catch((e) => setC({ error: e.message }));
  useEffect(() => { load(); }, []);
  const save = async () => {
    setBusy("save");
    try { await adminSaveAlert(pwd(), { email, threshold: Number(threshold) }); toast.success("Alerte enregistrée"); load(); } catch (e) { toast.error(e.message); } finally { setBusy(""); }
  };
  const test = async () => {
    setBusy("test");
    try { const r = await adminTestAlert(pwd()); r.sent ? toast.success(`E-mail envoyé à ${email}`) : toast.message(r.reason || "Aucun e-mail envoyé"); } catch (e) { toast.error(e.message); } finally { setBusy(""); }
  };
  return (
    <div className="mt-4 rounded-2xl border border-white/10 bg-slate-900/60 p-5" data-testid="admin-credit-card">
      <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-200"><Wallet className="h-4 w-4 text-amber-400" />Crédit IA restant</h3>
      {!c ? <Loader2 className="h-4 w-4 animate-spin text-slate-400" /> : c.error ? <p className="text-xs text-red-400">{c.error}</p> : (
        <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
          <div className="space-y-3">
            <p className="text-[11px] uppercase tracking-wider text-slate-500">OpenRouter (analyses, Radar, packs)</p>
            <Balance o={c.openrouter} threshold={threshold} />
            <p className="text-[11px] text-slate-500">Anthropic : {c.anthropic.configured ? "configuré" : "non configuré"} · solde non disponible par API (voir « Tester les fournisseurs IA »).</p>
            <div className="flex flex-wrap gap-2">
              <a href={c.links.openrouter} target="_blank" rel="noreferrer" data-testid="admin-topup-openrouter" className="flex items-center gap-1.5 rounded-lg bg-amber-500 px-3 py-1.5 text-xs font-semibold text-black hover:bg-amber-400"><ExternalLink className="h-3.5 w-3.5" />Ajouter du crédit OpenRouter</a>
              <a href={c.links.anthropic} target="_blank" rel="noreferrer" data-testid="admin-topup-anthropic" className="flex items-center gap-1.5 rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:border-white/20"><ExternalLink className="h-3.5 w-3.5" />Recharger Anthropic</a>
            </div>
          </div>
          <div className="space-y-2" data-testid="admin-alert-form">
            <p className="flex items-center gap-1.5 text-[11px] uppercase tracking-wider text-slate-500"><BellRing className="h-3.5 w-3.5" />Alerte par e-mail</p>
            <input type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="votre@courriel.com" data-testid="admin-alert-email" className="w-full rounded-lg border border-white/10 bg-slate-950 px-3 py-2 text-sm text-white outline-none focus:border-amber-400/60" />
            <label className="flex items-center gap-2 text-xs text-slate-400">Seuil
              <input type="number" min={5} max={90} value={threshold} onChange={(e) => setThreshold(e.target.value)} data-testid="admin-alert-threshold" className="w-16 rounded-lg border border-white/10 bg-slate-950 px-2 py-1 text-sm text-white" />% du crédit acheté</label>
            <div className="flex flex-wrap gap-2">
              <button onClick={save} disabled={!!busy} data-testid="admin-alert-save" className="rounded-lg bg-indigo-600 px-3 py-1.5 text-xs font-semibold text-white disabled:opacity-60">{busy === "save" ? "…" : "Enregistrer"}</button>
              <button onClick={test} disabled={!!busy || !c.alert.email} data-testid="admin-alert-test" className="rounded-lg border border-white/10 px-3 py-1.5 text-xs text-slate-300 disabled:opacity-50">{busy === "test" ? "Envoi…" : "Envoyer un e-mail de test"}</button>
            </div>
            <p className="text-[11px] text-slate-500" data-testid="admin-alert-status">{!c.email_ready ? "Envoi d'e-mails non configuré sur le serveur." : c.alert.last_sent_at ? `Dernière alerte : ${new Date(c.alert.last_sent_at).toLocaleString("fr-CA")}` : "Une seule alerte est envoyée par passage sous le seuil (vérification quotidienne)."}</p>
          </div>
        </div>
      )}
    </div>
  );
};
