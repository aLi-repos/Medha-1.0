const LOCAL_DEV_HOSTS = ["localhost", "127.0.0.1"];
const API_BASE = LOCAL_DEV_HOSTS.includes(window.location.hostname) ? "/api" : "http://127.0.0.1:8000/api";

function getToken() {
  return localStorage.getItem("medha_token");
}

function setToken(token) {
  localStorage.setItem("medha_token", token);
}

function clearToken() {
  localStorage.removeItem("medha_token");
}

function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" };
}

function authHeadersGet() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

async function apiPost(path, body) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "POST", headers: authHeaders(), body: JSON.stringify(body) });
  } catch (e) {
    throw new Error("Authentication service unavailable. Please ensure the backend is running.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

async function apiGet(path) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "GET", headers: authHeadersGet() });
  } catch (e) {
    throw new Error("Authentication service unavailable. Please ensure the backend is running.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

async function apiPatch(path, body) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, { method: "PATCH", headers: authHeaders(), body: JSON.stringify(body) });
  } catch (e) {
    throw new Error("Authentication service unavailable. Please ensure the backend is running.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

async function apiDelete(path) {
  const res = await fetch(`${API_BASE}${path}`, { method: "DELETE", headers: authHeadersGet() });
  if (!res.ok && res.status !== 204) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.status === 204 ? null : res.json();
}

export async function login(username, password, userId = null) {
  const body = { username, password };
  if (userId) body.user_id = userId;
  const data = await apiPost("/auth/login", body);
  setToken(data.access_token);
  return data;
}

export async function register(username, password, userId = null, role = "operator") {
  const body = { username, password, role };
  if (userId) body.user_id = userId;
  const data = await apiPost("/auth/register", body);
  setToken(data.access_token);
  return data;
}

export async function getIdentity() {
  return apiGet("/auth/me");
}

export async function createTask(payload) {
  return apiPost("/tasks", payload);
}

export async function getTask(taskId) {
  return apiGet(`/tasks/${taskId}`);
}

export async function listTasks(securityMode) {
  const params = securityMode && securityMode !== "standard" ? `?security_mode=${securityMode}` : "";
  return apiGet(`/tasks${params}`);
}

export async function transitionTask(taskId, newStatus, detail = "") {
  let res;
  try {
    res = await fetch(`${API_BASE}/tasks/${taskId}/status`, {
      method: "PATCH",
      headers: authHeaders(),
      body: JSON.stringify({ new_status: newStatus, detail }),
    });
  } catch (e) {
    throw new Error("Authentication service unavailable. Please ensure the backend is running.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Request failed");
  }
  return res.json();
}

export async function ingestDocument(text, sourceName, classification = "internal") {
  return apiPost("/knowledge/documents", { text, source_name: sourceName, classification });
}

export async function searchKnowledge(taskId, query, topK = 5) {
  return apiPost("/knowledge/search", { task_id: taskId, query, top_k: topK });
}

export async function listSources() {
  return apiGet("/knowledge/sources");
}

export async function runLocalOcr(taskId, file, ingest = true) {
  const t = getToken();
  const formData = new FormData();
  formData.append("task_id", taskId);
  formData.append("file", file);
  formData.append("ingest", ingest ? "true" : "false");
  let res;
  try {
    res = await fetch(`${API_BASE}/knowledge/ocr`, {
      method: "POST",
      headers: t ? { Authorization: `Bearer ${t}` } : {},
      body: formData,
    });
  } catch (e) {
    throw new Error("OCR service unavailable.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "OCR failed");
  }
  return res.json();
}

export async function infer(taskId, prompt, maxTokens = 512) {
  return apiPost("/models/infer", { task_id: taskId, prompt, max_tokens: maxTokens });
}

export async function listModels() {
  return apiGet("/models/available");
}

export async function getLocalLLMHealth() {
  // Public local runtime health — model availability only, no config internals.
  let res;
  try {
    res = await fetch(`${API_BASE}/health/local-llm`, { headers: authHeadersGet() });
  } catch (e) {
    return {
      runtime: "ollama-compatible",
      model: "",
      status: "UNAVAILABLE",
      reason: "local backend unreachable",
    };
  }
  if (!res.ok) {
    return {
      runtime: "ollama-compatible",
      model: "",
      status: "UNAVAILABLE",
      reason: "local health endpoint error",
    };
  }
  return res.json();
}

export async function getEnvironmentStatus() {
  // Live, truthful environment status — no secrets/config internals.
  try {
    const res = await fetch(`${API_BASE}/environment/status`, { headers: authHeadersGet() });
    if (!res.ok) throw new Error("status endpoint error");
    return await res.json();
  } catch {
    return {
      execution: "UNKNOWN",
      model: { name: "", status: "UNKNOWN", runtime: "ollama-compatible", reason: "backend unreachable" },
      network: { policy: "UNKNOWN", external_ai: "UNKNOWN" },
      rag: { execution: "UNKNOWN", status: "UNKNOWN" },
      ocr: { execution: "UNKNOWN", status: "UNKNOWN" },
      sandbox: { execution: "UNKNOWN", status: "UNKNOWN", network: "UNKNOWN" },
      security_mode: { available: [], scope: "" },
      error: true,
    };
  }
}

export async function createPlan(taskId, query) {
  return apiPost("/agent/plan", { task_id: taskId, query });
}

export async function listTools() {
  return apiGet("/agent/tools");
}

export async function executeStep(planId, stepId, inputData = {}) {
  return apiPost("/agent/plan/execute-step", { plan_id: planId, step_id: stepId, input_data: inputData });
}

export async function approveStep(planId, stepId) {
  return apiPost("/agent/plan/approve-step", { plan_id: planId, step_id: stepId });
}

export async function executeTool(taskId, toolName, action, inputData = {}, code = null) {
  const body = { task_id: taskId, tool_name: toolName, action, input_data: inputData };
  if (code != null) body.code = code;
  return apiPost("/sandbox/execute", body);
}

export async function rollbackExecution(taskId, executionId) {
  return apiPost("/sandbox/rollback", { task_id: taskId, execution_id: executionId });
}

export async function verifyOutput(taskId, outputText) {
  return apiPost("/verifier/verify", { task_id: taskId, output_text: outputText });
}

export async function getAuditTrail(taskId) {
  return apiGet(`/verifier/audit/${taskId}`);
}

export async function getTasksWithAuditSummary(securityMode) {
  const params = securityMode && securityMode !== "standard" ? `?security_mode=${securityMode}` : "";
  return apiGet(`/verifier/audit${params}`);
}

// --- Conversation API ---

export async function createConversation(taskId, title = "New Conversation") {
  // taskId null/undefined → General Chat (no Task Passport created).
  return apiPost("/chat/conversations", { task_id: taskId ?? null, title });
}

export async function listConversations(taskId) {
  // taskId null/"general" → General Chat conversations only.
  if (!taskId || taskId === "general") {
    return apiGet("/chat/conversations/general");
  }
  return apiGet(`/chat/conversations/${taskId}`);
}

export async function listAllConversations() {
  return apiGet("/chat/conversations-all");
}

export async function deleteConversation(conversationId) {
  return apiDelete(`/chat/conversations/${conversationId}`);
}

export async function deleteTask(taskId) {
  return apiDelete(`/tasks/${taskId}`);
}

export async function listMessages(conversationId) {
  return apiGet(`/chat/messages/${conversationId}`);
}

export async function sendChatMessage(taskId, prompt, model = null, conversationId = null, maxTokens = 512) {
  // taskId null/undefined → General Chat (task_id omitted/null in payload).
  return apiPost("/chat/send", {
    task_id: taskId ?? null,
    conversation_id: conversationId,
    prompt,
    model,
    max_tokens: maxTokens,
  });
}

export async function uploadFile(taskId, conversationId, file) {
  const t = getToken();
  const formData = new FormData();
  formData.append("file", file);
  formData.append("task_id", taskId);
  if (conversationId) formData.append("conversation_id", conversationId);

  let res;
  try {
    res = await fetch(`${API_BASE}/chat/upload`, {
      method: "POST",
      headers: t ? { Authorization: `Bearer ${t}` } : {},
      body: formData,
    });
  } catch (e) {
    throw new Error("Upload service unavailable.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Upload failed");
  }
  return res.json();
}

// --- Secure Analysis API ---

export async function runSecureAnalysis(taskId, allowedTools = null) {
  return apiPost("/analysis/run", {
    task_id: taskId,
    allowed_tools: allowedTools,
  });
}

export async function approveHandover(taskId, approved, reason = "") {
  return apiPost("/analysis/handover", {
    task_id: taskId,
    approved,
    reason,
  });
}

export async function getAnalysisDataset() {
  return apiGet("/analysis/dataset");
}

// --- Account API ---

export async function updateUsername(newUsername) {
  return apiPatch("/auth/username", { username: newUsername });
}

export async function updatePassword(currentPassword, newPassword) {
  return apiPatch("/auth/password", {
    current_password: currentPassword,
    new_password: newPassword,
  });
}

export async function getSecurityMode() {
  return apiGet("/auth/security-mode");
}

export async function setSecurityMode(mode) {
  return apiPatch("/auth/security-mode", { security_mode: mode });
}

// --- Task Security Mode API ---

export async function getSecurityStatus(taskId) {
  return apiGet(`/security-mode/status/${taskId}`);
}

export async function setTaskSecurityMode(taskId, mode) {
  return apiPost("/security-mode/set", { task_id: taskId, security_mode: mode });
}

export async function getSecurityPolicy(mode) {
  return apiGet(`/security-mode/policy/${mode}`);
}

// --- Supervision & Verification API (manager/admin only) ---

export async function getSupervisedTasks(statusFilter = null, workerRole = null) {
  const params = new URLSearchParams();
  if (statusFilter) params.set("status_filter", statusFilter);
  if (workerRole) params.set("worker_role", workerRole);
  const qs = params.toString();
  return apiGet(`/supervision/tasks${qs ? `?${qs}` : ""}`);
}

export async function getSupervisedTaskDetail(taskId) {
  return apiGet(`/supervision/tasks/${taskId}`);
}

export async function approveSupervisedTask(taskId) {
  return apiPost(`/supervision/tasks/${taskId}/approve`, {});
}

export async function rejectSupervisedTask(taskId, reason) {
  return apiPost(`/supervision/tasks/${taskId}/reject`, { reason });
}

export async function verifySupervisedCompletion(taskId) {
  return apiPost(`/supervision/tasks/${taskId}/verify-completion`, {});
}

export async function rejectSupervisedCompletion(taskId, reason) {
  return apiPost(`/supervision/tasks/${taskId}/reject-completion`, { reason });
}

export async function downloadExcelReport(taskId) {
  const t = getToken();
  let res;
  try {
    res = await fetch(`${API_BASE}/analysis/excel`, {
      method: "POST",
      headers: t ? { Authorization: `Bearer ${t}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId }),
    });
  } catch (e) {
    throw new Error("Excel generation service unavailable.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "Excel generation failed");
  }
  const blob = await res.blob();
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = "MEDHA_P204_Maintenance_Analysis.xlsx";
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
}

export async function downloadDocxReport(taskId) {
  const t = getToken();
  let res;
  try {
    res = await fetch(`${API_BASE}/analysis/docx`, {
      method: "POST",
      headers: t ? { Authorization: `Bearer ${t}`, "Content-Type": "application/json" } : { "Content-Type": "application/json" },
      body: JSON.stringify({ task_id: taskId }),
    });
  } catch (e) {
    throw new Error("DOCX generation service unavailable.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }));
    throw new Error(err.detail || "DOCX generation failed");
  }
  const blob = await res.blob();
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename=([^;]+)/);
  const filename = match ? match[1].trim() : "MEDHA_Report.docx";
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
  return { ok: true, size: blob.size };
}

// --- Public evaluator demo (synthetic Pump P-204 scenario only) ---
// Deliberately unauthenticated and body-less: no user identity, no tokens,
// no client-supplied documents/prompts/tools. Isolated from private data.

async function demoPost(path) {
  let res;
  try {
    res = await fetch(`${API_BASE}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    throw new Error("MEDHA backend unreachable. Start the local backend and try again.");
  }
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: "" }));
    throw new Error(err.detail || "Demo step failed. Please try again.");
  }
  return res.json();
}

export function runDemoEvidence() {
  return demoPost("/demo/evidence");
}

export function runDemoAnalysis() {
  return demoPost("/demo/analysis");
}

export async function downloadDemoReport() {
  let res;
  try {
    res = await fetch(`${API_BASE}/demo/report`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
    });
  } catch {
    throw new Error("Report service unreachable. Start the local backend and try again.");
  }
  if (!res.ok) {
    throw new Error("Report generation failed. Please try again.");
  }
  const blob = await res.blob();
  if (!blob.size) {
    throw new Error("Report generation failed. Please try again.");
  }
  const disposition = res.headers.get("Content-Disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/);
  const filename = match ? match[1].trim() : "MEDHA_Pump_P204_Demo_Report.docx";
  const url = window.URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  window.URL.revokeObjectURL(url);
  return { ok: true, size: blob.size, filename };
}

export { getToken, clearToken };
