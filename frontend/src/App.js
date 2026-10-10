import "@/App.css";
import { Toaster } from "sonner";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import InterviewConsole from "@/pages/InterviewConsole";
import AdminDashboard from "@/pages/AdminDashboard";
import PrivacyBanner from "@/components/PrivacyBanner";

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/admin" element={<AdminDashboard />} />
          <Route path="/" element={<InterviewConsole />} />
        </Routes>
        <PrivacyBanner />
      </BrowserRouter>
      <Toaster theme="dark" position="top-center" richColors />
    </div>
  );
}

export default App;
