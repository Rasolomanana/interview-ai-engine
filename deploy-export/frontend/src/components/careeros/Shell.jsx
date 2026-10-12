import { Link, NavLink } from "react-router-dom";
import { Brain, LogOut, Mic } from "lucide-react";
import { useAuth } from "./AuthProvider";

const tab = ({ isActive }) =>
  `rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${isActive ? "bg-white/10 text-white" : "text-slate-400 hover:text-white"}`;

export const Shell = ({ children }) => {
  const { user, logout } = useAuth();
  return (
    <div className="min-h-screen bg-[#090a0f] text-slate-100">
      <div className="pointer-events-none fixed inset-0 bg-[radial-gradient(ellipse_at_top_left,rgba(99,102,241,0.10),transparent_55%)]" />
      <header className="sticky top-0 z-30 border-b border-white/5 bg-[#090a0f]/80 backdrop-blur-xl">
        <div className="mx-auto flex max-w-6xl items-center gap-3 px-4 py-3 sm:px-6">
          <Link to="/careeros" className="flex items-center gap-2" data-testid="careeros-home-link">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-indigo-500/15 ring-1 ring-indigo-400/30">
              <Brain className="h-4 w-4 text-indigo-300" />
            </span>
            <span className="font-display text-lg font-bold tracking-tight">CareerOS</span>
          </Link>
          <nav className="ml-2 hidden items-center gap-1 sm:flex">
            <NavLink end to="/careeros" className={tab} data-testid="nav-dashboard">Tableau de bord</NavLink>
            <NavLink to="/careeros/nouveau" className={tab} data-testid="nav-new-pack">Pack candidature</NavLink>
            <NavLink to="/careeros/memoire" className={tab} data-testid="nav-memory">Career Memory</NavLink>
          </nav>
          <div className="ml-auto flex items-center gap-2">
            <Link to="/careeros/copilote" className="hidden items-center gap-1.5 rounded-full border border-white/10 px-3 py-1.5 text-xs text-slate-300 hover:text-white md:flex" data-testid="nav-interview-console">
              <Mic className="h-3.5 w-3.5" /> Copilote d'entrevue
            </Link>
            <span className="hidden max-w-[160px] truncate text-xs text-slate-500 lg:block" data-testid="member-email">{user?.email}</span>
            <button onClick={logout} className="rounded-full p-2 text-slate-400 hover:bg-white/5 hover:text-white" data-testid="logout-btn" title="Déconnexion">
              <LogOut className="h-4 w-4" />
            </button>
          </div>
        </div>
        <nav className="flex gap-1 overflow-x-auto px-4 pb-2 sm:hidden">
          <NavLink end to="/careeros" className={tab}>Tableau de bord</NavLink>
          <NavLink to="/careeros/nouveau" className={tab}>Pack</NavLink>
          <NavLink to="/careeros/memoire" className={tab}>Memory</NavLink>
          <NavLink to="/careeros/copilote" className={tab} data-testid="nav-interview-console-mobile">Copilote</NavLink>
        </nav>
      </header>
      <main className="relative mx-auto max-w-6xl px-4 py-8 sm:px-6 sm:py-10">{children}</main>
    </div>
  );
};
