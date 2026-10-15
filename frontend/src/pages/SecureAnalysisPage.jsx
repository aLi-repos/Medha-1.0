import { useState, useEffect, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import {
  getIdentity, listTasks, clearToken,
  runSecureAnalysis, approveHandover, downloadExcelReport,
} from "../api";
import TopNav from "../components/TopNav";
import { useSecurity } from "../contexts/SecurityContext";
import Toast from "../components/Toast";

const STAGE_ICONS = {
  authentication: "🔑",
  rbac_check: "🛡️",
  task_passport: "📋",
  action_gate: "🚧",
  permission_rag: "📚",
  model_routing: "🧠",
  agent_planning: "🤖",
  tool_validation: "🔧",
  controlled_execution: "⚡",
  output_verification: "✅",
  secure_handover: "🤝",
  audit_trail: "📝",
};

const STAGE_COLORS = {
  completed: "#10b981",
  approved: "#10b981",
  denied: "#ef4444",
  blocked: "#ef4444",
  pending: "#6b7280",
  in_progress: "#3b82f6",
};

export default function SecureAnalysisPage() {
  const { securityMode } = useSecurity();
  const [user, setUser] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("overview");
  const [handoverDecision, setHandoverDecision] = useState(null);
  const [handoverReason, setHandoverReason] = useState("");
  const [showHandoverForm, setShowHandoverForm] = useState(false);
  const [downloading, setDownloading] = useState(false);
  const [toast, setToast] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    getIdentity()
      .then((u) => {
        setUser(u);
        listTasks()
          .then((t) => {
            const list = Array.isArray(t) ? t : [];
            setTasks(list);
            if (list.length > 0) setSelectedTask(list[0].task_id);
          })
          .catch(() => {});
      })
      .catch(() => {
        clearToken();
        navigate("/");
      });
  }, [navigate]);

  const handleRunAnalysis = useCallback(async () => {
    if (!selectedTask) return;
    setLoading(true);
    setAnalysis(null);
    setHandoverDecision(null);
    try {
      const result = await runSecureAnalysis(selectedTask);
      setAnalysis(result);
      setToast({ type: "success", message: "Analysis pipeline completed — 11 stages verified" });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
    setLoading(false);
  }, [selectedTask]);

  const handleHandover = useCallback(async (approved) => {
    if (!analysis) return;
    setLoading(true);
    try {
      const result = await approveHandover(analysis.task_id, approved, handoverReason);
      setHandoverDecision(result);
      setShowHandoverForm(false);
      setToast({
        type: approved ? "success" : "warning",
        message: approved ? "Handover approved — results released" : "Handover rejected — results retained",
      });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
    setLoading(false);
  }, [analysis, handoverReason]);

  const handleDownloadExcel = useCallback(async () => {
    if (!analysis) return;
    setDownloading(true);
    try {
      await downloadExcelReport(analysis.task_id);
      setToast({ type: "success", message: "Excel report downloaded — MEDHA_P204_Maintenance_Analysis.xlsx" });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
    setDownloading(false);
  }, [analysis]);

  const handleLogout = () => { clearToken(); navigate("/"); };
  const handleUserUpdate = (updated) => setUser(updated);

  const tabs = [
    { id: "overview", label: "Overview" },
    { id: "failures", label: "Failure Data" },
    { id: "sensors", label: "Sensor Analysis" },
    { id: "risk", label: "Risk Assessment" },
    { id: "recommendations", label: "Recommendations" },
    { id: "trace", label: "Security Trace" },
    { id: "handover", label: "Handover" },
    { id: "about", label: "About MEDHA" },
  ];

  return (
    <div className="app-layout">
      <div className="brush-bg" />
      <TopNav user={user} onLogout={handleLogout} securityMode={securityMode} onUserUpdate={handleUserUpdate} />
      <main className="main-content secure-analysis-page">
        <Toast toast={toast} onClear={() => setToast(null)} />

        <div className="sa-header">
          <div className="sa-header-left">
            <h1>Secure Industrial Analysis</h1>
            <p className="sa-subtitle">
              Full security pipeline demonstration — Pump P-204 Maintenance Failure Analysis
            </p>
          </div>
          <div className="sa-header-right">
            <select
              className="sa-task-select"
              value={selectedTask || ""}
              onChange={(e) => setSelectedTask(e.target.value)}
            >
              {tasks.map((t) => (
                <option key={t.task_id} value={t.task_id}>
                  {t.title || t.task_id}
                </option>
              ))}
            </select>
            <button
              className="sa-run-btn"
              onClick={handleRunAnalysis}
              disabled={loading || !selectedTask}
            >
              {loading ? "Running Pipeline..." : "Run Secure Analysis"}
            </button>
            {analysis && (
              <button
                className="sa-download-btn"
                onClick={handleDownloadExcel}
                disabled={downloading}
              >
                {downloading ? "Generating..." : "Download Excel"}
              </button>
            )}
          </div>
        </div>

        <div className="sa-disclaimer">
          <strong>Synthetic demonstration data.</strong>{" "}
          Illustrative industrial scenario inspired by publicly documented refinery
          and enterprise security requirements. This demonstration does not represent
          MRPL's internal architecture.
        </div>

        {!analysis && !loading && (
          <div className="sa-empty">
            <div className="sa-empty-icon">🔒</div>
            <h3>Secure Analysis Pipeline</h3>
            <p>Select a task and run the analysis to demonstrate the full MEDHA security pipeline.</p>
            <div className="sa-pipeline-preview">
              {["Authentication", "RBAC", "Task Passport", "Action Gate", "Permission-Aware RAG",
                "Model Routing", "Agent Planning", "Tool Validation", "Controlled Execution",
                "Output Verification", "Secure Handover", "Audit Trail"].map((stage, i) => (
                <div key={stage} className="sa-pipeline-stage-preview">
                  <span className="sa-stage-num">{i + 1}</span>
                  <span className="sa-stage-name">{stage}</span>
                </div>
              ))}
            </div>
          </div>
        )}

        {loading && (
          <div className="sa-loading">
            <div className="sa-loading-spinner" />
            <p>Executing secure analysis pipeline...</p>
                    <p className="sa-loading-detail">Verifying all 11 security stages + handover</p>
          </div>
        )}

        {analysis && (
          <>
            <div className="sa-tabs">
              {tabs.map((tab) => (
                <button
                  key={tab.id}
                  className={`sa-tab ${activeTab === tab.id ? "active" : ""}`}
                  onClick={() => setActiveTab(tab.id)}
                >
                  {tab.label}
                </button>
              ))}
            </div>

            <div className="sa-tab-content">
              {activeTab === "overview" && (
                <div className="sa-overview">
                  <div className="sa-equipment-card">
                    <h3>Equipment Information</h3>
                    <div className="sa-equipment-grid">
                      <div className="sa-equip-field">
                        <span className="sa-equip-label">Equipment ID</span>
                        <span className="sa-equip-value">{analysis.equipment_info.id}</span>
                      </div>
                      <div className="sa-equip-field">
                        <span className="sa-equip-label">Name</span>
                        <span className="sa-equip-value">{analysis.equipment_info.name}</span>
                      </div>
                      <div className="sa-equip-field">
                        <span className="sa-equip-label">Location</span>
                        <span className="sa-equip-value">{analysis.equipment_info.location}</span>
                      </div>
                      <div className="sa-equip-field">
                        <span className="sa-equip-label">Manufacturer</span>
                        <span className="sa-equip-value">{analysis.equipment_info.manufacturer}</span>
                      </div>
                      <div className="sa-equip-field">
                        <span className="sa-equip-label">Model</span>
                        <span className="sa-equip-value">{analysis.equipment_info.model}</span>
                      </div>
                      <div className="sa-equip-field">
                        <span className="sa-equip-label">Installation Date</span>
                        <span className="sa-equip-value">{analysis.equipment_info.installation_date}</span>
                      </div>
                      <div className="sa-equip-field">
                        <span className="sa-equip-label">Rated Flow</span>
                        <span className="sa-equip-value">{analysis.equipment_info.rated_flow_m3h} m³/h</span>
                      </div>
                      <div className="sa-equip-field">
                        <span className="sa-equip-label">Motor Power</span>
                        <span className="sa-equip-value">{analysis.equipment_info.motor_power_kw} kW</span>
                      </div>
                    </div>
                  </div>

                  <div className="sa-summary-cards">
                    <div className="sa-card sa-card-critical">
                      <div className="sa-card-number">{analysis.failure_summary.total_failures}</div>
                      <div className="sa-card-label">Total Failures</div>
                      <div className="sa-card-detail">{analysis.failure_summary.critical} critical</div>
                    </div>
                    <div className="sa-card sa-card-warning">
                      <div className="sa-card-number">{analysis.failure_summary.total_downtime_hours}h</div>
                      <div className="sa-card-label">Total Downtime</div>
                      <div className="sa-card-detail">24-month period</div>
                    </div>
                    <div className="sa-card sa-card-danger">
                      <div className="sa-card-number">
                        ${analysis.failure_summary.total_cost_usd.toLocaleString()}
                      </div>
                      <div className="sa-card-label">Total Cost Impact</div>
                      <div className="sa-card-detail">Failure + maintenance</div>
                    </div>
                    <div className="sa-card sa-card-info">
                      <div className="sa-card-number">{analysis.failure_summary.mtbf_hours}h</div>
                      <div className="sa-card-label">MTBF</div>
                      <div className="sa-card-detail">Mean Time Between Failures</div>
                    </div>
                  </div>

                  <div className="sa-risk-badge">
                    <span
                      className="sa-risk-level"
                      data-level={analysis.risk_assessment.risk_level}
                    >
                      Risk Level: {analysis.risk_assessment.risk_level.toUpperCase()}
                    </span>
                    <span className="sa-risk-score">
                      Score: {analysis.risk_assessment.risk_score}/100
                    </span>
                  </div>
                </div>
              )}

              {activeTab === "failures" && (
                <div className="sa-failures">
                  <h3>Failure Records (24 months)</h3>
                  <div className="sa-freq-chart">
                    <h4>Failure Frequency by Component</h4>
                    <div className="sa-bar-chart">
                      {Object.entries(analysis.graph_data.failure_frequency.labels || {}).length > 0
                        ? analysis.graph_data.failure_frequency.labels.map((label, i) => {
                            const maxVal = Math.max(...analysis.graph_data.failure_frequency.values);
                            const pct = (analysis.graph_data.failure_frequency.values[i] / maxVal) * 100;
                            return (
                              <div key={label} className="sa-bar-row">
                                <span className="sa-bar-label">{label}</span>
                                <div className="sa-bar-track">
                                  <div
                                    className="sa-bar-fill"
                                    style={{ width: `${pct}%` }}
                                  />
                                </div>
                                <span className="sa-bar-value">
                                  {analysis.graph_data.failure_frequency.values[i]}
                                </span>
                              </div>
                            );
                          })
                        : <p>No failure data available</p>
                      }
                    </div>
                  </div>
                  <div className="sa-table-wrap">
                    <table className="sa-table">
                      <thead>
                        <tr>
                          <th>Timestamp</th>
                          <th>Failure Type</th>
                          <th>Severity</th>
                          <th>Component</th>
                          <th>Downtime (h)</th>
                          <th>Cost (USD)</th>
                          <th>Root Cause</th>
                          <th>Resolved</th>
                        </tr>
                      </thead>
                      <tbody>
                        {(analysis.failure_summary.failures || []).slice(0, 30).map((f, i) => (
                          <tr key={i}>
                            <td>{new Date(f.timestamp).toLocaleDateString()}</td>
                            <td>{f.failure_type}</td>
                            <td>
                              <span className={`sa-severity sa-sev-${f.severity}`}>
                                {f.severity}
                              </span>
                            </td>
                            <td>{f.component}</td>
                            <td>{f.downtime_hours}</td>
                            <td>${f.cost_usd.toLocaleString()}</td>
                            <td>{f.root_cause}</td>
                            <td>{f.resolved ? "✓" : "✗"}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {activeTab === "sensors" && (
                <div className="sa-sensors">
                  <h3>Sensor Analysis</h3>
                  <div className="sa-sensor-cards">
                    <div className="sa-sensor-card">
                      <div className="sa-sensor-icon">📳</div>
                      <div className="sa-sensor-label">Vibration</div>
                      <div className="sa-sensor-value">{analysis.sensor_summary.vibration_avg} mm/s</div>
                      <div className="sa-sensor-unit">avg over {analysis.sensor_summary.readings_count} readings</div>
                    </div>
                    <div className="sa-sensor-card">
                      <div className="sa-sensor-icon">🌡️</div>
                      <div className="sa-sensor-label">Temperature</div>
                      <div className="sa-sensor-value">{analysis.sensor_summary.temperature_avg}°C</div>
                      <div className="sa-sensor-unit">avg</div>
                    </div>
                    <div className="sa-sensor-card">
                      <div className="sa-sensor-icon">🔵</div>
                      <div className="sa-sensor-label">Pressure</div>
                      <div className="sa-sensor-value">{analysis.sensor_summary.pressure_avg} bar</div>
                      <div className="sa-sensor-unit">avg</div>
                    </div>
                    <div className="sa-sensor-card">
                      <div className="sa-sensor-icon">💧</div>
                      <div className="sa-sensor-label">Flow Rate</div>
                      <div className="sa-sensor-value">{analysis.sensor_summary.flow_rate_avg} m³/h</div>
                      <div className="sa-sensor-unit">avg</div>
                    </div>
                    <div className="sa-sensor-card">
                      <div className="sa-sensor-icon">⚡</div>
                      <div className="sa-sensor-label">Current</div>
                      <div className="sa-sensor-value">{analysis.sensor_summary.current_avg} A</div>
                      <div className="sa-sensor-unit">avg</div>
                    </div>
                  </div>
                  <div className="sa-chart-section">
                    <h4>Monthly Downtime Trend</h4>
                    <div className="sa-line-chart">
                      {(analysis.graph_data.downtime_trend.labels || []).map((label, i) => {
                        const maxVal = Math.max(...analysis.graph_data.downtime_trend.values);
                        const pct = maxVal > 0 ? (analysis.graph_data.downtime_trend.values[i] / maxVal) * 100 : 0;
                        return (
                          <div key={label} className="sa-chart-bar-col">
                            <div className="sa-chart-bar-value">{analysis.graph_data.downtime_trend.values[i].toFixed(1)}</div>
                            <div className="sa-chart-bar-vert" style={{ height: `${pct}%` }} />
                            <div className="sa-chart-bar-label">{label.slice(5)}</div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "risk" && (
                <div className="sa-risk">
                  <h3>Risk Assessment</h3>
                  <div className="sa-risk-main">
                    <div className="sa-risk-gauge">
                      <div
                        className="sa-risk-gauge-fill"
                        style={{
                          background: `conic-gradient(${STAGE_COLORS[analysis.risk_assessment.risk_level === "critical" ? "denied" : analysis.risk_assessment.risk_level === "high" ? "blocked" : "completed"]} ${analysis.risk_assessment.risk_score * 3.6}deg, #1a2332 0deg)`,
                        }}
                      />
                      <div className="sa-risk-gauge-center">
                        <span className="sa-risk-gauge-number">{analysis.risk_assessment.risk_score}</span>
                        <span className="sa-risk-gauge-label">/ 100</span>
                      </div>
                    </div>
                    <div className="sa-risk-details">
                      <div className="sa-risk-row">
                        <span>Risk Level</span>
                        <span
                          className="sa-risk-level-badge"
                          data-level={analysis.risk_assessment.risk_level}
                        >
                          {analysis.risk_assessment.risk_level.toUpperCase()}
                        </span>
                      </div>
                      <div className="sa-risk-row">
                        <span>Critical Failures</span>
                        <span>{analysis.risk_assessment.critical_failures_count}</span>
                      </div>
                      <div className="sa-risk-row">
                        <span>High Failures</span>
                        <span>{analysis.risk_assessment.high_failures_count}</span>
                      </div>
                      <div className="sa-risk-row">
                        <span>MTBF Trend</span>
                        <span>{analysis.risk_assessment.mtbf_trend}</span>
                      </div>
                      <div className="sa-risk-row">
                        <span>Priority</span>
                        <span>{analysis.risk_assessment.recommendation_priority}</span>
                      </div>
                    </div>
                  </div>
                </div>
              )}

              {activeTab === "recommendations" && (
                <div className="sa-recommendations">
                  <h3>Recommendations</h3>
                  <div className="sa-rec-list">
                    {(analysis.recommendations || []).map((rec) => (
                      <div key={rec.id} className={`sa-rec-card sa-rec-${rec.priority}`}>
                        <div className="sa-rec-header">
                          <span className="sa-rec-id">{rec.id}</span>
                          <span className={`sa-rec-priority sa-pri-${rec.priority}`}>
                            {rec.priority}
                          </span>
                        </div>
                        <div className="sa-rec-action">{rec.action}</div>
                        <div className="sa-rec-rationale">{rec.rationale}</div>
                        <div className="sa-rec-meta">
                          <span>Est. Cost: ${rec.estimated_cost_usd.toLocaleString()}</span>
                          <span>Downtime: {rec.estimated_downtime_hours}h</span>
                          <span>Tools: {rec.tools_required.join(", ")}</span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {activeTab === "trace" && (
                <div className="sa-trace">
                  <h3>Security Pipeline Trace</h3>
                  <p className="sa-trace-desc">
                    Full pipeline execution trace — every security stage with timestamp, status, and detail.
                  </p>
                  <div className="sa-trace-timeline">
                    {(analysis.pipeline_events || []).map((event, i) => (
                      <div
                        key={i}
                        className={`sa-trace-event sa-trace-${event.status}`}
                      >
                        <div className="sa-trace-icon">
                          {STAGE_ICONS[event.stage] || "•"}
                        </div>
                        <div className="sa-trace-content">
                          <div className="sa-trace-header">
                            <span className="sa-trace-stage">{event.stage.replace(/_/g, " ")}</span>
                            <span
                              className="sa-trace-status"
                              style={{ color: STAGE_COLORS[event.status] || "#6b7280" }}
                            >
                              {event.status.toUpperCase()}
                            </span>
                          </div>
                          <div className="sa-trace-detail">{event.detail}</div>
                          <div className="sa-trace-meta">
                            <span>{event.timestamp}</span>
                            <span>Actor: {event.actor}</span>
                            {event.latency_ms > 0 && <span>{event.latency_ms}ms</span>}
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {activeTab === "handover" && (
                <div className="sa-handover">
                  <h3>Secure Handover</h3>
                  <p className="sa-handover-desc">
                    Human-in-the-loop approval workflow. Analysis results require explicit
                    approval before release.
                  </p>

                  {handoverDecision ? (
                    <div className={`sa-handover-result sa-ho-${handoverDecision.handover_status}`}>
                      <div className="sa-handover-icon">
                        {handoverDecision.handover_status === "approved" ? "✅" : "❌"}
                      </div>
                      <div className="sa-handover-status">
                        {handoverDecision.handover_status.toUpperCase()}
                      </div>
                      <div className="sa-handover-meta">
                        <span>Decided by: {handoverDecision.decided_by}</span>
                        <span>At: {new Date(handoverDecision.decided_at).toLocaleString()}</span>
                        {handoverDecision.reason && <span>Reason: {handoverDecision.reason}</span>}
                      </div>
                    </div>
                  ) : showHandoverForm ? (
                    <div className="sa-handover-form">
                      <h4>Review Analysis Results</h4>
                      <div className="sa-handover-summary">
                        <div className="sa-ho-row">
                          <span>Equipment</span>
                          <span>{analysis.equipment_info.id} — {analysis.equipment_info.name}</span>
                        </div>
                        <div className="sa-ho-row">
                          <span>Failures Analyzed</span>
                          <span>{analysis.failure_summary.total_failures}</span>
                        </div>
                        <div className="sa-ho-row">
                          <span>Risk Level</span>
                          <span className={`sa-risk-level-badge`} data-level={analysis.risk_assessment.risk_level}>
                            {analysis.risk_assessment.risk_level.toUpperCase()}
                          </span>
                        </div>
                        <div className="sa-ho-row">
                          <span>Recommendations</span>
                          <span>{analysis.recommendations.length} items</span>
                        </div>
                        <div className="sa-ho-row">
                        <span>Pipeline Stages Verified</span>
                        <span>{analysis.pipeline_events.length}/11 + handover</span>
                        </div>
                      </div>
                      <textarea
                        className="sa-handover-reason"
                        placeholder="Reason for decision (optional)"
                        value={handoverReason}
                        onChange={(e) => setHandoverReason(e.target.value)}
                        rows={3}
                      />
                      <div className="sa-handover-actions">
                        <button
                          className="sa-handover-approve"
                          onClick={() => handleHandover(true)}
                          disabled={loading}
                        >
                          Approve &amp; Release
                        </button>
                        <button
                          className="sa-handover-reject"
                          onClick={() => handleHandover(false)}
                          disabled={loading}
                        >
                          Reject
                        </button>
                        <button
                          className="sa-handover-cancel"
                          onClick={() => setShowHandoverForm(false)}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  ) : (
                    <div className="sa-handover-pending">
                      <div className="sa-handover-icon">🤝</div>
                      <p>Analysis results are ready for review.</p>
                      <button
                        className="sa-handover-start"
                        onClick={() => setShowHandoverForm(true)}
                      >
                        Begin Handover Review
                      </button>
                    </div>
                  )}
                </div>
              )}

              {activeTab === "about" && (
                <div className="sa-about">
                  <h3>About MEDHA</h3>
                  <div className="sa-about-content">
                    <div className="sa-about-section">
                      <h4>MEDHA — Multimodal Enterprise Data Handling Assistant</h4>
                      <p>
                        A sovereign-controlled AI workbench designed for enterprise environments
                        requiring strict data governance, audit trails, and human-in-the-loop
                        oversight.
                      </p>
                    </div>
                    <div className="sa-about-section">
                      <h4>Security Architecture</h4>
                      <div className="sa-arch-diagram">
                        {["Auth Gateway", "RBAC Engine", "Task Passport", "Action Gate",
                          "Permission-Aware RAG", "Model Router", "Agent Orchestrator",
                          "Tool Registry", "Sandbox", "Output Verifier", "Secure Handover",
                          "Audit Trail"].map((component, i) => (
                          <div key={component} className="sa-arch-block">
                            <span className="sa-arch-num">{i + 1}</span>
                            <span className="sa-arch-name">{component}</span>
                          </div>
                        ))}
                      </div>
                    </div>
                    <div className="sa-about-section">
                      <h4>Demonstration Mode</h4>
                      <ul className="sa-about-list">
                        <li>Simulated model inference — no live LLM calls</li>
                        <li>Application-level sandbox — not Docker-based isolation</li>
                        <li>Simulated network policy enforcement</li>
                        <li>Synthetic industrial dataset — clearly labeled</li>
                      </ul>
                    </div>
                    <div className="sa-about-section">
                      <h4>Implementation Status</h4>
                      <div className="sa-status-grid">
                        <div className="sa-status-item implemented">
                          <span className="sa-status-dot" /> Task Passport — Implemented
                        </div>
                        <div className="sa-status-item implemented">
                          <span className="sa-status-dot" /> Action Gate (5 checks) — Implemented
                        </div>
                        <div className="sa-status-item implemented">
                          <span className="sa-status-dot" /> Permission-Aware RAG — Implemented
                        </div>
                        <div className="sa-status-item implemented">
                          <span className="sa-status-dot" /> Audit Trail — Implemented
                        </div>
                        <div className="sa-status-item partial">
                          <span className="sa-status-dot" /> Model Router — Partial (simulation)
                        </div>
                        <div className="sa-status-item partial">
                          <span className="sa-status-dot" /> Sandbox — Partial (application-level)
                        </div>
                        <div className="sa-status-item simulated">
                          <span className="sa-status-dot" /> Network Policy — Simulated
                        </div>
                        <div className="sa-status-item simulated">
                          <span className="sa-status-dot" /> Output Verifier — Simulated
                        </div>
                      </div>
                    </div>
                  </div>
                </div>
              )}
            </div>
          </>
        )}
      </main>
    </div>
  );
}
