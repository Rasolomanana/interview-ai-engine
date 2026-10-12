import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";
import { Brain, Loader2 } from "lucide-react";
import { useAuth } from "@/components/careeros/AuthProvider";
import { ThemeToggle, usePageTitle } from "@/components/careeros/ThemeToggle";

const Field = ({ label, ...p }) => (
  <label className="block">
    <span className="mb-1.5 block text-xs font-medium text-slate-400">{label}</span>
    <input {...p} className="w-full rounded-xl border border-white/10 bg-black/40 px-3.5 py-2.5 text-sm text-white outline-none transition-colors focus:border-indigo-400/60" />
  </label>
);

export default function AuthPage() {
  const { login, register } = useAuth();
  const nav = useNavigate();
  const [params] = useSearchParams();
  const [mode, setMode] = useState("login");
  usePageTitle(mode === "login" ? "Connexion" : "Créer un compte");
  const [form, setForm] = useState({ email: "", password: "", name: "" });
  const [err, setErr] = useState("");
  const [busy, setBusy] = useState(false);
  const set = (k) => (e) => setForm({ ...form, [k]: e.target.value });

  const submit = async (e) => {
    e.preventDefault();
    setErr(""); setBusy(true);
    try {
      if (mode === "login") await login(form.email, form.password);
      else await register(form.email, form.password, form.name);
      nav(params.get("next") || "/careeros", { replace: true });
    } catch (e2) { setErr(e2.message); } finally { setBusy(false); }
  };

  return (
    <div className="relative grid min-h-screen bg-[#090a0f] text-slate-100 lg:grid-cols-2">
      <ThemeToggle className="absolute right-4 top-4 z-10" />
      <section className="relative hidden flex-col justify-between overflow-hidden border-r border-white/5 p-12 lg:flex">
        <div className="absolute inset-0 bg-[radial-gradient(circle_at_20%_20%,rgba(99,102,241,0.18),transparent_50%),radial-gradient(circle_at_80%_90%,rgba(16,185,129,0.10),transparent_45%)]" />
        <div className="relative flex items-center gap-2"><Brain className="h-5 w-5 text-indigo-300" /><span className="font-display text-xl font-bold">CareerOS</span></div>
        <div className="relative max-w-md">
          <h1 className="font-display text-5xl font-bold leading-[1.05] tracking-tight">Votre directeur de carrière personnel.</h1>
          <p className="mt-5 text-base text-slate-400">Analyser, prioriser, recommander. Chaque opportunité devient une décision éclairée — et une candidature de niveau professionnel.</p>
        </div>
        <p className="relative font-mono text-[11px] uppercase tracking-[0.2em] text-slate-600">Interview AI Engine · IPS · Career Memory</p>
      </section>
      <section className="flex items-center justify-center p-6">
        <form onSubmit={submit} className="w-full max-w-sm space-y-4" data-testid="auth-form">
          <div className="mb-6 lg:hidden"><span className="font-display text-2xl font-bold">CareerOS</span></div>
          <div className="flex rounded-full border border-white/10 p-1 text-xs">
            {[["login", "Connexion"], ["register", "Créer un compte"]].map(([m, l]) => (
              <button type="button" key={m} onClick={() => { setMode(m); setErr(""); }} data-testid={`auth-tab-${m}`}
                className={`flex-1 rounded-full py-2 font-medium transition-colors ${mode === m ? "bg-indigo-500 text-white" : "text-slate-400 hover:text-white"}`}>{l}</button>
            ))}
          </div>
          {mode === "register" && <Field label="Nom" value={form.name} onChange={set("name")} data-testid="auth-name-input" autoComplete="name" />}
          <Field label="E-mail" type="email" required value={form.email} onChange={set("email")} data-testid="auth-email-input" autoComplete="email" />
          <Field label={mode === "register" ? "Mot de passe (8 caractères min.)" : "Mot de passe"} type="password" required minLength={mode === "register" ? 8 : 1}
            value={form.password} onChange={set("password")} data-testid="auth-password-input" autoComplete={mode === "login" ? "current-password" : "new-password"} />
          {err && <p className="rounded-lg border border-red-500/30 bg-red-950/30 px-3 py-2 text-xs text-red-300" data-testid="auth-error">{err}</p>}
          <button disabled={busy} data-testid="auth-submit-btn"
            className="flex w-full items-center justify-center gap-2 rounded-xl bg-indigo-500 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-indigo-400 disabled:opacity-60">
            {busy && <Loader2 className="h-4 w-4 animate-spin" />}{mode === "login" ? "Se connecter" : "Créer mon compte"}
          </button>
        </form>
      </section>
    </div>
  );
}
