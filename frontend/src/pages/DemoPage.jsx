import { useState, useEffect, useCallback, Fragment } from "react";
import { useNavigate } from "react-router-dom";
import {
  getEnvironmentStatus,
  runDemoEvidence,
  runDemoAnalysis,
  downloadDemoReport,
} from "../api";
import "../pages/DemoPage.css";

/**
 * Static, demo-scoped scenario data only.
 * Never mixed with real users, tasks, conversations, audit, or documents.
 */
const DEMO_SCENARIO = Object.freeze({
  id: "sih26117-demo-pump-p204-inspection",
  title: "Pump P-204 Inspection Analysis",
  purpose:
    "Analyze an industrial pump inspection report and demonstrate how MEDHA processes confidential industrial work locally and securely.",
  description:
    "Analyze a prepared industrial inspection scenario using MEDHA's local, security-controlled AI architecture.",
  sensitivity: "confidential",
  security_mode: "secure",
  equipment: "Centrifugal Pump P-204",
  location: "Refinery Unit 3 — Crude Distillation",
  document: "Pump_P204_Scanned_Inspection",
  mode: "DEMO MODE",
  badge: "SIH26117 — Evaluator Demonstration",
});

const STEPS = Object.freeze([
  "Pump P-204 Inspection",
  "Process Local Evidence",
  "Analyze with Local AI",
  "Controlled Execution",
  "View Result",
  "Download Report",
]);

/** P10-C/P10-G — MEDHA security & AI pipeline shown before the run starts. */
const PIPELINE_PREVIEW = Object.freeze([
  { label: "SCANNED DOCUMENT", hint: "Read locally with OCR — fixed synthetic input" },
  { label: "TASK / POLICY", hint: "Fixed confidential · secure demo scenario" },
  { label: "PERMISSION-AWARE RAG", hint: "Retrieval limited to allowlisted demo sources" },
  { label: "LOCAL QWEN", hint: "Local open-weight model — no cloud LLM" },
  { label: "CONTROLLED TOOL", hint: "One fixed authorized calculation" },
  { label: "SANDBOX EXECUTION", hint: "Isolated subprocess — controlled network" },
  { label: "RESULT", hint: "Evidence-grounded finding and answer" },
  { label: "DOCX REPORT", hint: "Built locally — demo writes no audit rows" },
]);

/** P10-L — industrial concerns mapped only to implemented MEDHA capabilities. */
const INDUSTRIAL_RELEVANCE = Object.freeze([
  {
    category: "CONFIDENTIAL KNOWLEDGE",
    concern: "Restricted and confidential data drawn from multiple systems.",
    relevance: "RBAC · Task Passport · Permission-aware, task-scoped RAG",
  },
  {
    category: "EQUIPMENT RELIABILITY",
    concern: "Equipment inspection, reliability and root-cause questions.",
    relevance: "Local OCR · Evidence retrieval · Evidence-backed local analysis",
  },
  {
    category: "CONTROLLED AI",
    concern: "AI/ML adoption with model and tool control.",
    relevance: "Local Qwen · Model router · Tool policy",
  },
  {
    category: "SECURE EXECUTION",
    concern: "Cyber intrusion and business disruption risk.",
    relevance: "Action Gate · Controlled tools · Sandbox execution",
  },
  {
    category: "IT/OT BOUNDARY",
    concern: "Keeping AI interaction separated from operational systems.",
    relevance: "Controlled network policy · Controlled tool access",
  },
  {
    category: "TRACEABILITY",
    concern: "Regulatory and audit requirements.",
    relevance: "Audit trail · Task/execution trace on authenticated runs",
  },
  {
    category: "HUMAN DECISION SUPPORT",
    concern: "Human oversight of AI-assisted decisions.",
    relevance: "Evidence-backed result · Human handover architecture",
  },
]);

const DEMO_PROVES = Object.freeze([
  "Local OCR on the synthetic scan",
  "Local permission-aware RAG (demo-scoped sources)",
  "Local Qwen inference",
  "Controlled calculation / tool",
  "Sandbox execution",
  "Evidence-backed finding",
  "Local DOCX generation",
]);

const WORKBENCH_CAPABILITIES = Object.freeze([
  "JWT authentication and RBAC",
  "Task Passport and Action Gate",
  "Permission-aware, task-scoped RAG for user tasks",
  "Model router with passport-constrained model selection",
  "Agent plans with per-tool authorization",
  "Forensic audit trail for authenticated task runs",
  "Human approval / secure handover",
  "Secure analysis pipeline (Excel and DOCX deliverables)",
]);

const STATUS_TONE = {
  AVAILABLE: "ok",
  LOCAL: "ok",
  CONFIGURED: "ok",
  POLICY_CONTROLLED: "ok",
  completed: "ok",
  UNAVAILABLE: "warn",
  UNKNOWN: "warn",
  failed: "warn",
  timeout: "warn",
};

function tone(value) {
  return STATUS_TONE[value] || "neutral";
}

export default function DemoPage() {
  const navigate = useNavigate();
  const [step, setStep] = useState(1);
  const [evidence, setEvidence] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(null); // "evidence" | "analysis" | "report"
  const [error, setError] = useState("");
  const [reportError, setReportError] = useState("");
  const [reportReady, setReportReady] = useState(false);
  const [reportName, setReportName] = useState("");
  const [env, setEnv] = useState(null);
  const [runCount, setRunCount] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getEnvironmentStatus()
      .then((data) => {
        if (!cancelled) setEnv(data);
      })
      .catch(() => {
        if (!cancelled) setEnv(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleStartEvidence = useCallback(async () => {
    setError("");
    setLoading("evidence");
    try {
      const data = await runDemoEvidence();
      setEvidence(data);
      setStep(2);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(null);
    }
  }, []);

  const handleAnalyze = useCallback(async () => {
    setError("");
    setLoading("analysis");
    try {
      const data = await runDemoAnalysis();
      setAnalysis(data);
      setStep(3);
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(null);
    }
  }, []);

  const handleDownload = useCallback(async () => {
    setReportError("");
    setLoading("report");
    try {
      const data = await downloadDemoReport();
      setReportName(data?.filename || "");
      setReportReady(true);
    } catch (err) {
      setReportError(err.message);
    } finally {
      setLoading(null);
    }
  }, []);

  const handleRestart = () => {
    setStep(1);
    setEvidence(null);
    setAnalysis(null);
    setError("");
    setReportError("");
    setReportReady(false);
    setReportName("");
    setRunCount((n) => n + 1);
  };

  const handleBackToMedha = () => navigate("/");

  const model = env?.model || {};
  const unlocked = analysis ? 6 : evidence ? 2 : 1;
  const retry = analysis ? null : evidence ? handleAnalyze : handleStartEvidence;

  const pipelineNodes = [
    {
      label: "SCANNED DOCUMENT",
      state: !evidence
        ? "pending"
        : evidence.ocr?.status === "completed"
          ? "ok"
          : "warn",
    },
    {
      label: "TASK / POLICY",
      state: !env ? "pending" : env.error ? "warn" : "ok",
    },
    {
      label: "PERMISSION-AWARE RAG",
      state: !evidence ? "pending" : evidence.rag?.total > 0 ? "ok" : "warn",
    },
    {
      label: "LOCAL QWEN",
      state: !analysis
        ? "pending"
        : analysis.ai?.status === "AVAILABLE"
          ? "ok"
          : "warn",
    },
    {
      label: "CONTROLLED TOOL",
      state: !analysis
        ? "pending"
        : analysis.execution?.status === "completed"
          ? "ok"
          : "warn",
    },
    {
      label: "SANDBOX EXECUTION",
      state: !analysis
        ? "pending"
        : analysis.execution?.status === "completed"
          ? "ok"
          : "warn",
    },
    {
      label: "RESULT",
      state: analysis?.finding?.label ? "ok" : analysis ? "warn" : "pending",
    },
    {
      label: "DOCX REPORT",
      state: reportError ? "warn" : reportReady ? "ok" : "pending",
    },
  ];

  const securityRows = [
    { label: "Local AI", value: model.status || "UNKNOWN", state: tone(model.status) },
    {
      label: "Local RAG",
      value: env?.rag?.status || "UNKNOWN",
      state: tone(env?.rag?.status),
    },
    {
      label: "Local OCR",
      value: env?.ocr?.status || "UNKNOWN",
      state: tone(env?.ocr?.status),
    },
    {
      label: "Controlled Tools",
      value: env?.sandbox?.status || "UNKNOWN",
      state: tone(env?.sandbox?.status),
    },
    {
      label: "Auditable Execution",
      value: env?.execution || "UNKNOWN",
      state: tone(env?.execution),
    },
    {
      label: "External AI Policy Controlled",
      value:
        env?.external_ai?.status === "NOT_USED" && env?.network?.policy === "POLICY_CONTROLLED"
          ? "External AI not used"
          : "UNKNOWN",
      state:
        env?.external_ai?.status === "NOT_USED" && env?.network?.policy === "POLICY_CONTROLLED"
          ? "ok"
          : "warn",
    },
    {
      label: "Network Policy",
      value: env?.network?.policy || "UNKNOWN",
      state: tone(env?.network?.policy),
    },
  ];

  const evidenceSources = evidence?.rag?.chunks?.length
    ? [...new Set(evidence.rag.chunks.map((chunk) => chunk.source_name))].join(", ")
    : "";

  return (
    <div className="demo-page" data-testid="demo-page">
      <div className="demo-banner" data-testid="demo-banner">
        <span className="demo-banner-mode">DEMO MODE</span>
        <span className="demo-banner-sub">SIH26117 — Evaluator Demonstration · no login required</span>
      </div>

      <header className="demo-header">
        <div className="demo-brand">MEDHA</div>
        <div className="demo-brand-sub">Sovereign On-Premise Agentic AI Workbench</div>
      </header>

      <nav className="demo-stepper" aria-label="Demo steps">
        {STEPS.map((label, index) => {
          const number = index + 1;
          const reachable = number <= unlocked;
          return (
            <button
              key={label}
              type="button"
              className={`demo-step${step === number ? " is-active" : ""}${
                reachable ? "" : " is-locked"
              }`}
              disabled={!reachable}
              onClick={() => reachable && setStep(number)}
              data-testid={`demo-step-${number}`}
            >
              <span className="demo-step-num">{number}</span>
              <span className="demo-step-label">{label}</span>
            </button>
          );
        })}
      </nav>

      <div className="demo-layout">
        <main className="demo-stage" data-testid="demo-stage">
          {error && (
            <div className="demo-alert demo-alert-warn" role="alert">
              <p>{error}</p>
              <div className="demo-alert-actions">
                {retry && (
                  <button
                    type="button"
                    className="demo-btn demo-btn-primary"
                    onClick={retry}
                    disabled={!!loading}
                  >
                    RETRY
                  </button>
                )}
                <button type="button" className="demo-btn demo-btn-secondary" onClick={handleBackToMedha}>
                  BACK TO MEDHA
                </button>
              </div>
            </div>
          )}

          {/* P10-H — short visible proof of the local pipeline */}
          {step >= 2 && evidence && (
            <div className="demo-pipeline" data-testid="demo-pipeline">
              <p className="demo-label demo-pipeline-title">
                MEDHA Security &amp; AI Pipeline — live status
              </p>
              {pipelineNodes.map((node, index) => (
                <Fragment key={node.label}>
                  <span className={`demo-pipeline-node is-${node.state}`}>{node.label}</span>
                  {index < pipelineNodes.length - 1 && (
                    <span className="demo-pipeline-arrow" aria-hidden="true">
                      ↓
                    </span>
                  )}
                </Fragment>
              ))}
            </div>
          )}

          {/* ---------- STEP 1 ---------- */}
          {step === 1 && (
            <section className="demo-card" data-testid="demo-scenario-card">
              <p className="demo-label">Step 1 · Scenario</p>
              <h1 className="demo-title" data-testid="demo-scenario-title">
                {DEMO_SCENARIO.title}
              </h1>
              <p className="demo-description" data-testid="demo-scenario-description">
                {DEMO_SCENARIO.description}
              </p>

              <dl className="demo-meta">
                <div>
                  <dt>Input document</dt>
                  <dd>{DEMO_SCENARIO.document} (synthetic scanned inspection)</dd>
                </div>
                <div>
                  <dt>Equipment</dt>
                  <dd>{DEMO_SCENARIO.equipment}</dd>
                </div>
                <div>
                  <dt>Location</dt>
                  <dd>{DEMO_SCENARIO.location}</dd>
                </div>
                <div>
                  <dt>Sensitivity</dt>
                  <dd>{DEMO_SCENARIO.sensitivity} · {DEMO_SCENARIO.security_mode} mode</dd>
                </div>
              </dl>

              <div className="demo-flow" data-testid="demo-pipeline-preview">
                <p className="demo-label">MEDHA Security &amp; AI Pipeline</p>
                <ol>
                  {PIPELINE_PREVIEW.map((stage) => (
                    <li key={stage.label}>
                      <span className="demo-flow-node">{stage.label}</span>
                      <span className="demo-flow-hint">{stage.hint}</span>
                    </li>
                  ))}
                </ol>
              </div>

              <div className="demo-actions">
                <button
                  type="button"
                  className="demo-btn demo-btn-primary"
                  onClick={handleStartEvidence}
                  disabled={loading === "evidence"}
                  data-testid="start-demo"
                >
                  {loading === "evidence" ? "PROCESSING…" : "START ANALYSIS"}
                </button>
                <button
                  type="button"
                  className="demo-btn demo-btn-secondary"
                  onClick={handleBackToMedha}
                  data-testid="back-to-medha"
                >
                  BACK TO MEDHA
                </button>
              </div>
              <p className="demo-note">
                Runs local OCR and local retrieval on the bundled synthetic scan —
                usually a few seconds. No account, no upload, no private data.
              </p>
            </section>
          )}

          {/* ---------- STEP 2 ---------- */}
          {step === 2 && evidence && (
            <section className="demo-card">
              <p className="demo-label">Step 2 · Process Local Evidence</p>
              <h1 className="demo-title">Local OCR → local knowledge</h1>

              <div className="demo-panel">
                <div className="demo-panel-head">
                  <span className="demo-label">Local OCR</span>
                  <span className={`demo-chip is-${tone(evidence.ocr?.status)}`}>
                    {evidence.ocr?.status === "completed" ? "LOCAL · COMPLETED" : evidence.ocr?.status}
                  </span>
                </div>
                <p className="demo-kv">
                  Engine: <strong>{evidence.ocr?.engine || "—"}</strong>
                  {" · "}Source: <strong>{evidence.ocr?.source}</strong>
                  {" · "}Characters: <strong>{evidence.ocr?.chars ?? 0}</strong>
                </p>
                {evidence.ocr?.status !== "completed" && (
                  <p className="demo-warn-text">
                    Local OCR unavailable. Evidence read from the bundled demo document
                    instead. {evidence.ocr?.reason}
                  </p>
                )}
                <pre className="demo-pre">{evidence.ocr?.text || "—"}</pre>
              </div>

              <div className="demo-panel">
                <div className="demo-panel-head">
                  <span className="demo-label">RAG evidence (demo-scoped retrieval)</span>
                  <span className="demo-chip is-ok">LOCAL · {evidence.rag?.total ?? 0} chunks</span>
                </div>
                <ul className="demo-evidence-list">
                  {(evidence.rag?.chunks || []).map((chunk, index) => (
                    <li
                      key={`${chunk.source_name}-${index}`}
                      className={`demo-evidence-item${
                        chunk.source_name === DEMO_SCENARIO.document ? " is-primary" : ""
                      }`}
                      data-testid="demo-evidence-name"
                    >
                      <div className="demo-evidence-head">
                        <span>{chunk.source_name}</span>
                        <span className="demo-evidence-score">{chunk.score}</span>
                      </div>
                      <p className="demo-evidence-snippet">{chunk.text}</p>
                    </li>
                  ))}
                </ul>
                <p className="demo-note">
                  The highlighted source is the synthetic Pump P-204 scan — it
                  backs the finding you will see in Step 5.
                </p>
              </div>

              <div className="demo-actions">
                <button
                  type="button"
                  className="demo-btn demo-btn-primary"
                  onClick={handleAnalyze}
                  disabled={loading === "analysis"}
                  data-testid="analyze-local-ai"
                >
                  {loading === "analysis" ? "RUNNING LOCAL AI…" : "ANALYZE WITH LOCAL AI"}
                </button>
                <button
                  type="button"
                  className="demo-btn demo-btn-secondary"
                  onClick={() => setStep(1)}
                >
                  BACK
                </button>
              </div>
              <p className="demo-note">
                Runs the local model over the retrieved evidence — typically 10–30
                seconds on CPU. No cloud model is called.
              </p>
            </section>
          )}

          {/* ---------- STEP 3 ---------- */}
          {step === 3 && analysis && (
            <section className="demo-card">
              <p className="demo-label">Step 3 · Analyze with Local AI</p>
              <h1 className="demo-title">Local model answer</h1>

              <div className="demo-panel" data-testid="demo-local-model">
                <div className="demo-panel-head">
                  <span className="demo-label">Local model</span>
                  <span className={`demo-chip is-${tone(analysis.ai?.status)}`}>
                    {analysis.ai?.status}
                  </span>
                </div>
                <p className="demo-kv">
                  Model: <strong>{analysis.ai?.model || "—"}</strong>
                  {" · "}Provider: <strong>{analysis.ai?.provider || "—"}</strong>
                  {" · "}Runtime: <strong>{analysis.ai?.runtime || "—"}</strong>
                </p>
              </div>

              <div className="demo-panel">
                <div className="demo-panel-head">
                  <span className="demo-label">AI response</span>
                  {analysis.ai?.latency_ms ? (
                    <span className="demo-chip is-neutral">{analysis.ai.latency_ms} ms</span>
                  ) : null}
                </div>
                {analysis.ai?.status === "AVAILABLE" ? (
                  <p className="demo-answer" data-testid="demo-ai-answer">
                    {analysis.ai.answer}
                  </p>
                ) : (
                  <p className="demo-warn-text" data-testid="demo-ai-unavailable">
                    {analysis.ai?.reason || "Local AI runtime unavailable."}
                  </p>
                )}
                <p className="demo-note">
                  This answer was generated by the local open-weight model from the
                  retrieved evidence above — not from an external cloud model.
                </p>
              </div>

              <div className="demo-actions">
                <button
                  type="button"
                  className="demo-btn demo-btn-primary"
                  onClick={() => setStep(4)}
                  data-testid="next-execution"
                >
                  NEXT: CONTROLLED EXECUTION
                </button>
                <button type="button" className="demo-btn demo-btn-secondary" onClick={() => setStep(2)}>
                  BACK
                </button>
              </div>
            </section>
          )}

          {/* ---------- STEP 4 ---------- */}
          {step === 4 && analysis && (
            <section className="demo-card">
              <p className="demo-label">Step 4 · Controlled Execution</p>
              <h1 className="demo-title">Authorized tool in the sandbox</h1>

              <div className="demo-exec-flow" data-testid="demo-execution">
                <span className="demo-exec-node">AUTHORIZED TOOL</span>
                <span className="demo-exec-arrow">↓</span>
                <span className="demo-exec-node">CONTROLLED SANDBOX</span>
                <span className="demo-exec-arrow">↓</span>
                <span className="demo-exec-node">CALCULATION</span>
                <span className="demo-exec-arrow">↓</span>
                <span className="demo-exec-node is-result">RESULT</span>
              </div>

              <div className="demo-panel">
                <div className="demo-panel-head">
                  <span className="demo-label">
                    Controlled tool operation · {analysis.execution?.tool || "tool"}
                  </span>
                  <span className={`demo-chip is-${tone(analysis.execution?.status)}`}>
                    {analysis.execution?.status?.toUpperCase()}
                  </span>
                </div>
                <p className="demo-exec-equation" data-testid="demo-execution-result">
                  {analysis.execution?.operation} ={" "}
                  <strong>{analysis.execution?.result || "—"}</strong>
                </p>
                <p className="demo-kv">
                  Sandbox: <strong>{analysis.execution?.sandbox || "—"}</strong>
                  {" · "}Network: <strong>{analysis.execution?.network || "—"}</strong>
                  {" · "}Duration: <strong>{analysis.execution?.duration_ms ?? "—"} ms</strong>
                </p>
                {analysis.execution?.status !== "completed" && (
                  <p className="demo-warn-text">
                    {analysis.execution?.reason || "Controlled execution unavailable."}
                  </p>
                )}
                <p className="demo-note">
                  Real isolated subprocess with network and filesystem guards. The demo
                  runs one fixed authorized calculation only — no client-supplied code.
                </p>
              </div>

              <div className="demo-actions">
                <button
                  type="button"
                  className="demo-btn demo-btn-primary"
                  onClick={() => setStep(5)}
                  data-testid="next-result"
                >
                  NEXT: VIEW RESULT
                </button>
                <button type="button" className="demo-btn demo-btn-secondary" onClick={() => setStep(3)}>
                  BACK
                </button>
              </div>
            </section>
          )}

          {/* ---------- STEP 5 ---------- */}
          {step === 5 && analysis && (
            <section className="demo-card">
              <p className="demo-label">Step 5 · View Result</p>
              <h1 className="demo-title">Final result</h1>

              <div className="demo-result-block">
                <span className="demo-label">Final finding</span>
                <p className="demo-result-finding" data-testid="demo-result-finding">
                  {analysis.finding?.label}
                </p>
              </div>

              <div className="demo-panel">
                <div className="demo-panel-head">
                  <span className="demo-label">Why? — source and evidence</span>
                  <span className="demo-chip is-ok">LOCAL RAG</span>
                </div>
                <p className="demo-kv">
                  Source: <strong>{analysis.finding?.source}</strong> — synthetic
                  Pump P-204 inspection document
                </p>
                <p className="demo-label demo-sub-label">Relevant evidence</p>
                <blockquote className="demo-evidence-quote">
                  {analysis.finding?.evidence || "—"}
                </blockquote>
                <p className="demo-kv">
                  Retrieved locally: <strong>{evidence?.rag?.total ?? 0}</strong>{" "}
                  chunks
                  {evidenceSources ? (
                    <>
                      {" · "}from <strong>{evidenceSources}</strong>
                    </>
                  ) : null}
                </p>
                <p className="demo-note">
                  Source and snippet come from the local OCR and retrieval run in
                  Step 2 — real demo data, no invented citations.
                </p>
              </div>

              <div className="demo-panel">
                <div className="demo-panel-head">
                  <span className="demo-label">Local AI</span>
                  <span className={`demo-chip is-${tone(analysis.ai?.status)}`}>
                    {analysis.ai?.status}
                  </span>
                </div>
                <p className="demo-kv">
                  Model: <strong>{analysis.ai?.model || "—"}</strong>
                  {" · "}Provider: <strong>{analysis.ai?.provider || "—"}</strong>
                  {" · "}Runtime: <strong>{analysis.ai?.runtime || "—"}</strong>
                </p>
                {analysis.ai?.status === "AVAILABLE" ? (
                  <p className="demo-answer demo-answer-compact">{analysis.ai.answer}</p>
                ) : (
                  <p className="demo-warn-text">
                    {analysis.ai?.reason || "Local AI runtime unavailable."}
                  </p>
                )}
                <p className="demo-note">
                  Answer generated by the local Qwen path over the retrieved
                  evidence above — not from a cloud model.
                </p>
              </div>

              <div className="demo-actions">
                <button
                  type="button"
                  className="demo-btn demo-btn-primary"
                  onClick={() => setStep(6)}
                  data-testid="next-report"
                >
                  NEXT: DOWNLOAD REPORT
                </button>
                <button type="button" className="demo-btn demo-btn-secondary" onClick={() => setStep(4)}>
                  BACK
                </button>
              </div>
            </section>
          )}

          {/* ---------- STEP 6 ---------- */}
          {step === 6 && (
            <section className="demo-card">
              <p className="demo-label">Step 6 · Download Report</p>
              <h1 className="demo-title">DOCX report</h1>
              <p className="demo-description">
                A real .docx report built locally from the synthetic Pump P-204 demo
                scenario: finding, evidence sources, recommendations and execution
                details.
              </p>

              <div className="demo-actions">
                <button
                  type="button"
                  className="demo-btn demo-btn-primary"
                  onClick={handleDownload}
                  disabled={loading === "report"}
                  data-testid="download-docx"
                >
                  {loading === "report" ? "GENERATING…" : "DOWNLOAD DOCX REPORT"}
                </button>
                <button type="button" className="demo-btn demo-btn-secondary" onClick={handleRestart}>
                  RESTART DEMO
                </button>
                <button
                  type="button"
                  className="demo-btn demo-btn-secondary"
                  onClick={handleBackToMedha}
                  data-testid="back-to-medha-workspace"
                >
                  BACK TO MEDHA
                </button>
              </div>

              {reportReady && !reportError && (
                <p className="demo-success-text" data-testid="demo-report-ready">
                  {reportName
                    ? `Report downloaded — ${reportName}`
                    : "Report downloaded."}
                </p>
              )}
              {reportError && (
                <div className="demo-alert demo-alert-warn" role="alert">
                  <p>{reportError}</p>
                </div>
              )}

              {/* P10-M — evaluator recap, only steps the demo state actually supports */}
              <div className="demo-summary" data-testid="demo-summary">
                <p className="demo-label">What MEDHA just did</p>
                <ul>
                  <li>Read the synthetic Pump P-204 inspection document locally.</li>
                  <li>
                    {evidence?.ocr?.status === "completed"
                      ? "Extracted information using local OCR."
                      : "Read the document content (local OCR unavailable — bundled text used)."}
                  </li>
                  <li>
                    {evidence?.rag?.total > 0
                      ? `Retrieved ${evidence.rag.total} relevant local evidence chunks.`
                      : "Searched local evidence (no chunks matched)."}
                  </li>
                  <li>
                    {analysis?.ai?.status === "AVAILABLE"
                      ? "Used local Qwen for analysis."
                      : "Local Qwen unavailable — reported honestly instead of using a cloud model."}
                  </li>
                  <li>
                    {analysis?.execution?.status === "completed"
                      ? "Executed the authorized calculation/tool."
                      : "Controlled execution unavailable — reported honestly."}
                  </li>
                  <li>
                    {analysis?.finding?.label
                      ? `Produced the structured finding: ${analysis.finding.label}`
                      : "Produced the result status."}
                  </li>
                  <li>
                    {reportReady
                      ? "Generated the DOCX report locally."
                      : reportError
                        ? "DOCX report generation failed — see the error above."
                        : "DOCX report ready to generate locally."}
                  </li>
                </ul>
              </div>

              <p className="demo-note">
                Demo uses synthetic Pump P-204 data. It does not access private
                organizational data.
              </p>
              <p className="demo-note">
                Synthetic demonstration content only. The report never contains real
                accounts, credentials, private documents or audit records.
              </p>
            </section>
          )}
        </main>

        <aside className="demo-side">
          <div className="demo-panel" data-testid="demo-security">
            <div className="demo-panel-head">
              <span className="demo-label">MEDHA SECURITY</span>
              <span className="demo-chip is-neutral">LIVE</span>
            </div>
            <ul className="demo-security-list">
              {securityRows.map((row) => (
                <li key={row.label} className={`is-${row.state}`}>
                  <span className="demo-sec-mark" aria-hidden="true">
                    {row.state === "ok" ? "✓" : row.state === "warn" ? "!" : "·"}
                  </span>
                  <span className="demo-sec-label">{row.label}</span>
                  <span className="demo-sec-value">
                    {row.value === "UNKNOWN" ? "Status unavailable" : row.value}
                  </span>
                </li>
              ))}
            </ul>
            <p className="demo-note">
              {env?.network?.note ||
                "Connectivity follows security-mode policy. This is policy control, not a physical air gap."}
            </p>
            <p className="demo-note">
              Audit events are recorded for authenticated task runs. This evaluator
              demo writes no audit records.
            </p>
          </div>

          <div className="demo-panel" data-testid="demo-model-panel">
            <div className="demo-panel-head">
              <span className="demo-label">LOCAL MODEL</span>
              <span className={`demo-chip is-${tone(model.status)}`}>
                {model.status && model.status !== "UNKNOWN"
                  ? model.status
                  : "Status unavailable"}
              </span>
            </div>
            <p className="demo-model-name">{model.name || "—"}</p>
            <p className="demo-kv">
              Runtime: <strong>{model.runtime || "—"}</strong>
            </p>
            {model.status !== "AVAILABLE" && (
              <p className="demo-warn-text">
                {model.reason
                  ? "Local AI runtime unavailable. Start Ollama and try again."
                  : "Local AI status could not be determined."}
              </p>
            )}
          </div>

          {runCount > 0 && (
            <p className="demo-note">Run {runCount} · repeatable, synthetic data only.</p>
          )}
        </aside>
      </div>

      {/* P10-L — industrial relevance, connected only to implemented capabilities */}
      <section
        className="demo-relevance"
        aria-labelledby="relevance-title"
        data-testid="demo-relevance"
      >
        <h2 className="demo-relevance-title" id="relevance-title">
          Why MEDHA for Industrial Operations?
        </h2>

        <div className="demo-relevance-grid">
          {INDUSTRIAL_RELEVANCE.map((item) => (
            <article key={item.category} className="demo-relevance-card">
              <h3>{item.category}</h3>
              <p className="demo-relevance-concern">
                <span className="demo-relevance-kicker">Industrial concern</span>
                {item.concern}
              </p>
              <p className="demo-relevance-controls">
                <span className="demo-relevance-kicker">MEDHA relevance</span>
                {item.relevance}
              </p>
            </article>
          ))}
        </div>

        <div className="demo-relevance-split">
          <div className="demo-relevance-list is-demo" data-testid="demo-proves">
            <p className="demo-label">Demonstrated in this live demo</p>
            <ul>
              {DEMO_PROVES.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
          <div className="demo-relevance-list is-caps" data-testid="demo-capabilities">
            <p className="demo-label">
              MEDHA workbench capabilities — not all exercised by this demo
            </p>
            <ul>
              {WORKBENCH_CAPABILITIES.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </div>
      </section>

      <footer className="demo-footer">
        <span>Isolated demo path — synthetic data only — no login required</span>
      </footer>
    </div>
  );
}
