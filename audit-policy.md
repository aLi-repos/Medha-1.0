# Medha AI — Audit Policy

**Project:** Medha AI  
**Subtitle:** Sovereign Controlled Multimodal AI Workbench for Confidential Industrial Work  
**Policy:** `docs/audit-policy.md`  
**Status:** Normative policy derived from the authoritative Master `/plan`  
**Year:** 2026

---

## 1. Purpose

This document defines the normative audit, traceability, integrity, access, retention, and observability policy for Medha AI.

The Audit Policy exists to ensure that controlled AI work can be reconstructed from identity through secure handover.

Medha must make the following execution chain reconstructable:

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

Audit is not merely application logging. It is a security and governance control boundary.

The system must record enough structured information to answer:

- Who performed or requested an action?
- What task was being executed?
- Why was the action requested?
- What resource or data was involved?
- Which policy permitted or denied it?
- Which model and tools were involved?
- What evidence supported the work?
- What was executed?
- What was verified?
- Who approved the result?
- What deliverable was produced?
- What was handed over, to whom, and under what access policy?
- Can the result and its integrity be reconstructed later?

---

## 2. Governing Principles

### 2.1 Auditability by design

Every security-relevant and consequential stage of Medha must produce traceable events.

Audit must be integrated into the workflow rather than added after execution.

### 2.2 Complete workflow trace

The audit system must support reconstruction of:

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

### 2.3 No silent bypass

No component may perform a consequential operation without producing the audit information required by policy.

A failed, denied, blocked, interrupted, or approved action must be distinguishable from a successful action.

### 2.4 Audit does not replace authorization

Audit records what happened and supports reconstruction.

It does not grant permission.

The LLM cannot use the existence of an audit system to bypass:

- Authentication.
- RBAC.
- OpenFGA authorization.
- OPA policy.
- Task Passport.
- Action Gate.
- Workspace controls.
- Sandbox controls.
- Verification.
- Review.
- Secure handover.

### 2.5 Sovereignty

In sovereign mode, audit data must remain within the organization's controlled environment.

External logging, telemetry, monitoring, or analytics services must not receive confidential task data unless explicitly permitted by an approved deployment policy.

---

## 3. Scope

This policy applies to:

- Authentication events.
- Authorization decisions.
- Task Passport creation and changes.
- RAG permission decisions.
- Knowledge access.
- Model routing.
- Agent planning.
- Tool requests and execution.
- Action Gate decisions.
- Workspace access.
- Sandbox execution.
- Verification.
- Deliverable generation.
- Review and approval.
- Secure handover.
- Network blocks and security events.
- Administrative security changes.
- Policy changes.
- Failures and degraded states.

It applies to both the MVP and future components that participate in controlled AI execution.

---

## 4. Audit Architecture

The Master Plan specifies:

```text
OpenTelemetry
+
PostgreSQL or equivalent durable audit store
```

OpenTelemetry is the baseline observability technology.

PostgreSQL or an equivalent durable store is the baseline durable audit repository.

The architecture must preserve stable internal audit contracts so that the implementation can be replaced without weakening:

- Event completeness.
- Traceability.
- Integrity.
- Access control.
- Retention.
- Sovereignty.

---

## 5. Audit Event Model

### 5.1 Minimum event content

The Master Plan requires recording:

```text
who
when
what
why
which data
model
tool
action
policy
evidence
verification
approval
output
```

These concepts should be represented as structured fields rather than relying only on free-text messages.

### 5.2 Recommended audit event schema

A concrete implementation should support fields such as:

```text
event_id
trace_id
parent_event_id
task_id
timestamp
event_type
event_version

user_id
identity
role

purpose
sensitivity
requested_operation

resource_type
resource_id
resource_classification

tool_id
tool_version
model_id
model_version

action
action_parameters_reference

policy_id
policy_version
policy_decision
decision_reason

evidence_reference
verification_reference
approval_reference

workspace_reference
sandbox_reference

deliverable_reference
handover_reference

status
error_code

input_hash
output_hash
artifact_hash

source_ip_or_session_reference
service_id
environment

created_at
```

The exact production schema may differ, but it must preserve the required trace semantics.

---

## 6. Stable Event Identity

Every audit event must have a stable unique `event_id`.

Every execution should have a `trace_id` connecting related events.

Child events should preserve their relationship to their parent event where applicable.

Example:

```text
trace_id = TASK-2026-001

AUTHENTICATION
  ↓
TASK_CREATED
  ↓
PASSPORT_CREATED
  ↓
RAG_PERMISSION_DECISION
  ↓
MODEL_SELECTED
  ↓
PLAN_CREATED
  ↓
ACTION_GATE
  ↓
TOOL_EXECUTION
  ↓
SANDBOX_EXECUTION
  ↓
VERIFICATION
  ↓
DELIVERABLE_CREATED
  ↓
REVIEW
  ↓
HANDOVER
```

This allows the entire task lifecycle to be reconstructed without relying on application-specific log ordering alone.

---

## 7. Event Types

The following event families should be supported.

### 7.1 Identity events

Examples:

```text
AUTHENTICATION_SUCCESS
AUTHENTICATION_FAILURE
SESSION_CREATED
SESSION_EXPIRED
LOGOUT
```

Record sufficient identity and session references to establish who initiated the task.

Do not store raw credentials, passwords, tokens, or secrets in audit records.

### 7.2 Authorization events

Examples:

```text
RBAC_DECISION
RESOURCE_PERMISSION_DECISION
POLICY_EVALUATION
AUTHORIZATION_ALLOW
AUTHORIZATION_DENY
AUTHORIZATION_REQUIRE_APPROVAL
```

The record should identify the relevant task, resource, action, policy version, and outcome.

### 7.3 Task Passport events

Examples:

```text
TASK_CREATED
TASK_PASSPORT_CREATED
TASK_PASSPORT_VERSIONED
TASK_STATUS_CHANGED
TASK_CLOSED
TASK_CANCELLED
```

Security-critical changes must preserve version history.

### 7.4 RAG and knowledge events

Examples:

```text
KNOWLEDGE_SCOPE_RESOLVED
RETRIEVAL_REQUESTED
RETRIEVAL_PERMISSION_FILTERED
EVIDENCE_RETURNED
KNOWLEDGE_ACCESS_DENIED
OCR_COMPLETED
EMBEDDING_CREATED
```

The audit trail must show that permission filtering occurred before protected evidence was exposed.

### 7.5 Model events

Examples:

```text
MODEL_ROUTING_REQUESTED
MODEL_SELECTED
MODEL_FALLBACK_SELECTED
MODEL_EXECUTION_STARTED
MODEL_EXECUTION_COMPLETED
MODEL_EXECUTION_FAILED
```

The selected model and routing rationale must be traceable.

### 7.6 Agent events

Examples:

```text
PLAN_CREATED
ACTION_REQUESTED
REPLAN_STARTED
REPLAN_COMPLETED
LOOP_LIMIT_REACHED
AGENT_STOPPED
```

Agent execution must remain bounded and auditable.

### 7.7 Tool events

Examples:

```text
TOOL_REQUESTED
ACTION_GATE_EVALUATED
TOOL_ALLOWED
TOOL_DENIED
TOOL_APPROVAL_REQUIRED
TOOL_EXECUTION_STARTED
TOOL_EXECUTION_COMPLETED
TOOL_EXECUTION_FAILED
```

Tool events must reference the registered tool identity and relevant policy decision.

### 7.8 Sandbox events

Examples:

```text
SANDBOX_CREATED
SANDBOX_EXECUTION_STARTED
SANDBOX_EXECUTION_COMPLETED
SANDBOX_TIMEOUT
SANDBOX_RESOURCE_LIMIT
SANDBOX_FAILED
SANDBOX_INTERRUPTED
SANDBOX_SECURITY_VIOLATION
NETWORK_BLOCKED
```

Security-relevant sandbox events must be retained according to security-event retention rules.

### 7.9 Verification events

Examples:

```text
VERIFICATION_STARTED
VERIFICATION_PASSED
VERIFICATION_FAILED
VERIFICATION_RETRIED
```

The audit record must identify what was verified and the result.

### 7.10 Deliverable events

Examples:

```text
DELIVERABLE_GENERATION_STARTED
DELIVERABLE_GENERATED
MANIFEST_CREATED
HASH_CREATED
DELIVERABLE_VERIFICATION_COMPLETED
```

### 7.11 Review and approval events

Examples:

```text
REVIEW_REQUIRED
REVIEW_ASSIGNED
REVIEW_APPROVED
REVIEW_REJECTED
MINIMAL_CHANGE_REVIEW
AUTO_REVIEW_APPROVED
```

Automatic review events must identify the policy path that authorized automatic handling.

### 7.12 Handover events

Examples:

```text
HANDOVER_PREPARED
HANDOVER_ACCESS_CHECKED
HANDOVER_APPROVED
HANDOVER_COMPLETED
HANDOVER_DENIED
HANDOVER_FAILED
```

---

## 8. Required Trace Relationships

The audit system must preserve relationships among:

```text
Identity
↓
Task
↓
Task Passport
↓
Resource
↓
Policy decision
↓
Model
↓
Plan
↓
Action
↓
Tool
↓
Workspace
↓
Sandbox
↓
Evidence
↓
Verification
↓
Deliverable
↓
Review
↓
Handover
```

A trace should not merely contain isolated events.

It must allow an auditor or authorized reviewer to follow causality and task context.

---

## 9. Task-Centric Audit

Every controlled task must have a unique `task_id`.

All significant events should be associated with that task.

A task trace should answer:

```text
Who?
What task?
Why?
What data?
What was allowed?
What was denied?
Which model?
Which plan?
Which tools?
Which actions?
What executed?
What evidence?
What verification?
What review?
What output?
Who received it?
```

If an event cannot reasonably be associated with a task, it must be categorized as a system, administrative, security, or operational event.

---

## 10. Policy Decision Audit

Every authorization or policy decision must preserve:

```text
policy_id
policy_version
decision
decision_reason
subject
task
resource
action
sensitivity
timestamp
```

The decision must be one of:

```text
ALLOW
DENY
REQUIRE_APPROVAL
```

Audit records must preserve the decision actually enforced.

The model's explanation is not a substitute for the authoritative policy decision.

---

## 11. Tool and Action Audit

For consequential tool actions, audit must preserve:

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
execution_status
sandbox_reference
timestamp
error_code
```

Where possible, large inputs and outputs should be referenced or hashed rather than duplicated into the audit store.

The audit record must still preserve enough information to reconstruct the action and its integrity.

---

## 12. RAG and Evidence Audit

The RAG audit trail must support reconstruction of:

```text
QUERY
→ ALLOWED KNOWLEDGE SCOPE
→ RETRIEVAL
→ PERMISSION FILTERING
→ AUTHORIZED EVIDENCE
```

Relevant events should preserve:

- Task ID.
- Query/reference.
- Knowledge scope.
- Permission decision.
- Document ID.
- Chunk ID.
- Page reference.
- Classification.
- Evidence reference.
- Retrieval status.
- OCR status where relevant.

The system must be able to demonstrate that semantic relevance did not override authorization.

Important claims should remain traceable through:

```text
SOURCE → EVIDENCE → CLAIM → ACTION → OUTPUT
```

Audit must not silently classify an inference as an organizational fact.

---

## 13. Model and Agent Audit

The audit system must record:

- Selected model.
- Model category/version.
- Selection rationale.
- Task type.
- Modality.
- Complexity.
- Sensitivity.
- Required tools.
- GPU/availability constraints where relevant.
- Fallback behavior.
- Execution status.
- Agent plan.
- Replanning events.
- Stop reason.

The audit trail must make it possible to determine why a particular model was selected.

The model cannot write a policy decision claiming it was authorized merely because it generated the plan.

---

## 14. Sandbox and Execution Audit

For sandboxed execution, audit should preserve:

```text
task_id
sandbox_id
execution_id
code_or_artifact_reference
resource_limits
network_policy
mount_policy
start_time
end_time
exit_status
timeout_status
resource_limit_status
security_status
logs_reference
```

The system must record blocked external-network attempts.

A failed or interrupted sandbox execution must preserve logs and status without exposing host resources.

---

## 15. Deliverable and Integrity Audit

A deliverable must be treated as a package, not merely a file.

The package may contain:

```text
MEDHA-PACKAGE/
├── approval_note.docx
├── evidence.json
├── verification.json
├── audit.json
└── manifest.json
```

The audit record should link the package to:

- Task ID.
- Source references.
- Evidence.
- Verification.
- Review.
- Manifest.
- Integrity hash.
- Access policy.
- Handover event.

Secure handover requires:

```text
OUTPUT
→ PACKAGE
→ HASH
→ ACCESS CONTROL
→ AUTHORIZED RECIPIENT
```

The Master Plan specifies SHA-256 for integrity.

---

## 16. Hash and Integrity Policy

SHA-256 is the baseline integrity mechanism.

Where a hash is generated for a deliverable or artifact, audit should preserve:

```text
artifact_reference
hash_algorithm = SHA-256
hash_value
timestamp
task_id
manifest_reference
```

Hashing does not itself prove that content is authorized or correct.

Integrity, authorization, verification, and provenance remain separate controls.

---

## 17. Audit Access Control

Audit data is sensitive and must itself be access-controlled.

Access must be governed by identity and role.

Initial roles in the Master Plan are:

- Operator.
- Engineer.
- Reviewer.
- Administrator.

The system should expose only the audit information authorized for the current identity and task.

Audit access must not become an indirect method of accessing protected source documents.

For example:

```text
AUDIT ACCESS ≠ AUTOMATIC SOURCE DATA ACCESS
```

An audit event may reference a protected document without making the document contents visible to an unauthorized auditor.

Fine-grained authorization may use OpenFGA, with policy evaluation through OPA and OpenFGA as defined by the Master Plan.

---

## 18. Audit Immutability and Integrity

Audit history must be protected against unauthorized modification.

At minimum:

- Events must have stable identifiers.
- Events must be timestamped.
- Event relationships must be preserved.
- Policy versions must be recorded.
- Material task changes must be versioned.
- Deliverable integrity hashes must be retained.
- Unauthorized alteration must be detectable.

The implementation may use additional integrity mechanisms such as append-oriented storage, database controls, signed records, or chained hashes, but such mechanisms are implementation choices unless separately approved.

The core requirement is that audit history must support trustworthy reconstruction and detectable tampering.

---

## 19. Retention Policy

The Master Plan explicitly requires `docs/audit-policy.md` to define retention.

The following retention model is the baseline policy structure:

| Event category | Baseline retention principle |
|---|---|
| Security events | Retain for the longest applicable security/audit period |
| Authorization decisions | Retain with the associated task lifecycle and applicable compliance period |
| Task execution trace | Retain for the task lifecycle plus the organization's approved audit period |
| Deliverable/package trace | Retain at least as long as the associated deliverable remains governed by organizational retention |
| Review/approval events | Retain with the governed task/deliverable record |
| Operational telemetry | Retain according to operational monitoring requirements |
| Debug logs | Shorter retention where they are not required for security or audit |

Exact durations must be configured according to the organization's approved retention requirements, legal obligations, classification rules, and deployment environment.

No fixed duration is asserted by this policy where the Master Plan does not define one.

### 19.1 Retention safety

Retention mechanisms must not:

- Move confidential audit data to unauthorized external services.
- Break task-to-event relationships.
- Delete mandatory security evidence before its approved retention period.
- Preserve data beyond policy where deletion is required.

### 19.2 Secure disposal

When records reach their approved retention limit, disposal must follow the organization's authorized secure deletion policy.

Security or legal holds must override ordinary automated disposal where applicable.

---

## 20. Audit Classification

Audit records may contain sensitive metadata.

Audit storage and access should therefore preserve relevant classification information.

At minimum, records should be associated with:

```text
task_id
resource_classification
sensitivity
access_policy
```

The audit system must not assume that metadata is non-sensitive simply because it is not the original document content.

Examples of sensitive metadata include:

- Document names.
- Resource identifiers.
- User identities.
- Internal tool names.
- Policy decisions.
- Internal model selection.
- Business task purpose.

---

## 21. Data Minimization

Audit must be sufficiently detailed for reconstruction while avoiding unnecessary duplication of confidential content.

Prefer:

```text
reference
+
hash
+
metadata
```

over copying large confidential payloads into audit logs when the referenced artifact remains securely accessible.

Do not record:

- Passwords.
- Authentication secrets.
- API keys.
- Session tokens.
- Private cryptographic keys.

Raw confidential content should be logged only when explicitly justified by an approved policy and necessary for the required trace.

---

## 22. Security Event Handling

The following should be treated as security-relevant audit events:

- Authorization denial.
- Permission bypass attempt.
- Tool abuse.
- Unauthorized file access.
- RAG permission bypass.
- Prompt injection detection or handling.
- Malicious document handling.
- Malicious code execution attempt.
- Sandbox escape attempt.
- External network attempt.
- Data leakage attempt.
- Approval bypass attempt.
- Unauthorized output release attempt.
- Excessive agent loops.
- Malicious multimodal input.
- Policy configuration change.
- Audit integrity failure.

Security failures must be traceable to:

```text
task
identity
policy decision
resource
action
audit event
```

---

## 23. Network and Sovereignty Audit

In sovereign mode, external network access is denied by default.

The audit trail must visibly demonstrate blocked attempts where they occur.

Example:

```text
TOOL_REQUESTED
→ NETWORK_POLICY_CHECK
→ NETWORK_BLOCKED
→ ACTION_DENIED
```

The prototype must visibly demonstrate sovereignty through:

- Local model endpoint.
- Local vector database.
- Local OCR.
- Local embeddings.
- Local files.
- Blocked external network attempts.
- Audit logs.

“Everything is local” is not sufficient without observable evidence.

---

## 24. Review and Approval Audit

Review mode must be auditable.

Supported review modes are:

| Mode | Audit expectation |
|---|---|
| Human | Reviewer identity, decision, time, task, output, and approval state |
| Minimal-change iterative | Requested change, affected portion, verification rerun, and new review state |
| Auto | Policy basis proving the work satisfied automatic-review requirements |

The LLM must not decide by itself that a task is safe for automatic release.

Every release decision must be attributable to the applicable policy and authorized approval path.

---

## 25. Handover Audit

Secure handover must record:

```text
task_id
package_reference
manifest_reference
sha256_hash
verification_status
classification
access_policy
authorized_recipient
handover_decision
timestamp
completion_status
```

A handover must not occur when required authorization, verification, review, or integrity conditions are unsatisfied.

The handover event closes the trace of controlled execution but does not replace retention requirements.

---

## 26. Failure and Degraded-State Audit

Failures must be visible rather than silently converted into success.

Examples:

```text
POLICY_DENIED
AUTHORIZATION_FAILED
APPROVAL_REQUIRED
TOOL_FAILED
SANDBOX_FAILED
SANDBOX_TIMEOUT
NETWORK_BLOCKED
VERIFICATION_FAILED
LOOP_LIMIT_REACHED
HANDOVER_DENIED
HANDOVER_FAILED
AUDIT_WRITE_FAILED
```

A failure must preserve enough context to determine:

- What failed.
- Why it failed.
- Which task was affected.
- Which identity initiated it.
- Which policy applied.
- Which resource/action was involved.
- What happened next.

If mandatory audit recording fails during a consequential operation, the implementation must follow a documented fail-closed or explicitly approved degraded mode. It must never silently represent an unrecorded consequential action as fully auditable.

---

## 27. Observability vs Audit

Operational telemetry and security audit are related but distinct.

### Observability

Used to understand:

- Performance.
- Latency.
- Availability.
- Resource usage.
- Service health.
- Failures.

### Audit

Used to reconstruct:

- Identity.
- Authorization.
- Task purpose.
- Data access.
- Policy decisions.
- Model/tool behavior.
- Verification.
- Approval.
- Deliverables.
- Handover.

OpenTelemetry may support both, but the system must not assume that ordinary application logs automatically satisfy audit requirements.

---

## 28. Metrics

The Master Plan requires experimental measurement of:

- Task completion rate.
- Retrieval quality.
- Authorization rejection rate.
- OCR quality.
- Model-routing accuracy.
- Verification pass rate.
- Sandbox success rate.
- End-to-end latency.
- Human-review rate.
- Failed-action rate.
- Blocked external-network attempts.
- Evidence coverage.

Audit-specific operational metrics should additionally include:

- Audit event creation success rate.
- Audit event write latency.
- Trace completeness rate.
- Orphan-event rate.
- Policy-decision traceability rate.
- Tool-action traceability rate.
- Deliverable-to-task traceability rate.
- Handover-to-manifest traceability rate.
- Audit integrity-check failures.
- Retention-job failures.

The specification must define formulas, collection points, datasets, reporting frequency, and acceptable MVP thresholds after baseline measurement.

---

## 29. Audit Security Tests

Tests must verify:

### Access control

- Unauthorized users cannot access protected audit records.
- Authorized reviewers can access permitted task traces.
- Audit access does not bypass source-document authorization.

### Completeness

- Authentication produces an auditable event.
- Task Passport creation produces an event.
- RAG permission decisions are recorded.
- Model selection is recorded.
- Action Gate decisions are recorded.
- Tool execution is recorded.
- Sandbox execution is recorded.
- Verification is recorded.
- Deliverable generation is recorded.
- Review is recorded.
- Handover is recorded.

### Integrity

- Audit records cannot be silently modified.
- Hashes can be independently checked.
- Trace relationships remain intact.

### Security

- Denied actions do not appear as successful executions.
- Blocked network attempts are recorded.
- Sandbox violations are recorded.
- Approval bypass attempts are recorded.
- Excessive loops are recorded.

### Retention

- Retention jobs do not delete records before the configured period.
- Records are disposed of according to the approved disposal policy.
- Holds prevent inappropriate deletion.

---

## 30. MVP Audit Demonstration

The primary vertical slice is:

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

The audit UI should visibly show a timeline similar to:

```text
[01] User authenticated
[02] Task Passport created
[03] Knowledge permission checked
[04] Authorized evidence retrieved
[05] Model selected + rationale
[06] Agent plan created
[07] Action requested
[08] Action Gate → ALLOW
[09] Tool executed
[10] Sandbox executed
[11] Verification passed
[12] DOCX deliverable generated
[13] Audit package linked
[14] Human review completed
[15] SHA-256 manifest created
[16] Secure handover completed
```

The prototype should also demonstrate at least one negative control such as:

```text
Agent requests unauthorized tool
→ Action Gate
→ DENY
→ Tool not executed
→ Audit event recorded
```

And, where practical:

```text
Tool attempts external network
→ Network policy
→ BLOCKED
→ Audit event recorded
```

---

## 31. Trace Reconstruction Test

A complete task must support reconstruction from start to finish.

### Test procedure

1. Select a completed task.
2. Retrieve its `task_id`.
3. Retrieve the associated `trace_id`.
4. Reconstruct identity.
5. Verify authorization.
6. Verify Task Passport.
7. Verify RAG permission decision.
8. Verify model selection and rationale.
9. Verify agent plan.
10. Verify Action Gate decision.
11. Verify tool execution.
12. Verify sandbox execution.
13. Verify verification result.
14. Verify deliverable.
15. Verify review/approval.
16. Verify manifest and SHA-256 hash.
17. Verify secure handover.
18. Confirm no stage is missing or inconsistent.

Acceptance condition:

> An authorized reviewer can reconstruct the controlled execution path without relying on undocumented application behavior.

---

## 32. Stable Requirements

### Event schema

- `REQ-AUDIT-001` — Every consequential and security-relevant action must produce an auditable event.
- `REQ-AUDIT-002` — Audit events must contain stable unique identifiers.
- `REQ-AUDIT-003` — Related task events must share a reconstructable trace relationship.
- `REQ-AUDIT-004` — Audit records must preserve who, when, what, why, data/resource, model, tool, action, policy, evidence, verification, approval, and output information as applicable.

### Authorization and policy

- `REQ-AUDIT-005` — Authorization and policy decisions must be auditable.
- `REQ-AUDIT-006` — Audit records must preserve the enforced policy decision and policy version.
- `REQ-AUDIT-007` — Audit access must itself be authorization-controlled.
- `REQ-AUDIT-008` — Audit access must not bypass source-resource permissions.

### Task and execution trace

- `REQ-AUDIT-009` — Every controlled task must have a unique task identifier.
- `REQ-AUDIT-010` — Task Passport lifecycle events must be traceable.
- `REQ-AUDIT-011` — RAG permission decisions and evidence references must be traceable.
- `REQ-AUDIT-012` — Model selection and routing rationale must be traceable.
- `REQ-AUDIT-013` — Agent plans, action requests, and replanning must be traceable.
- `REQ-AUDIT-014` — Action Gate decisions and tool executions must be traceable.
- `REQ-AUDIT-015` — Sandbox executions and security events must be traceable.
- `REQ-AUDIT-016` — Verification results must be traceable.
- `REQ-AUDIT-017` — Deliverable generation and integrity metadata must be traceable.
- `REQ-AUDIT-018` — Review and approval decisions must be traceable.
- `REQ-AUDIT-019` — Secure handover must be traceable.

### Integrity and sovereignty

- `REQ-AUDIT-020` — Audit history must support detection of unauthorized modification.
- `REQ-AUDIT-021` — Deliverable integrity must use SHA-256 as the baseline mechanism.
- `REQ-AUDIT-022` — Sovereign-mode audit data must remain within the controlled environment unless explicitly authorized otherwise.
- `REQ-AUDIT-023` — External network blocks and attempted data-exfiltration paths must be auditable.

### Data minimization and retention

- `REQ-AUDIT-024` — Audit logging must not record credentials, secrets, tokens, or private keys.
- `REQ-AUDIT-025` — Audit records should prefer references and hashes over unnecessary duplication of confidential payloads.
- `REQ-AUDIT-026` — Audit retention must be configurable according to approved organizational requirements.
- `REQ-AUDIT-027` — Security and audit records must not be deleted before their approved retention period.
- `REQ-AUDIT-028` — Retention and disposal must respect applicable holds and security requirements.

### Failures and testing

- `REQ-AUDIT-029` — Security and consequential failures must remain visible in the audit trail.
- `REQ-AUDIT-030` — Every security failure must be traceable to task, identity, policy decision, resource, action, and audit event.
- `REQ-AUDIT-031` — Audit completeness and integrity must be covered by positive and negative tests.
- `REQ-AUDIT-032` — The MVP must demonstrate end-to-end trace reconstruction.

---

## 33. Verification Methods

| Requirement area | Verification method |
|---|---|
| Event schema | Schema/contract tests |
| Event identity | Uniqueness tests |
| Trace relationship | End-to-end trace reconstruction |
| Authorization audit | Positive/negative authorization tests |
| Task Passport | Workflow integration tests |
| RAG audit | Permission-filtering and trace tests |
| Model audit | Routing integration tests |
| Tool audit | Action Gate + tool integration tests |
| Sandbox audit | Sandbox security tests |
| Verification audit | End-to-end verification tests |
| Deliverable audit | Package/manifest/hash validation |
| Review audit | Approval workflow tests |
| Handover audit | Access-control and handover tests |
| Integrity | Tamper-detection tests |
| Access control | Role and resource authorization tests |
| Retention | Retention simulation tests |
| Sovereignty | Network isolation and local-storage tests |
| Failure traceability | Negative-path integration tests |

---

## 34. Repository Placement

The Master Plan defines:

```text
backend/
└── audit/

docs/
└── audit-policy.md
```

The audit subsystem should integrate with the broader repository without creating an independent authorization path.

The default technology baseline is:

```text
OpenTelemetry
PostgreSQL or equivalent durable audit store
SHA-256
```

---

## 35. Relationship to Other Policies

Audit Policy receives information from, but does not replace:

```text
Authentication
RBAC
OpenFGA
OPA
Task Passport
RAG Policy
Model Policy
Tool Policy
Action Gate
Workspace
Sandbox
Verifier
Review
Secure Handover
```

Important relationships:

```text
Task Passport
→ establishes task context

Permission Engine
→ establishes policy decision

Action Gate
→ enforces consequential action decision

Tool / Sandbox
→ executes controlled operation

Verifier
→ validates result

Audit
→ records the complete trace

Review
→ records human/iterative/automatic decision

Secure Handover
→ records controlled release
```

---

## 36. No-Bypass Rule

The audit system must not become a bypass mechanism.

It must not:

- Grant permissions.
- Expose unauthorized documents.
- Approve actions.
- Disable network restrictions.
- Modify Task Passport security fields.
- Override Action Gate decisions.
- Release deliverables.
- Bypass verification.

Likewise, no other component may disable mandatory audit for the purpose of avoiding traceability.

---

## 37. Failure-Closed and Degraded Operation

Audit availability is an operational dependency for trustworthy controlled execution.

The implementation must define behavior for:

- Audit store unavailable.
- OpenTelemetry unavailable.
- Database unavailable.
- Event schema mismatch.
- Trace creation failure.
- Integrity-check failure.
- Retention subsystem failure.

For mandatory security/audit events, the system must use an explicitly documented fail-closed or approved degraded mode.

It must never silently execute a consequential action and later claim that the action was fully auditable when the required event was never recorded.

---

## 38. Definition of Done

The Audit Policy is complete for the MVP when:

1. OpenTelemetry or an equivalent approved observability layer is integrated.
2. A durable audit store is configured.
3. Every MVP task receives a unique task ID and trace ID.
4. Authentication is auditable.
5. Authorization decisions are auditable.
6. Task Passport lifecycle is auditable.
7. RAG permission decisions are auditable.
8. Model selection and rationale are auditable.
9. Agent plans and replanning are auditable.
10. Action Gate decisions are auditable.
11. Tool execution is auditable.
12. Sandbox execution is auditable.
13. Verification is auditable.
14. Deliverable creation is auditable.
15. Review and approval are auditable.
16. Secure handover is auditable.
17. SHA-256 integrity information is preserved.
18. Unauthorized audit access is blocked.
19. Security failures are traceable.
20. Blocked network attempts are visible.
21. Audit data remains sovereign in sovereign mode.
22. Retention behavior is configurable and tested.
23. Audit integrity is tested.
24. End-to-end trace reconstruction is demonstrated.
25. No control boundary can be bypassed by disabling or manipulating audit.

---

## 39. Final Policy Statement

Medha AI must make controlled AI execution reconstructable.

The audit principle is:

```text
WHO
→ DID WHAT
→ FOR WHICH TASK
→ FOR WHAT PURPOSE
→ USING WHICH DATA
→ UNDER WHICH POLICY
→ WITH WHICH MODEL
→ USING WHICH TOOLS
→ WITH WHICH ACTIONS
→ IN WHICH SANDBOX
→ PRODUCING WHICH EVIDENCE
→ VERIFIED HOW
→ REVIEWED BY WHOM
→ PACKAGED WITH WHICH INTEGRITY
→ HANDED OVER TO WHOM
```

The audit system records the evidence of that chain.

The policy engine authorizes.

The Action Gate enforces.

The tools execute.

The sandbox isolates.

The verifier checks.

The reviewer approves where required.

The secure handover controls release.

Audit makes the entire workflow reconstructable and accountable.

Any implementation that removes mandatory traceability, weakens audit integrity, exposes audit data without authorization, or allows consequential actions to occur without the required audit boundary is outside the intended Medha AI control model unless the deviation is explicitly documented, approved, and shown not to weaken security or sovereignty.

---

## References

The Master Plan identifies these implementation references:

1. FastAPI documentation.
2. Keycloak documentation.
3. Open Policy Agent documentation.
4. OpenFGA documentation.
5. Qdrant documentation.
6. OpenTelemetry documentation.

External technology documentation should be consulted during implementation and recorded in `docs/decisions.md` and `docs/spec.md` when specific versions, APIs, or deployment behavior are selected.
