import { useState, useEffect, useMemo, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { getIdentity, listTasks, createTask, deleteTask, getSecurityStatus, clearToken } from "../api";
import { useSecurity } from "../contexts/SecurityContext";
import { getGreeting, isTaskPinned, toggleTaskPin } from "../utils/helpers";
import TopNav from "../components/TopNav";
import TaskCard from "../components/TaskCard";
import LiveSecurityPipeline from "../components/LiveSecurityPipeline";
import EnvironmentStatus from "../components/EnvironmentStatus";
import Toast from "../components/Toast";
import Modal from "../components/Modal";

const PENDING_QUERY_KEY = "medha_pending_query";

export default function Dashboard() {
  const [user, setUser] = useState(null);
  const [newTask, setNewTask] = useState({ title: "", purpose: "", sensitivity: "internal", security_mode: "standard" });
  const [tasks, setTasks] = useState([]);
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [toast, setToast] = useState(null);
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [creating, setCreating] = useState(false);
  const { securityMode, switchMode } = useSecurity();
  const [securityPanel, setSecurityPanel] = useState(null);
  const [showSecurityPanel, setShowSecurityPanel] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    getIdentity().then((u) => {
      setUser(u);
      listTasks(securityMode).then((t) => setTasks(Array.isArray(t) ? t : [])).catch(() => {});
      const pending = localStorage.getItem(PENDING_QUERY_KEY);
      if (pending) {
        localStorage.removeItem(PENDING_QUERY_KEY);
        setNewTask((prev) => ({ ...prev, title: pending, purpose: pending }));
        setShowCreate(true);
      }
    }).catch(() => { clearToken(); navigate("/"); });
  }, [navigate, securityMode]);

  const handleCreate = async (e) => {
    e.preventDefault();
    if (creating) return;
    setCreating(true);
    try {
      const task = await createTask(newTask);
      setTasks((prev) => [task, ...prev]);
      setNewTask({ title: "", purpose: "", sensitivity: "internal" });
      setShowCreate(false);
      setToast({ type: "success", message: "Task created" });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
    setCreating(false);
  };

  const handleDelete = async (taskId) => {
    try {
      await deleteTask(taskId);
      setTasks((prev) => prev.filter((t) => t.task_id !== taskId));
      setDeleteConfirm(null);
      setToast({ type: "success", message: "Task deleted" });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
  };

  const handlePin = (taskId) => {
    toggleTaskPin(taskId);
    setTasks((prev) => [...prev]);
  };

  const handleSensitivityChange = useCallback((sensitivity) => {
    // Auto-enforce security mode based on sensitivity
    const requirements = { internal: "standard", confidential: "secure", restricted: "sovereign" };
    const requiredMode = requirements[sensitivity] || "standard";
    setNewTask((prev) => ({ ...prev, sensitivity, security_mode: requiredMode }));
    // Also switch global mode if sensitivity requires it
    if (requiredMode !== securityMode) {
      switchMode(requiredMode);
    }
  }, [securityMode, switchMode]);

  const handleToggleSecurityPanel = useCallback(async (forceClose) => {
    if (forceClose === false) {
      setShowSecurityPanel(false);
      return;
    }
    if (!showSecurityPanel && tasks.length > 0) {
      // Fetch status for the first task
      try {
        const status = await getSecurityStatus(tasks[0].task_id);
        setSecurityPanel(status);
      } catch {
        setSecurityPanel({ task_title: "No task selected", sensitivity: "—" });
      }
    }
    setShowSecurityPanel((prev) => !prev);
  }, [showSecurityPanel, tasks]);

  const handleUserUpdate = (updated) => setUser(updated);
  const handleLogout = () => { clearToken(); navigate("/"); };

  const filteredTasks = useMemo(() => {
    if (!search) return tasks;
    const q = search.toLowerCase();
    return tasks.filter((t) => t.title?.toLowerCase().includes(q) || t.purpose?.toLowerCase().includes(q));
  }, [tasks, search]);

  const pinnedTasks = useMemo(() => filteredTasks.filter((t) => isTaskPinned(t.task_id)), [filteredTasks]);
  const unpinnedTasks = useMemo(() => filteredTasks.filter((t) => !isTaskPinned(t.task_id)), [filteredTasks]);

  return (
    <div className="app-layout">
      <div className="brush-bg" />
      <TopNav
        user={user}
        onLogout={handleLogout}
        securityMode={securityMode}
        onSwitchMode={switchMode}
        securityPanel={showSecurityPanel ? securityPanel : null}
        onToggleSecurityPanel={handleToggleSecurityPanel}
        onUserUpdate={handleUserUpdate}
      />
      <main className="main-content">
        <Toast toast={toast} onClear={() => setToast(null)} />

        <div className="dash-header">
          <div className="dash-greeting">{getGreeting()}, {user?.username || "user"}</div>
          <div className="dash-subtitle">Create, manage and monitor your AI tasks in a secure environment.</div>
        </div>

        <div className="dash-actions">
          <input
            className="dash-search"
            placeholder="Search tasks..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
          <button className="btn-new-task" onClick={() => setShowCreate(!showCreate)}>+ New Task</button>
        </div>

        {showCreate && (
          <div className="card">
            <h3>Create Task Passport</h3>
            <form onSubmit={handleCreate} className="task-form">
              <div className="form-group">
                <label>Title</label>
                <input placeholder="Task title" value={newTask.title} onChange={(e) => setNewTask({ ...newTask, title: e.target.value })} required />
              </div>
              <div className="form-group">
                <label>Purpose</label>
                <input placeholder="Purpose" value={newTask.purpose} onChange={(e) => setNewTask({ ...newTask, purpose: e.target.value })} required />
              </div>
              <div className="form-group">
                <label>Sensitivity</label>
                <select value={newTask.sensitivity} onChange={(e) => handleSensitivityChange(e.target.value)}>
                  <option value="internal">Internal</option>
                  <option value="confidential">Confidential</option>
                  <option value="restricted">Restricted</option>
                </select>
              </div>
              <div className="form-group">
                <label>Security Mode</label>
                <select
                  value={newTask.security_mode}
                  onChange={(e) => handleSecurityModeChange(e.target.value)}
                >
                  <option value="standard">Standard</option>
                  <option value="secure">Secure</option>
                  <option value="sovereign">Sovereign</option>
                </select>
                {newTask.security_mode === "sovereign" && (
                  <div className="form-hint sovereign">
                    Sovereign Lock: Reduced external attack surface.
                    Local-first security policy.
                  </div>
                )}
                {newTask.sensitivity === "confidential" && newTask.security_mode === "standard" && (
                  <div className="form-hint warning">
                    Sensitive data detected. Stronger security policy is recommended.
                  </div>
                )}
                {newTask.sensitivity === "restricted" && newTask.security_mode !== "sovereign" && (
                  <div className="form-hint enforced">
                    Sovereign Lock is required by the task security policy.
                  </div>
                )}
              </div>
              <button type="submit" disabled={creating}>{creating ? "Creating..." : "Create"}</button>
            </form>
          </div>
        )}

        <div className="dash-security-section">
          <LiveSecurityPipeline tasks={tasks} />
          <EnvironmentStatus />
        </div>

        {pinnedTasks.length > 0 && (
          <>
            <div className="section-header">
              <h2>Pinned Tasks</h2>
              <span className="section-meta">{pinnedTasks.length} pinned</span>
            </div>
            <div className="task-grid">
              {pinnedTasks.map((t) => (
                <TaskCard key={t.task_id} task={t} onDelete={setDeleteConfirm} onPin={handlePin} isPinned={true} />
              ))}
            </div>
          </>
        )}

        <div className="section-header">
          <h2>Recent Tasks</h2>
          <span className="section-meta">{unpinnedTasks.length} task{unpinnedTasks.length !== 1 ? "s" : ""}</span>
        </div>

        {unpinnedTasks.length > 0 ? (
          <div className="task-grid">
            {unpinnedTasks.map((t) => (
              <TaskCard key={t.task_id} task={t} onDelete={setDeleteConfirm} onPin={handlePin} isPinned={false} />
            ))}
          </div>
        ) : (
          <div className="card">
            <p className="text-muted">{search ? "No tasks match your search." : "No tasks yet. Create your first task passport."}</p>
          </div>
        )}

        {deleteConfirm && (
          <Modal
            title="Delete Task"
            onClose={() => setDeleteConfirm(null)}
            actions={
              <>
                <button className="btn-secondary" onClick={() => setDeleteConfirm(null)}>Cancel</button>
                <button className="btn-danger" onClick={() => handleDelete(deleteConfirm.task_id)}>Delete</button>
              </>
            }
          >
            <p>Are you sure you want to delete <strong>{deleteConfirm.title}</strong>?</p>
            <p className="text-muted">Audit records will be preserved.</p>
          </Modal>
        )}
      </main>
    </div>
  );
}
