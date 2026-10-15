import { useState, useEffect, useRef } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { getTask, getAuditTrail, transitionTask, listConversations, getIdentity, clearToken, createPlan, executeStep, runLocalOcr, executeTool, downloadDocxReport } from "../api";
import { STATUS_COLORS, formatEventType, isTaskPinned, toggleTaskPin } from "../utils/helpers";
import TopNav from "../components/TopNav";
import { useSecurity } from "../contexts/SecurityContext";
import Toast from "../components/Toast";

const TABS = ["Overview", "AI Analysis", "Evidence", "Conversation", "Execution", "Report"];

export default function TaskWorkspace() {
  const { securityMode } = useSecurity();
  const { id } = useParams();
  const [task, setTask] = useState(null);
  const [auditEvents, setAuditEvents] = useState([]);
  const [conversations, setConversations] = useState([]);
  const [activeTab, setActiveTab] = useState("Overview");
  const [error, setError] = useState("");
  const [user, setUser] = useState(null);
  const [toast, setToast] = useState(null);
  const [toolRun, setToolRun] = useState(null);
  const [toolRunning, setToolRunning] = useState(false);
  const [ocrFile, setOcrFile] = useState(null);
  const [ocrRunning, setOcrRunning] = useState(false);
  const [ocrResult, setOcrResult] = useState(null);
  const ocrInputRef = useRef(null);
  const [codeRunning, setCodeRunning] = useState(false);
  const [codeRun, setCodeRun] = useState(null);
  const [docxRunning, setDocxRunning] = useState(false);
  const navigate = useNavigate();

  const handleDownloadDocx = async () => {
    if (docxRunning) return;
    setDocxRunning(true);
    try {
      const result = await downloadDocxReport(id);
      setToast({ type: "success", message: `DOCX report downloaded (${result.size} bytes)` });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
    setDocxRunning(false);
  };

  useEffect(() => {
    getIdentity().then(setUser).catch(() => { clearToken(); navigate("/"); });
    getTask(id).then((t) => {
      setTask(t);
      getAuditTrail(id).then((trail) => setAuditEvents(trail.events || [])).catch(() => {});
      listConversations(id).then((res) => setConversations(res.conversations || [])).catch(() => {});
    }).catch((err) => setError(err.message));
  }, [id, navigate]);

  const handleTransition = async (newStatus) => {
    try {
      const updated = await transitionTask(id, newStatus, `Transitioned to ${newStatus}`);
      setTask(updated);
      const trail = await getAuditTrail(id);
      setAuditEvents(trail.events || []);
      setToast({ type: "success", message: `Status changed to ${newStatus}` });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
  };

  const handlePin = () => {
    toggleTaskPin(id);
    setToast({ type: "success", message: isTaskPinned(id) ? "Task pinned" : "Task unpinned" });
  };

  const handleLogout = () => { clearToken(); navigate("/"); };
  const handleUserUpdate = (updated) => setUser(updated);

  const canRunDataAnalyzer =
    task &&
    (task.status === "authorized" || task.status === "executing") &&
    Array.isArray(task.allowed_tools) &&
    task.allowed_tools.includes("data_analyzer");

  const handleRunDataAnalyzer = async () => {
    if (!canRunDataAnalyzer || toolRunning) return;
    setToolRunning(true);
    setToolRun(null);
    try {
      const plan = await createPlan(
        id,
        "Analyze the Pump P-204 inspection measurements and calculate basic statistics"
      );
      const step = (plan.steps || []).find((s) => s.tool_name === "data_analyzer");
      if (!step) {
        setToolRun({ success: false, output: "Planner did not select data_analyzer for this query." });
        setToolRunning(false);
        return;
      }
      const result = await executeStep(plan.plan_id, step.step_id, {});
      setToolRun(result);
      const trail = await getAuditTrail(id);
      setAuditEvents(trail.events || []);
    } catch (err) {
      setToolRun({ success: false, output: err.message });
    }
    setToolRunning(false);
  };

  const canRunOcr =
    task &&
    (task.status === "authorized" || task.status === "executing") &&
    ocrFile;

  const handleRunOcr = async () => {
    if (!canRunOcr || ocrRunning) return;
    setOcrRunning(true);
    setOcrResult(null);
    try {
      const result = await runLocalOcr(id, ocrFile, true);
      setOcrResult(result);
      const trail = await getAuditTrail(id);
      setAuditEvents(trail.events || []);
      setToast({ type: "success", message: `OCR completed (${result.char_count} chars)` });
    } catch (err) {
      setOcrResult({ status: "failed", error: err.message, text: "", source_name: ocrFile?.name || "" });
      setToast({ type: "error", message: err.message });
    }
    setOcrRunning(false);
  };

  const canRunCode =
    task &&
    (task.status === "authorized" || task.status === "executing") &&
    Array.isArray(task.allowed_tools) &&
    task.allowed_tools.includes("code_executor");

  const handleRunCode = async () => {
    if (!canRunCode || codeRunning) return;
    setCodeRunning(true);
    setCodeRun(null);
    try {
      const result = await executeTool(
        id,
        "code_executor",
        "Pump P-204 engineering calculation A + B",
        { A: 25, B: 17 },
        "A = INPUT.get('A', 0)\nB = INPUT.get('B', 0)\nprint(A + B)"
      );
      setCodeRun(result);
      const trail = await getAuditTrail(id);
      setAuditEvents(trail.events || []);
      setToast({
        type: result.status === "completed" ? "success" : "error",
        message: result.status === "completed" ? "Sandbox execution succeeded" : (result.error || "Sandbox execution failed"),
      });
    } catch (err) {
      setCodeRun({ status: "failed", error: err.message, output: "", sandbox: "active", network: "blocked" });
      setToast({ type: "error", message: err.message });
    }
    setCodeRunning(false);
  };

  const handleExportJSON = () => {
    const data = { task, auditEvents, exportedAt: new Date().toISOString(), generator: "MEDHA" };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `medha-task-${id}.json`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportReport = () => {
    const lines = [
      "MEDHA TASK REPORT",
      "=" .repeat(50),
      "",
      "Task Information",
      "-".repeat(30),
      `Task ID: ${task.task_id}`,
      `Title: ${task.title}`,
      `User: ${task.identity}`,
      `Role: ${task.role}`,
      `Purpose: ${task.purpose}`,
      `Sensitivity: ${task.sensitivity}`,
      `Status: ${task.status}`,
      `Network Policy: ${task.network_policy}`,
      `Allowed Tools: ${task.allowed_tools.join(", ") || "none"}`,
      `Allowed Models: ${task.allowed_models.join(", ") || "none"}`,
      `Created: ${task.created_at}`,
      `Updated: ${task.updated_at}`,
      "",
      "Audit Summary",
      "-".repeat(30),
      `Total Events: ${auditEvents.length}`,
      "",
    ];
    auditEvents.forEach((e) => {
      lines.push(`${e.timestamp} | ${formatEventType(e.event_type)} | ${e.identity} (${e.role})`);
      if (e.detail) lines.push(`  Detail: ${e.detail}`);
    });
    lines.push("", "Generated by MEDHA");

    const blob = new Blob([lines.join("\n")], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `medha-report-${id}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  if (error) return <div className="app-layout"><div className="brush-bg" /><TopNav user={user} onLogout={handleLogout} securityMode={securityMode} onUserUpdate={handleUserUpdate} /><main className="main-content"><p className="error">{error}</p></main></div>;
  if (!task) return <div className="app-layout"><div className="brush-bg" /><TopNav user={user} onLogout={handleLogout} securityMode={securityMode} onUserUpdate={handleUserUpdate} /><main className="main-content"><p className="text-muted">Loading...</p></main></div>;

  return (
    <div className="app-layout">
      <div className="brush-bg" />
      <TopNav user={user} onLogout={handleLogout} securityMode={securityMode} onUserUpdate={handleUserUpdate} />
      <main className="main-content">
        <Toast toast={toast} onClear={() => setToast(null)} />

        <div className="task-header">
          <button className="btn-back" onClick={() => navigate(-1)}>&larr;</button>
          <div style={{ flex: 1 }}>
            <h1>{task.title}</h1>
            <div className="task-header-meta">
              <span className="status-badge" style={{ background: STATUS_COLORS[task.status] || "#666" }}>{task.status}</span>
              <span className="sensitivity-tag">{task.sensitivity}</span>
              <span className="task-id-label">ID: {task.task_id.slice(0, 8)}...</span>
            </div>
          </div>
          <button className={`btn-pin-large ${isTaskPinned(id) ? "active" : ""}`} onClick={handlePin} title={isTaskPinned(id) ? "Unpin" : "Pin"}>
            <svg width="16" height="16" viewBox="0 0 24 24" fill={isTaskPinned(id) ? "currentColor" : "none"} stroke="currentColor" strokeWidth="2">
              <path d="M12 2L12 22M12 2L8 6M12 2L16 6" />
            </svg>
          </button>
        </div>

        <div className="workspace-tabs">
          {TABS.map((tab) => (
            <button
              key={tab}
              className={`workspace-tab ${activeTab === tab ? "active" : ""}`}
              onClick={() => setActiveTab(tab)}
            >
              {tab}
            </button>
          ))}
        </div>

        <div className="workspace-content">
          {task.status === "pending_approval" && (
            <div className="card" style={{ borderLeft: "3px solid #f59e0b" }}>
              <div className="passport-section-label">Human Verification</div>
              <p style={{ color: "#f59e0b", fontWeight: 600 }}>Waiting for Human Verification</p>
              <p className="text-muted">
                This task requires manager/admin approval before execution. A supervisor must
                review the plan on the Supervision &amp; Verification page. You cannot execute
                this task until it is approved.
              </p>
            </div>
          )}

          {task.status === "rejected" && (
            <div className="card" style={{ borderLeft: "3px solid #ef4444" }}>
              <div className="passport-section-label">Human Verification</div>
              <p style={{ color: "#ef4444", fontWeight: 600 }}>Rejected by supervisor</p>
              <p className="text-muted">Human approval was rejected. This task remains blocked.</p>
              {(() => {
                const rej = [...auditEvents]
                  .reverse()
                  .find((e) => e.event_type.includes("REJECT_TASK") || e.event_type.includes("REJECT_COMPLETION"));
                if (rej?.detail) {
                  const m = rej.detail.match(/reason=(.*)$/);
                  return (
                    <p className="text-muted">
                      <strong>Reason:</strong> {m ? m[1] : rej.detail} — {rej.identity} ({rej.role})
                    </p>
                  );
                }
                return null;
              })()}
            </div>
          )}

          {task.status === "pending_verification" && (
            <div className="card" style={{ borderLeft: "3px solid #a855f7" }}>
              <div className="passport-section-label">Completion Verification</div>
              <p style={{ color: "#a855f7", fontWeight: 600 }}>Waiting for Completion Verification</p>
              <p className="text-muted">
                Execution finished. A manager/admin must verify completion on the
                Supervision &amp; Verification page before this task is marked verified.
              </p>
            </div>
          )}

          {task.status === "verified" && (
            <div className="card" style={{ borderLeft: "3px solid #10b981" }}>
              <div className="passport-section-label">Completion Verification</div>
              <p style={{ color: "#10b981", fontWeight: 600 }}>Verified by supervisor</p>
            </div>
          )}

          {activeTab === "Overview" && (
            <div className="workspace-overview">
              <div className="card">
                <div className="passport-section-label">Task Passport</div>
                <div className="passport-details">
                  <div className="detail-row"><strong>Task ID</strong> {task.task_id}</div>
                  <div className="detail-row"><strong>Created by</strong> {task.identity}</div>
                  <div className="detail-row"><strong>Created at</strong> {new Date(task.created_at).toLocaleString()}</div>
                  <div className="detail-row"><strong>Purpose</strong> {task.purpose}</div>
                  <div className="detail-row"><strong>Sensitivity</strong> {task.sensitivity}</div>
                  <div className="detail-row"><strong>Security Mode</strong> <span className={`security-mode-badge ${task.security_mode}`}>{task.security_mode}</span></div>
                  <div className="detail-row"><strong>Network Policy</strong> {task.network_policy}</div>
                  <div className="detail-row"><strong>Allowed Tools</strong> {task.allowed_tools.join(", ") || "none"}</div>
                  <div className="detail-row"><strong>Allowed Models</strong> {task.allowed_models.join(", ") || "none"}</div>
                  <div className="detail-row"><strong>Status</strong> {task.status}</div>
                </div>
              </div>

              <div className="card">
                <div className="passport-section-label">Task Summary</div>
                <p className="text-muted">{task.purpose || "No purpose defined."}</p>
              </div>

              <div className="card">
                <div className="passport-section-label">Quick Actions</div>
                <div className="quick-actions">
                  <button className="btn-primary" onClick={() => navigate("/chat")}>Open AI Chat</button>
                  <button className="btn-secondary" onClick={handleExportReport}>Export Report</button>
                  <button className="btn-secondary" onClick={handleExportJSON}>Export JSON</button>
                </div>
              </div>
            </div>
          )}

          {activeTab === "AI Analysis" && (
            <div className="card">
              <div className="passport-section-label">AI Analysis</div>
              <p className="text-muted">AI analysis will appear here as conversations are conducted for this task.</p>
              <p className="text-muted" style={{ marginTop: "0.5rem" }}>Open AI Chat to start analyzing this task.</p>
            </div>
          )}

          {activeTab === "Evidence" && (
            <div className="card">
              <div className="passport-section-label">Evidence</div>
              <p className="text-muted">Document evidence and sources will appear here when ingested for this task.</p>

              <div style={{ marginTop: "1rem", borderTop: "1px solid rgba(255,255,255,0.08)", paddingTop: "0.75rem" }}>
                <div className="passport-section-label">Local OCR</div>
                <p className="text-muted" style={{ fontSize: "0.85rem" }}>
                  Upload a scanned image or PDF. OCR runs locally (no cloud) and can ingest text into RAG.
                </p>
                <input
                  type="file"
                  ref={ocrInputRef}
                  accept=".png,.jpg,.jpeg,.pdf"
                  style={{ display: "none" }}
                  onChange={(e) => {
                    const f = e.target.files?.[0];
                    if (f) {
                      setOcrFile(f);
                      setOcrResult(null);
                    }
                  }}
                  data-testid="ocr-file-input"
                />
                <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", alignItems: "center" }}>
                  <button className="btn-secondary" onClick={() => ocrInputRef.current?.click()}>
                    {ocrFile ? ocrFile.name : "Choose scan…"}
                  </button>
                  <button
                    className="btn-primary"
                    onClick={handleRunOcr}
                    disabled={!canRunOcr || ocrRunning}
                    data-testid="run-local-ocr"
                  >
                    {ocrRunning ? "Running local OCR…" : "OCR"}
                  </button>
                </div>

                {ocrResult && (
                  <div
                    data-testid="ocr-result"
                    style={{
                      marginTop: "0.75rem",
                      padding: "0.75rem",
                      borderRadius: "6px",
                      border: `1px solid ${ocrResult.status === "completed" ? "#10b981" : "#ef4444"}`,
                      background: ocrResult.status === "completed" ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
                    }}
                  >
                    <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", fontSize: "0.85rem", marginBottom: "0.5rem" }}>
                      <span><strong>File:</strong> {ocrResult.source_name}</span>
                      <span><strong>Status:</strong> {ocrResult.status === "completed" ? "● Completed" : "● Failed"}</span>
                      {ocrResult.engine && <span><strong>Engine:</strong> {ocrResult.engine}</span>}
                      {typeof ocrResult.char_count === "number" && (
                        <span><strong>Chars:</strong> {ocrResult.char_count}</span>
                      )}
                      {ocrResult.ingested && (
                        <span><strong>Ingested:</strong> {ocrResult.chunks_created} chunk(s)</span>
                      )}
                    </div>
                    {ocrResult.error && (
                      <div style={{ color: "#ef4444", fontSize: "0.85rem", marginBottom: "0.4rem" }}>
                        {ocrResult.error}
                      </div>
                    )}
                    {ocrResult.text && (
                      <div>
                        <div style={{ fontSize: "0.8rem", opacity: 0.75, marginBottom: "0.25rem" }}>Extracted text:</div>
                        <pre
                          style={{
                            margin: 0,
                            whiteSpace: "pre-wrap",
                            fontFamily: "monospace",
                            fontSize: "0.8rem",
                            maxHeight: "220px",
                            overflow: "auto",
                          }}
                        >
                          {ocrResult.text}
                        </pre>
                      </div>
                    )}
                  </div>
                )}
              </div>
            </div>
          )}

          {activeTab === "Conversation" && (
            <div className="card">
              <div className="passport-section-label">Conversations</div>
              {conversations.length > 0 ? (
                <div className="conversation-list">
                  {conversations.map((c) => (
                    <div key={c.id} className="conversation-item">
                      <span className="conversation-title">{c.title}</span>
                      <span className="conversation-meta">{new Date(c.updated_at || c.created_at).toLocaleString()}</span>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted">No conversations yet for this task.</p>
              )}
              <button className="btn-primary" style={{ marginTop: "0.75rem" }} onClick={() => navigate("/chat")}>Open AI Chat</button>
            </div>
          )}

          {activeTab === "Execution" && (
            <div className="card">
              <div className="passport-section-label">Execution History</div>
              {canRunCode && (
                <div style={{ marginBottom: "0.75rem" }}>
                  <button
                    className="btn-primary"
                    onClick={handleRunCode}
                    disabled={codeRunning}
                    data-testid="run-code-sandbox"
                  >
                    {codeRunning ? "Running in sandbox…" : "Run code (sandbox)"}
                  </button>
                  {codeRun && (
                    <div
                      data-testid="code-sandbox-result"
                      style={{
                        marginTop: "0.5rem",
                        padding: "0.6rem",
                        borderRadius: "6px",
                        border: `1px solid ${codeRun.status === "completed" ? "#10b981" : "#ef4444"}`,
                        background: codeRun.status === "completed" ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
                      }}
                    >
                      <div style={{ display: "flex", gap: "0.75rem", flexWrap: "wrap", fontSize: "0.85rem", marginBottom: "0.4rem" }}>
                        <span><strong>Code Execution</strong></span>
                        <span>Sandbox: {codeRun.sandbox === "active" ? "ACTIVE" : "—"}</span>
                        <span>Network: {codeRun.network === "blocked" ? "BLOCKED" : "—"}</span>
                        <span>Status: {codeRun.status === "completed" ? "SUCCESS" : codeRun.status.toUpperCase()}</span>
                      </div>
                      {codeRun.error && (
                        <div style={{ color: "#ef4444", fontSize: "0.85rem", marginBottom: "0.35rem" }}>{codeRun.error}</div>
                      )}
                      <div style={{ fontSize: "0.8rem", opacity: 0.75, marginBottom: "0.25rem" }}>Output:</div>
                      <pre
                        style={{
                          margin: 0,
                          whiteSpace: "pre-wrap",
                          fontFamily: "monospace",
                          fontSize: "0.85rem",
                        }}
                      >
                        {codeRun.output || ""}
                      </pre>
                    </div>
                  )}
                </div>
              )}
              {canRunDataAnalyzer && (
                <div style={{ marginBottom: "0.75rem" }}>
                  <button
                    className="btn-primary"
                    onClick={handleRunDataAnalyzer}
                    disabled={toolRunning}
                    data-testid="run-data-analyzer"
                  >
                    {toolRunning ? "Running data_analyzer…" : "Run data_analyzer"}
                  </button>
                  {toolRun && (
                    <div
                      data-testid="tool-execution-result"
                      style={{
                        marginTop: "0.5rem",
                        padding: "0.6rem",
                        borderRadius: "6px",
                        border: `1px solid ${toolRun.success ? "#10b981" : "#ef4444"}`,
                        background: toolRun.success ? "rgba(16,185,129,0.08)" : "rgba(239,68,68,0.08)",
                        fontFamily: "monospace",
                        fontSize: "0.8rem",
                        whiteSpace: "pre-wrap",
                      }}
                    >
                      {toolRun.output}
                    </div>
                  )}
                </div>
              )}
              {auditEvents.filter((e) => e.event_type.includes("plan") || e.event_type.includes("sandbox") || e.event_type.includes("execution")).length > 0 ? (
                <div className="timeline">
                  {auditEvents
                    .filter((e) => e.event_type.includes("plan") || e.event_type.includes("sandbox") || e.event_type.includes("execution"))
                    .map((evt) => (
                      <div key={evt.event_id} className="timeline-item">
                        <div className="timeline-dot" style={{ background: STATUS_COLORS[evt.new_status] || "#666" }} />
                        <div className="timeline-content">
                          <div className="timeline-header">
                            <span className="timeline-event">{formatEventType(evt.event_type)}</span>
                            <span className="timeline-time">{new Date(evt.timestamp).toLocaleTimeString()}</span>
                          </div>
                          {evt.detail && <div className="timeline-detail">{evt.detail}</div>}
                        </div>
                      </div>
                    ))}
                </div>
              ) : (
                <p className="text-muted">No execution history recorded yet.</p>
              )}
            </div>
          )}

          {activeTab === "Report" && (
            <div className="card">
              <div className="passport-section-label">Report</div>
              <div className="report-actions">
                <button
                  className="btn-primary"
                  onClick={handleDownloadDocx}
                  disabled={docxRunning}
                  data-testid="download-docx-report"
                >
                  {docxRunning ? "Generating DOCX…" : "Download DOCX Report"}
                </button>
                <button className="btn-secondary" onClick={handleExportReport}>Export Report</button>
                <button className="btn-secondary" onClick={handleExportJSON}>Export JSON</button>
              </div>
              <div className="report-preview">
                <div className="report-section">
                  <h4>MEDHA TASK REPORT</h4>
                  <p className="text-muted">Generated: {new Date().toLocaleString()}</p>
                </div>
                <div className="report-section">
                  <h4>Task Information</h4>
                  <div className="detail-row"><strong>Task ID</strong> {task.task_id}</div>
                  <div className="detail-row"><strong>User</strong> {task.identity}</div>
                  <div className="detail-row"><strong>Purpose</strong> {task.purpose}</div>
                  <div className="detail-row"><strong>Sensitivity</strong> {task.sensitivity}</div>
                  <div className="detail-row"><strong>Security Mode</strong> <span className={`security-mode-badge ${task.security_mode}`}>{task.security_mode}</span></div>
                  <div className="detail-row"><strong>Status</strong> {task.status}</div>
                </div>
                <div className="report-section">
                  <h4>Audit Summary</h4>
                  <p className="text-muted">{auditEvents.length} events recorded</p>
                </div>
              </div>
            </div>
          )}
        </div>

        <div className="card" style={{ marginTop: "1rem" }}>
          <div className="passport-section-label">Actions</div>
          <div className="action-buttons">
            {task.status === "draft" && task.approval_requirement !== "none" && (
              <button onClick={() => handleTransition("pending_approval")} className="btn-primary">
                Submit for Human Verification
              </button>
            )}
            {task.status === "draft" && task.approval_requirement === "none" && (
              <button onClick={() => handleTransition("authorized")} className="btn-success">Authorize</button>
            )}
            {task.status === "draft" && <button onClick={() => handleTransition("denied")} className="btn-danger">Deny</button>}
            {task.status === "pending_approval" && (
              <span className="text-muted">
                Awaiting manager/admin verification — actions are disabled until approved or rejected.
              </span>
            )}
            {task.status === "authorized" && <button onClick={() => handleTransition("executing")} className="btn-primary">Start Execution</button>}
            {task.status === "authorized" && <button onClick={() => handleTransition("denied")} className="btn-danger">Deny</button>}
            {task.status === "executing" && <button onClick={() => handleTransition("completed")} className="btn-success">Complete</button>}
            {task.status === "executing" && <button onClick={() => handleTransition("failed")} className="btn-danger">Fail</button>}
            {task.status === "failed" && <button onClick={() => handleTransition("authorized")} className="btn-primary">Re-authorize</button>}
            {task.status === "rejected" && (
              <span className="text-muted">Blocked — rejected by supervisor. Contact your manager/admin.</span>
            )}
            {task.status === "pending_verification" && (
              <span className="text-muted">Completion verification pending — manager/admin action required.</span>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
