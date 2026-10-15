import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import { STATUS_COLORS, timeAgo } from "../utils/helpers";
import Modal from "./Modal";

export default function TaskCard({ task, onDelete, onPin, isPinned }) {
  const navigate = useNavigate();
  const [menuOpen, setMenuOpen] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const menuRef = useRef(null);

  useEffect(() => {
    if (!menuOpen) return;
    const handleClickOutside = (e) => {
      if (menuRef.current && !menuRef.current.contains(e.target)) setMenuOpen(false);
    };
    const handleEsc = (e) => { if (e.key === "Escape") setMenuOpen(false); };
    document.addEventListener("mousedown", handleClickOutside);
    document.addEventListener("keydown", handleEsc);
    return () => {
      document.removeEventListener("mousedown", handleClickOutside);
      document.removeEventListener("keydown", handleEsc);
    };
  }, [menuOpen]);

  const handlePin = () => {
    onPin(task.task_id);
    setMenuOpen(false);
  };

  const handleDeleteClick = () => {
    setMenuOpen(false);
    setDeleteConfirm(true);
  };

  const handleConfirmDelete = () => {
    setDeleteConfirm(false);
    onDelete(task);
  };

  return (
    <div className={`task-card ${isPinned ? "pinned" : ""}`}>
      <div className="task-card-header">
        <h4>{task.title}</h4>
        <div className="task-card-header-right">
          <span className="status-badge small" style={{ background: STATUS_COLORS[task.status] || "#666" }}>{task.status}</span>
          <div className="card-menu-wrapper" ref={menuRef}>
            <button
              className="card-menu-btn"
              onClick={() => setMenuOpen(!menuOpen)}
              title="Actions"
              aria-label="Task actions"
              aria-expanded={menuOpen}
            >
              &#8943;
            </button>
            {menuOpen && (
              <div className="card-menu" role="menu">
                <button className="card-menu-item" role="menuitem" onClick={handlePin}>
                  <span className="card-menu-icon">{isPinned ? "📌" : "📌"}</span>
                  {isPinned ? "Unpin" : "Pin"}
                </button>
                <button className="card-menu-item danger" role="menuitem" onClick={handleDeleteClick}>
                  <span className="card-menu-icon">🗑</span>
                  Delete
                </button>
              </div>
            )}
          </div>
        </div>
      </div>
      {task.purpose && <div className="task-card-purpose">{task.purpose}</div>}
      <div className="task-card-meta">
        <span className="sensitivity-tag">{task.sensitivity}</span>
        {task.updated_at && <span>{timeAgo(task.updated_at)}</span>}
      </div>
      <div className="task-card-actions">
        <button className="btn-open" onClick={() => navigate(`/task/${task.task_id}`)}>Open</button>
      </div>

      {deleteConfirm && (
        <Modal
          title="Delete Task"
          onClose={() => setDeleteConfirm(false)}
          actions={
            <>
              <button className="btn-secondary" onClick={() => setDeleteConfirm(false)}>Cancel</button>
              <button className="btn-danger" onClick={handleConfirmDelete}>Delete</button>
            </>
          }
        >
          <p>Delete this task?</p>
          <p className="text-muted">This action cannot be undone.</p>
        </Modal>
      )}
    </div>
  );
}
