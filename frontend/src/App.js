import "@/App.css";
import { Toaster } from "sonner";
import InterviewConsole from "@/pages/InterviewConsole";

function App() {
  return (
    <div className="App">
      <InterviewConsole />
      <Toaster theme="dark" position="top-center" richColors />
    </div>
  );
}

export default App;
