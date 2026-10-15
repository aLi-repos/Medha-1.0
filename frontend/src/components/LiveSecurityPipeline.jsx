import { useMemo } from "react";

const STAGES = [
  { key: "identity", label: "Identity", desc: "User authenticated" },
  { key: "passport", label: "Task Passport", desc: "Policy defined" },
  { key: "gate", label: "Action Gate", desc: "Access controlled" },
  { key: "execution", label: "AI / RAG", desc: "Ready" },
  { key: "verification", label: "Verification", desc: "Output checked" },
  { key: "audit", label: "Audit Trail", desc: "Events logged" },
];

function getStageState(stage, activeTask) {
  if (!activeTask) {
    if (stage.key === "identity") return { status: "ready", label: "Ready" };
    if (stage.key === "audit") return { status: "ready", label: "Enabled" };
    return { status: "ready", label: "Ready" };
  }

  const s = activeTask.status;

  switch (stage.key) {
    case "identity":
      return { status: "verified", label: "Verified" };
    case "passport":
      if (s === "draft") return { status: "active", label: "Draft" };
      if (s === "authorized" || s === "executing" || s === "completed") return { status: "verified", label: "Authorized" };
      if (s === "denied") return { status: "denied", label: "Denied" };
      if (s === "failed") return { status: "denied", label: "Failed" };
      return { status: "ready", label: "Ready" };
    case "gate":
      if (s === "draft") return { status: "waiting", label: "Waiting" };
      if (s === "authorized" || s === "executing" || s === "completed") return { status: "verified", label: "Allowed" };
      if (s === "denied") return { status: "denied", label: "Blocked" };
      if (s === "failed") return { status: "denied", label: "Blocked" };
      return { status: "ready", label: "Ready" };
    case "execution":
      if (s === "executing") return { status: "active", label: "Processing" };
      if (s === "completed") return { status: "verified", label: "Complete" };
      if (s === "authorized") return { status: "waiting", label: "Awaiting" };
      if (s === "failed") return { status: "denied", label: "Failed" };
      if (s === "denied") return { status: "waiting", label: "Blocked" };
      return { status: "ready", label: "Ready" };
    case "verification":
      if (s === "completed") return { status: "verified", label: "Checked" };
      if (s === "executing") return { status: "waiting", label: "Pending" };
      if (s === "failed") return { status: "denied", label: "Failed" };
      return { status: "ready", label: "Ready" };
    case "audit":
      if (s === "draft") return { status: "ready", label: "Recording" };
      return { status: "verified", label: "Logged" };
    default:
      return { status: "ready", label: "Ready" };
  }
}

function StatusDot({ status }) {
  if (status === "active") return <span className="lp-dot lp-dot-active" />;
  if (status === "verified") return <span className="lp-dot lp-dot-verified" />;
  if (status === "denied") return <span className="lp-dot lp-dot-denied" />;
  if (status === "waiting") return <span className="lp-dot lp-dot-waiting" />;
  return <span className="lp-dot lp-dot-ready" />;
}

export default function LiveSecurityPipeline({ tasks }) {
  const activeTask = useMemo(() => {
    if (!tasks || tasks.length === 0) return null;
    const executing = tasks.find((t) => t.status === "executing");
    if (executing) return executing;
    const authorized = tasks.find((t) => t.status === "authorized");
    if (authorized) return authorized;
    return tasks[0];
  }, [tasks]);

  return (
    <div className="live-pipeline">
      <div className="lp-header">
        <h3>Live Security Pipeline</h3>
        <span className="lp-live-badge"><span className="lp-live-dot" /> LIVE</span>
      </div>

      <div className="lp-stages">
        {STAGES.map((stage, i) => {
          const state = getStageState(stage, activeTask);
          return (
            <div key={stage.key} className="lp-stage-wrap">
              <div className={`lp-stage lp-stage-${state.status}`}>
                <StatusDot status={state.status} />
                <div className="lp-stage-icon">
                  {stage.key === "identity" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>}
                  {stage.key === "passport" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>}
                  {stage.key === "gate" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"/><path d="M7 11V7a5 5 0 0 1 10 0v4"/></svg>}
                  {stage.key === "execution" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"/></svg>}
                  {stage.key === "verification" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>}
                  {stage.key === "audit" && <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/></svg>}
                </div>
                <div className="lp-stage-info">
                  <span className="lp-stage-name">{stage.label}</span>
                  <span className={`lp-stage-status lp-status-${state.status}`}>{state.label}</span>
                </div>
              </div>
              {i < STAGES.length - 1 && <div className={`lp-connector lp-conn-${state.status}`} />}
            </div>
          );
        })}
      </div>

      {activeTask && (
        <div className="lp-task-label">
          {activeTask.title} — {activeTask.status}
        </div>
      )}

      <div className="lp-summary">
        Task-scoped execution &bull; External network blocked &bull; Policy-controlled AI &bull; Audit logging enabled
      </div>
    </div>
  );
}
