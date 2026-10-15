import { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { login, register } from "../api";

export default function LoginPage() {
  const navigate = useNavigate();
  const location = useLocation();
  const showRegister = location.state?.showRegister;
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [userId, setUserId] = useState("");
  const [role, setRole] = useState("operator");
  const [error, setError] = useState("");
  const [isRegister, setIsRegister] = useState(!!showRegister);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    try {
      if (isRegister) {
        await register(username, password, userId.trim() || null, role);
      } else {
        await login(username, password, userId.trim() || null);
      }
      navigate("/dashboard");
    } catch (err) {
      setError(err.message);
    }
  };

  return (
    <div className="login-page">
      <div className="brush-bg" />
      <Link to="/" className="login-back">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <polyline points="15 18 9 12 15 6" />
        </svg>
        Back
      </Link>
      <div className="login-card">
        <h1>MEDHA</h1>
        <p className="subtitle">Sovereign Controlled Multimodal AI Workbench</p>
        <form onSubmit={handleSubmit}>
          <input type="text" placeholder="Username" value={username} onChange={(e) => setUsername(e.target.value)} required />
          <input type="password" placeholder="Password" value={password} onChange={(e) => setPassword(e.target.value)} required />
          {isRegister ? (
            <input type="text" placeholder="User ID (assigned by your organization)" value={userId} onChange={(e) => setUserId(e.target.value)} required />
          ) : (
            <input type="text" placeholder="User ID (if usernames overlap)" value={userId} onChange={(e) => setUserId(e.target.value)} />
          )}
          {isRegister && (
            <select value={role} onChange={(e) => setRole(e.target.value)} required>
              <option value="senior_engineer">Senior Engineer</option>
              <option value="admin">Admin</option>
              <option value="manager">Manager</option>
              <option value="operator">Operator</option>
              <option value="junior_engineer">Junior Engineer</option>
              <option value="monitor">Monitor</option>
            </select>
          )}
          <button type="submit">{isRegister ? "Create Account" : "Sign In"}</button>
        </form>
        {error && <p className="error">{error}</p>}
        {isRegister && (
          <p className="subtitle" style={{ fontSize: "0.8rem", marginTop: "0.5rem" }}>
            Role must match your organization&apos;s authorized User ID record.
          </p>
        )}
        <div className="login-toggle">
          {isRegister ? (
            <>Already have an account? <button type="button" onClick={() => { setIsRegister(false); setError(""); }}>Sign In</button></>
          ) : (
            <>Don&apos;t have an account? <button type="button" onClick={() => { setIsRegister(true); setError(""); }}>Create Account</button></>
          )}
        </div>
        {!isRegister && (
          <div className="demo-creds">
            <p>Demo accounts:</p>
            <code>operator / medha-operator-2026</code><br />
            <code>engineer / medha-engineer-2026</code><br />
            <code>admin / medha-admin-2026</code>
          </div>
        )}
      </div>
    </div>
  );
}
