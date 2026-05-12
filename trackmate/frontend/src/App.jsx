import { Link, Route, Routes } from "react-router-dom";
import Navbar from "./components/Navbar.jsx";
import Dashboard from "./pages/Dashboard.jsx";
import GenerateTest from "./pages/GenerateTest.jsx";
import SchedulePage from "./pages/SchedulePage.jsx";
import TestPage from "./pages/TestPage.jsx";
import ResultPage from "./pages/ResultPage.jsx";

export default function App() {
  return (
    <div>
      <Navbar />
      <main className="container">
        <Routes>
          <Route path="/" element={<Dashboard />} />
          <Route path="/generate-test" element={<GenerateTest />} />
          <Route path="/test" element={<TestPage />} />
          <Route path="/result" element={<ResultPage />} />
          <Route path="/schedule" element={<SchedulePage />} />
        </Routes>
      </main>
    </div>
  );
}
