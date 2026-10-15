# Medha AI — Tool Policy

**Project:** Medha AI  
**Subtitle:** Sovereign Controlled Multimodal AI Workbench for Confidential Industrial Work  
**Policy:** `docs/tool-policy.md`  
**Status:** Normative policy derived from the authoritative Master `/plan`  
**Year:** 2026

---

## 1. Purpose

This document defines the normative policy for tools used by Medha AI.

The Tool Policy governs:

- Tool registration.
- Tool identity and metadata.
- Tool risk classification.
- Required permissions.
- Input and output schemas.
- Network restrictions.
- Task-scoped workspace access.
- Action Gate enforcement.
- Approval requirements.
- Sandboxed execution.
- Tool-output trust boundaries.
- Failure handling.
- Bounded retries and agent loops.
- Audit and trace requirements.
- Security testing.
- MVP acceptance criteria.

This policy must preserve the Medha AI control model. It must not turn Medha into an unrestricted prompt-to-tool system.

The governing execution model is:

```text
AGENT
→ ACTION GATE
→ POLICY CHECK
→ ALLOW / DENY / REQUIRE_APPROVAL
→ TOOL
```

No tool may be invoked through a path that bypasses the Action Gate, authorization, Task Passport, applicable policy checks, sandbox controls, verification, audit, or review requirements.

---

## 2. Governing Principles

### 2.1 Controlled execution

Medha AI is a controlled, sovereign, on-premise AI workbench for confidential industrial work. Tools exist to execute bounded work on behalf of an authorized task.

The system must not behave like:

```text
USER → CHATBOX → LLM → TOOL
```

It must behave like:

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

### 2.2 The model is not the security authority

The LLM or agent may propose a tool call, but it cannot:

- Grant itself permission.
- Broaden task scope.
- Select unauthorized tools.
- Override a policy denial.
- Disable network restrictions.
- Approve its own high-risk action.
- Release a deliverable without the required review.
- Escape the sandbox.
- Access resources outside the task scope.

### 2.3 Default deny

Tool execution is denied unless the system has sufficient evidence that:

1. The user is authenticated.
2. The task is authorized.
3. The Task Passport is valid.
4. The requested tool is allowed for the task.
5. The action is permitted by policy.
6. Required resource permissions are satisfied.
7. Network policy permits the requested behavior.
8. Any required approval has been obtained.
9. Required sandbox controls are active.

### 2.4 Sovereignty

In sovereign mode:

- Tool execution remains inside the organization's controlled environment.
- External AI services are not required.
- External network access is denied by default.
- Tools must not silently send confidential task data to external services.
- Tool dependencies must be compatible with the deployment's sovereignty and air-gapped requirements.

---

## 3. Scope

This policy applies to every tool callable by:

- The Agent Planner.
- Agent execution graphs.
- Model-generated tool requests.
- User-triggered controlled actions.
- Background task execution.
- Deliverable generation workflows.
- Coding workflows.
- Document and spreadsheet workflows.
- Calculation workflows.
- Multimodal workflows where a registered tool is involved.

It covers both baseline tools and future tools.

Every future tool must be registered and evaluated before it becomes available to controlled execution.

---

## 4. Relationship to Other Medha Policies

Tool Policy does not replace other security and control policies.

| Policy / Component | Responsibility |
|---|---|
| Authentication | Establishes user identity |
| RBAC | Defines broad role permissions |
| OpenFGA | Fine-grained relationships and resource authorization |
| OPA | Policy evaluation and deterministic decisions |
| Task Passport | Defines task identity, purpose, sensitivity, allowed sources, tools, models, approvals, and network policy |
| RAG Policy | Controls knowledge retrieval and evidence release |
| Model Policy | Controls model registration, selection, capability, and local serving |
| **Tool Policy** | Controls tool registration and execution |
| Action Gate | Enforces the decision before consequential tool execution |
| Workspace | Provides task-scoped working artifacts |
| Sandbox | Isolates code and other controlled execution |
| Verifier | Checks execution results and outputs |
| Review | Controls human, iterative, or policy-approved automatic release |
| Audit Policy | Records the execution trace |
| Secure Handover | Controls final package release |

No policy may be interpreted as permission to bypass another mandatory control.

---

## 5. Tool Registry

### 5.1 Registration requirement

Every tool must be registered before invocation.

The authoritative minimum registration fields are:

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

### 5.2 Tool identity

`tool_id` must be stable and unique.

A tool implementation may be replaced without changing its logical identity when the interface remains compatible. Material changes to security behavior, permissions, schemas, or network access must create a versioned registration change and an auditable policy update.

### 5.3 Tool metadata

A registered tool should additionally maintain, where supported:

```text
tool_id
name
version
description
owner
risk_level
required_permission
input_schema
output_schema
network_policy
filesystem_scope
workspace_scope
sandbox_required
approval_requirement
supported_work_types
enabled
policy_version
created_at
updated_at
```

The minimum fields above are normative; additional metadata must not weaken the required controls.

---

## 6. Initial Tool Set

The Master Plan defines the following initial tools:

1. Document reader.
2. Document search.
3. Calculator.
4. Spreadsheet reader.
5. Spreadsheet writer.
6. File manager.
7. DOCX generator.
8. PPTX generator.
9. Code executor.

### 6.1 Document reader

Purpose:

- Read authorized documents.
- Extract content from supported document formats.
- Support evidence extraction inside the task boundary.

Required controls:

- Task-scoped file access.
- Resource authorization.
- Classification checks.
- No access to unauthorized files.
- No unrestricted filesystem traversal.
- Output treated as untrusted tool data until interpreted and verified.

### 6.2 Document search

Purpose:

- Search authorized document sources.
- Support controlled retrieval for document-oriented tasks.

Required controls:

- Search scope derived from the Task Passport and knowledge permissions.
- Permission filtering before evidence release.
- No semantic relevance shortcut around authorization.
- Search results must preserve source references where applicable.

### 6.3 Calculator

Purpose:

- Perform controlled calculations.
- Provide deterministic or inspectable calculation results.

Required controls:

- Structured inputs.
- Bounded execution.
- No arbitrary filesystem access.
- No unrestricted network access.
- Calculation results must remain distinguishable from source facts.

### 6.4 Spreadsheet reader

Purpose:

- Read authorized workbook data.

Required controls:

- Task-scoped file access.
- Workbook and sheet restrictions where required.
- No unauthorized workbook access.
- Preserve relevant source/version information.
- Return structured results where practical.

### 6.5 Spreadsheet writer

Purpose:

- Modify or create authorized spreadsheet artifacts.

Required controls:

- Task-scoped output location.
- Explicit write permission.
- Classification and ownership metadata.
- Version/status tracking.
- Verification before release of consequential outputs.

### 6.6 File manager

Purpose:

- Manage authorized task files and working artifacts.

Required controls:

- Controlled workspace only.
- No unrestricted host filesystem access.
- Path validation.
- Task ownership checks.
- Classification checks.
- Explicit permissions for read/write/delete operations.
- Audit every consequential operation.

### 6.7 DOCX generator

Purpose:

- Generate authorized Word deliverables.

Required controls:

- Output must remain within the controlled workspace.
- Source references and evidence should be preserved where required by the deliverable workflow.
- Generated output must be verified.
- Final release must follow review and secure handover policy.

### 6.8 PPTX generator

Purpose:

- Generate authorized presentation deliverables.

Required controls:

- Controlled workspace.
- Authorized source material only.
- Output classification.
- Verification of generated content where applicable.
- Review according to task risk.

### 6.9 Code executor

Purpose:

- Execute authorized code required for coding, calculation, analysis, or controlled transformation tasks.

Mandatory controls:

- Code must never execute directly on the host.
- Execution must occur inside the sandbox.
- Isolated filesystem.
- CPU limits.
- Memory limits.
- Execution timeout.
- Restricted permissions.
- Controlled mounts.
- No unrestricted host access.
- Network disabled by default.
- Execution logs and status preserved on failure or interruption.

Docker is the baseline sandbox technology; gVisor may be used for hardened deployments.

---

## 7. Risk Classification

Every registered tool must have a `risk_level`.

Risk level determines the strength of authorization, approval, isolation, and verification required.

A baseline classification is:

| Risk | Meaning | Typical treatment |
|---|---|---|
| Low | Read-only or low-consequence task-scoped operation | Policy-controlled execution may be possible |
| Medium | Writes, transformations, or operations with meaningful task impact | Explicit permissions and verification required |
| High | Consequential, sensitive, privileged, or potentially destructive operation | Human approval normally required |
| Critical | Operation capable of severe confidentiality, integrity, availability, or authorization impact | Deny unless explicitly authorized by a separately approved policy path |

The exact risk classification of each tool and operation must be represented in the registered tool policy.

Risk is a property of the requested action as well as the underlying tool. A generally low-risk tool may perform a higher-risk operation depending on inputs, target resources, or requested effect.

---

## 8. Required Permission

Every tool must declare:

```text
required_permission
```

The required permission must be evaluated before invocation.

Permission evaluation must consider:

```text
User
+ Task
+ Resource
+ Action
+ Sensitivity
+ Policy
```

A valid user role alone is not sufficient.

Examples of authorization dimensions include:

- Department membership.
- Document access.
- Task execution.
- Tool invocation.
- Deliverable approval.
- Resource ownership.
- File read/write permissions.

Fine-grained relationships are handled through OpenFGA, while policy decisions are evaluated through OPA and OpenFGA together as defined by the Master Plan.

---

## 9. Task Passport Binding

Every tool invocation must be associated with a persisted Task Passport.

The Task Passport contains, at minimum:

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

Tool execution must respect:

- `task_id`
- `purpose`
- `sensitivity`
- `allowed_tools`
- `approval_requirement`
- `network_policy`
- task status
- authorization state

Security-critical passport changes after execution begins must be immutable or versioned and must trigger re-authorization as required by the Master Plan.

A tool cannot expand its own task scope.

---

## 10. Action Gate

### 10.1 Mandatory path

Every consequential tool action must follow:

```text
AGENT
→ ACTION GATE
→ POLICY CHECK
→ ALLOW / DENY / REQUIRE_APPROVAL
→ TOOL
```

The Action Gate is a mandatory enforcement boundary.

### 10.2 Agent request

The agent may produce a structured request such as:

```text
task_id
tool_id
operation
arguments
target_resources
requested_effect
reason
```

The request is untrusted until policy evaluation succeeds.

### 10.3 Policy check

The Action Gate must evaluate:

- User identity.
- User role.
- Task Passport.
- Tool registration.
- Tool risk.
- Required permission.
- Target resource authorization.
- Task sensitivity.
- Requested operation.
- Input constraints.
- Network policy.
- Sandbox requirement.
- Approval requirement.
- Current task status.
- Relevant policy versions.

### 10.4 Outcomes

The Action Gate returns exactly one of:

```text
ALLOW
DENY
REQUIRE_APPROVAL
```

#### `ALLOW`

Execution may proceed when all mandatory controls are satisfied.

#### `DENY`

Execution must not occur.

The system should provide a policy decision reason suitable for the user and audit trail without leaking protected policy information.

The agent must not retry the same denied request indefinitely or modify the request solely to circumvent the denial.

#### `REQUIRE_APPROVAL`

Execution is paused until the required authorized reviewer approves the action.

The agent cannot approve its own request.

---

## 11. Approval Requirements

High-risk, sensitive, ambiguous, or consequential tool actions must use human review or another explicitly authorized approval path.

The Master Plan defines review modes:

| Review mode | Use |
|---|---|
| Human | High-risk, sensitive, ambiguous, or consequential work |
| Minimal-change iterative | Limited corrections without unnecessary full regeneration |
| Auto | Only low-risk work that explicitly satisfies policy |

The tool policy must never infer that an action is safe for automatic execution merely because the model claims it is safe.

Approval must be bound to:

- Task ID.
- Requested action.
- Tool.
- Target resource.
- Relevant policy decision.
- Approver identity.
- Approval status.
- Timestamp.

A materially changed action requires fresh policy evaluation and, where applicable, fresh approval.

---

## 12. Input Schema Enforcement

Every tool must declare an `input_schema`.

The Action Gate or tool boundary must validate inputs before execution.

Input validation should include:

- Required fields.
- Types.
- Allowed values.
- Size limits.
- Path constraints.
- Resource identifiers.
- Operation restrictions.
- Task binding.
- Classification restrictions.
- Dangerous or unsupported parameters.

Malformed input must fail closed.

The model cannot bypass schema validation by generating arbitrary tool payloads.

---

## 13. Output Schema Enforcement

Every tool must declare an `output_schema`.

Tool outputs must be:

- Structurally validated where practical.
- Associated with the task.
- Associated with the invoking tool.
- Preserved with relevant status information.
- Treated as untrusted data.
- Passed through verification when required.

Tool output is not automatically an organizational fact.

For evidence-bearing workflows, outputs must preserve source or artifact references where available.

---

## 14. Tool Output Is Untrusted Data

Tool results can contain:

- Malicious document content.
- Prompt injection.
- Incorrect calculations.
- Unexpected file content.
- Model-generated text.
- Crafted strings designed to manipulate the agent.
- Unexpected executable content.

Therefore:

> Tool output must never be treated as trusted instructions.

The agent must not follow instructions found inside a retrieved document, spreadsheet, image, generated file, or other tool result unless those instructions are independently authorized as part of the task and policy.

This boundary is especially important for document readers, document search, spreadsheet readers, multimodal processing, and code execution.

---

## 15. File and Workspace Policy

The controlled workspace supports:

- Documents.
- PDFs.
- Images.
- Code.
- Excel files.
- Presentations.
- Generated files.
- Intermediate files.

Each working artifact must track:

```text
owner
task_id
classification
permissions
version
source
status
```

### 15.1 Task scoping

Tools may access only resources within the authorized task scope.

A tool must not:

- Traverse unrestricted host paths.
- Read another task's private workspace.
- Modify unauthorized files.
- Copy confidential data into unauthorized locations.
- Access host secrets.
- Access arbitrary system devices.

### 15.2 File deletion

Deletion is a consequential action and must be permission-checked and audited.

Where policy requires approval, deletion must return `REQUIRE_APPROVAL` rather than executing automatically.

---

## 16. Network Policy

Network behavior must be explicitly registered and enforced.

The tool registry contains:

```text
network_policy
```

In sovereign mode:

```text
External network = DENY by default
```

A tool must not:

- Call external AI APIs with confidential data.
- Upload task documents externally.
- Send prompts or embeddings to external services.
- Download arbitrary external content unless explicitly permitted by policy.
- Use an undeclared network endpoint.
- Bypass network restrictions through subprocesses or indirect calls.

If a network-enabled tool is explicitly authorized in a future policy, the allowed endpoints, purpose, data handling, and approval requirements must be documented and auditable.

A blocked network attempt is a security-relevant event and must be recorded.

---

## 17. Sandbox Policy for Code Execution

All generated code must execute inside a sandbox.

### 17.1 Required controls

The sandbox must provide:

- Isolated filesystem.
- CPU limits.
- Memory limits.
- Execution timeout.
- Restricted permissions.
- Controlled mounts.
- No unrestricted host access.
- Network disabled by default.

### 17.2 Baseline technology

```text
Docker
```

gVisor may be used where practical for hardened deployments.

### 17.3 Host protection

Code must never execute directly on the Medha host.

The sandbox must prevent access to:

- Host filesystem outside approved mounts.
- Host credentials.
- Host process namespace where not explicitly permitted.
- Host devices.
- Unrestricted network.
- Other task workspaces.

### 17.4 Failure handling

A failed or interrupted sandbox execution must:

1. Stop execution.
2. Preserve logs and status.
3. Preserve relevant task trace information.
4. Prevent host-resource exposure.
5. Return a controlled failure state.
6. Allow the agent to replan only within bounded limits.

---

## 18. Bounded Execution and Agent Loops

The Agent Planner may execute tools through a stateful graph equivalent to:

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

Retries and replanning must be bounded.

The agent must stop when:

- Policy denies the action.
- Authorization is missing.
- Verification repeatedly fails.
- Excessive loops occur.
- Unsafe tool requests are made.
- A high-risk condition is ambiguous.
- Required approval is unavailable.
- Sandbox execution violates its constraints.

The tool system must not allow the agent to create an unlimited self-directed execution loop.

---

## 19. Work Separation

Tool availability must follow the task's declared work type.

| Work type | Relevant tool family |
|---|---|
| Document work | Document parsing, reading, search, document generation |
| Spreadsheet work | Workbook reader/writer |
| Code work | Coding tools, code workspace, tests, sandbox |
| Image work | Multimodal processing and visual evidence handling |
| Calculation work | Controlled calculator or execution tool |
| Analysis work | Agent reasoning, evidence graph, verifier |

A combined task must explicitly declare the combination in the Task Passport and execution plan.

The agent must not gain unrestricted access to every registered tool merely because multiple tools exist.

---

## 20. Tool Invocation Lifecycle

The normative lifecycle is:

```text
1. Task created
2. Identity established
3. Authorization established
4. Task Passport persisted
5. Work type determined
6. Agent proposes tool action
7. Tool identity validated
8. Input schema validated
9. Task Passport checked
10. Resource permissions checked
11. Risk evaluated
12. Network policy checked
13. Sandbox requirement checked
14. Approval requirement checked
15. Action Gate evaluates policy
16. ALLOW / DENY / REQUIRE_APPROVAL
17. Approved tool executes
18. Tool result captured
19. Result schema validated
20. Result verified where required
21. Agent observes result
22. Replan if permitted
23. Audit event recorded
24. Continue or stop
```

The order may be implemented differently internally only if the resulting control boundaries and security properties are preserved.

---

## 21. Consequential Actions

Consequential actions include operations that can materially affect:

- Confidentiality.
- Integrity.
- Availability.
- Files.
- Deliverables.
- Organizational records.
- External communication.
- Code execution.
- Approval state.
- Output release.

Such actions must be explicitly policy-checked.

Examples include:

- Writing files.
- Deleting files.
- Executing code.
- Generating official deliverables.
- Modifying spreadsheets.
- Accessing sensitive resources.
- Releasing outputs.
- Any future external communication capability.

The mere fact that an action is technically possible does not make it authorized.

---

## 22. Deliverable Generation

Tool-generated deliverables are part of a controlled package.

The Deliverable Factory may generate:

- DOCX.
- XLSX.
- PPTX.
- PDF.
- Authorized code.

A deliverable is not merely a file.

The package must contain, where applicable:

```text
final output
source references
evidence
verification result
Task ID
audit reference
manifest
```

Example:

```text
MEDHA-PACKAGE/
├── approval_note.docx
├── evidence.json
├── verification.json
├── audit.json
└── manifest.json
```

Tool-generated output must not bypass:

- Verification.
- Review.
- Audit.
- Classification.
- Integrity metadata.
- Secure handover.

---

## 23. Verification of Tool Results

The Verifier must check applicable tool results for:

- Schema correctness.
- Calculations.
- Evidence.
- Document consistency.
- Tool results.
- Policy compliance.
- Unsupported claims.
- Output completeness.

Verification types include:

- Rule verification.
- Calculation verification.
- Execution verification.
- Evidence verification.
- Policy verification.

When verification fails:

```text
FAIL
→ FEEDBACK
→ REPLAN
→ EXECUTE
→ VERIFY
```

Retries must be bounded and visible in the audit trail.

---

## 24. Audit and Trace Requirements

Every consequential tool request and execution must be auditable.

The trace must make it possible to reconstruct:

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

At minimum, audit information must identify:

- Who.
- When.
- What.
- Why.
- Which data.
- Model.
- Tool.
- Action.
- Policy.
- Evidence.
- Verification.
- Approval.
- Output.

Tool-specific audit records should include:

```text
task_id
user_id
tool_id
tool_version
operation
target_resource
risk_level
policy_decision
policy_version
approval_reference
input_hash_or_reference
output_reference
execution_status
sandbox_reference
timestamp
error_code
```

Sensitive raw input/output should not be copied into audit logs unless explicitly permitted by the applicable data-handling policy. References and integrity metadata should be preferred where possible.

Use OpenTelemetry and PostgreSQL or an equivalent durable audit store as defined by the Master Plan.

---

## 25. Error States

Tool execution must expose controlled error states.

Recommended stable categories include:

```text
TOOL_NOT_REGISTERED
TOOL_DISABLED
TOOL_NOT_ALLOWED
INVALID_INPUT
INVALID_OUTPUT
RESOURCE_NOT_AUTHORIZED
TASK_SCOPE_VIOLATION
POLICY_DENIED
APPROVAL_REQUIRED
APPROVAL_REJECTED
NETWORK_BLOCKED
SANDBOX_REQUIRED
SANDBOX_FAILED
SANDBOX_TIMEOUT
RESOURCE_LIMIT_EXCEEDED
VERIFICATION_FAILED
TOOL_EXECUTION_FAILED
TOOL_INTERRUPTED
LOOP_LIMIT_REACHED
SECURITY_VIOLATION
```

Security-relevant failures must fail closed and must be traceable to the task, identity, policy decision, resource, action, and audit event.

---

## 26. Security Invariants

The following invariants are mandatory:

### TOOL-INV-001 — Registration
No unregistered tool may execute.

### TOOL-INV-002 — Task binding
Every tool invocation must belong to an authorized task.

### TOOL-INV-003 — Permission
Tool execution requires applicable authorization.

### TOOL-INV-004 — Action Gate
Every consequential tool action must pass through the Action Gate.

### TOOL-INV-005 — Default deny
Missing or ambiguous authorization must not produce execution.

### TOOL-INV-006 — Model limitation
The model cannot grant itself tool permission.

### TOOL-INV-007 — Network sovereignty
External network access is denied by default in sovereign mode.

### TOOL-INV-008 — Host isolation
Generated code must never execute directly on the host.

### TOOL-INV-009 — Workspace isolation
A tool cannot access unauthorized task workspaces.

### TOOL-INV-010 — Output trust
Tool output is untrusted data until applicable verification.

### TOOL-INV-011 — Approval
Required approvals cannot be self-generated by the agent.

### TOOL-INV-012 — Audit
Consequential tool actions must generate an auditable trace.

### TOOL-INV-013 — Bounded execution
Agent retries and tool loops must be bounded.

### TOOL-INV-014 — No bypass
No component may bypass authorization, policy, sandbox, verification, audit, review, or handover boundaries.

---

## 27. Threats and Abuse Cases

Tool controls must address at least:

| Threat | Required control |
|---|---|
| Unauthorized tool invocation | Task Passport + RBAC/OpenFGA + OPA + Action Gate |
| Tool privilege escalation | Required permission + default deny |
| Agent self-authorization | Model cannot override policy |
| Prompt injection through tool output | Treat tool output as untrusted data |
| Malicious document | Permission-aware access + parsing/OCR controls + verification |
| Malicious code | Docker sandbox + limits + no host access |
| Sandbox escape | Isolation + restricted permissions + security testing |
| Unauthorized file access | Task-scoped workspace + resource authorization |
| Unauthorized file modification | Write permission + Action Gate |
| Destructive file operation | Risk classification + approval |
| External data exfiltration | Network deny-by-default |
| Hidden network access | Enforced network policy + blocked-attempt audit |
| Tool schema abuse | Input validation |
| Malformed tool output | Output validation |
| Infinite agent loop | Bounded retries/loops |
| Approval bypass | Explicit approval state + audit |
| Unauthorized deliverable release | Review + secure handover |
| Cross-task data access | Task binding + workspace isolation |
| Privileged tool misuse | Risk classification + authorization |
| Audit evasion | Mandatory event generation |

Security testing must include both positive and negative cases.

---

## 28. Security Testing Requirements

The tool subsystem must be tested against:

- Unauthorized document access.
- RBAC bypass.
- OpenFGA bypass.
- OPA policy bypass.
- RAG permission bypass where tool search interacts with RAG.
- Prompt injection.
- Malicious documents.
- Malicious code.
- Sandbox escape.
- Tool abuse.
- Unauthorized file access.
- Unauthorized file modification.
- External network attempts.
- Data leakage.
- Approval bypass.
- Unauthorized output release.
- Excessive agent loops.
- Malicious multimodal inputs.

Every security failure must be traceable to:

```text
task
identity
policy decision
resource
action
audit event
```

Where practical, security tests should run in CI.

---

## 29. Metrics

Tool-system quality must be measured experimentally.

Relevant metrics include:

- Task completion rate.
- Tool authorization rejection rate.
- Failed-action rate.
- Sandbox success rate.
- Sandbox failure rate.
- Sandbox timeout rate.
- Verification pass rate.
- Human-review rate.
- Blocked external-network attempts.
- Tool execution latency.
- Agent loop termination rate.
- Tool schema validation failure rate.
- Unauthorized access rejection rate.
- Evidence coverage for tool-derived claims.

The specification should define metric formulas, collection points, datasets, reporting frequency, and acceptable MVP thresholds after baseline measurement.

---

## 30. MVP Vertical Slice

The Tool Policy must support the Master Plan's primary vertical slice:

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

- A scanned inspection report.
- An internal SOP or manual.
- An inspection photograph.

It must produce an evidence-linked inspection analysis and approval note while preserving:

- Classification.
- Authorization.
- Verification.
- Audit metadata.
- Integrity metadata.

The secondary coding workflow is:

```text
User
→ Task Passport
→ Purpose
→ Work Separation
→ Coding Model
→ Agent Plan
→ Action Gate
→ Code Workspace
→ Docker Sandbox
→ Test
→ Verifier
→ Review
→ Output
→ Secure Handover
→ Audit
```

The MVP should prioritize demonstrable control behavior over broad tool count.

---

## 31. MVP Acceptance Criteria

The Tool Policy is considered implemented for the MVP only when all applicable criteria are demonstrated:

- Every available tool is registered.
- Each registered tool has the required metadata.
- Tool risk is represented.
- Required permissions are enforced.
- Task Passport binding is enforced.
- Input schemas are validated.
- Output schemas are validated where applicable.
- Consequential actions pass through the Action Gate.
- Action Gate returns `ALLOW`, `DENY`, or `REQUIRE_APPROVAL`.
- Denied actions do not execute.
- Required approvals block execution until authorized approval exists.
- Agent-generated requests cannot self-authorize.
- Workspace access is task-scoped.
- File operations are policy-controlled.
- Code executes only inside the Docker sandbox.
- Sandbox resource limits are enforced.
- Network is disabled by default for sandboxed execution.
- Blocked network attempts are auditable.
- Tool outputs are treated as untrusted data.
- Verification is performed where required.
- Retries and agent loops are bounded.
- Tool failures preserve status and audit information.
- Security failures are traceable.
- Tool execution appears in the audit timeline.
- Tool-generated deliverables follow review and secure handover.
- No tool bypasses authorization, policy, sandbox, verification, audit, review, or handover boundaries.

---

## 32. Stable Requirements

The following stable identifiers should be used when implementing the Tool Policy.

### Tool registration

- `REQ-TOOL-001` — Every callable tool must be registered.
- `REQ-TOOL-002` — Every registered tool must expose the required registration fields.
- `REQ-TOOL-003` — Tool identity and material policy changes must be versioned and auditable.

### Authorization and Action Gate

- `REQ-TOOL-004` — Tool execution must be bound to an authorized Task Passport.
- `REQ-TOOL-005` — Every consequential tool action must pass through the Action Gate.
- `REQ-TOOL-006` — Action Gate outcomes must be `ALLOW`, `DENY`, or `REQUIRE_APPROVAL`.
- `REQ-TOOL-007` — The LLM must not self-authorize tool execution.
- `REQ-TOOL-008` — Missing or ambiguous authorization must fail closed.
- `REQ-TOOL-009` — Required approval must be obtained before execution.

### Schemas and resources

- `REQ-TOOL-010` — Tool input must conform to its registered input schema.
- `REQ-TOOL-011` — Tool output must conform to its registered output schema where applicable.
- `REQ-TOOL-012` — Tool resource access must be task-scoped and permission-checked.
- `REQ-TOOL-013` — Working artifacts must preserve owner, task ID, classification, permissions, version, source, and status.

### Network and sandbox

- `REQ-TOOL-014` — Network policy must be explicitly enforced per tool.
- `REQ-TOOL-015` — External network access must be denied by default in sovereign mode.
- `REQ-TOOL-016` — Generated code must execute only inside an isolated sandbox.
- `REQ-TOOL-017` — Sandbox execution must enforce filesystem, CPU, memory, timeout, permission, mount, host-access, and network controls.

### Verification and reliability

- `REQ-TOOL-018` — Tool outputs must be treated as untrusted data until applicable verification.
- `REQ-TOOL-019` — Tool failures and verification failures must enter controlled failure/replan paths.
- `REQ-TOOL-020` — Agent retries and tool loops must be bounded.

### Audit and security

- `REQ-TOOL-021` — Consequential tool actions must be auditable.
- `REQ-TOOL-022` — Security failures must be traceable to task, identity, policy decision, resource, action, and audit event.
- `REQ-TOOL-023` — Tool security controls must be covered by positive and negative security tests.

### Deliverables and handover

- `REQ-TOOL-024` — Tool-generated deliverables must pass applicable verification and review.
- `REQ-TOOL-025` — Tool-generated outputs must preserve classification and integrity metadata.
- `REQ-TOOL-026` — Tool execution must not bypass secure handover controls.

---

## 33. Verification Methods

Each requirement should identify how it is verified.

| Requirement area | Verification method |
|---|---|
| Registration | Registry inspection + automated tests |
| Permission enforcement | Positive/negative authorization tests |
| Action Gate | Unit + integration + policy tests |
| Schema validation | Contract tests |
| Workspace isolation | Security/integration tests |
| Network restrictions | Network-blocking tests |
| Sandbox isolation | Container security tests |
| Approval | Workflow integration tests |
| Output trust | Prompt-injection and malicious-input tests |
| Verification | End-to-end workflow tests |
| Bounded loops | Agent execution tests |
| Audit | Trace reconstruction tests |
| Deliverables | Artifact/package validation |
| Secure handover | Manifest/hash/access-control tests |

---

## 34. Implementation Guidance vs Normative Policy

This document is normative where it uses mandatory language such as:

- must
- shall
- cannot
- denied by default
- required

Implementation choices may use the baseline stack from the Master Plan:

```text
Backend: Python / FastAPI / Pydantic / Uvicorn
Authorization: Keycloak / OpenFGA / OPA
Workspace and execution: Docker
Tool architecture: MCP-compatible internal architecture
Database: PostgreSQL
Observability: OpenTelemetry
Integrity: SHA-256
Deployment: Linux / Docker Compose / NVIDIA CUDA where available
```

These are implementation baselines, not permission to weaken the Tool Policy.

A replaceable implementation is acceptable when it preserves the same stable internal contract and security behavior.

---

## 35. No-Bypass Rule

The following is an explicit architectural invariant:

```text
NO TOOL
MAY BYPASS
AUTHENTICATION
→ AUTHORIZATION
→ TASK PASSPORT
→ PERMISSION ENGINE
→ ACTION GATE
→ WORKSPACE/SANDBOX
→ VERIFICATION
→ AUDIT
→ REVIEW
→ SECURE HANDOVER
```

A tool may not call another tool through an uncontrolled internal path.

Tool-to-tool chaining must remain inside the same policy-controlled execution context.

---

## 36. Failure-Closed Behavior

When a security-critical control cannot be evaluated reliably, the system must not guess.

Examples:

- Tool registration unavailable → do not execute.
- Permission service unavailable → do not execute consequential action.
- Task Passport missing → do not execute.
- Approval state unavailable → do not execute an approval-required action.
- Network policy unavailable → do not permit external network.
- Sandbox unavailable for code execution → do not execute code.
- Schema validation unavailable → do not execute unsafe/unvalidated action.
- Audit system unavailable for a mandatory auditable action → fail according to the system's defined fail-closed policy rather than silently executing without trace.

Degraded modes must be explicitly documented and must not weaken the core control model.

---

## 37. Traceability to Master Plan

This policy directly implements the Master Plan sections covering:

- Tool Registry.
- Action Gate.
- Controlled workspace.
- Sandbox.
- Verification.
- Deliverable generation.
- Review.
- Audit and trace.
- Sovereign mode.
- Security testing.
- MVP vertical slice.
- Definition of done.

The authoritative tool architecture remains:

```text
Medha
├── UI
├── API Gateway
├── Authentication
├── RBAC
├── Task Passport
├── Permission Engine
├── RAG
├── Model Router
├── Agent Planner
├── Tool Registry
├── Action Gate
├── Sandbox
├── Verifier
├── Deliverable Factory
├── Audit / Trace
└── Secure Handover
```

The Tool Registry and Action Gate are control boundaries within this architecture, not independent authorization systems.

---

## 38. Definition of Done for Tool Policy

Tool Policy is complete for the MVP when:

1. The initial tool set is registered.
2. Tool risk levels and permissions are represented.
3. Input/output schemas are enforced.
4. Tool requests are bound to Task Passport context.
5. Every consequential action passes through the Action Gate.
6. `ALLOW`, `DENY`, and `REQUIRE_APPROVAL` behavior is demonstrated.
7. Unauthorized tool requests are rejected.
8. Workspace access is task-scoped.
9. Code execution is isolated in Docker.
10. Sandbox restrictions are demonstrated.
11. Network access is denied by default.
12. Tool output is treated as untrusted.
13. Verification is integrated.
14. Agent loops are bounded.
15. Tool failures are controlled and auditable.
16. Security tests cover tool abuse and bypass attempts.
17. Tool execution is visible in the audit trace.
18. Deliverables pass verification/review and secure handover.
19. Sovereignty is demonstrable.
20. No implementation bypasses the authoritative control workflow.

---

## 39. Final Policy Statement

Medha AI must not provide an unrestricted tool-using agent.

It must provide:

```text
AUTHORIZED USER
→ AUTHORIZED TASK
→ AUTHORIZED TOOL
→ AUTHORIZED ACTION
→ CONTROLLED EXECUTION
→ VERIFIED RESULT
→ AUDITABLE TRACE
→ APPROVED OUTPUT
→ SECURE HANDOVER
```

The agent may reason and propose.

The policy engine decides.

The Action Gate enforces.

The sandbox isolates.

The verifier checks.

The audit records.

The reviewer approves where required.

The secure handover controls release.

Any implementation that weakens or bypasses these boundaries is outside the intended Medha AI control model unless the deviation is explicitly documented, approved, and shown not to weaken security or sovereignty.

---

## References

The Master Plan identifies the following implementation references:

1. FastAPI documentation.
2. Keycloak documentation.
3. Open Policy Agent documentation.
4. OpenFGA documentation.
5. Qdrant documentation.
6. OpenTelemetry documentation.

External technology documentation should be consulted during implementation and recorded in `docs/decisions.md` and `docs/spec.md` when specific versions, APIs, or deployment behavior are selected.
