import { useState, useEffect } from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import "./App.css";
import { SecurityProvider } from "./contexts/SecurityContext";
import ProtectedRoute from "./components/ProtectedRoute";
import PageTransition from "./components/PageTransition";
import LandingPage from "./pages/LandingPage";
import DemoPage from "./pages/DemoPage";
import LoginPage from "./pages/LoginPage";
import Dashboard from "./pages/Dashboard";
import TasksPage from "./pages/TasksPage";
import TaskWorkspace from "./pages/TaskWorkspace";
import ChatPage from "./pages/ChatPage";
import AuditPage from "./pages/AuditPage";
import SecureAnalysisPage from "./pages/SecureAnalysisPage";
import SupervisionPage from "./pages/SupervisionPage";
import AccountPage from "./pages/AccountPage";
import { getToken, clearToken, getIdentity } from "./api";

function AuthGate() {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setReady(true);
      return;
    }
    getIdentity()
      .then(() => setReady(true))
      .catch(() => {
        clearToken();
        setReady(true);
      });
  }, []);

  if (!ready) return null;

  return (
    <PageTransition>
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/login" element={<LoginPage />} />
        {/* Isolated evaluator Demo Mode — no auth, no real user data. */}
        <Route path="/demo" element={<DemoPage />} />
        <Route path="/dashboard" element={<ProtectedRoute><Dashboard /></ProtectedRoute>} />
        <Route path="/tasks" element={<ProtectedRoute><TasksPage /></ProtectedRoute>} />
        <Route path="/task/:id" element={<ProtectedRoute><TaskWorkspace /></ProtectedRoute>} />
        <Route path="/chat" element={<ProtectedRoute><ChatPage /></ProtectedRoute>} />
        <Route path="/audit" element={<ProtectedRoute><AuditPage /></ProtectedRoute>} />
        <Route path="/analysis" element={<ProtectedRoute><SecureAnalysisPage /></ProtectedRoute>} />
        <Route path="/supervision" element={<ProtectedRoute><SupervisionPage /></ProtectedRoute>} />
        <Route path="/account" element={<ProtectedRoute><AccountPage /></ProtectedRoute>} />
        <Route path="*" element={<Navigate to="/" />} />
      </Routes>
    </PageTransition>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <SecurityProvider>
        <AuthGate />
      </SecurityProvider>
    </BrowserRouter>
  );
}
