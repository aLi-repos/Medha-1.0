import { useState, useEffect, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import { getIdentity, listTasks, createTask, deleteTask, clearToken } from "../api";
import { isTaskPinned, toggleTaskPin } from "../utils/helpers";
import TopNav from "../components/TopNav";
import { useSecurity } from "../contexts/SecurityContext";
import TaskCard from "../components/TaskCard";
import Toast from "../components/Toast";
import Modal from "../components/Modal";

const FILTER_TABS = [
  { key: "all", label: "All" },
  { key: "pinned", label: "Pinned" },
  { key: "draft", label: "Draft" },
  { key: "authorized", label: "Authorized" },
  { key: "executing", label: "Executing" },
  { key: "completed", label: "Completed" },
  { key: "failed", label: "Failed" },
  { key: "denied", label: "Denied" },
];

export default function TasksPage() {
  const { securityMode } = useSecurity();
  const [user, setUser] = useState(null);
  const [tasks, setTasks] = useState([]);
  const [filter, setFilter] = useState("all");
  const [search, setSearch] = useState("");
  const [showCreate, setShowCreate] = useState(false);
  const [newTask, setNewTask] = useState({ title: "", purpose: "", sensitivity: "internal" });
  const [deleteConfirm, setDeleteConfirm] = useState(null);
  const [toast, setToast] = useState(null);
  const [creating, setCreating] = useState(false);
  const navigate = useNavigate();

  useEffect(() => {
    getIdentity().then((u) => {
      setUser(u);
      listTasks().then((t) => setTasks(Array.isArray(t) ? t : [])).catch(() => {});
    }).catch(() => { clearToken(); navigate("/"); });
  }, [navigate]);

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

  const handleLogout = () => { clearToken(); navigate("/"); };
  const handleUserUpdate = (updated) => setUser(updated);

  const filteredTasks = useMemo(() => {
    let result = tasks;
    if (search) {
      const q = search.toLowerCase();
      result = result.filter((t) => t.title?.toLowerCase().includes(q) || t.purpose?.toLowerCase().includes(q));
    }
    if (filter === "pinned") {
      result = result.filter((t) => isTaskPinned(t.task_id));
    } else if (filter !== "all") {
      result = result.filter((t) => t.status === filter);
    }
    return result;
  }, [tasks, search, filter]);

  return (
    <div className="app-layout">
      <div className="brush-bg" />
      <TopNav user={user} onLogout={handleLogout} securityMode={securityMode} onUserUpdate={handleUserUpdate} />
      <main className="main-content">
        <Toast toast={toast} onClear={() => setToast(null)} />

        <div className="tasks-header">
          <h1>Tasks</h1>
          <div className="tasks-actions">
            <input
              className="dash-search"
              placeholder="Search tasks..."
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
            <button className="btn-new-task" onClick={() => setShowCreate(!showCreate)}>+ New Task</button>
          </div>
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
                <select value={newTask.sensitivity} onChange={(e) => setNewTask({ ...newTask, sensitivity: e.target.value })}>
                  <option value="internal">Internal</option>
                  <option value="confidential">Confidential</option>
                  <option value="restricted">Restricted</option>
                </select>
              </div>
              <button type="submit" disabled={creating}>{creating ? "Creating..." : "Create"}</button>
            </form>
          </div>
        )}

        <div className="filter-tabs">
          {FILTER_TABS.map((tab) => (
            <button
              key={tab.key}
              className={`filter-tab ${filter === tab.key ? "active" : ""}`}
              onClick={() => setFilter(tab.key)}
            >
              {tab.label}
            </button>
          ))}
        </div>

        <div className="section-header">
          <span className="section-meta">{filteredTasks.length} task{filteredTasks.length !== 1 ? "s" : ""}</span>
        </div>

        {filteredTasks.length > 0 ? (
          <div className="task-grid">
            {filteredTasks.map((t) => (
              <TaskCard key={t.task_id} task={t} onDelete={setDeleteConfirm} onPin={handlePin} isPinned={isTaskPinned(t.task_id)} />
            ))}
          </div>
        ) : (
          <div className="card">
            <p className="text-muted">{search || filter !== "all" ? "No tasks match your filters." : "No tasks yet. Create your first task passport."}</p>
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
