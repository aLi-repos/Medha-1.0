export const STATUS_COLORS = {
  draft: "#f59e0b",
  pending_approval: "#f59e0b",
  authorized: "#3b82f6",
  executing: "#3b82f6",
  completed: "#22c55e",
  pending_verification: "#a855f7",
  verified: "#10b981",
  rejected: "#ef4444",
  failed: "#ef4444",
  denied: "#ef4444",
};

export function formatEventType(eventType) {
  const map = {
    passport_created: "Task Created",
    passport_status_transition: "Status Transition",
    passport_security_fields_updated: "Security Fields Updated",
    passport_deleted: "Task Deleted",
    model_inference: "Model Inference",
    model_input_blocked: "Model Input Blocked",
    rag_search: "RAG Search",
    chat_conversation_created: "Conversation Created",
    chat_message_sent: "Message Sent",
    file_attached: "File Attached",
    image_attached: "Image Attached",
    model_blocked: "Model Blocked",
    plan_created: "Plan Created",
    plan_step_added: "Step Added",
    plan_step_approved: "Step Approved",
    plan_step_executing: "Step Executing",
    plan_step_completed: "Step Completed",
    plan_step_failed: "Step Failed",
    plan_completed: "Plan Completed",
    sandbox_execution_started: "Execution Started",
    sandbox_execution_completed: "Execution Completed",
    sandbox_execution_rolled_back: "Execution Rolled Back",
    output_verified: "Output Verified",
    MANAGER_VIEW_TASK: "Manager Viewed Task",
    MANAGER_VIEW_TRACE: "Manager Viewed Trace",
    ADMIN_VIEW_TASK: "Admin Viewed Task",
    ADMIN_VIEW_TRACE: "Admin Viewed Trace",
    MANAGER_APPROVE_TASK: "Manager Approved Task",
    ADMIN_APPROVE_TASK: "Admin Approved Task",
    MANAGER_REJECT_TASK: "Manager Rejected Task",
    ADMIN_REJECT_TASK: "Admin Rejected Task",
    MANAGER_VERIFY_COMPLETION: "Manager Verified Completion",
    ADMIN_VERIFY_COMPLETION: "Admin Verified Completion",
    MANAGER_REJECT_COMPLETION: "Manager Rejected Completion",
    ADMIN_REJECT_COMPLETION: "Admin Rejected Completion",
    MANAGER_SUPERVISION_LIST_VIEW: "Manager Opened Supervision",
    ADMIN_SUPERVISION_LIST_VIEW: "Admin Opened Supervision",
  };
  return map[eventType] || eventType.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function getGreeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

export function timeAgo(dateStr) {
  if (!dateStr) return "";
  const d = new Date(dateStr);
  const now = new Date();
  const diff = Math.floor((now - d) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return d.toLocaleDateString();
}

export function groupConversationsByDate(conversations) {
  const now = new Date();
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);
  const lastWeek = new Date(today);
  lastWeek.setDate(lastWeek.getDate() - 7);

  const groups = { Today: [], Yesterday: [], "Last 7 days": [], Older: [] };
  conversations.forEach((c) => {
    const d = new Date(c.updated_at || c.created_at);
    if (d >= today) groups.Today.push(c);
    else if (d >= yesterday) groups.Yesterday.push(c);
    else if (d >= lastWeek) groups["Last 7 days"].push(c);
    else groups.Older.push(c);
  });
  return groups;
}

export function getPinnedTasks() {
  try {
    return JSON.parse(localStorage.getItem("medha_pinned_tasks") || "[]");
  } catch {
    return [];
  }
}

export function setPinnedTasks(pinned) {
  localStorage.setItem("medha_pinned_tasks", JSON.stringify(pinned));
}

export function isTaskPinned(taskId) {
  return getPinnedTasks().includes(taskId);
}

export function toggleTaskPin(taskId) {
  const pinned = getPinnedTasks();
  if (pinned.includes(taskId)) {
    const next = pinned.filter((id) => id !== taskId);
    setPinnedTasks(next);
    return false;
  } else {
    pinned.push(taskId);
    setPinnedTasks(pinned);
    return true;
  }
}
