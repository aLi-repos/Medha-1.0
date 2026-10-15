import { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { getIdentity, getAuditTrail, getTasksWithAuditSummary, clearToken } from "../api";
import { STATUS_COLORS, formatEventType } from "../utils/helpers";
import TopNav from "../components/TopNav";
import { useSecurity } from "../contexts/SecurityContext";

const MODE_LABELS = {
  standard: { icon: "◯", label: "STANDARD AUDIT", desc: "Only Standard Mode operations are displayed." },
  secure: { icon: "🔐", label: "SECURE AUDIT", desc: "Only Secure Mode operations are displayed." },
  sovereign: { icon: "🛡", label: "SOVEREIGN AUDIT", desc: "Only Sovereign Mode operations are displayed." },
};

export default function AuditPage() {
  const { securityMode } = useSecurity();
  const [user, setUser] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [selectedTask, setSelectedTask] = useState(null);
  const [auditTrail, setAuditTrail] = useState(null);
  const [loading, setLoading] = useState(true);
  const navigate = useNavigate();

  const handleSelectTask = async (taskId) => {
    setSelectedTask(taskId);
    try {
      const trail = await getAuditTrail(taskId);
      setAuditTrail(trail);
    } catch {
      setAuditTrail(null);
    }
  };

  useEffect(() => {
    getIdentity().then((u) => {
      setUser(u);
      setLoading(true);
      getTasksWithAuditSummary(securityMode).then((res) => {
        const taskList = res.tasks || [];
        setTasks(taskList);
        setSelectedTask(null);
        setAuditTrail(null);
      }).catch(() => setTasks([])).finally(() => setLoading(false));
    }).catch(() => { clearToken(); navigate("/"); });
  }, [navigate, securityMode]);

  const handleLogout = () => { clearToken(); navigate("/"); };
  const handleUserUpdate = (updated) => setUser(updated);

  return (
    <div className="app-layout">
      <div className="brush-bg" />
      <TopNav user={user} onLogout={handleLogout} securityMode={securityMode} onUserUpdate={handleUserUpdate} />
      <main className="main-content">
        <div className="audit-header">
          <h1>
            <span className="audit-mode-icon">{MODE_LABELS[securityMode]?.icon}</span>
            {MODE_LABELS[securityMode]?.label}
          </h1>
          <p className="audit-mode-desc">{MODE_LABELS[securityMode]?.desc}</p>
        </div>
        <div className="audit-layout">
          <div className="card audit-sidebar">
            <div className="card-header-row">
              <h3>My Tasks</h3>
              <span className="section-meta">{tasks.length} task{tasks.length !== 1 ? "s" : ""}</span>
            </div>
            <div className="task-list">
              {tasks.length === 0 && !loading && <p className="text-muted">No tasks found.</p>}
              {tasks.map((t) => (
                <button
                  key={t.task_id}
                  className={`task-item ${selectedTask === t.task_id ? "active" : ""}`}
                  onClick={() => handleSelectTask(t.task_id)}
                >
                  <div className="task-item-info">
                    <span className="task-item-title">{t.title}</span>
                    <span className="task-item-meta">
                      <span className="status-badge small" style={{ background: STATUS_COLORS[t.status] || "#666" }}>{t.status}</span>
                      {t.total_events > 0 && <span className="event-count">{t.total_events} events</span>}
                    </span>
                  </div>
                  {t.latest_event_timestamp && (
                    <div className="task-item-latest">
                      Last: {formatEventType(t.latest_event_type)} at {new Date(t.latest_event_timestamp).toLocaleTimeString()}
                    </div>
                  )}
                </button>
              ))}
            </div>
          </div>

          <div className="card audit-main">
            {auditTrail ? (
              <>
                <h3>{tasks.find((t) => t.task_id === selectedTask)?.title || selectedTask}</h3>
                <p className="text-muted" style={{ marginBottom: "1rem" }}>{auditTrail.total_events} events recorded</p>
                <div className="timeline">
                  {auditTrail.events.map((e) => (
                    <div key={e.event_id} className="timeline-item">
                      <div className="timeline-dot" style={{ background: STATUS_COLORS[e.new_status] || "#666" }} />
                      <div className="timeline-content">
                        <div className="timeline-header">
                          <span className="timeline-event">{formatEventType(e.event_type)}</span>
                          <span className="timeline-time">{new Date(e.timestamp).toLocaleTimeString()}</span>
                        </div>
                        <div className="timeline-actor">{e.identity} ({e.role || "system"})</div>
                        {e.previous_status && e.new_status && (
                          <div className="timeline-transition">{e.previous_status} &rarr; {e.new_status}</div>
                        )}
                        {e.detail && <div className="timeline-detail">{e.detail}</div>}
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <p className="text-muted">{loading ? "Loading..." : "Select a task to view its audit trail."}</p>
            )}
          </div>
        </div>
      </main>
    </div>
  );
}
