import { useNavigate } from "react-router-dom";
import "../pages/LandingPage.css";

const WHY_MEDHA = [
  {
    title: "Local open-weight LLM",
    text: "Inference runs on a local open-weight Qwen model instead of a mandatory cloud LLM.",
  },
  {
    title: "Permission-aware retrieval",
    text: "Document retrieval is filtered by source and sensitivity before results reach the model.",
  },
  {
    title: "Local OCR",
    text: "Scanned industrial documents are read with a local OCR engine on this machine.",
  },
  {
    title: "Controlled tool execution",
    text: "Tools run only when policy and authorization checks allow it, inside a controlled sandbox.",
  },
  {
    title: "Security and audit trail",
    text: "JWT auth, RBAC, Task Passports, Action Gate and a forensic audit trail for task runs.",
  },
  {
    title: "Confidential industrial work",
    text: "Designed for confidential inspection and maintenance knowledge work inside the organization.",
  },
];

const ARCHITECTURE = [
  "USER",
  "AUTH / RBAC",
  "TASK PASSPORT",
  "ACTION GATE",
  "LOCAL KNOWLEDGE / RAG",
  "LOCAL MODEL ROUTER",
  "LOCAL QWEN",
  "CONTROLLED TOOLS / SANDBOX",
  "VERIFICATION",
  "AUDIT / DELIVERABLE",
];

export default function LandingPage() {
  const navigate = useNavigate();

  const handleTryDemo = () => navigate("/demo");
  const handleSignIn = () => navigate("/login");
  const handleCreateAccount = () => navigate("/login", { state: { showRegister: true } });

  return (
    <div className="landing-page">
      <div className="landing-glow-bg" />

      <nav className="landing-navbar">
        <div className="landing-nav-brand">MEDHA</div>
        <div className="landing-nav-meta">SIH26117</div>
      </nav>

      <div className="landing-content">
        <header className="landing-hero">
          <h1 className="landing-title">MEDHA</h1>
          <p className="landing-tagline">
            Sovereign Agentic AI Workbench for Confidential Industrial Work
          </p>
          <p className="landing-oneline">
            Run industrial AI workflows locally — with controlled data access,
            local models, evidence, tools, and auditability.
          </p>
          <p className="landing-problem">
            The problem: confidential industrial work cannot safely depend on
            cloud AI services.
          </p>

          <div className="landing-cta-row">
            <button
              type="button"
              className="landing-cta landing-cta-primary"
              onClick={handleTryDemo}
              data-testid="try-live-demo"
            >
              TRY LIVE DEMO
            </button>
            <button
              type="button"
              className="landing-cta landing-cta-secondary"
              onClick={handleSignIn}
            >
              Sign In
            </button>
            <button
              type="button"
              className="landing-cta landing-cta-ghost"
              onClick={handleCreateAccount}
            >
              Sign Up
            </button>
          </div>

          <ul className="landing-proof-strip">
            <li>No login required for the demo</li>
            <li>Synthetic Pump P-204 data only</li>
            <li>Confidential processing stays local</li>
            <li>External AI controlled by policy</li>
          </ul>
        </header>

        <section className="landing-section" aria-labelledby="why-title">
          <h2 id="why-title" className="landing-section-title">
            WHY MEDHA?
          </h2>
          <div className="landing-why-grid">
            {WHY_MEDHA.map((point) => (
              <article key={point.title} className="landing-why-card">
                <h3>{point.title}</h3>
                <p>{point.text}</p>
              </article>
            ))}
          </div>
        </section>

        <section className="landing-section" aria-labelledby="arch-title">
          <h2 id="arch-title" className="landing-section-title">
            ARCHITECTURE SNAPSHOT
          </h2>
          <ol className="landing-arch" data-testid="architecture-snapshot">
            {ARCHITECTURE.map((stage, index) => (
              <li key={stage}>
                <span className="landing-arch-index">{index + 1}</span>
                <span className="landing-arch-label">{stage}</span>
              </li>
            ))}
          </ol>
        </section>

        <div className="landing-footer">
          <span className="footer-badge">MEDHA</span>
          <span className="footer-text">
            Sovereign On-Premise Agentic AI Workbench — synthetic demonstration data
          </span>
        </div>
      </div>
    </div>
  );
}
