import { useState, useEffect } from "react";
import { toast } from "sonner";
import {
  Lock, Users, PlayCircle, FileSearch, FileText, Mail, Cpu, Download,
  RefreshCw, LogOut, ShieldCheck,
} from "lucide-react";
import { adminLogin, adminStats, adminExport } from "@/lib/api";
import { SimulationsTable } from "@/components/admin/SimulationsTable";

const money = (n) => `$${(Number(n) || 0).toFixed(4)}`;
const num = (n) => (Number(n) || 0).toLocaleString();

function StatCard({ icon: Icon, label, value, accent }) {
  return (
    <div data-testid={`stat-${label}`} className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
      <div className="flex items-center gap-2 text-slate-400">
        <Icon className={`h-4 w-4 ${accent}`} />
        <span className="text-[11px] font-mono uppercase tracking-widest">{label}</span>
      </div>
      <div className="mt-2 text-3xl font-bold text-white">{value}</div>
    </div>
  );
}

function Bars({ title, data, keys }) {
  const max = Math.max(1, ...data.map((d) => keys.reduce((s, k) => s + (d[k] || 0), 0)));
  return (
    <div className="rounded-2xl border border-white/10 bg-slate-900/60 p-5">
      <h3 className="mb-3 text-sm font-semibold text-slate-200">{title}</h3>
      {data.length === 0 ? (
        <p className="text-xs text-slate-500">Aucune donnée.</p>
      ) : (
        <div className="space-y-1.5">
          {data.slice(-14).map((d) => (
            <div key={d.bucket} className="flex items-center gap-2">
              <span className="w-24 shrink-0 font-mono text-[10px] text-slate-500">{d.bucket}</span>
              <div className="flex h-4 flex-1 overflow-hidden rounded bg-black/40">
                <div className="bg-emerald-500" style={{ width: `${((d.simulations || 0) / max) * 100}%` }} title={`Simulations: ${d.simulations || 0}`} />
                <div className="bg-sky-500" style={{ width: `${((d.ats || 0) / max) * 100}%` }} title={`ATS: ${d.ats || 0}`} />
                <div className="bg-amber-500" style={{ width: `${((d.cover_letters || 0) / max) * 100}%` }} title={`Lettres: ${d.cover_letters || 0}`} />
              </div>
            </div>
          ))}
          <div className="mt-2 flex gap-4 text-[10px] text-slate-400">
            <span className="flex items-center gap-1"><i className="inline-block h-2 w-2 rounded-sm bg-emerald-500" /> Simulations</span>
            <span className="flex items-center gap-1"><i className="inline-block h-2 w-2 rounded-sm bg-sky-500" /> ATS</span>
            <span className="flex items-center gap-1"><i className="inline-block h-2 w-2 rounded-sm bg-amber-500" /> Lettres</span>
          </div>
        </div>
      )}
    </div>
  );
}

export default function AdminDashboard() {
  const [pwd, setPwd] = useState("");
  const [authed, setAuthed] = useState(false);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState(null);
  const [err, setErr] = useState("");

  const debugErr = (step, url, e) =>
    `[DEBUG] Étape : ${step}\nURL : ${url}\nerror.name : ${e?.name}\nerror.message : ${e?.message}\nerror.stack : ${e?.stack}`;

  const load = async (password) => {
    setLoading(true);
    try {
      const d = await adminStats(password);
      setStats(d);
      setAuthed(true);
      sessionStorage.setItem("adminPwd", password);
    } catch (e) {
      console.error("[admin] stats error", e);
      setErr(debugErr("GET /stats", `${process.env.REACT_APP_BACKEND_URL}/api/admin/stats`, e));
      setAuthed(false);
      sessionStorage.removeItem("adminPwd");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    const saved = sessionStorage.getItem("adminPwd");
    if (saved) load(saved);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const doLogin = async (e) => {
    e.preventDefault();
    setErr("");
    try {
      await adminLogin(pwd);
    } catch (e2) {
      console.error("[admin] login error", e2);
      setErr(debugErr("POST /login", `${process.env.REACT_APP_BACKEND_URL}/api/admin/login`, e2));
      return;
    }
    await load(pwd);
  };

  const logout = () => {
    sessionStorage.removeItem("adminPwd");
    setAuthed(false);
    setStats(null);
    setPwd("");
  };

  const doExport = async (fmt) => {
    try {
      await adminExport(sessionStorage.getItem("adminPwd"), fmt);
    } catch (e) {
      toast.error(e.message);
    }
  };

  if (!authed) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-slate-950 px-4">
        <form onSubmit={doLogin} data-testid="admin-login-form" className="w-full max-w-sm rounded-2xl border border-white/10 bg-slate-900/70 p-7">
          <div className="mb-5 flex items-center gap-2 text-white">
            <Lock className="h-5 w-5 text-amber-400" />
            <h1 className="text-lg font-semibold">Espace administrateur</h1>
          </div>
          <input
            type="password"
            data-testid="admin-password-input"
            value={pwd}
            onChange={(e) => setPwd(e.target.value)}
            placeholder="Mot de passe administrateur"
            className="mb-3 w-full rounded-xl border border-white/10 bg-black/50 px-4 py-2.5 text-sm text-slate-100 outline-none focus:border-amber-500/60"
          />
          {err && <pre data-testid="admin-login-error" className="mb-3 max-h-64 overflow-auto whitespace-pre-wrap break-all rounded-lg bg-black/60 p-2 text-[10px] text-red-400">{err}</pre>}
          <button type="submit" disabled={loading || !pwd} data-testid="admin-login-btn" className="w-full rounded-xl bg-amber-500 px-4 py-2.5 text-sm font-semibold text-black hover:bg-amber-400 disabled:opacity-50">
            {loading ? "Connexion…" : "Se connecter"}
          </button>
          <a href="/" className="mt-4 block text-center text-xs text-slate-500 hover:text-slate-300">← Retour à l'application</a>
        </form>
      </div>
    );
  }

  const t = stats?.totals || {};
  const llm = stats?.llm || { calls: 0, tokens_in: 0, tokens_out: 0, cost: 0, by_provider: {} };

  return (
    <div className="min-h-screen bg-slate-950 px-4 py-6 text-slate-200" data-testid="admin-dashboard">
      <div className="mx-auto max-w-6xl">
        <header className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <div className="flex items-center gap-2">
            <ShieldCheck className="h-6 w-6 text-emerald-400" />
            <h1 className="text-xl font-bold text-white">Tableau de bord administrateur</h1>
            <span className="rounded-md border border-white/10 bg-black/30 px-2 py-0.5 font-mono text-[10px] text-slate-400">rétention {stats?.retention_days ?? 90} j</span>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => load(sessionStorage.getItem("adminPwd"))} data-testid="admin-refresh-btn" className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-slate-900 px-3 py-1.5 text-xs hover:border-white/20">
              <RefreshCw className="h-3.5 w-3.5" /> Rafraîchir
            </button>
            <button onClick={() => doExport("csv")} data-testid="admin-export-csv" className="flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-3 py-1.5 text-xs text-emerald-200 hover:border-emerald-400/50">
              <Download className="h-3.5 w-3.5" /> CSV
            </button>
            <button onClick={() => doExport("xlsx")} data-testid="admin-export-xlsx" className="flex items-center gap-1.5 rounded-lg border border-emerald-500/30 bg-emerald-950/30 px-3 py-1.5 text-xs text-emerald-200 hover:border-emerald-400/50">
              <Download className="h-3.5 w-3.5" /> Excel
            </button>
            <button onClick={logout} data-testid="admin-logout-btn" className="flex items-center gap-1.5 rounded-lg border border-white/10 bg-slate-900 px-3 py-1.5 text-xs hover:border-white/20">
              <LogOut className="h-3.5 w-3.5" /> Quitter
            </button>
          </div>
        </header>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
          <StatCard icon={Users} label="Visiteurs" value={num(t.visitors)} accent="text-indigo-400" />
          <StatCard icon={PlayCircle} label="Simulations" value={num(t.simulations)} accent="text-emerald-400" />
          <StatCard icon={FileSearch} label="Analyses ATS" value={num(t.ats_analyses)} accent="text-sky-400" />
          <StatCard icon={FileText} label="CV analysés" value={num(t.cvs_analyzed)} accent="text-cyan-400" />
          <StatCard icon={Mail} label="Lettres" value={num(t.cover_letters)} accent="text-amber-400" />
        </div>

        <div className="mt-4 rounded-2xl border border-white/10 bg-slate-900/60 p-5">
          <div className="mb-3 flex items-center gap-2">
            <Cpu className="h-4 w-4 text-fuchsia-400" />
            <h3 className="text-sm font-semibold text-slate-200">Consommation LLM</h3>
            <span className="text-[10px] text-slate-500">(reportée par le client — couvre Gemini & Serveur)</span>
          </div>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <div><div className="text-[10px] uppercase text-slate-500">Appels</div><div className="text-xl font-bold text-white">{num(llm.calls)}</div></div>
            <div><div className="text-[10px] uppercase text-slate-500">Tokens entrée</div><div className="text-xl font-bold text-white">{num(llm.tokens_in)}</div></div>
            <div><div className="text-[10px] uppercase text-slate-500">Tokens sortie</div><div className="text-xl font-bold text-white">{num(llm.tokens_out)}</div></div>
            <div><div className="text-[10px] uppercase text-slate-500">Coût estimé</div><div className="text-xl font-bold text-amber-300">{money(llm.cost)}</div></div>
          </div>
          <div className="mt-4 grid grid-cols-2 gap-3" data-testid="admin-llm-split">
            <div data-testid="admin-gemini-calls" className="rounded-xl border border-sky-500/20 bg-sky-950/20 p-3">
              <div className="text-[10px] uppercase text-sky-300">Appels Gemini (navigateur)</div>
              <div className="text-2xl font-bold text-white">{num(llm.gemini_calls)}</div>
              <div className="text-[11px] text-slate-400">{money(llm.gemini_cost)}</div>
            </div>
            <div data-testid="admin-server-calls" className="rounded-xl border border-fuchsia-500/20 bg-fuchsia-950/20 p-3">
              <div className="text-[10px] uppercase text-fuchsia-300">Appels Serveur (Anthropic, OpenRouter…)</div>
              <div className="text-2xl font-bold text-white">{num(llm.server_calls)}</div>
              <div className="text-[11px] text-slate-400">{money(llm.server_cost)}</div>
            </div>
          </div>
          {Object.keys(llm.by_provider || {}).length > 0 && (
            <div className="mt-3 flex flex-wrap gap-2 text-[11px]">
              {Object.entries(llm.by_provider).map(([p, v]) => (
                <span key={p} data-testid={`admin-provider-${p}`} className="rounded-md border border-white/10 bg-black/30 px-2 py-1 text-slate-300">
                  <b className="text-white">{p}</b> · {num(v.calls)} appels · {money(v.cost)}
                </span>
              ))}
            </div>
          )}
        </div>

        <div className="mt-4 grid gap-3 lg:grid-cols-3">
          <Bars title="Par jour (30 j)" data={stats?.by_day || []} keys={["simulations", "ats", "cover_letters"]} />
          <Bars title="Par semaine (12 s)" data={stats?.by_week || []} keys={["simulations", "ats", "cover_letters"]} />
          <Bars title="Par mois (12 m)" data={stats?.by_month || []} keys={["simulations", "ats", "cover_letters"]} />
        </div>

        <SimulationsTable rows={stats?.simulations_detail || []} />

        <div className="mt-4 rounded-2xl border border-white/10 bg-slate-900/60 p-5">
          <h3 className="mb-3 text-sm font-semibold text-slate-200">Dernières analyses ATS (max 100)</h3>
          <div className="overflow-x-auto">
            <table className="w-full text-left text-[12px]">
              <thead className="text-slate-500">
                <tr className="border-b border-white/10">
                  <th className="py-2 pr-4">Date</th>
                  <th className="py-2 pr-4">Score</th>
                  <th className="py-2 pr-4">Entreprise</th>
                  <th className="py-2 pr-4">Consent.</th>
                  <th className="py-2 pr-4">CV stocké</th>
                  <th className="py-2 pr-4">IP (anon.)</th>
                </tr>
              </thead>
              <tbody data-testid="admin-submissions-table">
                {(stats?.submissions || []).length === 0 ? (
                  <tr><td colSpan={6} className="py-4 text-center text-slate-500">Aucune analyse enregistrée.</td></tr>
                ) : (
                  stats.submissions.map((s, i) => (
                    <tr key={i} className="border-b border-white/5">
                      <td className="py-2 pr-4 font-mono text-[11px] text-slate-400">{(s.ts || "").slice(0, 19).replace("T", " ")}</td>
                      <td className="py-2 pr-4 text-white">{s.score ?? "—"}</td>
                      <td className="py-2 pr-4 text-slate-300">{(s.company || "").slice(0, 40) || "—"}</td>
                      <td className="py-2 pr-4">{s.consent ? <span className="text-emerald-400">oui</span> : <span className="text-slate-500">non</span>}</td>
                      <td className="py-2 pr-4">{s.has_cv ? <span className="text-emerald-400">oui</span> : <span className="text-slate-500">non</span>}</td>
                      <td className="py-2 pr-4 font-mono text-[11px] text-slate-500">{s.ip_trunc || "—"}</td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        </div>

        <a href="/" className="mt-6 block text-center text-xs text-slate-500 hover:text-slate-300">← Retour à l'application</a>
      </div>
    </div>
  );
}
