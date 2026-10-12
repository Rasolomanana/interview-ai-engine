import "@/App.css";
import { Toaster } from "sonner";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import InterviewConsole from "@/pages/InterviewConsole";
import AdminDashboard from "@/pages/AdminDashboard";
import PrivacyBanner from "@/components/PrivacyBanner";
import { AuthProvider, RequireMember, RootRedirect } from "@/components/careeros/AuthProvider";
import AuthPage from "@/pages/careeros/AuthPage";
import Dashboard from "@/pages/careeros/Dashboard";
import NewPack from "@/pages/careeros/NewPack";
import PackView from "@/pages/careeros/PackView";
import Profile from "@/pages/careeros/Profile";
import { useTheme } from "@/components/careeros/ThemeToggle";

const member = (el) => <RequireMember>{el}</RequireMember>;

function App() {
  const theme = useTheme();
  return (
    <div className="App">
      <BrowserRouter>
        <AuthProvider>
          <Routes>
            <Route path="/admin" element={<AdminDashboard />} />
            <Route path="/connexion" element={<AuthPage />} />
            <Route path="/careeros" element={member(<Dashboard />)} />
            <Route path="/careeros/nouveau" element={member(<NewPack />)} />
            <Route path="/careeros/memoire" element={member(<Profile />)} />
            <Route path="/careeros/candidature/:id" element={member(<PackView />)} />
            <Route path="/careeros/copilote" element={member(<InterviewConsole />)} />
            <Route path="/" element={<RootRedirect />} />
            <Route path="*" element={<RootRedirect />} />
          </Routes>
        </AuthProvider>
        <PrivacyBanner />
      </BrowserRouter>
      <Toaster theme={theme} position="top-center" richColors />
    </div>
  );
}

export default App;
