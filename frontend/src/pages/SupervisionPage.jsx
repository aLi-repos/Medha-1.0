import { useState, useEffect, useCallback } from "react";
import { useNavigate, Navigate } from "react-router-dom";
import {
  getIdentity,
  clearToken,
  getSupervisedTasks,
  getSupervisedTaskDetail,
  approveSupervisedTask,
  rejectSupervisedTask,
  verifySupervisedCompletion,
  rejectSupervisedCompletion,
} from "../api";
import { STATUS_COLORS, formatEventType } from "../utils/helpers";
import TopNav from "../components/TopNav";
import Toast from "../components/Toast";
import Modal from "../components/Modal";
import { useSecurity } from "../contexts/SecurityContext";

const ROLE_LABELS = {
  operator: "Operator",
  junior_engineer: "Junior Engineer",
  monitor: "Monitor",
};

const VERIFICATION_LABELS = {
  not_required: "Not required",
  not_submitted: "Not submitted",
  waiting_verification: "Waiting for Human Verification",
  approved: "Approved",
  rejected: "Rejected",
  waiting_completion_verification: "Waiting for Completion Verification",
  verified: "Verified",
  unknown: "—",
};

const STATUS_FILTERS = [
  { key: "all", label: "All" },
  { key: "pending_approval", label: "Waiting Verification" },
  { key: "authorized", label: "Approved" },
  { key: "executing", label: "Executing" },
  { key: "pending_verification", label: "Completion Verification" },
  { key: "verified", label: "Verified" },
  { key: "rejected", label: "Rejected" },
];

export default function SupervisionPage() {
  const { securityMode } = useSecurity();
  const navigate = useNavigate();
  const [user, setUser] = useState(null);
  const [access, setAccess] = useState("loading");
  const [tasks, setTasks] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState("all");
  const [workerRole, setWorkerRole] = useState("all");
  const [detail, setDetail] = useState(null);
  const [toast, setToast] = useState(null);
  const [rejectTarget, setRejectTarget] = useState(null); // {taskId, kind}
  const [rejectReason, setRejectReason] = useState("");
  const [acting, setActing] = useState(false);

  const loadList = useCallback(() => {
    setLoading(true);
    getSupervisedTasks()
      .then((res) => setTasks(res.tasks || []))
      .catch((err) => setToast({ type: "error", message: err.message }))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    getIdentity()
      .then((u) => {
        setUser(u);
        if (u.role === "manager" || u.role === "admin") {
          setAccess("ok");
          loadList();
        } else {
          setAccess("deny");
        }
      })
      .catch(() => {
        clearToken();
        navigate("/");
      });
  }, [navigate, loadList]);

  const openDetail = async (taskId) => {
    try {
      const d = await getSupervisedTaskDetail(taskId);
      setDetail(d);
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
  };

  const refreshAfterAction = async (taskId) => {
    await openDetail(taskId);
    loadList();
  };

  const handleApprove = async (taskId) => {
    setActing(true);
    try {
      const res = await approveSupervisedTask(taskId);
      setToast({ type: "success", message: `Task approved — status: ${res.status}` });
      await refreshAfterAction(taskId);
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
    setActing(false);
  };

  const handleVerifyCompletion = async (taskId) => {
    setActing(true);
    try {
      const res = await verifySupervisedCompletion(taskId);
      setToast({ type: "success", message: `Completion verified — status: ${res.status}` });
      await refreshAfterAction(taskId);
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
    setActing(false);
  };

  const submitRejection = async () => {
    if (!rejectTarget) return;
    if (!rejectReason.trim()) {
      setToast({ type: "error", message: "A rejection reason is required" });
      return;
    }
    setActing(true);
    try {
      if (rejectTarget.kind === "completion") {
        const res = await rejectSupervisedCompletion(rejectTarget.taskId, rejectReason.trim());
        setToast({ type: "success", message: `Completion rejected — status: ${res.status}` });
      } else {
        const res = await rejectSupervisedTask(rejectTarget.taskId, rejectReason.trim());
        setToast({ type: "success", message: `Task rejected — status: ${res.status}` });
      }
      setRejectTarget(null);
      setRejectReason("");
      await refreshAfterAction(rejectTarget.taskId);
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
    setActing(false);
  };

  const handleLogout = () => {
    clearToken();
    navigate("/");
  };
  const handleUserUpdate = (updated) => setUser(updated);

  if (access === "deny") return <Navigate to="/dashboard" replace />;

  const visibleTasks = tasks.filter((t) => {
    if (workerRole !== "all" && t.role !== workerRole) return false;
    if (filter === "all") return true;
    return t.status === filter;
  });

  const dt = detail?.task;

  return (
    <div className="app-layout">
      <div className="brush-bg" />
      <TopNav
        user={user}
        onLogout={handleLogout}
        securityMode={securityMode}
        onUserUpdate={handleUserUpdate}
      />
      <main className="main-content">
        <Toast toast={toast} onClear={() => setToast(null)} />

        <div className="tasks-header">
          <div>
            <h1>Supervision &amp; Verification</h1>
            <p className="text-muted" style={{ margin: "0.25rem 0 0" }}>
              Inspect authorized worker activity, approve tasks before execution, and verify
              completions. Every action is recorded in the audit trail.
            </p>
          </div>
        </div>

        <div className="filter-tabs">
          {STATUS_FILTERS.map((tab) => (
            <button
              key={tab.key}
              className={`filter-tab ${filter === tab.key ? "active" : ""}`}
              onClick={() => setFilter(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="section-header" style={{ display: "flex", alignItems: "center", gap: "1rem" }}>
          <span className="section-meta">
            {visibleTasks.length} task{visibleTasks.length !== 1 ? "s" : ""}
          </span>
          <select
            className="dash-search"
            style={{ maxWidth: "220px" }}
            value={workerRole}
            onChange={(e) => setWorkerRole(e.target.value)}
          >
            <option value="all">All worker roles</option>
            <option value="operator">Operator</option>
            <option value="junior_engineer">Junior Engineer</option>
            <option value="monitor">Monitor</option>
          </select>
        </div>

        {detail ? (
          <div className="audit-layout">
            <div className="card audit-sidebar">
              <div className="card-header-row">
                <h3>Supervised Tasks</h3>
                <button className="btn-secondary" onClick={() => setDetail(null)}>
                  ← Back
                </button>
              </div>
              <div className="task-list">
                {visibleTasks.map((t) => (
                  <button
                    key={t.task_id}
                    className={`task-item ${dt?.task_id === t.task_id ? "active" : ""}`}
                    onClick={() => openDetail(t.task_id)}
                  >
                    <div className="task-item-info">
                      <span className="task-item-title">{t.title}</span>
                      <span className="task-item-meta">
                        <span className="status-badge small" style={{ background: STATUS_COLORS[t.status] || "#666" }}>
                          {t.status}
                        </span>
                        <span className="event-count">{t.username} · {t.user_id}</span>
                      </span>
                    </div>
                  </button>
                ))}
              </div>
            </div>

            <div className="card audit-main">
              {dt ? (
                <>
                  <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", gap: "1rem" }}>
                    <div>
                      <h3>{dt.title}</h3>
                      <div className="task-header-meta" style={{ marginTop: "0.4rem" }}>
                        <span className="status-badge" style={{ background: STATUS_COLORS[dt.status] || "#666" }}>
                          {dt.status}
                        </span>
                        <span className="sensitivity-tag">{dt.sensitivity}</span>
                        <span className={`security-mode-badge ${dt.security_mode}`}>{dt.security_mode}</span>
                      </div>
                    </div>
                    <div style={{ textAlign: "right" }}>
                      {dt.status === "pending_approval" && (
                        <div className="action-buttons" style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                          <button
                            className="btn-success"
                            disabled={acting}
                            onClick={() => handleApprove(dt.task_id)}
                          >
                            Approve
                          </button>
                          <button
                            className="btn-danger"
                            disabled={acting}
                            onClick={() => {
                              setRejectTarget({ taskId: dt.task_id, kind: "pre_execution" });
                              setRejectReason("");
                            }}
                          >
                            Reject
                          </button>
                        </div>
                      )}
                      {dt.status === "pending_verification" && (
                        <div className="action-buttons" style={{ display: "flex", gap: "0.5rem", justifyContent: "flex-end" }}>
                          <button
                            className="btn-success"
                            disabled={acting}
                            onClick={() => handleVerifyCompletion(dt.task_id)}
                          >
                            Verify Completion
                          </button>
                          <button
                            className="btn-danger"
                            disabled={acting}
                            onClick={() => {
                              setRejectTarget({ taskId: dt.task_id, kind: "completion" });
                              setRejectReason("");
                            }}
                          >
                            Reject / Request Review
                          </button>
                        </div>
                      )}
                    </div>
                  </div>

                  <div className="passport-section-label" style={{ marginTop: "1rem" }}>
                    Worker &amp; Task
                  </div>
                  <div className="passport-details">
                    <div className="detail-row"><strong>Worker</strong> {dt.username}</div>
                    <div className="detail-row"><strong>User ID</strong> {dt.user_id}</div>
                    <div className="detail-row"><strong>Role</strong> {ROLE_LABELS[dt.role] || dt.role}</div>
                    <div className="detail-row"><strong>Task ID</strong> {dt.task_id}</div>
                    <div className="detail-row"><strong>Purpose</strong> {dt.purpose}</div>
                    <div className="detail-row"><strong>Requested action</strong> {dt.requested_operation || "—"}</div>
                    <div className="detail-row"><strong>Security mode</strong> {dt.security_mode}</div>
                    <div className="detail-row"><strong>Network policy</strong> {dt.network_policy}</div>
                    <div className="detail-row"><strong>Tools requested</strong> {dt.allowed_tools?.join(", ") || "none"}</div>
                    <div className="detail-row"><strong>Sources</strong> {dt.allowed_sources?.join(", ") || "none"}</div>
                    <div className="detail-row"><strong>Models</strong> {dt.allowed_models?.join(", ") || "none"}</div>
                    <div className="detail-row"><strong>Approval requirement</strong> {dt.approval_requirement}</div>
                    <div className="detail-row"><strong>Created</strong> {new Date(dt.created_at).toLocaleString()}</div>
                    <div className="detail-row"><strong>Execution status</strong> {dt.execution_status}</div>
                    <div className="detail-row">
                      <strong>Verification status</strong>{" "}
                      {VERIFICATION_LABELS[dt.verification_status] || dt.verification_status}
                    </div>
                  </div>

                  <div className="passport-section-label" style={{ marginTop: "1rem" }}>
                    AI / Execution Plan
                  </div>
                  {detail.plan ? (
                    <div className="timeline" style={{ marginTop: "0.5rem" }}>
                      {detail.plan.steps.map((s) => (
                        <div key={s.step_id} className="timeline-item">
                          <div className="timeline-dot" style={{ background: "#3b82f6" }} />
                          <div className="timeline-content">
                            <div className="timeline-header">
                              <span className="timeline-event">
                                Step {s.order + 1}: {s.tool_name}
                              </span>
                              <span className="timeline-time">{s.status} · risk {s.risk}</span>
                            </div>
                            <div className="timeline-detail">{s.action}</div>
                          </div>
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted">
                      No agent plan yet — review the requested operation and tools above.
                    </p>
                  )}

                  <div className="passport-section-label" style={{ marginTop: "1rem" }}>
                    Verification Decisions
                  </div>
                  {detail.verifications.length > 0 ? (
                    <div className="passport-details">
                      {detail.verifications.map((v, i) => (
                        <div className="detail-row" key={i}>
                          <strong>
                            {v.kind === "pre_execution" ? "Pre-execution" : "Completion"} · {v.decision}
                          </strong>{" "}
                          by {v.actor_username} ({v.actor_role}) at {new Date(v.created_at).toLocaleString()}
                          {v.reason ? ` — ${v.reason}` : ""}
                        </div>
                      ))}
                    </div>
                  ) : (
                    <p className="text-muted">No verification decisions recorded yet.</p>
                  )}

                  <div className="passport-section-label" style={{ marginTop: "1rem" }}>
                    Execution Trace &amp; Audit ({detail.audit_events.length} events)
                  </div>
                  <div className="timeline" style={{ marginTop: "0.5rem" }}>
                    {detail.audit_events.map((e) => (
                      <div key={e.event_id} className="timeline-item">
                        <div className="timeline-dot" style={{ background: STATUS_COLORS[e.new_status] || "#666" }} />
                        <div className="timeline-content">
                          <div className="timeline-header">
                            <span className="timeline-event">{formatEventType(e.event_type)}</span>
                            <span className="timeline-time">{new Date(e.timestamp).toLocaleString()}</span>
                          </div>
                          <div className="timeline-actor">{e.identity} ({e.role || "system"})</div>
                          {e.previous_status && e.new_status && (
                            <div className="timeline-transition">{e.previous_status} → {e.new_status}</div>
                          )}
                          {e.detail && <div className="timeline-detail">{e.detail}</div>}
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              ) : (
                <p className="text-muted">Loading task…</p>
              )}
            </div>
          </div>
        ) : (
          <>
            {loading ? (
              <div className="card">
                <p className="text-muted">Loading supervised activity…</p>
              </div>
            ) : visibleTasks.length === 0 ? (
              <div className="card">
                <p className="text-muted">No supervised worker tasks found.</p>
              </div>
            ) : (
              <div className="card" style={{ overflowX: "auto" }}>
                <table className="supervision-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "0.9rem" }}>
                  <thead>
                    <tr style={{ textAlign: "left", borderBottom: "1px solid rgba(255,255,255,0.08)" }}>
                      <th style={{ padding: "0.6rem" }}>Worker</th>
                      <th style={{ padding: "0.6rem" }}>User ID</th>
                      <th style={{ padding: "0.6rem" }}>Role</th>
                      <th style={{ padding: "0.6rem" }}>Task</th>
                      <th style={{ padding: "0.6rem" }}>Status</th>
                      <th style={{ padding: "0.6rem" }}>Security</th>
                      <th style={{ padding: "0.6rem" }}>Execution</th>
                      <th style={{ padding: "0.6rem" }}>Verification</th>
                      <th style={{ padding: "0.6rem" }}>Created</th>
                      <th style={{ padding: "0.6rem" }}>Latest Audit</th>
                      <th style={{ padding: "0.6rem" }}></th>
                    </tr>
                  </thead>
                  <tbody>
                    {visibleTasks.map((t) => (
                      <tr key={t.task_id} style={{ borderBottom: "1px solid rgba(255,255,255,0.05)" }}>
                        <td style={{ padding: "0.6rem" }}>{t.username}</td>
                        <td style={{ padding: "0.6rem", fontFamily: "monospace" }}>{t.user_id}</td>
                        <td style={{ padding: "0.6rem" }}>{ROLE_LABELS[t.role] || t.role}</td>
                        <td style={{ padding: "0.6rem" }}>
                          <div>{t.title}</div>
                          <div className="text-muted" style={{ fontSize: "0.75rem", fontFamily: "monospace" }}>
                            {t.task_id.slice(0, 8)}…
                          </div>
                        </td>
                        <td style={{ padding: "0.6rem" }}>
                          <span className="status-badge small" style={{ background: STATUS_COLORS[t.status] || "#666" }}>
                            {t.status}
                          </span>
                        </td>
                        <td style={{ padding: "0.6rem" }}>{t.security_mode}</td>
                        <td style={{ padding: "0.6rem" }}>{t.execution_status}</td>
                        <td style={{ padding: "0.6rem" }}>
                          {VERIFICATION_LABELS[t.verification_status] || t.verification_status}
                        </td>
                        <td style={{ padding: "0.6rem" }}>{new Date(t.created_at).toLocaleString()}</td>
                        <td style={{ padding: "0.6rem" }} className="text-muted">
                          {t.latest_event_type ? formatEventType(t.latest_event_type) : "—"}
                          {t.total_audit_events > 0 && ` (${t.total_audit_events})`}
                        </td>
                        <td style={{ padding: "0.6rem" }}>
                          <button className="btn-secondary" onClick={() => openDetail(t.task_id)}>
                            Inspect
                          </button>
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
          </>
        )}

        {rejectTarget && (
          <Modal
            title={rejectTarget.kind === "completion" ? "Reject Completion" : "Reject Task"}
            onClose={() => setRejectTarget(null)}
            actions={
              <>
                <button className="btn-secondary" onClick={() => setRejectTarget(null)} disabled={acting}>
                  Cancel
                </button>
                <button className="btn-danger" onClick={submitRejection} disabled={acting || !rejectReason.trim()}>
                  {acting ? "Submitting…" : "Reject"}
                </button>
              </>
            }
          >
            <p>
              A reason is required. The worker will see that{" "}
              {rejectTarget.kind === "completion"
                ? "completion verification was rejected"
                : "human approval was rejected"}{" "}
              and the reason you provide.
            </p>
            <textarea
              className="account-edit-input"
              style={{ width: "100%", minHeight: "90px", marginTop: "0.5rem" }}
              placeholder="Rejection reason (required)"
              value={rejectReason}
              onChange={(e) => setRejectReason(e.target.value)}
              maxLength={1000}
            />
          </Modal>
        )}
      </main>
    </div>
  );
}
