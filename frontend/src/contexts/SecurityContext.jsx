import { createContext, useContext, useState, useEffect, useCallback } from "react";
import { getSecurityMode, setSecurityMode as apiSetSecurityMode } from "../api";

const SecurityContext = createContext(null);

const STORAGE_KEY = "medha_security_mode";

export function SecurityProvider({ children }) {
  const [securityMode, setSecurityMode] = useState(() => {
    return localStorage.getItem(STORAGE_KEY) || "standard";
  });
  const [roleFloor, setRoleFloor] = useState("standard");
  const [policy, setPolicy] = useState(null);
  const [loading, setLoading] = useState(true);
  const [confirmation, setConfirmation] = useState(null);

  // Load mode from server on mount
  useEffect(() => {
    getSecurityMode()
      .then((data) => {
        setSecurityMode(data.security_mode);
        setPolicy(data.policy);
        if (data.role_floor) setRoleFloor(data.role_floor);
        localStorage.setItem(STORAGE_KEY, data.security_mode);
      })
      .catch(() => {
        // Use localStorage fallback
      })
      .finally(() => setLoading(false));
  }, []);

  const switchMode = useCallback(async (newMode) => {
    if (newMode === securityMode) return;
    try {
      const data = await apiSetSecurityMode(newMode);
      setSecurityMode(data.security_mode);
      setPolicy(data.policy);
      localStorage.setItem(STORAGE_KEY, data.security_mode);
      setConfirmation({
        mode: data.security_mode,
        message: `${data.security_mode.charAt(0).toUpperCase() + data.security_mode.slice(1)} Mode enabled.`,
      });
      setTimeout(() => setConfirmation(null), 3000);
    } catch (err) {
      console.error("Failed to switch security mode:", err);
    }
  }, [securityMode]);

  return (
    <SecurityContext.Provider value={{ securityMode, roleFloor, policy, loading, switchMode, confirmation }}>
      {children}
    </SecurityContext.Provider>
  );
}

export function useSecurity() {
  const ctx = useContext(SecurityContext);
  if (!ctx) throw new Error("useSecurity must be used within SecurityProvider");
  return ctx;
}
