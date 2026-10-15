import { useState, useEffect } from "react";
import { getEnvironmentStatus } from "../api";
import { useSecurity } from "../contexts/SecurityContext";

const STATUS_TONE = {
  AVAILABLE: "safe",
  LOCAL: "safe",
  CONFIGURED: "safe",
  ALLOWED: "safe",
  UNAVAILABLE: "warn",
  UNKNOWN: "warn",
};

function tone(value) {
  return STATUS_TONE[value] || "neutral";
}

export default function EnvironmentStatus() {
  const [status, setStatus] = useState(null);
  const { securityMode } = useSecurity();

  useEffect(() => {
    let cancelled = false;
    getEnvironmentStatus()
      .then((data) => {
        if (!cancelled) setStatus(data);
      })
      .catch(() => {
        if (!cancelled) setStatus(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const model = status?.model || {};
  const network = status?.network || {};
  const sandbox = status?.sandbox || {};

  const items = [
    { label: "Execution", value: status?.execution || "UNKNOWN", tone: tone(status?.execution) },
    { label: "Local AI Model", value: model.status || "UNKNOWN", tone: tone(model.status) },
    { label: "Model Name", value: model.name || "—", tone: model.name ? "neutral" : "warn" },
    { label: "External AI", value: network.external_ai || "UNKNOWN", tone: tone(network.external_ai) },
    { label: "Network Policy", value: network.policy || "UNKNOWN", tone: tone(network.policy) },
    { label: "RAG", value: status?.rag?.status || "UNKNOWN", tone: tone(status?.rag?.status) },
    { label: "OCR", value: status?.ocr?.status || "UNKNOWN", tone: tone(status?.ocr?.status) },
    { label: "Sandbox", value: sandbox.status || "UNKNOWN", tone: tone(sandbox.status) },
    { label: "Security Mode", value: securityMode?.toUpperCase() || "—", tone: "neutral" },
  ];

  return (
    <div className="env-status">
      <div className="env-status-header">Environment Status</div>
      <div className="env-status-list">
        {items.map((item) => (
          <div key={item.label} className="env-status-item">
            <span className="env-label">{item.label}</span>
            <span className={`env-value env-${item.tone}`}>{item.value}</span>
          </div>
        ))}
      </div>
      <p className="env-statement">
        Controlled environment with policy-based access. Connectivity and model
        use follow the active security-mode policy — this is policy control,
        not a physical air gap.
      </p>
    </div>
  );
}
