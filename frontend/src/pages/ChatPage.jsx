import { useState, useEffect, useRef } from "react";
import { useNavigate } from "react-router-dom";
import {
  getIdentity, listTasks, listModels, listTools,
  listConversations, createConversation, deleteConversation, sendChatMessage,
  uploadFile, listMessages, clearToken, getLocalLLMHealth
} from "../api";
import { groupConversationsByDate, timeAgo } from "../utils/helpers";
import TopNav from "../components/TopNav";
import { useSecurity } from "../contexts/SecurityContext";
import Toast from "../components/Toast";

export default function ChatPage() {
  const { securityMode } = useSecurity();
  const [user, setUser] = useState(null);
  const [tasks, setTasks] = useState([]);
  // null = General Chat (default). A task id string activates the task pipeline.
  const [selectedTask, setSelectedTask] = useState(null);
  const [allConversations, setAllConversations] = useState([]);
  const [selectedConversation, setSelectedConversation] = useState(null);
  const [messages, setMessages] = useState([]);
  const [prompt, setPrompt] = useState("");
  const [loading, setLoading] = useState(false);
  const [pendingFiles, setPendingFiles] = useState([]);
  const [models, setModels] = useState([]);
  const [selectedModel, setSelectedModel] = useState(null);
  const [localLLM, setLocalLLM] = useState(null);
  const [tools, setTools] = useState([]);
  const [showPlugins, setShowPlugins] = useState(false);
  const [toast, setToast] = useState(null);
  const [chatSearch, setChatSearch] = useState("");
  const messagesEndRef = useRef(null);
  const fileInputRef = useRef(null);
  const cameraInputRef = useRef(null);
  const pluginsRef = useRef(null);
  const navigate = useNavigate();

  const isGeneralChat = !selectedTask;

  useEffect(() => {
    getIdentity().then((u) => {
      setUser(u);
      // Default remains General Chat — do NOT auto-select a task.
      listTasks().then((t) => {
        setTasks(Array.isArray(t) ? t : []);
      }).catch(() => {});
      listModels().then((m) => setModels(m.available_models || [])).catch(() => {});
      listTools().then((res) => setTools(res.tools || [])).catch(() => {});
      getLocalLLMHealth().then(setLocalLLM).catch(() => setLocalLLM(null));
      // Conversations load in the selectedTask effect (default = General Chat).
    }).catch(() => { clearToken(); navigate("/"); });
  }, [navigate]);

  useEffect(() => {
    // Switching selection clears the open conversation/messages.
    setSelectedConversation(null);
    setMessages([]);
    if (selectedTask) {
      listConversations(selectedTask).then((res) => setAllConversations(res.conversations || [])).catch(() => {});
    } else {
      // General Chat: load only conversations with no active task.
      listConversations(null).then((res) => setAllConversations(res.conversations || [])).catch(() => {});
    }
  }, [selectedTask]);

  const selectedTaskData = tasks.find((t) => t.task_id === selectedTask) || null;

  useEffect(() => {
    if (selectedConversation) {
      listMessages(selectedConversation).then((res) => setMessages(res.messages || [])).catch(() => {});
    }
  }, [selectedConversation]);

  useEffect(() => { messagesEndRef.current?.scrollIntoView({ behavior: "smooth" }); }, [messages]);

  useEffect(() => {
    const handleClickOutside = (e) => {
      if (pluginsRef.current && !pluginsRef.current.contains(e.target)) setShowPlugins(false);
    };
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const handleSelectChatContext = (value) => {
    // Empty value → General Chat (task_id = null / no active task).
    setSelectedTask(value || null);
  };

  const handleNewConversation = async () => {
    try {
      const convo = await createConversation(selectedTask, "New Conversation");
      setAllConversations((prev) => [convo, ...prev]);
      setSelectedConversation(convo.id);
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
  };

  const handleDeleteConversation = async (convoId) => {
    try {
      await deleteConversation(convoId);
      setAllConversations((prev) => prev.filter((c) => c.id !== convoId));
      if (selectedConversation === convoId) { setSelectedConversation(null); setMessages([]); }
      setToast({ type: "success", message: "Conversation deleted" });
    } catch (err) {
      setToast({ type: "error", message: err.message });
    }
  };

  const handleOpenRecentChat = (convo) => {
    // Task conversations select that task; General Chat conversations clear it.
    setSelectedTask(convo.task_id || null);
    setTimeout(() => setSelectedConversation(convo.id), 100);
  };

  const handleFileSelect = (e) => {
    setPendingFiles((prev) => [...prev, ...Array.from(e.target.files || [])]);
    e.target.value = "";
  };

  const handleRemoveFile = (index) => {
    setPendingFiles((prev) => prev.filter((_, i) => i !== index));
  };

  const handleSend = async (e) => {
    e.preventDefault();
    if (!prompt.trim()) return;
    setLoading(true);
    let conversationId = selectedConversation;
    try {
      if (pendingFiles.length > 0 && conversationId && selectedTask) {
        for (const file of pendingFiles) await uploadFile(selectedTask, conversationId, file);
        setPendingFiles([]);
      }
      // General Chat sends task_id = null; task chat sends the selected id.
      const result = await sendChatMessage(selectedTask, prompt, selectedModel, conversationId, 512);
      if (!conversationId) {
        conversationId = result.conversation_id;
        setSelectedConversation(conversationId);
        listConversations(selectedTask).then((res) => setAllConversations(res.conversations || [])).catch(() => {});
      }
      setMessages((prev) => [
        ...prev,
        { id: "user-" + Date.now(), role: "user", content: prompt, created_at: new Date().toISOString() },
        {
          id: result.message_id,
          role: "assistant",
          content: result.response_text,
          model: result.model_used,
          sources: Array.isArray(result.sources) ? result.sources : [],
          created_at: new Date().toISOString(),
        },
      ]);
      setPrompt("");
    } catch (err) {
      setMessages((prev) => [...prev, { id: "error-" + Date.now(), role: "error", content: err.message, created_at: new Date().toISOString() }]);
    }
    setLoading(false);
  };

  const handleLogout = () => { clearToken(); navigate("/"); };
  const handleUserUpdate = (updated) => setUser(updated);

  const getToolAvailability = (toolName) => {
    if (!selectedTaskData) return "unknown";
    const allowed = selectedTaskData.allowed_tools;
    if (!allowed || allowed.length === 0) return "available";
    return allowed.includes(toolName) ? "available" : "blocked";
  };

  const recentChats = allConversations.slice(0, 30).filter((c) =>
    chatSearch ? c.title?.toLowerCase().includes(chatSearch.toLowerCase()) : true
  );
  const groupedChats = groupConversationsByDate(recentChats);

  return (
    <div className="app-layout">
      <div className="brush-bg" />
      <TopNav user={user} onLogout={handleLogout} securityMode={securityMode} onUserUpdate={handleUserUpdate} />
      <main className="main-content chat-workbench">
        <Toast toast={toast} onClear={() => setToast(null)} />

        <div className="chat-sidebar">
          <div className="chat-sidebar-header">
            <h3>Recent Chats</h3>
            <button className="btn-new-chat" onClick={handleNewConversation}>+ New</button>
          </div>
          <div className="chat-sidebar-search">
            <input
              type="text"
              placeholder="Search conversations..."
              value={chatSearch}
              onChange={(e) => setChatSearch(e.target.value)}
              className="chat-search-input"
            />
          </div>
          <div className="recent-chats-list">
            {recentChats.length === 0 && <p className="text-muted" style={{ padding: "0.5rem" }}>No conversations yet</p>}
            {Object.entries(groupedChats).map(([label, convos]) => (
              convos.length > 0 && (
                <div key={label}>
                  <div className="recent-chat-group-label">{label}</div>
                  {convos.map((c) => (
                    <div
                      key={c.id}
                      className={`recent-chat-item ${selectedConversation === c.id ? "active" : ""}`}
                      onClick={() => handleOpenRecentChat(c)}
                    >
                      <svg className="recent-chat-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" /></svg>
                      <div className="recent-chat-text">
                        <div className="recent-chat-title">{c.title}</div>
                        {c.last_message && <div className="recent-chat-preview">"{c.last_message}"</div>}
                        <div className="recent-chat-meta">
                          <span>{c.task_id ? (tasks.find((t) => t.task_id === c.task_id)?.title || "Task") : "General Chat"}</span>
                          <span>{timeAgo(c.updated_at)}</span>
                        </div>
                      </div>
                      <button
                        className="recent-chat-delete"
                        onClick={(e) => { e.stopPropagation(); handleDeleteConversation(c.id); }}
                        title="Delete"
                      >
                        &times;
                      </button>
                    </div>
                  ))}
                </div>
              )
            ))}
          </div>
        </div>

        <div className="chat-main">
          <div className="chat-task-context">
            <div className="task-context-left">
              <div className="task-context-row">
                <span className="context-label">Chat:</span>
                <select
                  value={selectedTask || ""}
                  onChange={(e) => handleSelectChatContext(e.target.value)}
                  className="task-select"
                  data-testid="chat-context-select"
                >
                  <option value="" data-testid="general-chat-option">General Chat</option>
                  {tasks.map((t) => (
                    <option key={t.task_id} value={t.task_id}>{t.title}</option>
                  ))}
                </select>
              </div>
              {selectedTaskData && (
                <div className="task-context-info">
                  <span className="context-badge">{selectedTaskData.sensitivity}</span>
                  <span className="context-badge">{selectedTaskData.network_policy}</span>
                  {selectedModel && <span className="context-badge">{selectedModel}</span>}
                </div>
              )}
            </div>
            <div className="local-llm-status" data-testid="local-llm-status" title={localLLM?.reason || "Local model runtime status"}>
              <span className="local-llm-label">Local AI:</span>{" "}
              <span className="local-llm-model">
                {!localLLM?.model
                  ? "—"
                  : localLLM.model.toLowerCase().includes("3b")
                    ? "Qwen 3B"
                    : localLLM.model}
              </span>
              {" · "}
              <span className="local-llm-runtime">Runtime: Ollama</span>
              {" · "}
              <span
                className={`local-llm-status-badge ${localLLM?.status === "AVAILABLE" ? "available" : "unavailable"}`}
              >
                Status:{" "}
                {localLLM?.status === "AVAILABLE"
                  ? "Available"
                  : localLLM?.status === "UNAVAILABLE"
                    ? "Unavailable"
                    : "Checking…"}
              </span>
            </div>
            {selectedTask && (
              <button className="btn-view-task" onClick={() => navigate(`/task/${selectedTask}`)}>View Task</button>
            )}
          </div>

          <div className="chat-messages">
            {messages.length === 0 && !loading && (
              <div className="chat-empty-state">
                <div className="chat-empty-orb">
                  <svg width="48" height="48" viewBox="0 0 48 48" fill="none">
                    <circle cx="24" cy="24" r="20" stroke="rgba(59,130,246,0.25)" strokeWidth="1.5" />
                    <circle cx="24" cy="24" r="12" stroke="rgba(59,130,246,0.4)" strokeWidth="1" />
                    <circle cx="24" cy="24" r="4" fill="rgba(59,130,246,0.6)" />
                  </svg>
                </div>
                <h2 className="chat-empty-title">Your move, {user?.username || "user"}!</h2>
                <p className="chat-empty-sub">
                  {isGeneralChat
                    ? "Ask MEDHA anything — General Chat."
                    : "Ask MEDHA anything about your task."}
                </p>
              </div>
            )}
            {messages.map((m) => (
              <div key={m.id} className={`message ${m.role}`}>
                {m.model && <span className="model-tag">{m.model}</span>}
                <p>{m.content}</p>
                {m.role === "assistant" && Array.isArray(m.sources) && m.sources.length > 0 && (
                  <div className="message-sources" data-testid="message-sources">
                    <div className="message-sources-label">Sources</div>
                    <ul className="message-sources-list">
                      {m.sources.map((s) => (
                        <li key={s.name} className="message-source-item">
                          <details>
                            <summary data-testid="message-source-name">{s.name}</summary>
                            {s.snippet && (
                              <p className="message-source-snippet">{s.snippet}</p>
                            )}
                          </details>
                        </li>
                      ))}
                    </ul>
                  </div>
                )}
              </div>
            ))}
            {loading && <div className="message assistant"><p>Thinking...</p></div>}
            <div ref={messagesEndRef} />
          </div>

          {pendingFiles.length > 0 && (
            <div className="pending-files">
              {pendingFiles.map((f, i) => (
                <div key={i} className="pending-file">
                  <span>{f.type?.startsWith("image/") ? "Image" : "File"}: {f.name}</span>
                  <button onClick={() => handleRemoveFile(i)}>&times;</button>
                </div>
              ))}
            </div>
          )}

          <form onSubmit={handleSend} className="chat-composer">
            <input type="file" ref={fileInputRef} onChange={handleFileSelect} multiple accept=".pdf,.txt,.docx,.png,.jpg,.jpeg" style={{ display: "none" }} />
            <input type="file" ref={cameraInputRef} onChange={handleFileSelect} accept="image/*" capture="environment" style={{ display: "none" }} />
            <div className="composer-tools">
              <button type="button" className="composer-tool" onClick={() => fileInputRef.current?.click()} title="Attach file">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="m21.44 11.05-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48" /></svg>
              </button>
              <button type="button" className="composer-tool" onClick={() => cameraInputRef.current?.click()} title="Camera">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" /><circle cx="12" cy="13" r="4" /></svg>
              </button>
              <div className="composer-plugins" ref={pluginsRef}>
                <button type="button" className="composer-tool" onClick={() => setShowPlugins(!showPlugins)} title="Plugins">
                  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z" /></svg>
                </button>
                {showPlugins && (
                  <div className="plugins-dropdown">
                    <div className="plugins-header">Plugins</div>
                    {tools.map((t) => {
                      const avail = getToolAvailability(t.name);
                      return (
                        <div key={t.name} className={`plugin-item ${avail}`}>
                          <span className="plugin-status">{avail === "available" ? "\u2713" : "\u25CB"}</span>
                          <span className="plugin-name">{t.name.replace(/_/g, " ")}</span>
                          {avail === "blocked" && <span className="plugin-blocked">blocked by Task Passport policy</span>}
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            </div>
            <input
              value={prompt}
              onChange={(e) => setPrompt(e.target.value)}
              placeholder={isGeneralChat ? "Ask MEDHA anything..." : "Ask MEDHA anything about this task..."}
              className="composer-input"
              data-testid="composer-input"
            />
            <div className="composer-model">
              <select value={selectedModel || ""} onChange={(e) => setSelectedModel(e.target.value || null)} className="model-select">
                <option value="">Auto</option>
                {models.map((m) => (
                  <option key={m} value={m}>
                    {m === "local-qwen2" ? "Local Qwen" : m === "api-openai" ? "OpenAI GPT" : m === "api-claude" ? "Claude" : m}
                  </option>
                ))}
              </select>
            </div>
            <button
              type="submit"
              className="composer-send"
              disabled={loading || !prompt.trim()}
              data-testid="send-button"
            >
              {loading ? "..." : "Send"}
            </button>
          </form>
        </div>
      </main>
    </div>
  );
}
