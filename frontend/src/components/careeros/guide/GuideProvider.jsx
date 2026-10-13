import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useLocation } from "react-router-dom";
import { call } from "@/lib/careeros";
import { useAuth } from "../AuthProvider";

const Ctx = createContext({ beginner: true, journey: null });
const TOUR_KEY = "careeros.tour";

export const GuideProvider = ({ children }) => {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const [journey, setJourney] = useState(null);
  const [prefs, setPrefs] = useState(user?.preferences || {});
  const [tour, setTour] = useState(() => JSON.parse(sessionStorage.getItem(TOUR_KEY) || "null"));
  const beginner = (prefs.guide_mode || "debutant") === "debutant";

  const refresh = useCallback(() => (user ? call("/careeros/journey").then((j) => { setJourney(j); setPrefs(j.preferences); }).catch(() => {}) : null), [user]);
  useEffect(() => { setPrefs(user?.preferences || {}); }, [user]);
  useEffect(() => { refresh(); }, [refresh, pathname]);
  useEffect(() => {
    if (user && pathname.startsWith("/careeros") && journey && !journey.preferences.tour_done && (journey.preferences.guide_mode || "debutant") === "debutant" && !tour) setTour({ step: 0 });
  }, [journey, pathname]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { tour ? sessionStorage.setItem(TOUR_KEY, JSON.stringify(tour)) : sessionStorage.removeItem(TOUR_KEY); }, [tour]);

  const save = (patch) => { setPrefs((p) => ({ ...p, ...patch })); return call("/auth/preferences", { method: "PATCH", body: patch }).catch(() => {}); };
  const value = {
    journey, beginner, refresh, tour,
    setMode: (m) => save({ guide_mode: m }),
    openTour: () => setTour({ step: 0 }),
    goTour: (step) => setTour({ step }),
    closeTour: () => { setTour(null); save({ tour_done: true }); setJourney((j) => j && { ...j, preferences: { ...j.preferences, tour_done: true } }); },
  };
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
};

export const useGuide = () => useContext(Ctx);
