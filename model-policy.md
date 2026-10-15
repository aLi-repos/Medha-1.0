# Medha AI — Model Policy

> **Status:** Normative policy derived from the authoritative Medha AI Master `/plan`.
>
> **Purpose:** Define model registration, capability classification, selection, local serving, routing, limits, fallback, verification, auditability, and sovereign-mode requirements.
>
> **Authority:** The Master `/plan` remains the source of truth. This document adds implementation-level policy detail without weakening, removing, reordering, or bypassing its authorization, Task Passport, RAG, Action Gate, sandbox, verification, review, audit, handover, or sovereignty boundaries.

---

## 1. Scope

This policy governs every AI model used by Medha:

- text models;
- reasoning models;
- multimodal/vision models;
- coding models;
- embedding models;
- future replaceable model categories;
- local model-serving infrastructure;
- Model Router decisions;
- model fallbacks and degradation;
- model capability limits;
- model-related audit records.

Medha must remain replaceable and must not depend on one vendor or one model.

---

## 2. Governing Principle

Medha is not:

```text
USER → LLM → ANSWER
```

Medha is:

```text
TASK
→ TASK PASSPORT
→ TASK / SENSITIVITY CHECK
→ MODEL CAPABILITY MATCH
→ MODEL ROUTER
→ PLAN
→ CONTROLLED EXECUTION
→ VERIFICATION
→ REVIEW / OUTPUT
```

> **The model may reason and propose; it cannot authorize itself, broaden task scope, approve release, or override security policy.**

---

## 3. Authoritative Model Architecture

The model layer operates conceptually as:

```text
Task Context
    ↓
Model Router
    ↓
Selected Local Model
    ↓
Agent Planner / Controlled Invocation
    ↓
Verifier
```

It remains bounded by:

- Identity;
- RBAC;
- Task Passport;
- Permission Engine;
- RAG permissions;
- Work Separation;
- Tool Policy;
- Network Policy;
- Review/Approval Policy.

Model selection must never bypass these controls.

---

## 4. Model Categories

### 4.1 Lightweight text model

For routine, lower-complexity text tasks where policy permits.

### 4.2 Reasoning model

For multi-step analysis, evidence synthesis, structured reasoning, and planning.

### 4.3 Multimodal model

For scanned documents, photographs, visual evidence, diagrams, and engineering images.

Vision output is an observation and is not automatically an organizational fact.

### 4.4 Coding model

For code generation, modification, test generation, debugging, and code-oriented planning.

Generated code remains subject to the controlled workspace, Action Gate, sandbox, verification, review, and audit.

### 4.5 Embedding model

For RAG indexing.

The Master Plan baseline is **BGE-M3 or replaceable equivalent**. Embeddings must run locally in sovereign mode.

---

## 5. Model Registration

Every production-eligible model SHOULD have a registration record:

```text
model_id
name
version
category
provider
artifact_reference
checksum
capabilities
modalities
context_limit
resource_requirements
sensitivity_constraints
supported_work_types
serving_endpoint
fallback_policy
status
policy_version
registered_at
```

Recommended model states:

```text
REGISTERED
ACTIVE
DEGRADED
DISABLED
RETIRED
```

Disabled or retired models must not be selected for new controlled execution.

---

## 6. Model Integrity and Provenance

Where practical, model registration should preserve:

- artifact checksum;
- source/provenance;
- version;
- configuration;
- tokenizer/runtime version;
- quantization information;
- registration status.

A model with an unknown or failed integrity check must not be treated as a trusted production model.

The exact signing/verification mechanism is an implementation decision and should be recorded in `decisions.md`.

---

## 7. Local Model Serving

The Master Plan baseline is **vLLM or a replaceable local serving layer**.

In sovereign mode:

- models must be served inside the organization's controlled environment;
- confidential prompts and evidence must remain local;
- external AI APIs must not be required;
- external network access is denied by default.

Conceptually:

```text
UI / API
   ↓
LOCAL MODEL ROUTER
   ↓
LOCAL MODEL ENDPOINT
   ↓
LOCAL MODEL
```

The prototype must visibly demonstrate the local model endpoint and blocked external network attempts.

---

## 8. Model Selection Inputs

The Model Router must consider:

- task type;
- modality;
- complexity;
- sensitivity;
- required tools;
- GPU availability;
- latency;
- model capability.

Additional implementation metadata may be used when documented.

The router must produce a meaningful selection rationale.

---

## 9. Model Selection Pipeline

```text
TASK CHECK
   ↓
CAPABILITY REQUIREMENTS
   ↓
SENSITIVITY / POLICY CONSTRAINTS
   ↓
AVAILABLE LOCAL MODELS
   ↓
RESOURCE / GPU CHECK
   ↓
MODEL SELECTION
   ↓
SELECTION RATIONALE
   ↓
AGENT PLAN
```

The selected model must satisfy the task's:

- modality;
- work type;
- sensitivity restrictions;
- allowed-model constraints;
- runtime availability.

If no eligible model exists, the system must not silently select an unauthorized model.

---

## 10. Task Passport Boundary

The Task Passport contains:

```text
allowed_models
```

This is a hard constraint.

The Model Router must not select a model outside the task's authorized model set.

Security-critical Task Passport changes must follow the Master Plan's versioning and re-authorization behavior.

---

## 11. Sensitivity-Aware Routing

Sensitivity is a routing constraint.

Conceptually:

```text
TASK SENSITIVITY
      ↓
ELIGIBLE MODEL SET
      ↓
CAPABILITY MATCH
      ↓
POLICY CHECK
      ↓
MODEL
```

A model cannot downgrade sensitivity to make itself eligible.

The exact classification-to-model matrix is deployment-specific and must be documented as policy.

---

## 12. Capability Matching

The router SHOULD maintain capability metadata such as:

```text
TEXT
REASONING
VISION
IMAGE UNDERSTANDING
CODE
STRUCTURED OUTPUT
LONG CONTEXT
TOOL USE
```

Example mapping:

| Task requirement | Preferred category |
|---|---|
| Routine text transformation | Lightweight text |
| Complex evidence analysis | Reasoning |
| Inspection photograph analysis | Multimodal |
| Code generation/debugging | Coding |
| Semantic indexing | Embedding |
| Mixed inspection analysis | Multimodal + reasoning |

These are routing categories, not mandatory model names.

---

## 13. Work Separation and Models

The Master Plan defines:

| Work type | Controlled model implication |
|---|---|
| Document | Text/reasoning + document tools |
| Spreadsheet | Text/reasoning + spreadsheet tools |
| Code | Coding model + coding tools |
| Image | Multimodal model |
| Calculation | Controlled calculator/execution |
| Analysis | Reasoning + evidence/verifier |

A combined task must explicitly declare its work types.

---

## 14. Model Router Output Contract

The router SHOULD return:

```text
model_id
model_category
selection_reason
required_capabilities
task_type
sensitivity
resource_constraints
fallback_options
policy_version
decision_id
```

The UI and audit record must expose at least:

- selected model;
- selection reason;
- required tools;
- constraints;
- fallback behavior.

---

## 15. Explainable Selection

Example:

```text
Task:
Scanned inspection analysis

Required:
- visual understanding
- document reasoning
- evidence synthesis

Sensitivity:
Confidential

Selected:
Local multimodal model

Reason:
Supports required visual input and operates inside
the sovereign runtime under the task's allowed-model policy.
```

The rationale explains the routing decision. It does not grant permission.

---

## 16. Agent Planner Boundary

The Agent Planner may request model use, but the model cannot alter the planner's security constraints.

Required execution graph:

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

Model output remains inside this controlled graph.

---

## 17. Model Output Is Untrusted

Model-generated:

- text;
- code;
- claims;
- classifications;
- plans;
- tool arguments;
- recommendations

must be treated as untrusted output until appropriate controls evaluate them.

The model must never be the authority for:

```text
DOCUMENT ACCESS
TOOL PERMISSION
NETWORK POLICY
TASK SENSITIVITY
DELIVERABLE RELEASE
```

Correct pattern:

```text
MODEL PROPOSAL
→ POLICY / ACTION GATE
→ CONTROLLED EXECUTION
```

---

## 18. RAG Boundary

Models receive only evidence authorized by RAG.

Required boundary:

```text
QUERY
→ KNOWLEDGE AUTHORIZATION
→ RETRIEVAL
→ PERMISSION FILTER
→ AUTHORIZED EVIDENCE
→ MODEL
```

The model must not receive unauthorized retrieval candidates.

Semantic relevance does not constitute authorization.

---

## 19. Multimodal Model Policy

Multimodal models may process:

- scanned PDFs;
- photographs;
- diagrams;
- visual evidence;
- engineering images.

Required conceptual flow:

```text
IMAGE
 ↓
MODEL OBSERVATION
 ↓
EVIDENCE / CONFIDENCE
 ↓
VERIFICATION
 ↓
CLAIM
```

Vision observations must not silently become source facts.

Ambiguous or low-confidence observations should be escalated when materially important.

---

## 20. Coding Model Policy

Coding models may inspect authorized code, propose changes, generate tests, and debug.

They must not:

- execute directly on the host;
- access unrestricted host files;
- access unrestricted networks;
- bypass Action Gate;
- bypass sandbox policy;
- release code without required verification/review.

Required path:

```text
CODING MODEL
→ CODE WORKSPACE
→ ACTION GATE
→ DOCKER SANDBOX
→ TEST
→ VERIFIER
→ REVIEW
→ OUTPUT
```

---

## 21. Structured Output

Where downstream components consume model output, structured output SHOULD be used.

Examples:

```text
model_selection.json
plan.json
tool_request.json
claim.json
verification_input.json
```

Schemas must be validated before downstream use.

Malformed model output must not be interpreted as a successful policy decision.

---

## 22. Model Context Boundaries

Model context must be limited to what the task requires.

It may include:

- authorized evidence;
- task purpose;
- permitted work type;
- required instructions;
- authorized tool descriptions;
- controlled execution state.

It must not contain unauthorized documents or unnecessary sensitive metadata.

The model must not receive broad organizational knowledge simply because that knowledge exists in the vector database.

---

## 23. Tool-Use Boundary

Models may propose tool calls but do not authorize them.

```text
MODEL
 ↓
TOOL REQUEST
 ↓
ACTION GATE
 ↓
POLICY CHECK
 ↓
ALLOW / DENY / REQUIRE_APPROVAL
 ↓
TOOL
```

Model reasoning cannot substitute for the Action Gate.

---

## 24. Network Policy

In sovereign mode:

```text
MODEL
 ↓
LOCAL SERVING
 ↓
LOCAL TOOLS / SERVICES
```

External AI APIs are not required.

External network access is denied by default.

The model cannot change network policy.

Blocked external requests should be recorded as observable security events.

---

## 25. Fallback Policy

Fallback is allowed only when the alternative remains authorized.

```text
PREFERRED MODEL
      ↓
AVAILABLE?
 ┌────┴────┐
YES       NO
 ↓         ↓
USE    CHECK FALLBACK
          ↓
      AUTHORIZED?
      ┌────┴────┐
     YES       NO
      ↓         ↓
    USE      STOP / REVIEW
```

A fallback model must satisfy:

- task capability;
- modality;
- sensitivity;
- `allowed_models`;
- sovereignty requirements;
- resource constraints;
- policy requirements.

The system must not fall back to an external AI API in sovereign mode.

---

## 26. Degraded Model Modes

Possible states:

```text
MODEL_UNAVAILABLE
MODEL_CAPABILITY_MISMATCH
GPU_RESOURCE_LIMIT
MODEL_POLICY_DENIED
MODEL_DISABLED
FALLBACK_UNAVAILABLE
```

The system should expose controlled degraded states.

It must not claim task completion when the required model capability was unavailable.

---

## 27. Bounded Agentic Use

Model participation in iterative execution must remain bounded.

The agent must stop on:

- policy denial;
- missing authorization;
- repeated verification failure;
- excessive loops;
- unsafe tool requests;
- ambiguous high-risk conditions.

The model cannot continue indefinitely because it believes another attempt may succeed.

---

## 28. Model and Verification Boundary

The Verifier checks model-produced work for:

- evidence;
- calculations;
- schema;
- document consistency;
- tool results;
- policy compliance;
- unsupported claims;
- output completeness.

Model confidence does not replace verification.

The model cannot mark its own output as verified.

---

## 29. Model and Review Boundary

Review mode is policy-controlled:

| Review mode | Use |
|---|---|
| Human | High-risk, sensitive, ambiguous, consequential work |
| Minimal-change iterative | Limited corrections |
| Auto | Low-risk work satisfying explicit policy |

The model cannot decide by itself that sensitive work is safe for automatic release.

---

## 30. Model Audit Requirements

Meaningful model decisions SHOULD record:

```text
task_id
user / identity
model_id
model_version
model_category
selection_reason
task_type
sensitivity
allowed_models
policy_version
decision
timestamp
fallback_used
```

The overall audit trace must make model selection reconstructable between Task Passport and Agent Plan.

---

## 31. Model Security Events

Useful events include:

```text
MODEL_SELECTED
MODEL_SELECTION_DENIED
MODEL_FALLBACK_REQUESTED
MODEL_FALLBACK_SELECTED
MODEL_DISABLED
MODEL_UNAVAILABLE
MODEL_CAPABILITY_MISMATCH
MODEL_POLICY_VIOLATION
EXTERNAL_MODEL_ATTEMPT_BLOCKED
MODEL_EXECUTION_FAILED
MODEL_OUTPUT_REJECTED
```

Detailed audit schema and retention belong to `audit-policy.md`.

---

## 32. Model Lifecycle

A controlled lifecycle is recommended:

```text
SOURCE
→ ACQUIRE
→ INTEGRITY CHECK
→ REGISTER
→ CAPABILITY TEST
→ SECURITY REVIEW
→ ACTIVATE
→ MONITOR
→ DISABLE / RETIRE
```

The exact approval and signing mechanisms are implementation decisions.

---

## 33. Model Evaluation

Before activation, evaluate:

- task capability;
- modality support;
- structured output reliability;
- latency;
- resource requirements;
- grounded behavior;
- unsupported-claim behavior;
- tool-request behavior;
- instruction following;
- prompt-injection resistance where applicable.

Evaluation results should be retained with the model registration.

---

## 34. Routing Quality Metrics

The Master Plan explicitly identifies **model-routing accuracy** as a metric.

Measure experimentally.

Useful metrics include:

- capability-match accuracy;
- sensitivity-compatible selection;
- fallback correctness;
- task completion after routing;
- latency;
- GPU/resource utilization;
- verification pass rate.

Do not claim fixed routing accuracy before benchmarking.

---

## 35. Security Testing

Model-related testing must cover applicable Master Plan threats:

- prompt injection;
- malicious documents;
- malicious code;
- tool abuse;
- data leakage;
- external network attempts;
- excessive agent loops;
- malicious multimodal inputs;
- approval bypass;
- unauthorized output release.

Recommended negative tests:

1. Model attempts to grant itself permission.
2. Model requests unauthorized RAG content.
3. Model requests a tool outside `allowed_tools`.
4. Model requests a model outside `allowed_models`.
5. Model attempts to change task sensitivity.
6. Model attempts to override network restrictions.
7. Model follows malicious instructions embedded in retrieved knowledge.
8. Model emits malformed tool arguments.
9. Model produces unsupported claims without evidence.
10. Model causes replanning beyond configured limits.
11. Model requests an external AI service in sovereign mode.
12. Model attempts to bypass review.

Every security failure must be traceable to the task, identity, policy decision, resource, action, and audit event.

---

## 36. MVP Model Demonstration

The Master Plan does not mandate specific model names.

The MVP should demonstrate automatic model selection across at least two task types using local models.

Representative demonstration:

```text
Task A: Document / reasoning
        ↓
Local text or reasoning model

Task B: Image / inspection
        ↓
Local multimodal model
```

Exact model names, sizes, quantization, and hardware should be selected after benchmarking and recorded in `decisions.md`.

---

## 37. Sovereign Model Acceptance Criteria

- [ ] Model serving is local.
- [ ] Model artifacts are inside the controlled environment.
- [ ] Confidential task context remains local.
- [ ] Authorized RAG evidence remains local.
- [ ] External AI APIs are not required.
- [ ] External network access is denied by default.
- [ ] Blocked external attempts are observable.
- [ ] Selected model is within `allowed_models`.
- [ ] Selection rationale is visible.
- [ ] Model capability matches task requirements.
- [ ] Fallback remains policy-constrained.
- [ ] Model output remains subject to Action Gate, verification, review, and audit.

---

## 38. Stable Requirement IDs

| ID | Requirement |
|---|---|
| `REQ-MODEL-001` | Models SHALL be selected through the controlled Model Router. |
| `REQ-MODEL-002` | Selection SHALL consider task type, modality, complexity, sensitivity, tools, GPU availability, latency, and capability. |
| `REQ-MODEL-003` | Selected models SHALL respect Task Passport `allowed_models`. |
| `REQ-MODEL-004` | Sovereign mode SHALL serve required models locally. |
| `REQ-MODEL-005` | Sovereign mode SHALL NOT require external AI APIs. |
| `REQ-MODEL-006` | Model selection SHALL expose a selection rationale to authorized users and audit. |
| `REQ-MODEL-007` | Model categories SHALL remain replaceable and shall not hard-code one model name. |
| `REQ-MODEL-008` | Model output SHALL NOT grant permissions or override policy. |
| `REQ-MODEL-009` | Model-generated tool requests SHALL pass through the Action Gate. |
| `REQ-MODEL-010` | Coding-model output SHALL execute only through the controlled workspace/sandbox path. |
| `REQ-MODEL-011` | Multimodal observations SHALL be verified before becoming authoritative claims. |
| `REQ-MODEL-012` | Model fallback SHALL remain within task, sensitivity, capability, and sovereignty policy. |
| `REQ-MODEL-013` | Model retries/replanning SHALL remain bounded. |
| `REQ-MODEL-014` | Relevant model decisions and execution events SHALL be auditable. |
| `REQ-MODEL-015` | Model failures SHALL produce explicit controlled failure/degraded states. |
| `REQ-MODEL-016` | Model security behavior SHALL be tested with positive and negative cases. |
| `REQ-MODEL-017` | Model artifacts SHOULD have integrity/provenance records before trusted activation. |
| `REQ-MODEL-018` | Model routing quality SHALL be benchmarked experimentally. |

---

## 39. Normative Policy vs Implementation Choices

### Normative

- controlled Model Router;
- local serving in sovereign mode;
- Task Passport model constraints;
- capability-aware selection;
- explainable selection;
- no self-authorization;
- Action Gate for tool actions;
- bounded execution;
- verification;
- auditability;
- policy-constrained fallback;
- sovereign network boundary.

### Baseline / replaceable implementation

The Master Plan identifies:

- vLLM or replaceable local serving;
- open-weight models;
- local multimodal models;
- replaceable model categories.

Specific model names, quantization, GPU allocation, serving parameters, and benchmark thresholds are implementation decisions.

---

## 40. Relationship to Other Policies

```text
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

Model Policy integrates with:

- Task Passport;
- Permission Engine;
- RAG;
- Work Separation;
- Agent Planner;
- Tool Registry;
- Action Gate;
- Sandbox;
- Verifier;
- Review;
- Audit / Trace;
- Secure Handover.

No model may bypass these boundaries.

---

## 41. Governing Model Principle

> **Choose the smallest authorized model capable of the task, keep it inside the sovereign boundary, make the selection explainable, constrain what it can see and do, verify what it produces, and never allow the model to become the authority over its own permissions.**

Final control relationship:

```text
MODEL
  ↓
PROPOSE / REASON
  ↓
POLICY
  ↓
ACTION GATE
  ↓
CONTROLLED EXECUTION
  ↓
VERIFICATION
  ↓
REVIEW
  ↓
AUDIT
  ↓
SECURE HANDOVER
```

Any implementation that allows a model to bypass these controls is outside the authoritative Medha architecture unless the deviation is explicitly documented, approved, and shown not to weaken security or sovereignty.
