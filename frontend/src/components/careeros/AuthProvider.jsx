import { createContext, useContext, useEffect, useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { Loader2 } from "lucide-react";
import { auth, tokens } from "@/lib/careeros";

const AuthCtx = createContext(null);

export const AuthProvider = ({ children }) => {
  // null = checking, false = signed out, object = member
  const [user, setUser] = useState(null);

  useEffect(() => {
    if (!tokens.get()) { setUser(false); return; }
    auth.me().then(setUser).catch(() => { tokens.clear(); setUser(false); });
  }, []);

  const value = {
    user,
    login: async (e, p) => setUser(await auth.login(e, p)),
    register: async (e, p, n) => setUser(await auth.register(e, p, n)),
    logout: () => { auth.logout(); setUser(false); },
  };
  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
};

export const useAuth = () => useContext(AuthCtx);

const Checking = () => (
  <div className="flex min-h-screen items-center justify-center bg-[#090a0f]" data-testid="auth-checking">
    <Loader2 className="h-6 w-6 animate-spin text-indigo-400" />
  </div>
);

// CareerOS is the main product: "/" → /careeros when signed in, else /connexion.
export const RootRedirect = () => {
  const { user } = useAuth();
  if (user === null) return <Checking />;
  return <Navigate to={user ? "/careeros" : "/connexion"} replace />;
};

export const RequireMember = ({ children }) => {
  const { user } = useAuth();
  const loc = useLocation();
  if (user === null) return <Checking />;
  if (!user) return <Navigate to={`/connexion?next=${encodeURIComponent(loc.pathname)}`} replace />;
  return children;
};
