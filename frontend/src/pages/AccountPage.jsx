import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getIdentity, updateUsername, updatePassword, clearToken } from "../api";
import TopNav from "../components/TopNav";
import { useSecurity } from "../contexts/SecurityContext";
import Toast from "../components/Toast";

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

const SECURITY_MODE_LABELS = {
  standard: { icon: "◯", label: "Standard", color: "#6b7280" },
  secure: { icon: "🔐", label: "SECURE", color: "#3b82f6" },
  sovereign: { icon: "🛡", label: "SOVEREIGN", color: "#10b981" },
};

export default function AccountPage() {
  const [user, setUser] = useState(null);
  const [username, setUsername] = useState("");
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [saving, setSaving] = useState(false);
  const [savingPassword, setSavingPassword] = useState(false);
  const [toast, setToast] = useState(null);
  const { securityMode } = useSecurity();
  const navigate = useNavigate();

  useEffect(() => {
    getIdentity()
      .then((u) => {
        setUser(u);
        setUsername(u.username);
      })
      .catch(() => {
        clearToken();
        navigate("/");
      });
  }, [navigate]);

  const handleSave = async () => {
    if (!username.trim() || username === user?.username) return;
    setSaving(true);
    try {
      const updated = await updateUsername(username.trim());
      setUser(updated);
      setToast({ type: "success", message: "Username updated successfully" });
    } catch (err) {
      setToast({ type: "error", message: err.message });
      setUsername(user?.username || "");
    }
    setSaving(false);
  };

  const handlePasswordSave = async () => {
    if (!currentPassword || !newPassword) return;
    if (newPassword !== confirmPassword) {
      setToast({ type: "error", message: "New passwords do not match" });
      return;
    }
    setSavingPassword(true);
    try {
      const updated = await updatePassword(currentPassword, newPassword);
      setUser(updated);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setToast({ type: "success", message: "Password updated successfully" });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
    setSavingPassword(false);
  };

  const handleLogout = () => {
    clearToken();
    navigate("/");
  };

  const handleUserUpdate = (updated) => {
    setUser(updated);
    setUsername(updated.username);
  };

  return (
    <div className="app-layout">
      <div className="brush-bg" />
      <TopNav
        user={user}
        onLogout={handleLogout}
        securityMode={securityMode}
        onUserUpdate={handleUserUpdate}
      />
      <main className="main-content account-page">
        <Toast toast={toast} onClear={() => setToast(null)} />

        <div className="account-page-header">
          <h1>Account Settings</h1>
          <p className="account-page-subtitle">Manage your profile and security preferences</p>
        </div>

        <div className="account-settings-grid">
          {/* Profile Section */}
          <div className="account-settings-card">
            <h3>Profile</h3>

            <div className="account-settings-field">
              <label className="account-settings-label">Username</label>
              <div className="account-settings-input-row">
                <input
                  className="account-settings-input"
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  maxLength={100}
                  disabled={saving}
                />
                <button
                  className="account-settings-save"
                  onClick={handleSave}
                  disabled={saving || username === user?.username}
                >
                  {saving ? "Saving..." : "Save Username"}
                </button>
              </div>
              <div className="account-settings-hint">
                Letters, numbers, dots, hyphens, and underscores only. 3-100 characters.
              </div>
            </div>

            <div className="account-settings-field">
              <label className="account-settings-label">Role</label>
              <div className="account-settings-readonly">
                {ROLE_DISPLAY[user?.role] || user?.role}
              </div>
              <div className="account-settings-hint">Role is assigned by your administrator and cannot be changed.</div>
            </div>

            <div className="account-settings-field">
              <label className="account-settings-label">User ID</label>
              <div className="account-settings-readonly user-id">{user?.user_id || "—"}</div>
              <div className="account-settings-hint">Stable identifier assigned by your organization. Never changes, even if username is edited.</div>
            </div>

            <div className="account-settings-field">
              <label className="account-settings-label">Password</label>
              <div className="account-settings-input-col">
                <input
                  className="account-settings-input"
                  type="password"
                  placeholder="Current password"
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  disabled={savingPassword}
                  autoComplete="current-password"
                />
                <input
                  className="account-settings-input"
                  type="password"
                  placeholder="New password (min 6 characters)"
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  disabled={savingPassword}
                  autoComplete="new-password"
                />
                <input
                  className="account-settings-input"
                  type="password"
                  placeholder="Confirm new password"
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  disabled={savingPassword}
                  autoComplete="new-password"
                />
                <button
                  className="account-settings-save"
                  onClick={handlePasswordSave}
                  disabled={savingPassword || !currentPassword || !newPassword}
                >
                  {savingPassword ? "Saving..." : "Change Password"}
                </button>
              </div>
              <div className="account-settings-hint">
                Changing your password does not change your User ID or Role.
              </div>
            </div>
          </div>

          {/* Security Section */}
          <div className="account-settings-card">
            <h3>Security</h3>

            <div className="account-settings-field">
              <label className="account-settings-label">Security Mode</label>
              <div className="account-settings-readonly" style={{ color: SECURITY_MODE_LABELS[securityMode]?.color }}>
                {SECURITY_MODE_LABELS[securityMode]?.icon} {SECURITY_MODE_LABELS[securityMode]?.label}
              </div>
              <div className="account-settings-hint">
                Effective security mode is derived from your organization-assigned role and enforced server-side.
                You cannot lower the mode required by your role. You may increase protection.
                When working on a task, the effective mode is the stricter of your selection and the task policy.
              </div>
            </div>

            <div className="account-settings-info-grid">
              <div className="account-settings-info-item">
                <span className="info-label">Standard</span>
                <span className="info-desc">Normal task-scoped policy</span>
              </div>
              <div className="account-settings-info-item">
                <span className="info-label">Secure</span>
                <span className="info-desc">Restricted external access, enhanced audit</span>
              </div>
              <div className="account-settings-info-item">
                <span className="info-label">Sovereign</span>
                <span className="info-desc">Strongest available sovereign policy. Reduced external attack surface.</span>
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
