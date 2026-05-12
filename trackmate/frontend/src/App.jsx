import { Navigate, Route, Routes } from "react-router-dom";

import Navbar from "./components/Navbar";
import ProtectedRoute from "./components/ProtectedRoute";

import Home from "./pages/Home";
import Signup from "./pages/Signup";
import Login from "./pages/Login";
import OtpPage from "./pages/OtpPage";
import SetupProfile from "./pages/SetupProfile";
import Dashboard from "./pages/Dashboard";
import GenerateTest from "./pages/GenerateTest";
import TestPage from "./pages/TestPage";
import ResultPage from "./pages/ResultPage";
import SchedulePage from "./pages/SchedulePage";
import HistoryPage from "./pages/HistoryPage";

import "./style.css";

function RootRedirect() {
  const token = localStorage.getItem("trackmate_token");

  if (token) {
    return <Navigate to="/dashboard" replace />;
  }

  return <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <>
      <Navbar />

      <Routes>
        <Route path="/" element={<RootRedirect />} />

        <Route path="/home" element={<Home />} />
        <Route path="/signup" element={<Signup />} />
        <Route path="/login" element={<Login />} />
        <Route path="/otp" element={<OtpPage />} />

        <Route
          path="/setup-profile"
          element={
            <ProtectedRoute>
              <SetupProfile />
            </ProtectedRoute>
          }
        />

        <Route
          path="/dashboard"
          element={
            <ProtectedRoute>
              <Dashboard />
            </ProtectedRoute>
          }
        />

        <Route
          path="/generate-test"
          element={
            <ProtectedRoute>
              <GenerateTest />
            </ProtectedRoute>
          }
        />

        <Route
          path="/test"
          element={
            <ProtectedRoute>
              <TestPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/result"
          element={
            <ProtectedRoute>
              <ResultPage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/schedule"
          element={
            <ProtectedRoute>
              <SchedulePage />
            </ProtectedRoute>
          }
        />

        <Route
          path="/history"
          element={
            <ProtectedRoute>
              <HistoryPage />
            </ProtectedRoute>
          }
        />

        <Route path="*" element={<RootRedirect />} />
      </Routes>
    </>
  );
}