# Medha AI — Threat Model

**Subtitle:** Sovereign Controlled Multimodal AI Workbench for Confidential Industrial Work  
**Project:** Medha AI  
**Source of truth:** Master `/plan`  
**Status:** Threat-modeling document for the Medha AI controlled execution architecture  
**Year:** 2026

> This document is derived from the authoritative Medha AI Master `/plan`. It does not alter, weaken, remove, reorder, or bypass the Master Plan's architecture, security boundaries, workflow stages, MVP scope, or acceptance criteria. It translates the defined controls into threats, abuse cases, mitigations, residual risks, and test mappings.

---

## 1. Purpose

Medha AI handles confidential industrial knowledge while allowing controlled agentic work execution. Its threat model therefore treats security as a property of the **entire workflow**, not merely of the local model.

The authoritative workflow is:

```text
INPUT
→ IDENTITY
→ AUTHORIZATION
→ KNOWLEDGE AUTHORIZATION
→ TASK CONTEXT
→ WORK SEPARATION
→ ACTION CONTROL
→ MODEL + TOOL PLANNING
→ CONTROLLED EXECUTION
→ VERIFICATION
→ DELIVERABLE
→ AUDIT
→ REVIEW
→ ISOLATED EXECUTION
→ OUTPUT
→ SECURE HANDOVER
```

The core security assumption is:

> **The AI model is not a security boundary. Policy, authorization, isolation, verification, audit, and controlled handover are the security boundaries.**

---

## 2. Scope

### 2.1 In scope

This threat model covers:

- User identity and authentication
- RBAC and fine-grained authorization
- Task Passport
- Permission Engine
- Permission-aware RAG
- Local document ingestion and OCR
- Multimodal inputs
- Model Router
- Agent Planner
- Tool Registry
- Action Gate
- Controlled workspace
- Docker/gVisor sandbox
- Verification
- Deliverable Factory
- Review paths
- Audit / Trace
- Secure handover
- Sovereign and air-gapped operation
- External-network blocking
- Model/tool execution boundaries
- Task and data isolation
- Security testing and failure handling

### 2.2 Out of scope

The Master Plan does not define a complete enterprise-wide threat model for:

- Physical security of the organization's facility
- Hardware manufacturing security
- GPU firmware supply-chain security
- Enterprise identity-provider compromise outside Medha
- Physical destruction or disaster recovery beyond deployment/backup procedures
- Security of third-party organizational networks outside Medha's controlled boundary

These may be addressed later if required by deployment decisions.

---

## 3. Security objectives

The threat model protects the following objectives:

| Objective | Security goal |
|---|---|
| Confidentiality | Confidential industrial information must not be exposed to unauthorized users, models, tools, tasks, or external services. |
| Integrity | Evidence, calculations, files, policies, audit records, and deliverables must not be silently altered. |
| Authorization correctness | Every sensitive access or action must be policy-checked. |
| Task isolation | One task must not silently gain access to another task's data or workspace. |
| Execution isolation | Generated code must not directly execute against the host. |
| Sovereignty | Sensitive inference and processing remain inside the organization's controlled environment. |
| Evidence integrity | Important claims must remain linked to their supporting evidence. |
| Verification | Generated results must be checked before release. |
| Controlled release | Deliverables must only reach authorized recipients. |
| Bounded autonomy | Agent actions and retries must remain within policy-defined limits. |
| Accountability | Security-relevant events must be reconstructable from audit records. |

---

## 4. Assets

### 4.1 Primary assets

- Confidential industrial documents
- P&IDs and engineering drawings
- Inspection reports
- Photographs and scanned records
- SOPs and manuals
- Internal correspondence
- Financial and commercial information
- Vendor and contract information
- Business strategies
- Internal code
- Calculations and intermediate results
- Generated DOCX/XLSX/PPTX/PDF/code deliverables
- User identities and roles
- Task Passports
- Permission policies
- RAG indexes and metadata
- Model configurations
- Tool definitions
- Workspace artifacts
- Sandbox outputs
- Evidence records
- Verification results
- Audit traces
- Deliverable manifests
- SHA-256 integrity metadata

### 4.2 Security-sensitive metadata

Metadata can itself reveal sensitive information. Protect:

- Classification
- Department
- Document ownership
- Permissions
- Task purpose
- Task sensitivity
- Allowed sources
- Allowed tools
- Allowed models
- Approval requirements
- Network policy
- Audit references

---

## 5. Trust boundaries

### 5.1 User → Medha boundary

Untrusted or potentially compromised user input enters the system.

Controls:

- Authentication
- RBAC
- Task Passport
- Permission Engine
- Task-scoped access

### 5.2 Identity → authorization boundary

Authentication answers **who** the user is. Authorization answers **what** the user may do.

Controls:

- Keycloak
- RBAC
- OpenFGA
- OPA
- Permission Engine

The LLM cannot grant authorization.

### 5.3 Knowledge boundary

Documents and indexed knowledge cross into the RAG subsystem.

Controls:

- Classification
- Permissions
- Local ingestion
- Permission-aware retrieval
- Permission filtering before model exposure

### 5.4 Model boundary

The Model Router supplies an appropriate local model to the task.

Threat:

A model may produce incorrect, unsafe, manipulated, or overconfident output.

Control:

The model is treated as a reasoning component, not an authority. Policy checks remain outside model reasoning.

### 5.5 Agent → tool boundary

Agent-generated actions cross into tools.

Controls:

```text
AGENT
→ ACTION GATE
→ POLICY CHECK
→ ALLOW / DENY / REQUIRE_APPROVAL
→ TOOL
```

### 5.6 Agent → workspace boundary

Agent access to files and artifacts is task-scoped.

Controls:

- Task ID
- Ownership
- Classification
- Permissions
- Versioning
- Policy checks

### 5.7 Code → host boundary

Generated code is potentially hostile even when generated by a trusted user workflow.

Controls:

- Docker sandbox
- Optional gVisor
- Isolated filesystem
- CPU/memory limits
- Timeout
- Restricted permissions
- Controlled mounts
- Network disabled by default
- No unrestricted host access

### 5.8 Output → recipient boundary

Generated work products cross into the recipient's access domain.

Controls:

```text
OUTPUT
→ PACKAGE
→ HASH
→ ACCESS CONTROL
→ AUTHORIZED RECIPIENT
```

---

## 6. Threat actors

### 6.1 Malicious or compromised user

Capabilities may include:

- Attempting unauthorized document access
- Manipulating task purpose
- Requesting prohibited tools
- Attempting approval bypass
- Attempting to retrieve another user's information
- Attempting to exfiltrate sensitive data

### 6.2 Curious authorized user

A legitimate user may have access to Medha but attempt to retrieve information outside their business need.

This is important because authentication alone does not establish authorization.

### 6.3 Malicious document author

A document may intentionally contain:

- Prompt injection
- Misleading instructions
- Malicious code
- Hidden text
- Manipulated OCR content
- Adversarial visual content

### 6.4 Compromised or unsafe tool

A tool may contain implementation defects or unexpectedly perform operations outside its declared behavior.

### 6.5 Compromised model or model behavior

A model may:

- Hallucinate
- Follow malicious instructions embedded in documents
- Request unsafe actions
- Produce unsupported claims
- Attempt excessive tool calls

### 6.6 Malicious code or artifact

Generated or uploaded code may attempt:

- Host access
- File traversal
- Resource exhaustion
- Network communication
- Unauthorized data access

### 6.7 Accidental operator error

Examples:

- Incorrect sensitivity
- Wrong recipient
- Incorrect task purpose
- Incorrect policy configuration
- Accidental document exposure
- Unsafe tool configuration

### 6.8 Infrastructure compromise

A compromised service, dependency, container, or host could undermine Medha controls. The MVP should minimize blast radius and make such failures observable, while full infrastructure hardening remains deployment-specific.

---

## 7. Attack surfaces

| Surface | Main threats |
|---|---|
| Login/session | Credential misuse, session abuse |
| API Gateway | Unauthorized requests, malformed inputs |
| Task Passport | Scope manipulation, privilege expansion |
| RBAC/OpenFGA/OPA | Authorization bypass |
| RAG query | Cross-classification retrieval |
| Document ingestion | Malicious files, parser abuse |
| OCR | Manipulated or low-confidence evidence |
| Multimodal input | Adversarial images/diagrams |
| Model Router | Unsafe model selection or fallback |
| Agent Planner | Prompt injection, excessive autonomy |
| Tool Registry | Tool spoofing, schema abuse |
| Action Gate | Policy bypass |
| Workspace | Unauthorized file access |
| Sandbox | Escape, resource exhaustion |
| Network | Data exfiltration |
| Verifier | Verification bypass or incomplete checks |
| Deliverables | Unsupported or leaked output |
| Review | Approval bypass |
| Audit | Missing, altered, or incomplete trace |
| Handover | Unauthorized release |

---

## 8. Threat classification

Use the following severity levels for implementation triage:

| Severity | Meaning |
|---|---|
| Critical | Could defeat sovereignty, expose major confidential data, escape the execution boundary, or bypass core authorization. |
| High | Could expose sensitive information, execute unauthorized actions, or release unsafe deliverables. |
| Medium | Could cause limited leakage, incorrect results, operational disruption, or incomplete traceability. |
| Low | Limited impact with straightforward containment or recovery. |

Severity should be reassessed using actual deployment context and observed exploitability.

---

# 9. Threat scenarios and mitigations

## TM-001 — Unauthorized document access

**Threat:** A user attempts to retrieve a document they are authenticated to Medha but not authorized to access.

**Attack path:**

```text
USER → RAG QUERY → RETRIEVAL → UNAUTHORIZED DOCUMENT
```

**Risk:** Confidentiality breach.

**Controls:**

- RBAC
- OpenFGA
- OPA
- Permission Engine
- Document classification and permissions
- Permission filtering before evidence reaches the model
- Default-deny behavior
- Audit event

**Residual risk:** Incorrect permissions or policy configuration can still expose information.

**Test:** Attempt access with an authorized and unauthorized identity and verify different outcomes.

---

## TM-002 — RAG permission bypass

**Threat:** Semantic retrieval returns a relevant chunk from a document that the task is not permitted to access.

**Risk:** High confidentiality impact because relevance could be mistaken for authorization.

**Required rule:**

```text
QUERY
→ DETERMINE ALLOWED KNOWLEDGE
→ RETRIEVE
→ APPLY PERMISSION FILTERING
→ RETURN AUTHORIZED EVIDENCE
```

**Controls:**

- Permission-aware RAG
- Classification metadata
- Permission metadata
- Task Passport
- Permission Engine

**Residual risk:** Metadata inconsistency or implementation defects.

**Test:** Index documents with different permissions and confirm unauthorized chunks never reach the model.

---

## TM-003 — RBAC bypass

**Threat:** A user manipulates an API or UI request to access an operation outside their role.

**Controls:**

- Keycloak roles
- Backend authorization
- OpenFGA
- OPA
- Default deny
- Server-side enforcement

**Residual risk:** Configuration errors or untested endpoints.

**Test:** Invoke protected operations directly without relying on UI restrictions.

---

## TM-004 — OpenFGA authorization bypass

**Threat:** Fine-grained relationship checks are omitted or incorrectly interpreted.

**Controls:**

- OpenFGA
- Permission Engine
- Policy decision logging
- Negative authorization tests

**Test:** Attempt document, task, tool, and deliverable operations across unauthorized relationships.

---

## TM-005 — OPA policy bypass

**Threat:** A component performs a consequential action without consulting the applicable policy.

**Controls:**

- Central policy evaluation
- Action Gate
- Pre-action checks
- Versioned/auditable decisions

**Test:** Attempt direct tool execution while bypassing the policy path.

---

## TM-006 — Task Passport manipulation

**Threat:** A user or agent changes purpose, sensitivity, allowed sources, allowed tools, allowed models, or network policy after authorization.

**Controls:**

- Persisted Task Passport
- Immutable security-critical fields after execution begins
- Versioning if changes are permitted
- Re-authorization on security-sensitive changes
- Audit event

**Residual risk:** Incorrect implementation of versioning or reauthorization.

**Test:** Attempt to expand task scope after execution starts.

---

## TM-007 — Privilege escalation through task purpose

**Threat:** A low-risk task is labeled as another purpose to gain access to sensitive knowledge or tools.

**Controls:**

- Purpose stored in Task Passport
- Permission Engine
- Policy-controlled model/tool selection
- Audit trail
- Approval requirements

**Test:** Change purpose while holding the same identity and verify policy outcome.

---

## TM-008 — Prompt injection from documents

**Threat:** A malicious document contains instructions such as commands to reveal secrets, ignore policy, or execute tools.

**Attack path:**

```text
DOCUMENT
→ OCR/PARSER
→ RAG
→ MODEL
→ MALICIOUS ACTION
```

**Controls:**

- Treat retrieved content as data/evidence, not authority
- Action Gate
- Permission Engine
- Tool policies
- Verification
- Bounded agent loop
- Human review for high-risk work

**Residual risk:** Models can still produce unsafe proposals.

**Test:** Seed documents with adversarial instructions and verify they cannot directly authorize actions.

---

## TM-009 — Malicious scanned document

**Threat:** A scanned PDF contains hidden or misleading content intended to manipulate OCR or downstream reasoning.

**Controls:**

- Local OCR
- OCR confidence
- Source references
- Evidence classification
- Verification
- No silent conversion of inference into fact

**Test:** Submit adversarial scanned documents and confirm low-confidence or conflicting content is flagged.

---

## TM-010 — Malicious multimodal input

**Threat:** A photograph, diagram, or engineering image contains misleading visual information or adversarial content.

**Controls:**

- Vision output treated as model-generated observation
- Evidence distinction
- Verification before authoritative claims
- Human review for ambiguous/high-risk cases

**Residual risk:** Visual model errors and adversarial inputs remain possible.

**Test:** Use ambiguous and adversarial images and verify uncertain observations are not silently treated as facts.

---

## TM-011 — OCR confidence abuse

**Threat:** Incorrect OCR is treated as authoritative source text.

**Controls:**

- OCR confidence metadata
- Page references
- Low-confidence flags
- Evidence verification
- Source-to-claim linkage

**Test:** Inject deliberately poor scans and verify confidence warnings propagate to evidence and output.

---

## TM-012 — Cross-task data leakage

**Threat:** Agent or user obtains files, RAG evidence, workspace artifacts, or intermediate outputs from another task.

**Controls:**

- Task-scoped workspace
- Task Passport
- Resource permissions
- Permission Engine
- Artifact ownership
- Audit trail

**Test:** Attempt file and retrieval access using another task ID.

---

## TM-013 — Unsafe model selection

**Threat:** The Model Router selects a model that lacks required capability or violates task sensitivity constraints.

**Controls:**

- Allowed model list in Task Passport
- Model policy
- Model capability metadata
- Local serving
- Explainable selection rationale
- Audit record

**Test:** Present tasks requiring different capabilities and verify selection follows policy.

---

## TM-014 — Unsafe fallback model

**Threat:** Primary model becomes unavailable and the fallback silently violates task constraints.

**Controls:**

- Explicit fallback behavior
- Allowed model policy
- Task sensitivity constraints
- Audit event
- Fail closed where no compliant fallback exists

**Test:** Disable the primary model and verify the fallback is either authorized or blocked.

---

## TM-015 — Excessive agent loops

**Threat:** Agent repeatedly replans or calls tools, causing resource exhaustion or uncontrolled behavior.

**Controls:**

- Bounded retries
- Maximum loop limits
- Resource limits
- Stop on repeated verification failure
- Stop on unsafe tool requests
- Audit trace

**Test:** Create a task that intentionally causes repeated failures and verify termination.

---

## TM-016 — Unauthorized tool invocation

**Threat:** Agent requests a tool not permitted by the Task Passport.

**Controls:**

- Tool Registry
- Required permissions
- Action Gate
- Policy decision
- Default deny

**Test:** Request each prohibited tool from the agent and verify denial.

---

## TM-017 — Tool schema abuse

**Threat:** Malformed or unexpected tool parameters are used to perform unintended operations.

**Controls:**

- Input schemas
- Output schemas
- Action Gate
- Risk levels
- Validation
- Controlled workspace

**Test:** Submit invalid, boundary, and malicious tool parameters.

---

## TM-018 — Tool impersonation or unregistered tool

**Threat:** Agent attempts to invoke a tool outside the registered Tool Registry.

**Controls:**

- Registry-only invocation
- Stable tool IDs
- Required permissions
- Action Gate

**Test:** Attempt invocation using an unknown tool ID.

---

## TM-019 — Host access through generated code

**Threat:** Generated code attempts to access host filesystem, processes, credentials, or devices.

**Controls:**

- Docker sandbox
- Optional gVisor
- Isolated filesystem
- Controlled mounts
- Restricted permissions
- No unrestricted host access

**Test:** Execute code attempting host filesystem and process access.

---

## TM-020 — Sandbox escape

**Threat:** Malicious code attempts to escape the execution environment.

**Controls:**

- Docker isolation
- gVisor where practical
- Restricted mounts
- Minimal permissions
- Resource limits
- Network disabled
- No unrestricted host access

**Residual risk:** Container/runtime vulnerabilities remain possible.

**Test:** Execute sandbox-escape test cases and verify host resources remain inaccessible.

---

## TM-021 — Sandbox resource exhaustion

**Threat:** Code consumes excessive CPU, memory, disk, or execution time.

**Controls:**

- CPU limits
- Memory limits
- Timeout
- Controlled workspace
- Bounded execution

**Test:** Run CPU-, memory-, disk-, and time-intensive code.

---

## TM-022 — Network exfiltration

**Threat:** A model, tool, document, or generated code attempts to transmit confidential information externally.

**Controls:**

- External network denied by default
- Local model serving
- Local OCR
- Local embeddings
- Local RAG
- Sandbox network restrictions
- Visible blocked-network demonstration
- Audit event

**Test:**

```text
Sandbox → external endpoint
```

must be blocked and recorded.

---

## TM-023 — External AI API leakage

**Threat:** Sensitive content is sent to an external AI service.

**Controls:**

- Sovereign mode
- Local models
- No external AI APIs required
- Network restrictions
- Audit/trace

**Test:** Attempt external model/API access and verify blocking.

---

## TM-024 — Unauthorized file access

**Threat:** Agent or user accesses files outside the task-scoped workspace.

**Controls:**

- Workspace permissions
- Task Passport
- Permission Engine
- Controlled mounts
- Action Gate

**Test:** Attempt path traversal and cross-task file access.

---

## TM-025 — Malicious uploaded code

**Threat:** User-provided code executes destructive or unauthorized operations.

**Controls:**

- Sandbox-only execution
- Network disabled
- Resource limits
- Restricted permissions
- Audit

**Test:** Execute malicious code samples inside the sandbox.

---

## TM-026 — Evidence tampering

**Threat:** Evidence is modified after being used to support a claim.

**Controls:**

- Source references
- Evidence records
- Version metadata
- Audit trail
- Package manifest
- SHA-256 integrity hash

**Test:** Modify a source artifact or evidence package and verify integrity/trace inconsistencies are detectable.

---

## TM-027 — Unsupported claim becomes organizational fact

**Threat:** Model inference is presented as a source fact.

**Controls:**

- Evidence types:
  - Source fact
  - Inference
  - Calculation
  - Recommendation
- Evidence-bound output
- Verifier
- Source → Evidence → Claim → Action → Output

**Test:** Use a prompt requiring an unsupported conclusion and verify it is marked as inference/uncertain or rejected.

---

## TM-028 — Verification bypass

**Threat:** A deliverable is released despite failed or missing verification.

**Controls:**

- Verifier
- Review routing
- Policy-controlled release
- Audit
- Secure handover

**Test:** Force a verification failure and attempt release.

---

## TM-029 — Repeated verification failure

**Threat:** Agent continues indefinitely after repeated failed verification.

**Controls:**

```text
FAIL
→ FEEDBACK
→ REPLAN
→ EXECUTE
→ VERIFY
```

with bounded retries.

**Test:** Force repeated failures and verify stop/escalation behavior.

---

## TM-030 — Approval bypass

**Threat:** Agent or user attempts to release high-risk work without required human approval.

**Controls:**

- Task Passport approval requirement
- Review policy
- Human review for high-risk work
- Action Gate
- Secure handover

**Test:** Attempt automatic release of a task requiring human approval.

---

## TM-031 — Automatic-review abuse

**Threat:** A high-risk task is incorrectly routed to automatic review.

**Controls:**

- Policy-defined review modes
- Task sensitivity
- Approval requirement
- LLM cannot decide its own release authority

**Test:** Create high-risk tasks and verify human review is enforced.

---

## TM-032 — Minimal-change review bypass

**Threat:** A supposedly small correction changes unrelated content or avoids required verification.

**Controls:**

- Modify only requested portion
- Rerun relevant verification
- Return to review
- Audit changes

**Test:** Request a narrow edit and verify unrelated content remains unchanged.

---

## TM-033 — Unauthorized output release

**Threat:** A valid deliverable is handed to an unauthorized recipient.

**Controls:**

- Access policy
- Recipient authorization
- Task ID
- Classification
- Manifest
- SHA-256 hash
- Secure handover

**Test:** Attempt handover to an unauthorized identity.

---

## TM-034 — Audit trace omission

**Threat:** A security-sensitive action occurs without a reconstructable audit trail.

**Controls:**

Audit must reconstruct:

```text
Authentication
→ RBAC
→ Task Passport
→ RAG permission decision
→ Model selection
→ Plan
→ Action Gate
→ Tool execution
→ Sandbox
→ Verification
→ Deliverable
→ Review
→ Handover
```

**Test:** Execute the full vertical slice and verify every required stage has trace events.

---

## TM-035 — Audit tampering or integrity failure

**Threat:** Audit records are modified or deleted to hide an action.

**Controls:**

- Durable audit store
- OpenTelemetry
- PostgreSQL/equivalent
- Integrity-aware event handling
- Access control
- Audit of security events

**Residual risk:** Full tamper-proof audit storage may require deployment-specific controls beyond the MVP.

**Test:** Attempt unauthorized modification/deletion and verify access is denied and/or modification is detectable.

---

## TM-036 — Model-generated policy override

**Threat:** Model output attempts to convince the system that it has permission to access data, invoke tools, or release output.

**Controls:**

> **LLM may propose; policy decides.**

- Permission Engine
- Action Gate
- Review
- Secure handover

**Test:** Prompt the model to declare itself authorized and verify no privilege changes.

---

## TM-037 — Prompt injection through tool output

**Threat:** A tool returns attacker-controlled text that instructs the agent to take an unauthorized action.

**Controls:**

- Tool outputs treated as data
- Action Gate
- Policy checks
- Bounded planning
- Verification

**Test:** Return adversarial instructions from a controlled tool and verify they cannot bypass policy.

---

## TM-038 — Classification downgrade

**Threat:** Sensitive material is incorrectly classified as lower sensitivity to obtain broader access or automatic release.

**Controls:**

- Task Passport sensitivity
- Resource classification
- Permission Engine
- Review policy
- Audit

**Test:** Attempt classification downgrade and verify authorization/review requirements remain enforced.

---

## TM-039 — Malicious dependency/container behavior

**Threat:** A compromised dependency or container image undermines application behavior.

**Controls:**

- Prefer self-hostable/open-source components
- Replaceable interfaces
- Controlled deployment
- Security testing
- Documented dependencies
- Container isolation

**Residual risk:** Dependency and supply-chain security requires operational scanning, provenance, patching, and deployment governance beyond the core MVP.

**Test:** Dependency/container validation should be included when the deployment pipeline is established.

---

## TM-040 — Configuration drift

**Threat:** Production policy or network configuration changes from the approved security design.

**Controls:**

- Versioned policies
- Deployment documentation
- Audit
- Configuration review
- Security tests
- Decisions log

**Test:** Validate critical security configuration at deployment/startup and during release checks.

---

# 10. Abuse-case matrix

| Abuse case | Expected result |
|---|---|
| Read unauthorized document | `DENY` |
| Retrieve unauthorized RAG chunk | `DENY` / filtered |
| Invoke prohibited tool | `DENY` |
| Execute unregistered tool | `DENY` |
| Change task sensitivity mid-run | Re-authorize or deny |
| Bypass Action Gate | `DENY` |
| Execute code on host | Blocked |
| Escape sandbox | Contained |
| Connect externally from sandbox | Blocked + audited |
| Send data to external AI | Blocked |
| Release high-risk output automatically | `REQUIRE_APPROVAL` |
| Release to unauthorized recipient | `DENY` |
| Publish unsupported claim | Verification failure / review |
| Exceed agent retry limit | Stop |
| Access another task's workspace | `DENY` |
| Use low-confidence OCR as authoritative fact | Flag / verification |
| Manipulate policy through model prompt | No policy effect |

---

# 11. Security control mapping

| Control | Threats primarily addressed |
|---|---|
| Keycloak | TM-003, TM-004, TM-005, TM-033 |
| RBAC | TM-001, TM-003, TM-007 |
| OpenFGA | TM-001, TM-004, TM-012, TM-033 |
| OPA | TM-005, TM-016, TM-030, TM-031 |
| Permission Engine | TM-001, TM-002, TM-006, TM-007, TM-016 |
| Task Passport | TM-006, TM-007, TM-012, TM-013, TM-030 |
| Permission-aware RAG | TM-001, TM-002, TM-012 |
| OCR confidence | TM-009, TM-011 |
| Evidence model | TM-027, TM-026 |
| Model Router | TM-013, TM-014 |
| Agent bounds | TM-008, TM-015, TM-036, TM-037 |
| Tool Registry | TM-016, TM-017, TM-018 |
| Action Gate | TM-008, TM-016, TM-018, TM-030, TM-036 |
| Workspace isolation | TM-012, TM-024 |
| Docker/gVisor | TM-019, TM-020, TM-021, TM-025 |
| Network deny-by-default | TM-022, TM-023 |
| Verifier | TM-027, TM-028, TM-029 |
| Review | TM-028, TM-030, TM-031, TM-032 |
| Audit / Trace | TM-026, TM-030, TM-034, TM-035 |
| SHA-256 manifest | TM-026, TM-033 |
| Secure handover | TM-033 |
| Versioned policy/configuration | TM-005, TM-006, TM-040 |

---

# 12. Security test plan

The Master Plan explicitly requires testing for:

- Unauthorized document access
- RBAC bypass
- OpenFGA bypass
- OPA policy bypass
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

Every security failure must be traceable to:

```text
TASK
→ IDENTITY
→ POLICY DECISION
→ RESOURCE
→ ACTION
→ AUDIT EVENT
```

### 12.1 Positive tests

Verify that legitimate authorized workflows succeed:

- Authorized user reads authorized document
- Authorized RAG evidence is returned
- Authorized tool executes
- Approved code runs in sandbox
- Valid deliverable passes verification
- Authorized reviewer approves
- Authorized recipient receives package

### 12.2 Negative tests

Verify that prohibited workflows fail:

- Unauthorized document retrieval
- Cross-task access
- Prohibited tool invocation
- Network connection
- Host filesystem access
- Sandbox escape attempt
- Approval bypass
- Unsupported output release
- Policy override by model
- Excessive retries

---

# 13. MVP security attack demonstration

The MVP should prioritize visible control behavior rather than merely showing successful AI output.

A strong security demonstration should show:

### Test A — RAG authorization

```text
Engineer
→ requests restricted document
→ Permission Engine
→ DENY
→ audit event
```

### Test B — Prompt injection

```text
Malicious document
→ OCR/RAG
→ model sees malicious instruction
→ Action Gate
→ policy refuses unauthorized action
→ audit event
```

### Test C — Sandbox

```text
Generated code
→ Docker sandbox
→ attempts external network/host access
→ BLOCK
→ audit event
```

### Test D — Human approval

```text
High-risk task
→ deliverable
→ REQUIRE_APPROVAL
→ reviewer
→ approval
→ secure handover
```

### Test E — Evidence

```text
Source
→ Evidence
→ Claim
→ Verification
→ Deliverable
```

The prototype should make these boundaries visible in the UI and audit trace.

---

# 14. Residual risk

Security controls reduce risk; they do not eliminate it.

Important residual risks include:

1. Incorrect identity or enterprise permission configuration.
2. Vulnerabilities in dependencies, containers, operating systems, or infrastructure.
3. Model hallucination or unsafe reasoning.
4. OCR and vision errors.
5. Incorrect document classification.
6. Incorrect or stale knowledge-base permissions.
7. Tool implementation defects.
8. Container/runtime vulnerabilities.
9. Human approval errors.
10. Configuration drift.
11. Compromised administrator credentials.
12. Unknown adversarial inputs.
13. Performance/resource exhaustion under unexpected workloads.
14. Operational mistakes during upgrades or model replacement.

Residual risk must be measured and revisited during implementation and deployment.

---

# 15. Fail-closed principles

When a security-critical decision cannot be established confidently, Medha should prefer containment over autonomous continuation.

Examples:

| Condition | Expected behavior |
|---|---|
| Identity unavailable | Stop |
| Authorization unavailable | Stop / deny |
| Knowledge permission unavailable | Do not expose evidence |
| Tool permission unavailable | Do not execute |
| Required model unavailable | Use only policy-approved fallback or stop |
| Verification repeatedly fails | Stop/escalate |
| High-risk ambiguity | Require review |
| Sandbox failure | Stop execution and preserve logs |
| External network attempt | Block and audit |
| Handover authorization unavailable | Do not release |

---

# 16. Security invariants

The following invariants must remain true:

1. The LLM cannot grant itself permissions.
2. Authentication does not imply authorization.
3. RAG relevance does not imply knowledge authorization.
4. Permission filtering occurs before unauthorized evidence reaches the model.
5. Every consequential action passes through the Action Gate.
6. Unregistered tools cannot execute.
7. Generated code cannot execute directly on the host.
8. Sandbox network access is disabled by default.
9. Agent retries are bounded.
10. High-risk work cannot silently bypass required review.
11. Unsupported claims cannot silently become organizational facts.
12. Audit must reconstruct security-relevant lifecycle events.
13. Secure handover must enforce recipient authorization.
14. Sovereign mode must not require external AI services.
15. Output must not bypass authorization, verification, audit, or handover boundaries.

---

# 17. Threat-model traceability to the authoritative workflow

| Workflow stage | Main threat classes |
|---|---|
| Identity | Credential/session abuse |
| Authorization | RBAC, OpenFGA, OPA bypass |
| Knowledge Authorization | Unauthorized RAG access |
| Task Context | Task Passport manipulation |
| Work Separation | Cross-purpose/capability abuse |
| Action Control | Tool abuse |
| Model + Tool Planning | Unsafe selection and prompt injection |
| Controlled Execution | Tool and workspace abuse |
| Verification | Unsupported/incorrect output |
| Deliverable | Data leakage and integrity issues |
| Audit | Missing/tampered trace |
| Review | Approval bypass |
| Isolated Execution | Sandbox escape/resource exhaustion |
| Output | Unauthorized release |
| Secure Handover | Recipient and integrity violations |

---

# 18. Threat-model verification metrics

The Master Plan requires experimental measurement rather than unsupported fixed promises.

Relevant measurements include:

- Authorization rejection rate
- Failed-action rate
- Verification pass rate
- Sandbox success rate
- Blocked external-network attempts
- Evidence coverage
- Retrieval quality
- OCR quality
- Human-review rate
- Task completion rate

Security-specific derived measures may include:

```text
Unauthorized Access Detection Rate
= blocked unauthorized attempts / total unauthorized test attempts
```

```text
Policy Enforcement Coverage
= policy-controlled consequential actions / total consequential actions
```

```text
Audit Trace Completeness
= required trace stages recorded / required trace stages
```

These should be benchmarked using repeatable positive and negative test datasets.

---

# 19. Threat-model acceptance criteria

The threat model is considered implemented for the MVP when:

- Core assets and trust boundaries are identified.
- Threat actors and attack surfaces are documented.
- Required security threats from the Master Plan have corresponding controls.
- Negative security tests exist for authorization, RAG, tools, sandbox, network, approval, output, and agent-loop behavior.
- Positive tests demonstrate legitimate authorized operation.
- Security failures produce traceable audit events.
- The vertical slice demonstrates at least one meaningful denial/blocking scenario.
- Sovereignty is demonstrated through observable local processing and blocked external network behavior.
- Residual risks are explicitly documented rather than hidden behind claims of complete security.

---

# 20. Relationship to other Medha documents

This document must remain consistent with:

```text
Master /plan
    ↓
spec.md
    ↓
architecture.md
    ↓
security.md
    ↓
threat-model.md
    ↓
rag-policy.md
    ↓
model-policy.md
    ↓
tool-policy.md
    ↓
audit-policy.md
    ↓
deployment.md
    ↓
decisions.md
```

### Document responsibilities

- `architecture.md` — what components exist and how they interact.
- `security.md` — security controls and security boundaries.
- `threat-model.md` — what can go wrong, how it can be attacked, what mitigates it, and how it is tested.
- `rag-policy.md` — knowledge-specific authorization and retrieval rules.
- `model-policy.md` — model-specific selection and capability rules.
- `tool-policy.md` — tool-specific execution and approval rules.
- `audit-policy.md` — audit event and trace rules.
- `deployment.md` — operational deployment and infrastructure procedures.
- `decisions.md` — recorded architecture choices and trade-offs.

---

# 21. Governing principle

Medha AI must never assume:

```text
LOCAL LLM = SAFE
```

Instead:

```text
TRUSTWORTHY MEDHA
=
IDENTITY
+ AUTHORIZATION
+ KNOWLEDGE PERMISSION
+ TASK SCOPE
+ POLICY
+ CONTROLLED TOOLS
+ ACTION GATE
+ SANDBOX
+ VERIFICATION
+ REVIEW
+ AUDIT
+ SECURE HANDOVER
+ SOVEREIGN NETWORK BOUNDARY
```

The purpose of this threat model is not to claim that Medha is invulnerable. Its purpose is to ensure that **important failure modes are identified, bounded, tested, observable, and prevented from silently bypassing the control workflow.**

> **If a component can touch confidential knowledge, execute an action, influence a deliverable, or cross a trust boundary, it must have an explicit threat, control, and verification story.**
