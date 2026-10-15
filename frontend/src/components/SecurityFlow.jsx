export default function SecurityFlow() {
  const steps = [
    { label: "User", icon: "U" },
    { label: "Task Passport", icon: "T" },
    { label: "Action Gate", icon: "A" },
    { label: "AI Execution", icon: "AI" },
    { label: "Verification", icon: "V" },
    { label: "Audit Trail", icon: "L" },
  ];

  return (
    <div className="security-flow">
      {steps.map((step, i) => (
        <div key={step.label} className="flow-step">
          <div className="flow-node">
            <span className="flow-icon">{step.icon}</span>
            <span className="flow-label">{step.label}</span>
          </div>
          {i < steps.length - 1 && <div className="flow-arrow">&rarr;</div>}
        </div>
      ))}
    </div>
  );
}
