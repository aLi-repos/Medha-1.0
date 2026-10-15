# Medha AI — Architecture Decisions, Trade-offs, Assumptions & Open Questions

**Project:** Medha AI  
**Subtitle:** Sovereign Controlled Multimodal AI Workbench for Confidential Industrial Work  
**Project owner:** Rahamath Ali  
**Institution:** Sri Chaitanya Institute of Technology and Research (SCITR), Khammam  
**Year:** 2026  
**Status:** Governing decision record derived from the authoritative Master `/plan`

---

## 1. Purpose and Status

This document records the architectural decisions, trade-offs, assumptions, rejected alternatives, and unresolved questions governing Medha AI.

The Master `/plan` is the authoritative source. This document must not weaken its security boundaries, control workflow, sovereignty requirements, MVP vertical slice, or definition of done.

Medha is a controlled, sovereign, on-premise AI workbench for confidential industrial work. It is not an unrestricted chatbot. The governing execution path is:

```text
IDENTITY
→ AUTHORIZATION
→ KNOWLEDGE PERMISSION
→ TASK PURPOSE
→ WORK SEPARATION
→ ACTION CONTROL
→ MODEL + PLAN
→ CONTROLLED EXECUTION
→ VERIFICATION
→ DELIVERABLE
→ AUDIT
→ REVIEW
→ SAFE ISOLATION
→ OUTPUT
→ SECURE HANDOVER
```

A decision in this document is valid only when it is consistent with that control path.

---

## 2. Decision Governance

### 2.1 Decision status

Each decision uses one of these statuses:

| Status | Meaning |
|---|---|
| `PROPOSED` | Candidate decision requiring review |
| `ACCEPTED` | Approved baseline for implementation |
| `CONDITIONAL` | Accepted subject to a stated constraint or test |
| `DEFERRED` | Intentionally postponed without changing the architecture |
| `REJECTED` | Alternative considered and not selected |
| `SUPERSEDED` | Replaced by a newer decision |

### 2.2 Decision rules

1. Security, sovereignty, authorization, auditability, and handover boundaries are non-negotiable.
2. Implementation technologies are replaceable when their internal contracts remain stable.
3. A deviation from the Master `/plan` must be explicitly documented.
4. A deviation must not weaken authorization, policy enforcement, verification, auditability, isolation, or sovereignty.
5. Security-critical Task Passport changes after execution begins require versioning and re-authorization.
6. The LLM cannot grant itself permission, broaden scope, approve release, or override network restrictions.
7. Decisions affecting production security require corresponding tests.
8. Every accepted decision should identify its rationale, consequences, verification method, and affected requirements.
9. Specific technology versions should be selected later from verified implementation documentation and recorded here when chosen.
10. Unresolved implementation choices must not silently become architectural dependencies.

---

# 3. Non-Negotiable Architectural Constraints

## DEC-001 — Controlled-agent architecture

**Status:** ACCEPTED

**Decision:** Medha shall be implemented as a controlled agentic workbench rather than a generic prompt-to-answer chatbot.

**Rationale:** Confidential industrial work requires identity, authorization, knowledge controls, action controls, verification, review, auditability, and secure handover.

**Required behavior:**

```text
USER
→ IDENTITY
→ AUTHORIZATION
→ KNOWLEDGE PERMISSION
→ TASK PURPOSE
→ WORK SEPARATION
→ ACTION CONTROL
→ MODEL + PLAN
→ CONTROLLED EXECUTION
→ VERIFICATION
→ DELIVERABLE
→ AUDIT
→ REVIEW
→ SAFE ISOLATION
→ OUTPUT
→ SECURE HANDOVER
```

**Trade-off:** More components and control points increase implementation complexity, but they provide the trust boundary required by the project.

**Verification:** End-to-end trace inspection and MVP acceptance test.

**Master trace:** Product definition, authoritative architecture, final governing principle.

---

## DEC-002 — Sovereignty is an architectural property

**Status:** ACCEPTED

**Decision:** Sovereign operation means the complete AI workflow can operate inside the organization's controlled environment.

Local components include LLMs, vision, OCR, embeddings, RAG, agents, tools, sandbox, verifier, audit, and deliverables.

External AI APIs are not required. External network access is denied by default.

**Rationale:** Keeping only the LLM local is insufficient if OCR, embeddings, retrieval, tools, or deliverable processing can leak confidential information externally.

**Trade-off:** Local operation can increase hardware, model-management, and operational requirements.

**Verification:** Demonstrate local endpoints, local vector database, local OCR, local embeddings, local files, blocked external network attempts, and audit logs.

**Master trace:** Technology principles; sovereign mode; definition of done.

---

## DEC-003 — Baseline technologies are replaceable behind contracts

**Status:** ACCEPTED

**Decision:** The following technologies are the initial baseline, not permanent vendor dependencies:

| Concern | Baseline |
|---|---|
| Backend | Python |
| API | FastAPI, Pydantic, Uvicorn |
| Frontend | TypeScript, React, Next.js, Tailwind CSS |
| Identity | Keycloak |
| Broad authorization | Keycloak roles / RBAC |
| Fine-grained authorization | OpenFGA |
| Policy | OPA |
| Database | PostgreSQL |
| Cache / temporary state | Redis |
| Parsing | Docling, PyMuPDF |
| OCR | PaddleOCR |
| Embeddings | BGE-M3 or replaceable equivalent |
| Vector DB | Qdrant |
| Local model serving | vLLM or replaceable local serving layer |
| Agent orchestration | LangGraph or replaceable stateful graph layer |
| Tool protocol | MCP-compatible internal architecture |
| Sandbox | Docker; gVisor where practical |
| Deliverables | python-docx, openpyxl, python-pptx, ReportLab |
| Observability | OpenTelemetry |
| Integrity | SHA-256 |
| Deployment | Linux, Docker Compose, NVIDIA CUDA where GPU is available |

**Rationale:** The architecture should survive model, serving-layer, vector-store, or orchestration changes.

**Trade-off:** Stable interfaces require additional abstraction and testing.

**Verification:** Replaceable subsystems expose stable internal contracts and documented degradation/fallback behavior.

**Master trace:** Technology baseline and replaceable-interface principle.

---

# 4. Identity, Authorization and Task Decisions

## DEC-004 — Separate authentication from authorization

**Status:** ACCEPTED

**Decision:** Authentication establishes who the user is; authorization determines what the user may do.

Keycloak is the baseline for identity, login, sessions, tokens, roles, and administrator management.

Initial roles:

- Operator
- Engineer
- Reviewer
- Administrator

OpenFGA is the baseline for fine-grained relationships such as department membership, document access, task execution, tool invocation, and deliverable approval.

OPA and OpenFGA are used together for policy decisions.

**Rationale:** Identity alone does not establish access to each resource or action.

**Security consequence:** The LLM is never the final authority for security permissions.

**Verification:** Positive and negative authorization tests, RBAC bypass tests, OpenFGA bypass tests, and policy decision trace inspection.

**Master trace:** Identity, authorization, and security testing sections.

---

## DEC-005 — Task Passport is mandatory

**Status:** ACCEPTED

**Decision:** Every controlled task must receive a persisted Task Passport before execution.

Required fields:

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

The Task Passport travels with task context and is consulted by RAG, model routing, tool invocation, workspace access, sandbox policy, review routing, and secure handover.

**Rationale:** Authorization based only on the user identity is insufficient. Confidential work requires task-scoped purpose, sensitivity, sources, tools, models, and output constraints.

**Trade-off:** Task creation adds workflow overhead, but makes scope explicit and auditable.

**Security rule:** Security-critical fields are immutable after execution begins unless changed through versioned audit and re-authorization.

**Verification:** Attempt execution without a passport; attempt unauthorized passport mutation; verify denial and audit trace.

**Master trace:** Task Passport section.

---

## DEC-006 — Default-deny policy evaluation

**Status:** ACCEPTED

**Decision:** Permission decisions return exactly:

```text
ALLOW
DENY
REQUIRE_APPROVAL
```

Policy evaluation occurs before knowledge release, tool execution, consequential actions, file access, and output release.

**Rationale:** Confidential systems must fail closed rather than depend on model intent.

**Trade-off:** Default-deny can create friction when policy configuration is incomplete.

**Required controls:**

- Deterministic policies
- Versioned policies
- Testable policy evaluation
- Auditable decisions
- Defined precedence
- Approval ownership
- Conflict handling
- Emergency disable behavior

**Verification:** Policy unit tests, bypass tests, conflict tests, and audit-event checks.

**Master trace:** Permission Engine and policy outcomes.

---

# 5. RAG and Knowledge Decisions

## DEC-007 — Authorization precedes evidence exposure

**Status:** ACCEPTED

**Decision:** Medha RAG shall not be treated as ordinary vector search.

Required sequence:

```text
QUERY
→ DETERMINE ALLOWED KNOWLEDGE
→ RETRIEVE RELEVANT KNOWLEDGE
→ APPLY PERMISSION FILTERING
→ RETURN AUTHORIZED EVIDENCE
```

Semantic relevance is not authorization.

**Rationale:** A highly relevant chunk must still be rejected if the current task or identity is not authorized to access it.

**Trade-off:** Permission-aware retrieval adds metadata, policy checks, and filtering overhead.

**Security consequence:** Unauthorized evidence must never be passed to the model merely because it is semantically relevant.

**Verification:** Cross-department retrieval tests, unauthorized-document tests, permission-filter bypass tests, and evidence exposure tests.

**Master trace:** Permission-aware RAG section.

---

## DEC-008 — Local multimodal ingestion

**Status:** ACCEPTED

**Decision:** Supported inputs include PDF, scanned PDF, DOCX, TXT, images, and industrial documents.

Ingestion follows:

```text
FILE
→ TYPE DETECTION
→ DOCUMENT PARSING
→ OCR IF REQUIRED
→ CHUNKING
→ METADATA EXTRACTION
→ LOCAL EMBEDDING
→ QDRANT
```

OCR runs locally and records text, tables, page references, OCR confidence, and document metadata.

Low-confidence OCR must be flagged and must not silently become authoritative evidence.

**Rationale:** Industrial source material is often scanned, image-based, or multimodal.

**Trade-off:** OCR and vision introduce uncertainty and additional verification requirements.

**Verification:** OCR quality measurement, page-reference checks, low-confidence handling tests, and multimodal evidence review.

**Master trace:** RAG and multimodal ingestion.

---

## DEC-009 — Evidence has explicit types

**Status:** ACCEPTED

**Decision:** Evidence must distinguish:

- Source fact
- Inference
- Calculation
- Recommendation

Important claims must preserve:

```text
SOURCE → EVIDENCE → CLAIM → ACTION → OUTPUT
```

**Rationale:** The system must not silently turn model inference into an organizational fact.

**Trade-off:** Evidence metadata increases deliverable and UI complexity.

**Verification:** Claim-to-source trace test and unsupported-claim detection.

**Master trace:** Evidence model and definition of done.

---

# 6. Work Separation, Model and Agent Decisions

## DEC-010 — Work Separation is explicit

**Status:** ACCEPTED

**Decision:** Medha classifies work before planning execution.

| Work type | Controlled pipeline |
|---|---|
| Document | Parsing, evidence extraction, document generation |
| Spreadsheet | Workbook access and spreadsheet-specific tools |
| Code | Coding tools, versioned workspace, tests, sandbox |
| Image | Multimodal processing and visual evidence |
| Calculation | Controlled calculator or execution tool |
| Analysis | Agent reasoning, evidence graph, verifier |

Mixed tasks must explicitly declare their work types in the Task Passport and execution plan.

**Rationale:** Different operations have different tools, risks, verification methods, and model requirements.

**Trade-off:** Classification adds an orchestration stage but reduces unrestricted agent behavior.

**Verification:** Mixed-task tests and incorrect-work-type routing tests.

---

## DEC-011 — Model Router selects capability, not a fixed model name

**Status:** ACCEPTED

**Decision:** Model selection considers:

- Task type
- Modality
- Complexity
- Sensitivity
- Required tools
- GPU availability
- Latency
- Model capability

The architecture supports replaceable categories:

- Lightweight text
- Reasoning
- Multimodal
- Coding

Models are locally served in sovereign mode.

**Rationale:** No single model should be assumed to be optimal for every confidential task.

**Trade-off:** Multiple models increase deployment and evaluation complexity.

**Required transparency:** UI and audit record the selected model, selection reason, required tools, execution plan, constraints, and fallback behavior.

**Verification:** Two-task routing demonstration and routing accuracy measurement.

**Master trace:** Model Router section and metrics.

---

## DEC-012 — Stateful bounded agent graph

**Status:** ACCEPTED

**Decision:** The Agent Planner follows a graph equivalent to:

```text
UNDERSTAND
→ RETRIEVE
→ PLAN
→ REQUEST ACTION
→ ACTION GATE
→ EXECUTE
→ OBSERVE
→ VERIFY
→ REPLAN
→ DELIVER
```

Retries and replanning are bounded.

The agent stops on:

- Policy denial
- Missing authorization
- Repeated verification failure
- Excessive loops
- Unsafe tool request
- Ambiguous high-risk condition

**Rationale:** A bounded graph provides controllable state transitions instead of an unrestricted autonomous loop.

**Trade-off:** Bounded execution may stop before completing a difficult task, but safe stopping is preferable to uncontrolled execution.

**Verification:** Loop-limit tests, policy-denial tests, unsafe-tool tests, and verification-failure tests.

---

# 7. Tool, Action Gate and Sandbox Decisions

## DEC-013 — Tool Registry is mandatory

**Status:** ACCEPTED

**Decision:** Every tool is registered with:

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

Initial tools include document reader/search, calculator, spreadsheet reader/writer, file manager, DOCX/PPTX generators, and code executor.

**Rationale:** Unregistered tools create invisible capabilities and weaken policy enforcement.

**Verification:** Tool-registration validation and unknown-tool rejection tests.

---

## DEC-014 — Every consequential action passes the Action Gate

**Status:** ACCEPTED

**Decision:**

```text
AGENT
→ ACTION GATE
→ POLICY CHECK
→ ALLOW / DENY / REQUIRE_APPROVAL
→ TOOL
```

The Action Gate is independent of model-generated reasoning.

**Rationale:** The model may propose an action, but cannot authorize its own execution.

**Trade-off:** Additional checks add latency but establish a critical trust boundary.

**Verification:** Action Gate bypass tests, approval tests, and denied-action audit checks.

---

## DEC-015 — Task-scoped controlled workspace

**Status:** ACCEPTED

**Decision:** Files, code, PDFs, images, spreadsheets, presentations, generated files, and intermediate artifacts are handled inside a controlled workspace.

Each working artifact tracks:

```text
owner
task_id
classification
permissions
version
source
status
```

Agent access is task-scoped and policy-checked.

**Rationale:** Workspace isolation prevents unrestricted access to host or unrelated task data.

**Verification:** Cross-task file access tests and unauthorized artifact access tests.

---

## DEC-016 — Generated code never executes directly on the host

**Status:** ACCEPTED

**Decision:** All generated code runs inside a sandbox.

Baseline controls:

- Isolated filesystem
- CPU limits
- Memory limits
- Execution timeout
- Restricted permissions
- Controlled mounts
- No unrestricted host access
- Network disabled by default

Docker is the baseline. gVisor may be used for hardened deployments.

**Rationale:** Generated code is untrusted execution content.

**Trade-off:** Sandboxing introduces startup overhead and resource-management complexity.

**Verification:** Sandbox escape tests, host-access tests, resource-limit tests, network tests, and interrupted-execution tests.

---

# 8. Verification and Deliverable Decisions

## DEC-017 — Verification is a separate control stage

**Status:** ACCEPTED

**Decision:** The Verifier checks:

- Schema
- Calculations
- Evidence
- Document consistency
- Tool results
- Policy compliance
- Unsupported claims
- Output completeness

Verification types:

- Rule
- Calculation
- Execution
- Evidence
- Policy

Failure path:

```text
FAIL
→ FEEDBACK
→ REPLAN
→ EXECUTE
→ VERIFY
```

Retries are bounded and visible in audit.

**Rationale:** Generation success does not imply correctness or policy compliance.

**Trade-off:** Verification adds computation and latency.

**Verification:** Verification pass-rate metric, injected-error tests, and failed-verification replay.

---

## DEC-018 — Deliverables are packages, not isolated files

**Status:** ACCEPTED

**Decision:** A deliverable package contains the final output plus its provenance and integrity metadata.

Example:

```text
MEDHA-PACKAGE/
├── approval_note.docx
├── evidence.json
├── verification.json
├── audit.json
└── manifest.json
```

The package must preserve source references, evidence, verification result, Task ID, audit reference, and manifest.

**Rationale:** A file without provenance cannot provide a complete trust record.

**Verification:** Package completeness and manifest consistency tests.

---

## DEC-019 — Review mode is policy-selected

**Status:** ACCEPTED

| Review mode | Use |
|---|---|
| Human | High-risk, sensitive, ambiguous, or consequential work |
| Minimal-change iterative | Limited corrections |
| Auto | Only low-risk work explicitly satisfying policy |

The LLM cannot decide by itself that output is safe for automatic release.

**Rationale:** Human oversight must remain available where risk requires it.

**Trade-off:** Human review can reduce throughput but increases control for consequential work.

**Verification:** Risk-to-review routing tests and approval bypass tests.

---

## DEC-020 — Secure handover is a controlled release boundary

**Status:** ACCEPTED

**Decision:**

```text
OUTPUT
→ PACKAGE
→ HASH
→ ACCESS CONTROL
→ AUTHORIZED RECIPIENT
```

The handover package includes:

- Manifest
- SHA-256 integrity hash
- Task ID
- Timestamp
- Verification status
- Access policy

**Rationale:** Generation is not equivalent to authorized release.

**Trade-off:** Packaging and hashing add processing steps but make output integrity and release auditable.

**Verification:** Unauthorized-release tests, hash verification, recipient-policy tests, and manifest validation.

---

# 9. Audit and Observability Decisions

## DEC-021 — Full decision trace is required

**Status:** ACCEPTED

Baseline:

- OpenTelemetry
- PostgreSQL or equivalent durable audit store

The trace records who, when, what, why, data, model, tool, action, policy, evidence, verification, approval, and output.

The following chain must be reconstructable:

```text
Authentication
→ RBAC
→ Task Passport
→ RAG permission decision
→ Model selection
→ Plan generation
→ Action Gate
→ Tool execution
→ Sandbox execution
→ Verification
→ Deliverable
→ Audit
→ Review
→ Handover
```

**Rationale:** Confidential autonomous work must be reconstructable after the fact.

**Verification:** Trace reconstruction test from task ID to final handover.

---

## DEC-022 — Security failures are traceable

**Status:** ACCEPTED

Every security failure must be traceable to:

```text
task
identity
policy decision
resource
action
audit event
```

Positive and negative security tests are required, with CI where practical.

**Rationale:** A failed security control must be diagnosable rather than merely reported as an error.

**Verification:** Injected security failures and trace completeness checks.

---

# 10. Deployment and Sovereignty Decisions

## DEC-023 — Deployment modes are implementation choices under one architecture

**Status:** ACCEPTED

Medha may support:

1. Developer local mode
2. Prototype/single-workstation mode
3. On-premise production mode
4. Air-gapped mode

These modes must preserve the same security architecture.

**Rationale:** Development and demonstration environments differ from production, but control boundaries should not disappear.

**Trade-off:** Supporting multiple deployment modes increases operational documentation.

**Verification:** Environment-specific smoke tests and sovereign-mode demonstration.

---

## DEC-024 — External network is deny-by-default

**Status:** ACCEPTED

External network access is disabled by default for the sovereign workflow.

Any required network capability must be explicitly controlled by policy rather than granted implicitly to an agent or tool.

**Rationale:** Network egress is a direct data-exfiltration path.

**Verification:** Blocked-network demonstration and network-policy tests.

---

## DEC-025 — Local processing of confidential AI functions

**Status:** ACCEPTED

In sovereign mode, the following remain local:

- LLM inference
- Vision
- OCR
- Embeddings
- RAG
- Agents
- Tools
- Sandbox
- Verification
- Audit
- Deliverables

**Rationale:** Partial localization does not establish sovereignty.

**Verification:** Endpoint and dependency inspection plus blocked-egress test.

---

# 11. MVP and Sequencing Decisions

## DEC-026 — Prove one vertical slice before broad implementation

**Status:** ACCEPTED

Primary MVP:

```text
Scanned inspection PDF
→ Local OCR
→ Permission-aware RAG
→ Task Passport
→ Model Router
→ Agent Planner
→ Action Gate
→ Controlled tool
→ Docker sandbox
→ Verifier
→ DOCX deliverable
→ Audit
→ Review
→ Secure handover
```

The primary industrial workflow uses:

- Scanned inspection report
- Internal SOP/manual
- Inspection photograph

Output: evidence-linked inspection analysis and approval note with classification, authorization, verification, audit, and integrity metadata.

A secondary coding workflow may follow the same control pattern.

**Rationale:** Demonstrable end-to-end control behavior is more valuable for the MVP than isolated subsystem breadth.

**Trade-off:** Some features are deferred while the trust workflow is proven.

**Verification:** End-to-end MVP acceptance checklist.

---

## DEC-027 — Development phases may be interleaved for the vertical slice

**Status:** ACCEPTED

The Master `/plan` defines phases 0–19 from architecture/specification through end-to-end demo.

The vertical slice may interleave phases when doing so produces a working end-to-end path sooner, provided interfaces, tests, security implications, migrations, observability, and exit criteria remain defined.

**Rationale:** Strictly completing every subsystem in isolation can delay discovery of integration failures.

**Verification:** Phase exit criteria and vertical-slice test evidence.

---

# 12. Security Testing Decisions

## DEC-028 — Security testing is part of architecture, not a final-only activity

**Status:** ACCEPTED

Required coverage includes:

- Unauthorized document access
- RBAC bypass
- OpenFGA bypass
- OPA bypass
- RAG permission bypass
- Prompt injection
- Malicious documents
- Malicious code
- Sandbox escape
- Tool abuse
- Unauthorized file access
- External network attempts
- Data leakage
- Approval bypass
- Unauthorized output release
- Excessive agent loops
- Malicious multimodal inputs

**Rationale:** Each major control boundary needs adversarial validation.

**Trade-off:** Security testing consumes development time, but it directly supports the project's central trust claim.

**Verification:** Positive and negative test suites, CI where practical, and traceability to affected controls.

---

# 13. Metrics Decisions

## DEC-029 — Benchmark before promising thresholds

**Status:** ACCEPTED

Measure experimentally:

- Task completion rate
- Retrieval quality
- Authorization rejection rate
- OCR quality
- Model-routing accuracy
- Verification pass rate
- Sandbox success rate
- End-to-end latency
- Human-review rate
- Failed-action rate
- Blocked external-network attempts
- Evidence coverage

**Decision:** Fixed performance targets are not claimed before baseline measurement.

**Rationale:** Hardware, models, document types, and workload affect performance.

**Verification:** Define formulas, collection points, datasets, reporting frequency, and MVP thresholds after baseline measurement.

**Master trace:** Performance and quality metrics.

---

# 14. UI and Transparency Decisions

## DEC-030 — The UI must expose control state

**Status:** ACCEPTED

The UI shall not imitate a normal ChatGPT interface.

Required screens include:

- Login
- Dashboard
- New Task
- Task Passport
- Workspace
- Knowledge
- Agent Execution
- Evidence
- Review
- Deliverables
- Audit / Trace
- Administration

Where authorized, the UI exposes:

- Identity and role
- Task ID and sensitivity
- Task purpose and allowed sources
- Allowed tools and network policy
- Selected model and rationale
- Execution plan and current state
- Evidence for important claims
- Verification results/failures
- Review mode and approval status
- Deliverable manifest and integrity status
- Audit timeline

**Rationale:** Trust controls should be observable rather than hidden.

**Security rule:** UI visibility itself is permission-controlled.

**Verification:** Role-based UI tests and unauthorized-data exposure tests.

---

# 15. Failure and Degraded-State Decisions

## DEC-031 — Safe stopping is preferred to unsafe completion

**Status:** ACCEPTED

The system must stop rather than continue when:

- Authorization is missing
- Policy denies an action
- Required evidence is unavailable
- Verification repeatedly fails
- Agent loops exceed limits
- A tool request is unsafe
- A high-risk condition is ambiguous
- Sandbox execution fails

Failures must preserve status/log information without exposing protected resources.

**Rationale:** In confidential industrial work, incomplete safe behavior is preferable to uncontrolled completion.

**Verification:** Failure injection and recovery tests.

---

## DEC-032 — Replaceable subsystems require degradation behavior

**Status:** ACCEPTED

Each replaceable subsystem must define a stable contract and a fallback or degradation mode.

Examples:

| Subsystem | Required degradation principle |
|---|---|
| Model serving | Do not silently switch to an unauthorized model |
| OCR | Flag low confidence; do not silently promote uncertain text |
| RAG | Do not return evidence when permission cannot be established |
| Tool | Deny if registration/policy state is unavailable |
| Sandbox | Do not execute code outside isolation |
| Audit | Do not silently lose security-critical trace data |
| Handover | Do not release output when integrity/access checks cannot complete |

**Rationale:** Dependency failure must not become a security bypass.

**Verification:** Fault-injection tests for each critical boundary.

---

# 16. Data, Integrity and Operational Decisions

## DEC-033 — SHA-256 is the MVP integrity mechanism

**Status:** ACCEPTED

Secure handover uses SHA-256 to bind the delivered package to its recorded manifest.

**Rationale:** The Master `/plan` explicitly selects SHA-256 as the integrity baseline.

**Trade-off:** Hashing proves package integrity relative to the recorded digest; it does not by itself prove authorization or correctness.

**Verification:** Modify package contents and verify hash mismatch.

---

## DEC-034 — Durable audit storage is required

**Status:** ACCEPTED

Audit data is stored in PostgreSQL or an equivalent durable audit store, with OpenTelemetry used for observability.

**Rationale:** Security and compliance traces cannot depend only on transient process logs.

**Open implementation questions:** Exact retention, archival, backup, tamper-evidence, and operational access controls require deployment-specific definition.

---

# 17. Assumptions

The following assumptions are used by the Master `/plan` but may require validation during implementation:

1. A suitable organization-controlled Linux environment is available for deployment.
2. GPU resources are available for the prototype or production environment as required by the selected local models.
3. Local model serving can meet the demonstrated task requirements after benchmarking.
4. Keycloak, OpenFGA, and OPA can be deployed and integrated without weakening the control architecture.
5. Qdrant can store the required metadata alongside vector representations.
6. Local OCR and multimodal models can process the selected MVP inspection documents with measurable quality.
7. Docker provides the baseline sandbox boundary for the prototype; hardened deployments may add gVisor where practical.
8. Industrial documents used for the demonstration can be classified and permissioned without exposing real confidential information to an unauthorized audience.
9. The selected deliverable libraries can generate the required MVP document formats.
10. The project can create representative test data for positive and negative security tests.
11. Specific model names and versions remain replaceable until capability, hardware, licensing, and offline behavior are verified.
12. Performance thresholds will be established from measured baselines rather than assumed in advance.

---

# 18. Rejected or Non-Selected Alternatives

## DEC-035 — Unrestricted chatbot architecture

**Status:** REJECTED

**Alternative:** `USER → CHATBOX → LLM → ANSWER`

**Reason for rejection:** Does not provide the required task-scoped authorization, controlled tool access, evidence authorization, verification, audit, review, or secure handover.

---

## DEC-036 — LLM as security authority

**Status:** REJECTED

**Alternative:** Allow the model to decide whether a user may access data or execute a tool.

**Reason for rejection:** Model reasoning is not an authoritative security control and can be influenced by prompts or retrieved content.

---

## DEC-037 — Ordinary vector RAG without permission filtering

**Status:** REJECTED

**Alternative:** Retrieve top-k semantically relevant chunks and send them directly to the model.

**Reason for rejection:** Semantic relevance does not establish authorization.

---

## DEC-038 — Direct host execution of generated code

**Status:** REJECTED

**Alternative:** Execute generated code directly on the Medha host.

**Reason for rejection:** Creates unacceptable host-resource and data-access risk.

---

## DEC-039 — Cloud AI dependency in sovereign mode

**Status:** REJECTED

**Alternative:** Send confidential content to external LLM, OCR, embedding, or AI APIs.

**Reason for rejection:** Conflicts with the sovereign/on-premise requirement and creates external data-exfiltration paths.

---

## DEC-040 — One model for every task

**Status:** REJECTED

**Alternative:** Hard-code one model for document, coding, reasoning, and multimodal work.

**Reason for rejection:** Conflicts with the required model-selection behavior and reduces capability flexibility.

---

## DEC-041 — Deliverable as a file only

**Status:** REJECTED

**Alternative:** Return only `approval_note.docx` or another final file.

**Reason for rejection:** Omits evidence, verification, audit reference, provenance, and integrity metadata.

---

## DEC-042 — Hidden control state

**Status:** REJECTED

**Alternative:** Present Medha as an ordinary chat UI with hidden model/tool/evidence/policy state.

**Reason for rejection:** The project requires visible control, security, evidence, verification, review, and audit status.

---

# 19. Trade-off Summary

| Decision area | Selected approach | Benefit | Cost / trade-off |
|---|---|---|---|
| Architecture | Controlled agent workflow | Strong trust boundaries | More components |
| Deployment | Local/on-prem/air-gapped capable | Confidentiality and sovereignty | Infrastructure burden |
| Authorization | RBAC + OpenFGA + OPA | Broad + fine-grained + policy control | Integration complexity |
| RAG | Permission-aware | Prevents unauthorized evidence exposure | Extra filtering/metadata |
| Models | Router + multiple local categories | Task specialization | Model management |
| Agents | Bounded state graph | Controlled autonomy | May stop on hard tasks |
| Tools | Registry + Action Gate | Explicit capabilities | Extra policy checks |
| Code | Docker sandbox | Limits host exposure | Resource/startup overhead |
| Verification | Dedicated verifier | Detects errors/unsupported claims | Added latency |
| Review | Policy-selected modes | Human oversight where needed | Reduced automation for risky work |
| Deliverables | Evidence-backed package | Provenance + integrity | Larger output package |
| Audit | Full trace | Reconstruction and accountability | Storage/operational overhead |
| UI | Control-oriented | Transparency | More complex than chat UI |

---

# 20. Open Questions

These questions do not change the current architecture; they require explicit resolution before the affected production behavior is finalized.

## OQ-001 — Exact model set
Which specific open-weight models and versions will be deployed for lightweight text, reasoning, multimodal, and coding categories after hardware and capability benchmarking?

## OQ-002 — GPU capacity
What exact GPU memory, concurrency, quantization, and latency profile is available on the target workstation/server?

## OQ-003 — Model fallback policy
What is the approved fallback when the preferred local model is unavailable or overloaded, and what sensitivity restrictions apply to fallback models?

## OQ-004 — Authorization policy ownership
Who owns approval policies for departments, document classifications, tools, and deliverable release in a production deployment?

## OQ-005 — Policy precedence
What is the exact precedence order when Keycloak roles, OpenFGA relationships, Task Passport restrictions, and OPA rules produce conflicting outcomes?

## OQ-006 — Approval ownership
Which roles can approve high-risk tool actions and final deliverables for each work type?

## OQ-007 — Document classification
What organization-specific classification labels and handling rules will be mapped into the metadata model?

## OQ-008 — RAG freshness/versioning
What is the approved procedure for document replacement, version retirement, stale embeddings, and re-indexing?

## OQ-009 — OCR confidence threshold
What empirical confidence threshold should trigger manual review for MVP documents?

## OQ-010 — Vision verification
What verification rules will be used before visual observations from photographs or drawings can become evidence-backed claims?

## OQ-011 — Sandbox hardening
Which workloads require baseline Docker isolation and which require gVisor or another hardened runtime?

## OQ-012 — Network policy exceptions
Are any internal network tools required in production, and if so, what explicit allowlist and approval policy governs them?

## OQ-013 — Audit retention
How long must audit and trace records be retained, and what archival or tamper-evidence requirements apply?

## OQ-014 — Backup and restore
What RPO/RTO requirements apply to PostgreSQL, Qdrant, workspace artifacts, policies, and audit data?

## OQ-015 — Secure handover recipients
How are recipients identified and authorized, especially for external or cross-department delivery?

## OQ-016 — Metric thresholds
What measured MVP thresholds constitute acceptable retrieval, OCR, routing, verification, sandbox, latency, and evidence coverage performance?

## OQ-017 — Production identity integration
Will the production deployment use only Keycloak-managed identities or integrate with an existing enterprise identity provider?

## OQ-018 — Air-gapped artifact lifecycle
How will model weights, container images, Python packages, OCR assets, and other dependencies be transferred, verified, patched, and approved for an air-gapped environment?

---

# 21. Decision Verification Matrix

| Decision | Primary verification |
|---|---|
| DEC-001 | End-to-end controlled workflow |
| DEC-002 | Sovereignty demonstration |
| DEC-003 | Interface/dependency replacement test |
| DEC-004 | Auth/RBAC/OpenFGA/OPA tests |
| DEC-005 | Task Passport enforcement tests |
| DEC-006 | Default-deny and policy tests |
| DEC-007 | RAG authorization tests |
| DEC-008 | OCR/multimodal quality tests |
| DEC-009 | Claim-to-evidence trace |
| DEC-010 | Work-separation tests |
| DEC-011 | Multi-task model-routing test |
| DEC-012 | Bounded-agent/failure tests |
| DEC-013 | Tool registration tests |
| DEC-014 | Action Gate bypass tests |
| DEC-015 | Workspace isolation tests |
| DEC-016 | Sandbox escape/resource/network tests |
| DEC-017 | Verification fault-injection tests |
| DEC-018 | Package/manifest completeness |
| DEC-019 | Review routing/approval tests |
| DEC-020 | Handover authorization/hash tests |
| DEC-021 | Full trace reconstruction |
| DEC-022 | Security failure traceability |
| DEC-023 | Environment smoke tests |
| DEC-024 | Network egress tests |
| DEC-025 | Local endpoint/dependency inspection |
| DEC-026 | MVP vertical-slice acceptance |
| DEC-027 | Phase exit criteria |
| DEC-028 | Security test suite |
| DEC-029 | Baseline benchmark |
| DEC-030 | Role-based UI tests |
| DEC-031 | Failure-injection tests |
| DEC-032 | Degraded-state/fault tests |
| DEC-033 | SHA-256 tamper test |
| DEC-034 | Durable audit recovery test |

---

# 22. Traceability to the Master `/plan`

| Master section | Decision coverage |
|---|---|
| Product definition | DEC-001, DEC-002 |
| Authoritative architecture | DEC-001 and all control-boundary decisions |
| Technology principles | DEC-003 |
| UI/UX | DEC-030 |
| Identity/RBAC/Task Passport | DEC-004, DEC-005, DEC-006 |
| Permission Engine | DEC-006 |
| RAG/multimodal | DEC-007, DEC-008, DEC-009 |
| Work Separation | DEC-010 |
| Model Router/Agent Planner | DEC-011, DEC-012 |
| Tool Registry/Action Gate/workspace/sandbox | DEC-013–DEC-016 |
| Verification/deliverables/review/handover | DEC-017–DEC-020 |
| Audit/sovereign mode | DEC-021–DEC-025 |
| Repository | Governed by DEC-003 and component contracts |
| MVP vertical slice | DEC-026, DEC-027 |
| Development phases | DEC-027 |
| Security testing | DEC-028 |
| Metrics | DEC-029 |
| Definition of done | All accepted decisions, especially DEC-001–DEC-002 and DEC-026 |
| Ownership/license | No architecture decision required here; follow the Master `/plan` wording |
| Final governing principle | DEC-001 |

---

# 23. Decision Change Process

A proposed architectural change must include:

1. Decision ID.
2. Current decision and proposed replacement.
3. Reason for change.
4. Affected components.
5. Security impact.
6. Sovereignty impact.
7. Authorization impact.
8. Audit/trace impact.
9. Verification plan.
10. Migration or rollback plan.
11. Effect on MVP and definition of done.
12. Updated traceability.

A change must not be accepted if it weakens the authoritative control model.

When a decision is replaced, retain the previous decision as `SUPERSEDED` rather than deleting it, so architectural history remains reconstructable.

---

# 24. Final Decision Principle

Medha AI is not defined by a particular LLM, vector database, orchestration framework, or UI framework.

It is defined by the controlled execution boundary:

```text
WHO
→ MAY DO WHAT
→ WITH WHICH KNOWLEDGE
→ FOR WHICH PURPOSE
→ USING WHICH MODEL
→ THROUGH WHICH TOOLS
→ UNDER WHICH POLICY
→ IN WHICH SANDBOX
→ WITH WHICH EVIDENCE
→ VERIFIED HOW
→ REVIEWED BY WHOM
→ RELEASED TO WHOM
→ WITH WHICH AUDIT TRAIL
```

Technology may change. The control model must not.

Any implementation that bypasses these controls is out of scope unless the deviation is explicitly documented, approved, tested, and demonstrated not to weaken security or sovereignty.

---

## Master Plan Reference

This document is derived from the user-provided authoritative Medha AI Master `/plan`. Specific technology versions, APIs, deployment behavior, and production policies should be added only after verification and should be recorded as explicit decisions rather than silently assumed.
