import { useState, useEffect, useRef } from "react";
import { Link, useLocation } from "react-router-dom";
import { updateUsername } from "../api";
import { useSecurity } from "../contexts/SecurityContext";

const SECURITY_MODE_DISPLAY = {
  standard: { icon: "◯", label: "Standard", color: "#6b7280", glow: false, desc: "Normal task-scoped policy" },
  secure: { icon: "🔐", label: "Secure", color: "#3b82f6", glow: false, desc: "Restricted external access, enhanced audit" },
  sovereign: { icon: "🛡", label: "Sovereign", color: "#10b981", glow: true, desc: "Strongest available sovereign policy" },
};

const ROLE_DISPLAY = {
  operator: "Operator",
  engineer: "Engineer",
  senior_engineer: "Senior Engineer",
  manager: "Manager",
  reviewer: "Reviewer",
  admin: "Administrator",
  hr: "HR",
  junior_engineer: "Junior Engineer",
  monitor: "Monitor",
};

const MODE_ORDER = { standard: 0, secure: 1, sovereign: 2 };

export default function TopNav({ user, onLogout, securityMode, onSwitchMode, securityPanel, onToggleSecurityPanel, onUserUpdate }) {
  const location = useLocation();
  const { roleFloor } = useSecurity();
  const [showAccount, setShowAccount] = useState(false);
  const [showModeSelector, setShowModeSelector] = useState(false);
  const [editingUsername, setEditingUsername] = useState(false);
  const [newUsername, setNewUsername] = useState("");
  const [usernameError, setUsernameError] = useState("");
  const [saving, setSaving] = useState(false);
  const accountRef = useRef(null);
  const modeRef = useRef(null);
  const editInputRef = useRef(null);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (accountRef.current && !accountRef.current.contains(e.target)) {
        setShowAccount(false);
        setEditingUsername(false);
        setUsernameError("");
      }
      if (modeRef.current && !modeRef.current.contains(e.target)) {
        setShowModeSelector(false);
      }
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  useEffect(() => {
    if (editingUsername && editInputRef.current) {
      editInputRef.current.focus();
    }
  }, [editingUsername]);

  const isActive = (path) => location.pathname === path;
  const modeDisplay = SECURITY_MODE_DISPLAY[securityMode] || SECURITY_MODE_DISPLAY.standard;

  const handleStartEdit = () => {
    setNewUsername(user?.username || "");
    setEditingUsername(true);
    setUsernameError("");
  };

  const handleSaveUsername = async () => {
    if (!newUsername.trim() || newUsername === user?.username) {
      setEditingUsername(false);
      return;
    }
    setSaving(true);
    setUsernameError("");
    try {
      const updated = await updateUsername(newUsername.trim());
      if (onUserUpdate) onUserUpdate(updated);
      setEditingUsername(false);
    } catch (err) {
      setUsernameError(err.message);
    }
    setSaving(false);
  };

  const handleEditKeyDown = (e) => {
    if (e.key === "Enter") handleSaveUsername();
    if (e.key === "Escape") { setEditingUsername(false); setUsernameError(""); }
  };

  const handleModeSelect = (mode) => {
    if (MODE_ORDER[mode] < MODE_ORDER[roleFloor || "standard"]) return;
    if (mode !== securityMode && onSwitchMode) {
      onSwitchMode(mode);
    }
    setShowModeSelector(false);
  };

  return (
    <nav className="topnav">
      <div className="topnav-left">
        <Link to="/dashboard" className="topnav-logo">MEDHA</Link>
      </div>
      <div className="topnav-center">
        <Link to="/dashboard" className={`topnav-link ${isActive("/dashboard") ? "active" : ""}`}>Dashboard</Link>
        <Link to="/tasks" className={`topnav-link ${isActive("/tasks") ? "active" : ""}`}>Tasks</Link>
        <Link to="/chat" className={`topnav-link ${isActive("/chat") ? "active" : ""}`}>AI Chat</Link>
        <Link to="/analysis" className={`topnav-link ${isActive("/analysis") ? "active" : ""}`}>Secure Analysis</Link>
        {(user?.role === "manager" || user?.role === "admin") && (
          <Link to="/supervision" className={`topnav-link ${isActive("/supervision") ? "active" : ""}`}>Supervision &amp; Verification</Link>
        )}
        <Link to="/audit" className={`topnav-link ${isActive("/audit") ? "active" : ""}`}>Audit Trail</Link>
      </div>
      <div className="topnav-right">
        {/* Account Dropdown — FIRST */}
        <div className="account-wrapper" ref={accountRef}>
          <button
            className="account-trigger"
            onClick={() => setShowAccount(!showAccount)}
            title="Account"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
              <circle cx="12" cy="7" r="4" />
            </svg>
            <span className="account-username">{user?.username}</span>
            <span className="account-caret">▾</span>
          </button>

          {showAccount && (
            <div className="account-dropdown">
              <div className="account-dropdown-header">ACCOUNT</div>

              <div className="account-field">
                <span className="account-field-label">Username</span>
                {editingUsername ? (
                  <div className="account-edit-row">
                    <input
                      ref={editInputRef}
                      className="account-edit-input"
                      value={newUsername}
                      onChange={(e) => setNewUsername(e.target.value)}
                      onKeyDown={handleEditKeyDown}
                      maxLength={100}
                      disabled={saving}
                    />
                    <button
                      className="account-edit-save"
                      onClick={handleSaveUsername}
                      disabled={saving}
                    >
                      {saving ? "..." : "Save"}
                    </button>
                    <button
                      className="account-edit-cancel"
                      onClick={() => { setEditingUsername(false); setUsernameError(""); }}
                      disabled={saving}
                    >
                      ×
                    </button>
                  </div>
                ) : (
                  <div className="account-field-value-row">
                    <span className="account-field-value">{user?.username}</span>
                    <button className="account-edit-btn" onClick={handleStartEdit}>Edit</button>
                  </div>
                )}
                {usernameError && <div className="account-error">{usernameError}</div>}
              </div>

              <div className="account-field">
                <span className="account-field-label">Role</span>
                <span className="account-field-value readonly">{ROLE_DISPLAY[user?.role] || user?.role}</span>
              </div>

              <div className="account-field">
                <span className="account-field-label">User ID</span>
                <span className="account-field-value readonly user-id">{user?.user_id || "—"}</span>
              </div>

              <div className="account-divider" />

              <Link
                to="/account"
                className="account-settings-link"
                onClick={() => setShowAccount(false)}
              >
                Account Settings
              </Link>

              <div className="account-divider" />

              <button className="account-logout" onClick={onLogout}>Logout</button>
            </div>
          )}
        </div>

        {/* Security Mode Selector — AFTER Account */}
        <div className="security-mode-wrapper" ref={modeRef}>
          <button
            className="security-mode-trigger"
            onClick={() => setShowModeSelector(!showModeSelector)}
            title="Security Mode — click to switch"
            style={{ borderColor: `${modeDisplay.color}40`, color: modeDisplay.color }}
          >
            <span className="security-mode-icon">{modeDisplay.icon}</span>
            <span className="security-mode-label">{modeDisplay.label}</span>
            <span className="security-mode-caret">▾</span>
          </button>

          {showModeSelector && (
            <div className="security-mode-dropdown">
              <div className="security-mode-dropdown-header">SECURITY MODE</div>
              {Object.entries(SECURITY_MODE_DISPLAY).map(([key, display]) => {
                const belowFloor = MODE_ORDER[key] < MODE_ORDER[roleFloor || "standard"];
                return (
                <button
                  key={key}
                  className={`security-mode-option ${key === securityMode ? "active" : ""}`}
                  onClick={() => handleModeSelect(key)}
                  disabled={belowFloor}
                  style={{ "--mode-color": display.color, opacity: belowFloor ? 0.4 : 1 }}
                >
                  <span className="security-mode-option-icon">{display.icon}</span>
                  <span className="security-mode-option-info">
                    <span className="security-mode-option-label">{display.label}{belowFloor ? " (role minimum)" : ""}</span>
                    <span className="security-mode-option-desc">{display.desc}</span>
                  </span>
                  {key === securityMode && <span className="security-mode-check">✓</span>}
                </button>
                );
              })}
              <div className="security-mode-dropdown-footer">
                Effective mode = max(user selection, task policy, role minimum)
              </div>
            </div>
          )}
        </div>
      </div>

      {/* Security Panel Overlay (task-specific) */}
      {securityPanel && (
        <div className="security-panel-overlay" onClick={() => onToggleSecurityPanel && onToggleSecurityPanel(false)}>
          <div className="security-panel" onClick={(e) => e.stopPropagation()}>
            <div className="security-panel-header">
              <span className="security-panel-icon">{modeDisplay.icon}</span>
              <span className="security-panel-title" style={{ color: modeDisplay.color }}>
                {modeDisplay.label} MODE
              </span>
            </div>
            <div className="security-panel-body">
              <div className="security-panel-row">
                <span className="security-panel-key">Task</span>
                <span className="security-panel-value">{securityPanel.task_title || "—"}</span>
              </div>
              <div className="security-panel-row">
                <span className="security-panel-key">Sensitivity</span>
                <span className="security-panel-value">{securityPanel.sensitivity || "—"}</span>
              </div>
              <div className="security-panel-row">
                <span className="security-panel-key">External Network</span>
                <span className="security-panel-value" style={{ color: securityPanel.external_network?.color }}>
                  {securityPanel.external_network?.label || "—"}
                </span>
              </div>
              <div className="security-panel-row">
                <span className="security-panel-key">External Models</span>
                <span className="security-panel-value" style={{ color: securityPanel.external_models?.color }}>
                  {securityPanel.external_models?.label || "—"}
                </span>
              </div>
              <div className="security-panel-row">
                <span className="security-panel-key">RAG</span>
                <span className="security-panel-value" style={{ color: securityPanel.rag_policy?.color }}>
                  {securityPanel.rag_policy?.label || "—"}
                </span>
              </div>
              <div className="security-panel-row">
                <span className="security-panel-key">Tools</span>
                <span className="security-panel-value" style={{ color: securityPanel.tool_policy?.color }}>
                  {securityPanel.tool_policy?.label || "—"}
                </span>
              </div>
              <div className="security-panel-row">
                <span className="security-panel-key">Audit</span>
                <span className="security-panel-value" style={{ color: securityPanel.audit_level?.color }}>
                  {securityPanel.audit_level?.label || "—"}
                </span>
              </div>
            </div>
            <div className="security-panel-footer">
              Policy v{securityPanel.policy_version || "1.0"}
            </div>
          </div>
        </div>
      )}
    </nav>
  );
}
