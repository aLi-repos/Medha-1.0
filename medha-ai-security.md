# Medha AI — Security Architecture

**Project:** Medha AI  
**Subtitle:** Sovereign Controlled Multimodal AI Workbench for Confidential Industrial Work  
**Security document status:** Security architecture derived from the authoritative Master `/plan`  
**Year:** 2026

> **Governing rule:** This document preserves the security boundaries, workflow stages, policies, MVP scope, and control model defined by the Master `/plan`. It does not weaken, remove, reorder, or bypass them.

---

## 1. Purpose

Medha AI handles confidential industrial work using local open-weight multimodal models and controlled agentic execution.

The security architecture exists to ensure that AI productivity does not become uncontrolled access to:

- Confidential documents.
- Industrial knowledge.
- Internal correspondence.
- Engineering information.
- Code.
- Calculations.
- Vendor or business information.
- Generated deliverables.
- Organizational tools and execution environments.

The central security principle is:

> **The AI may propose; policy decides; controlled infrastructure executes; verification validates; audit records.**

---

## 2. Security Objectives

Medha must preserve:

1. **Confidentiality** — unauthorized users, models, tools, and processes must not receive protected information.
2. **Integrity** — evidence, calculations, outputs, policies, and deliverables must not be silently altered.
3. **Authorization correctness** — every protected operation must be evaluated against identity, task, resource, action, sensitivity, and policy.
4. **Execution isolation** — generated code and risky operations must not directly access the host.
5. **Sovereignty** — confidential processing remains inside the organization's controlled environment.
6. **Evidence integrity** — important claims remain linked to their supporting evidence.
7. **Auditability** — the task lifecycle must be reconstructable.
8. **Controlled release** — deliverables are released only through authorized review and secure handover.
9. **Bounded autonomy** — the agent cannot loop indefinitely, broaden its own scope, or bypass controls.
10. **Human oversight** — high-risk, sensitive, ambiguous, or consequential work can require human review.

---

## 3. Security Is a Workflow, Not a Single Feature

Medha must not rely on only one security layer.

The required defense-in-depth path is:

```text
USER
  ↓
IDENTITY
  ↓
AUTHORIZATION
  ↓
TASK PASSPORT
  ↓
KNOWLEDGE AUTHORIZATION
  ↓
PERMISSION-AWARE RAG
  ↓
WORK SEPARATION
  ↓
MODEL + TOOL POLICY
  ↓
ACTION GATE
  ↓
SANDBOX ISOLATION
  ↓
VERIFICATION
  ↓
REVIEW
  ↓
AUDIT
  ↓
SECURE HANDOVER
```

A local LLM alone does not provide this security boundary.

---

## 4. Security Trust Model

The security model assumes that individual AI components must not be trusted with unrestricted authority.

### Trusted security control plane

```text
Identity Provider
       ↓
Policy Engine
       ↓
Permission Decisions
       ↓
Task Passport
       ↓
Action Gate
       ↓
Sandbox Policy
       ↓
Review / Handover Controls
       ↓
Audit
```

### AI execution plane

```text
Model
 ↓
Agent Planner
 ↓
Tool Requests
 ↓
Controlled Execution
```

The execution plane operates under constraints established by the control plane.

### Critical rule

The model and agent may:

- Interpret.
- Classify.
- Retrieve through approved interfaces.
- Propose actions.
- Generate content.
- Request tools.
- Request replanning.

They may **not**:

- Grant themselves permission.
- Broaden task scope.
- Override policy.
- Approve their own sensitive output.
- Disable network restrictions.
- Directly access the host.
- Bypass the Action Gate.

---

## 5. Identity and Authentication Security

Baseline identity platform: **Keycloak**.

Responsibilities:

- User identity.
- Login.
- Sessions.
- Tokens.
- Roles.
- Administrator management.

Initial roles:

```text
Operator
Engineer
Reviewer
Administrator
```

Authentication establishes **who** the user is.

Authentication alone does not establish what the user may access.

Every controlled task must carry authenticated identity context into downstream authorization decisions.

---

## 6. Authorization Architecture

Authorization determines whether an identity may perform a specific operation.

### Authorization layers

| Layer | Purpose |
|---|---|
| Keycloak RBAC | Broad role-based access |
| OpenFGA | Fine-grained relationships |
| OPA | Policy evaluation |
| Permission Engine | Unified task/resource/action decision |
| Task Passport | Carries task-scoped security context |
| Action Gate | Enforces authorization before consequential tools |

OpenFGA relationships may include:

- Department membership.
- Document access.
- Task execution.
- Tool invocation.
- Deliverable approval.

OPA and OpenFGA decisions are independent of model-generated reasoning.

---

## 7. Permission Engine Security

The Permission Engine evaluates:

```text
User
+
Task
+
Resource
+
Action
+
Sensitivity
+
Policy
```

It returns exactly one policy outcome:

```text
ALLOW
DENY
REQUIRE_APPROVAL
```

### Default-deny principle

If the system cannot establish that an operation is authorized, it must not expose or execute the operation.

### Policy requirements

Policies must be:

- Deterministic.
- Testable.
- Versioned.
- Auditable.
- Independently evaluated from the LLM.

Policy evaluation must happen before:

- Knowledge release.
- Tool execution.
- Consequential actions.
- File access.
- Output release.

The LLM cannot become the security authority.

---

## 8. Task Passport Security

Every controlled task receives a persisted Task Passport.

Required security context:

```text
task_id
user_id
identity
role
purpose
sensitivity
requested_operation
allowed_sources
allowed_tools
allowed_models
approval_requirement
network_policy
created_at
status
```

The Task Passport is the security context of the task.

It must be consulted by:

```text
RAG
Model Router
Tool Invocation
Workspace
Sandbox
Review
Secure Handover
```

Security-critical fields are immutable after execution begins.

If a security-critical field must change:

```text
CHANGE REQUEST
 ↓
VERSIONED AUDIT EVENT
 ↓
RE-AUTHORIZATION
 ↓
CONTINUE
```

A task cannot silently expand its permissions during execution.

---

## 9. Knowledge Security and Permission-Aware RAG

RAG is a major security boundary because retrieval can expose confidential organizational knowledge.

Medha must use:

```text
QUERY
 ↓
DETERMINE ALLOWED KNOWLEDGE
 ↓
RETRIEVE RELEVANT KNOWLEDGE
 ↓
APPLY PERMISSION FILTERING
 ↓
RETURN AUTHORIZED EVIDENCE
```

### Critical security rule

> **Semantic relevance is not authorization.**

A document being highly relevant does not mean the user or task is permitted to see it.

Permission filtering must occur before evidence is exposed to the model or user.

### Indexed metadata

Each indexed representation must retain at least:

```text
embedding
document_id
chunk_id
page
classification
permissions
department
version
```

This metadata participates in authorization filtering.

---

## 10. Document Ingestion Security

Supported inputs include:

- PDF.
- Scanned PDF.
- DOCX.
- TXT.
- Images.
- Industrial documents.

Pipeline:

```text
FILE
 ↓
TYPE DETECTION
 ↓
DOCUMENT PARSING
 ↓
OCR IF REQUIRED
 ↓
CHUNKING
 ↓
METADATA EXTRACTION
 ↓
LOCAL EMBEDDING
 ↓
QDRANT
```

Security requirements:

- Processing is local in sovereign mode.
- External document-processing APIs are not required.
- Document classification and permissions must remain attached to indexed content.
- Untrusted documents must not automatically gain permission to invoke tools.
- Malicious document content must be treated as untrusted input.

---

## 11. OCR and Multimodal Security

OCR runs locally.

OCR output may include:

- Text.
- Tables.
- Page references.
- OCR confidence.
- Document metadata.

Low-confidence OCR must be flagged.

It must not silently become authoritative evidence.

For visual processing:

```text
IMAGE / SCAN
 ↓
LOCAL OCR / VISION
 ↓
MODEL OBSERVATION
 ↓
VERIFICATION
 ↓
AUTHORIZED EVIDENCE
```

Vision output is an observation, not automatically an organizational fact.

Multimodal inputs must be included in security testing for malicious or adversarial content.

---

## 12. Evidence Security

Medha distinguishes:

```text
SOURCE FACT
INFERENCE
CALCULATION
RECOMMENDATION
```

Important claims must preserve:

```text
SOURCE
 ↓
EVIDENCE
 ↓
CLAIM
 ↓
ACTION
 ↓
OUTPUT
```

The system must never silently convert:

```text
MODEL INFERENCE → ORGANIZATIONAL FACT
```

Evidence access itself is permission-controlled.

Evidence presented to the user or model must be traceable to authorized sources.

---

## 13. Model Security

Models are replaceable components.

Security requirements:

- Models must operate within the task's allowed model policy.
- Sovereign mode uses locally served models.
- A model cannot select an unauthorized model for itself.
- Model selection must respect sensitivity and task constraints.
- Model fallback must remain within the Task Passport's allowed model set.
- External model APIs are not required in sovereign mode.

The Model Router records:

```text
Selected model
Selection rationale
Required tools
Execution plan
Constraints
Fallback behavior
```

This makes model selection observable and auditable.

---

## 14. Agent Security and Bounded Autonomy

The Agent Planner operates as a bounded stateful graph:

```text
UNDERSTAND
 ↓
RETRIEVE
 ↓
PLAN
 ↓
REQUEST ACTION
 ↓
ACTION GATE
 ↓
EXECUTE
 ↓
OBSERVE
 ↓
VERIFY
 ↓
REPLAN
 ↓
DELIVER
```

The agent is not an unrestricted autonomous process.

### Mandatory stop conditions

The agent must stop on:

- Policy denial.
- Missing authorization.
- Repeated verification failure.
- Excessive loops.
- Unsafe tool request.
- Ambiguous high-risk condition.

Retries and replanning must be bounded.

The agent cannot use successful reasoning as evidence that a denied operation should be permitted.

---

## 15. Prompt Injection Security

Prompt injection is treated as an untrusted-input problem.

Potential sources include:

- User prompts.
- Retrieved documents.
- Scanned documents.
- OCR text.
- Images.
- Tool output.
- Generated files.
- External or embedded content.

### Security principle

Instructions contained inside data must not automatically become trusted system instructions.

Conceptually:

```text
UNTRUSTED CONTENT
      ↓
CONTENT PROCESSING
      ↓
POLICY / TASK CONTEXT
      ↓
MODEL REASONING
      ↓
ACTION REQUEST
      ↓
ACTION GATE
```

Even if prompt injection causes the model to propose a malicious action, the Action Gate and Permission Engine must independently evaluate the requested action.

Prompt injection testing is mandatory.

---

## 16. Tool Security

Every tool must be registered with:

```text
tool_id
name
description
risk_level
required_permission
input_schema
output_schema
network_policy
```

Initial tools:

- Document reader.
- Document search.
- Calculator.
- Spreadsheet reader.
- Spreadsheet writer.
- File manager.
- DOCX generator.
- PPTX generator.
- Code executor.

No consequential tool may be directly exposed to an unrestricted agent loop.

---

## 17. Action Gate Security

Every consequential action must pass:

```text
AGENT
 ↓
ACTION GATE
 ↓
POLICY CHECK
 ↓
ALLOW / DENY / REQUIRE_APPROVAL
 ↓
TOOL
```

The Action Gate is a mandatory enforcement boundary.

It prevents a model from turning generated text into unrestricted system action.

Examples of protected operations include:

- Reading protected files.
- Writing files.
- Executing code.
- Modifying work artifacts.
- Invoking tools.
- Producing consequential deliverables.
- Releasing outputs.

---

## 18. Workspace Security

Workspace artifacts must track:

```text
owner
task_id
classification
permissions
version
source
status
```

Access must be:

- Task-scoped.
- Permission-checked.
- Classification-aware.
- Auditable.

Generated artifacts must not silently escape the task's security context.

---

## 19. Sandbox Security

Generated code must never execute directly on the host.

Baseline:

```text
Docker
```

Optional hardened deployment:

```text
gVisor
```

Required controls:

- Isolated filesystem.
- CPU limits.
- Memory limits.
- Execution timeout.
- Restricted permissions.
- Controlled mounts.
- No unrestricted host access.
- Network disabled by default.

### Security boundary

```text
GENERATED CODE
      ↓
ACTION GATE
      ↓
SANDBOX POLICY
      ↓
DOCKER / gVISOR
      ↓
EXECUTION
      ↓
RESULT + LOGS
```

A failed or interrupted sandbox execution must preserve logs and status without exposing host resources.

---

## 20. Network Security and Sovereignty

In sovereign mode:

```text
External AI APIs: NOT REQUIRED
External network: DENIED BY DEFAULT
```

Local components include:

- LLM.
- Vision.
- OCR.
- Embeddings.
- RAG.
- Agent.
- Tools.
- Sandbox.
- Verifier.
- Audit.
- Deliverables.

The prototype must visibly demonstrate:

- Local model endpoint.
- Local vector database.
- Local OCR.
- Local embeddings.
- Local files.
- Blocked external network attempts.
- Audit logs.

### Network trust boundary

```text
┌─────────────────────────────────────────────┐
│        ORGANIZATION CONTROLLED ZONE         │
│                                             │
│ UI → API → Auth → RAG → Models → Agent     │
│                  → Tools → Sandbox          │
│                  → Verify → Audit → Output  │
│                                             │
│          External network: DENIED           │
└─────────────────────────────────────────────┘
```

“Everything is local” is not sufficient without observable evidence.

---

## 21. Deliverable Security

The Deliverable Factory creates:

- DOCX.
- XLSX.
- PPTX.
- PDF.
- Code where authorized.

A deliverable is treated as a controlled package.

Example:

```text
MEDHA-PACKAGE/
├── approval_note.docx
├── evidence.json
├── verification.json
├── audit.json
└── manifest.json
```

The package preserves the relationship between output, evidence, verification, and audit.

---

## 22. Verification Security

The Verifier checks:

- Schema.
- Calculations.
- Evidence.
- Document consistency.
- Tool results.
- Policy compliance.
- Unsupported claims.
- Output completeness.

Verification categories:

```text
RULE
CALCULATION
EXECUTION
EVIDENCE
POLICY
```

Failure path:

```text
FAIL
 ↓
FEEDBACK
 ↓
REPLAN
 ↓
EXECUTE
 ↓
VERIFY
```

Verification retries must be bounded.

The agent cannot mark its own failed verification as successful merely by generating another explanation.

---

## 23. Review and Human Oversight

Review mode is policy-controlled.

| Mode | Security use |
|---|---|
| Human | High-risk, sensitive, ambiguous, consequential work |
| Minimal-change iterative | Limited corrections with relevant re-verification |
| Auto | Only explicitly policy-approved low-risk work |

The LLM cannot independently decide that output is safe for automatic release.

Minimal-change review must:

1. Modify only the requested portion.
2. Rerun relevant verification.
3. Return to review.

---

## 24. Secure Handover

Final release follows:

```text
OUTPUT
 ↓
PACKAGE
 ↓
SHA-256 HASH
 ↓
ACCESS CONTROL
 ↓
AUTHORIZED RECIPIENT
```

Handover package includes:

- Manifest.
- SHA-256 integrity hash.
- Task ID.
- Timestamp.
- Verification status.
- Access policy.

Secure handover prevents an otherwise valid deliverable from being released to an unauthorized recipient.

---

## 25. Audit and Trace Security

Baseline:

- OpenTelemetry.
- PostgreSQL or equivalent durable audit store.

Audit records must capture:

```text
who
when
what
why
data
model
tool
action
policy
evidence
verification
approval
output
```

Minimum reconstructable chain:

```text
Authentication
 ↓
RBAC
 ↓
Task Passport
 ↓
RAG Permission Decision
 ↓
Model Selection
 ↓
Plan Generation
 ↓
Action Gate
 ↓
Tool Execution
 ↓
Sandbox Execution
 ↓
Verification
 ↓
Deliverable
 ↓
Audit
 ↓
Review
 ↓
Handover
```

Every security failure must be traceable to:

```text
Task
Identity
Policy decision
Resource
Action
Audit event
```

---

## 26. Security Event Integrity

Security-relevant events must be:

- Associated with a task.
- Associated with an identity.
- Associated with the applicable policy decision.
- Timestamped.
- Persisted durably.
- Reconstructable in lifecycle order.

Deliverable integrity uses:

```text
SHA-256
```

Audit and output metadata must make tampering or unexplained lifecycle gaps detectable.

---

## 27. Security Testing Requirements

The security test program must cover:

### Authorization

- Unauthorized document access.
- RBAC bypass.
- OpenFGA bypass.
- OPA policy bypass.
- RAG permission bypass.
- Approval bypass.
- Unauthorized output release.

### AI / Agent

- Prompt injection.
- Excessive agent loops.
- Unsafe tool requests.
- Model-policy violations.
- Malicious multimodal inputs.

### Documents and Files

- Malicious documents.
- Unauthorized file access.
- Permission metadata manipulation.
- Classification boundary failures.

### Execution

- Malicious code.
- Sandbox escape.
- Tool abuse.
- Host filesystem access.
- Resource exhaustion.
- Network access attempts.

### Data Protection

- Data leakage.
- Unauthorized evidence exposure.
- Cross-task data leakage.
- Unauthorized deliverable access.

Security tests must include positive and negative cases.

Where practical, security tests run in CI.

---

## 28. Security Test Flow

Every important security boundary should have an explicit negative test.

Example:

```text
UNAUTHORIZED USER
      ↓
REQUEST PROTECTED DOCUMENT
      ↓
PERMISSION ENGINE
      ↓
DENY
      ↓
NO DOCUMENT CONTENT RELEASED
      ↓
AUDIT EVENT
```

Tool example:

```text
AGENT REQUESTS RESTRICTED TOOL
      ↓
ACTION GATE
      ↓
POLICY CHECK
      ↓
DENY / REQUIRE_APPROVAL
      ↓
TOOL NOT EXECUTED
      ↓
AUDIT EVENT
```

Network example:

```text
SANDBOX ATTEMPTS EXTERNAL CONNECTION
      ↓
NETWORK POLICY
      ↓
BLOCK
      ↓
EXECUTION STATUS + LOG
      ↓
AUDIT EVENT
```

---

## 29. Security Metrics

Measure experimentally rather than promising fixed values before benchmarking.

Relevant security and quality metrics include:

- Authorization rejection rate.
- Verification pass rate.
- Failed-action rate.
- Blocked external-network attempts.
- Evidence coverage.
- OCR quality.
- Retrieval quality.
- Model-routing accuracy.
- Sandbox success rate.
- Human-review rate.
- End-to-end latency.
- Task completion rate.

Security metrics should be collected at the relevant enforcement points and included in test reporting.

---

## 30. Security Failure Handling

Security failures are fail-closed events unless a documented policy explicitly defines another safe response.

Examples:

### Missing authorization

```text
DENY
 ↓
NO ACCESS
 ↓
AUDIT
```

### Policy ambiguity

```text
REQUIRE_APPROVAL
 ↓
HUMAN / AUTHORIZED REVIEW
```

### Sandbox failure

```text
STOP EXECUTION
 ↓
PRESERVE LOGS
 ↓
AUDIT
```

### Verification failure

```text
FAIL
 ↓
FEEDBACK
 ↓
BOUNDED REPLAN
 ↓
REVERIFY
```

### Excessive agent loop

```text
STOP
 ↓
PRESERVE STATE
 ↓
AUDIT
```

---

## 31. Security Invariants

These invariants must remain true:

1. **The LLM never grants itself permission.**
2. **Knowledge relevance never overrides authorization.**
3. **The Action Gate mediates consequential tool actions.**
4. **Generated code never executes directly on the host.**
5. **Network access is denied by default in sovereign mode.**
6. **Verification precedes important deliverable release.**
7. **Important claims remain evidence-linked.**
8. **Review mode is policy-controlled.**
9. **Secure handover enforces recipient access and integrity.**
10. **Audit can reconstruct the task lifecycle.**
11. **Task security scope cannot silently expand.**
12. **Model replacement cannot weaken security boundaries.**
13. **Security failures remain auditable.**
14. **Sovereignty is demonstrated with observable controls.**
15. **No implementation may bypass a security boundary without an explicitly documented, approved deviation that does not weaken security or sovereignty.**

---

## 32. MVP Security Demonstration

The primary MVP must demonstrate:

```text
USER AUTHENTICATES
       ↓
RBAC / FINE-GRAINED AUTH
       ↓
TASK PASSPORT
       ↓
KNOWLEDGE PERMISSION
       ↓
LOCAL OCR + RAG
       ↓
MODEL ROUTING
       ↓
AGENT PLAN
       ↓
ACTION GATE
       ↓
CONTROLLED TOOL
       ↓
DOCKER SANDBOX
       ↓
VERIFIER
       ↓
DOCX DELIVERABLE
       ↓
AUDIT
       ↓
REVIEW
       ↓
SHA-256 + ACCESS CONTROL
       ↓
AUTHORIZED HANDOVER
```

The demo should visibly show at least one denied/blocked security action and its corresponding audit trace.

Sovereignty should also be demonstrated using local endpoints and a blocked external network attempt.

---

## 33. Security Boundaries for the Primary Industrial Workflow

Primary demo:

```text
SCANNED INSPECTION REPORT
+
INTERNAL SOP / MANUAL
+
INSPECTION PHOTOGRAPH
```

Security flow:

```text
INPUT
 ↓
IDENTITY
 ↓
TASK PASSPORT
 ↓
DOCUMENT PERMISSION CHECK
 ↓
LOCAL OCR / VISION
 ↓
PERMISSION-AWARE RAG
 ↓
AUTHORIZED EVIDENCE
 ↓
MODEL + PLAN
 ↓
ACTION GATE
 ↓
CONTROLLED CALCULATION / TOOL
 ↓
SANDBOX IF CODE EXECUTION IS REQUIRED
 ↓
VERIFICATION
 ↓
EVIDENCE-LINKED INSPECTION ANALYSIS
 ↓
APPROVAL NOTE
 ↓
REVIEW
 ↓
AUDIT
 ↓
SECURE HANDOVER
```

The workflow must preserve classification, authorization, verification, audit, and integrity metadata.

---

## 34. Security Boundaries for the Coding Workflow

Secondary workflow:

```text
USER
 ↓
TASK PASSPORT
 ↓
PURPOSE
 ↓
WORK SEPARATION
 ↓
CODING MODEL
 ↓
AGENT PLAN
 ↓
ACTION GATE
 ↓
CODE WORKSPACE
 ↓
DOCKER SANDBOX
 ↓
TEST
 ↓
VERIFIER
 ↓
REVIEW
 ↓
OUTPUT
 ↓
SECURE HANDOVER
 ↓
AUDIT
```

Security priorities:

- No unrestricted host access.
- No uncontrolled network.
- Task-scoped files.
- Registered tools only.
- Bounded execution.
- Verification before release.

---

## 35. Security Responsibilities by Component

| Component | Primary security responsibility |
|---|---|
| UI | Do not expose unauthorized information/actions |
| API Gateway | Request validation and controlled routing |
| Keycloak | Identity and role management |
| RBAC | Broad role authorization |
| OpenFGA | Fine-grained relationships |
| OPA | Policy evaluation |
| Task Passport | Task security context |
| Permission Engine | Unified authorization decision |
| RAG | Permission-aware knowledge release |
| OCR / Vision | Local processing and observation handling |
| Model Router | Allowed model selection |
| Agent Planner | Bounded autonomy |
| Tool Registry | Registered/risk-aware tool definitions |
| Action Gate | Consequential-action enforcement |
| Workspace | Task-scoped artifact control |
| Sandbox | Execution isolation |
| Verifier | Evidence/output validation |
| Deliverable Factory | Controlled work-product creation |
| Review | Human/policy release control |
| Audit / Trace | Lifecycle reconstruction |
| Secure Handover | Authorized release + integrity |

---

## 36. Security Architecture vs. Convenience

Medha may have development conveniences such as:

- Local developer environments.
- Docker Compose.
- Frontend preview hosting.

These do not override sovereign security requirements.

For example:

```text
Vercel
  =
Optional non-confidential frontend preview

On-Prem
  =
Sovereign production environment

Docker
  =
Execution isolation

gVisor
  =
Optional hardened sandbox
```

Confidential industrial data must remain inside the approved security boundary.

---

## 37. Security Governance

Security-sensitive architecture changes must follow:

```text
PROPOSE CHANGE
 ↓
IDENTIFY TRUST BOUNDARY
 ↓
IDENTIFY SECURITY INVARIANTS
 ↓
ASSESS IMPACT
 ↓
DOCUMENT DECISION
 ↓
UPDATE TESTS
 ↓
VERIFY SECURITY
 ↓
APPROVE
```

Changes must be recorded in `docs/decisions.md`.

The security document and related policies must remain synchronized with the architecture and specification.

---

## 38. Relationship to Threat Model

This document defines the security architecture and controls.

`docs/threat-model.md` must separately document:

- Threat actors.
- Assets.
- Attack surfaces.
- Abuse cases.
- Threat scenarios.
- Mitigations.
- Residual risk.
- Security test mapping.

The threat model must not weaken the security invariants defined here.

---

## 39. Relationship to Supporting Policies

Security architecture is implemented through specialized policies:

```text
security.md
   ├── threat-model.md
   ├── rag-policy.md
   ├── model-policy.md
   ├── tool-policy.md
   ├── audit-policy.md
   └── deployment.md
```

Each policy must preserve the same authorization, sovereignty, isolation, verification, audit, and handover boundaries.

---

## 40. Final Security Principle

Medha must never reduce security to:

```text
LOCAL LLM = SECURE
```

The required security model is:

```text
SECURE MEDHA
=
IDENTITY
+
AUTHORIZATION
+
KNOWLEDGE PERMISSION
+
TASK SCOPE
+
POLICY
+
CONTROLLED TOOLS
+
ACTION GATE
+
SANDBOX
+
VERIFICATION
+
REVIEW
+
AUDIT
+
SECURE HANDOVER
+
SOVEREIGN NETWORK BOUNDARY
```

And the governing execution model remains:

```text
USER
 ↓
IDENTITY
 ↓
AUTHORIZATION
 ↓
KNOWLEDGE PERMISSION
 ↓
TASK PURPOSE
 ↓
WORK SEPARATION
 ↓
ACTION CONTROL
 ↓
MODEL + PLAN
 ↓
CONTROLLED EXECUTION
 ↓
VERIFICATION
 ↓
DELIVERABLE
 ↓
AUDIT
 ↓
REVIEW
 ↓
SAFE ISOLATION
 ↓
OUTPUT
 ↓
SECURE HANDOVER
```

Any implementation that bypasses these controls is out of scope unless the deviation is explicitly documented, approved, and shown not to weaken security or sovereignty.

---

## References

This security architecture is derived from the user-provided Medha AI Master `/plan`. The Master `/plan` identifies `docs/security.md` as the document responsible for security controls, trust boundaries, authentication, authorization, isolation, and secure handover, and defines the required security testing scope and MVP security demonstrations.
