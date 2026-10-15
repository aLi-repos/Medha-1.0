# Medha AI — Technical Specification

**Derived solely from:** `medha-ai-master-plan.md`  
**Document status:** Authoritative implementation specification derived from the Master `/plan`  
**Project:** Medha AI  
**Subtitle:** Sovereign Controlled Multimodal AI Workbench for Confidential Industrial Work  
**Project owner:** Rahamath Ali  
**Institutional affiliation:** Sri Chaitanya Institute of Technology and Research (SCITR), Khammam  
**Year:** 2026

> **Governing rule:** This specification operationalizes the Master `/plan`. It does not alter, weaken, remove, reorder, or bypass the authoritative architecture, security boundaries, workflow stages, interfaces, policies, MVP scope, or acceptance criteria defined in the Master `/plan`.

---

## 1. Purpose

Medha AI is a controlled, sovereign, on-premise AI workbench for confidential industrial work. It uses open-weight multimodal models and controlled agentic execution.

Medha is **not** a generic chatbot and must not be implemented as an unrestricted prompt-to-answer system.

The authoritative product workflow is:

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

The central product proposition is **controlled AI work execution**.

---

# 2. Scope

## 2.1 In scope

Medha shall provide:

- Authentication and identity management.
- Role-based access control.
- Fine-grained authorization.
- Task Passport creation and enforcement.
- Permission-aware RAG.
- Local document ingestion.
- Local OCR.
- Local embeddings.
- Multimodal processing.
- Task-purpose classification.
- Work separation.
- Local model routing.
- Stateful agent planning.
- Controlled tool execution.
- Action Gate enforcement.
- Task-scoped workspace.
- Sandboxed code execution.
- Verification.
- Evidence-linked outputs.
- Real deliverable generation.
- Human, minimal-change iterative, and policy-controlled automatic review paths.
- Audit and traceability.
- Sovereign/air-gapped execution.
- Secure handover with manifest and SHA-256 integrity hash.

## 2.2 Non-goals

The following are explicitly outside the intended product behavior:

- A generic public chatbot.
- An unrestricted agent with access to all organizational data.
- Model-generated permission decisions.
- Automatic permission escalation.
- Unrestricted host execution.
- Unrestricted network access.
- External AI APIs as a requirement for sovereign operation.
- Claims of uniqueness based only on using a local LLM.

---

# 3. Authoritative Architecture

The following architecture is the conceptual source of truth:

```text
Medha
├── UI
├── API Gateway
├── Authentication
├── RBAC
├── Task Passport
├── Permission Engine
├── RAG
│   ├── ingestion
│   ├── OCR
│   ├── embeddings
│   ├── retrieval
│   └── permission filtering
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

## 3.1 Authoritative execution stages

The implementation shall preserve these stages:

1. User.
2. Authorization gate.
3. Knowledge permission and RAG.
4. Task purpose.
5. Work separation.
6. Action gate.
7. Task checking, model selection, and plan generation.
8. Controlled workspace for files, code, spreadsheets, and working artifacts.
9. Docker or hardened sandbox execution.
10. Verification.
11. Deliverable factory and deliverable package creation.
12. Audit and trace.
13. Review through human, minimal-change iterative, or policy-approved automatic paths.
14. Safe and isolated AI execution environment.
15. Output and secure handover.

No component may bypass authorization, policy, verification, audit, or handover boundaries.

---

# 4. Technology Baseline

| Concern | Baseline |
|---|---|
| Backend orchestration | Python |
| API | FastAPI, Pydantic, Uvicorn |
| Frontend | TypeScript, React, Next.js, Tailwind CSS |
| Identity | Keycloak |
| Broad authorization | Keycloak roles / RBAC |
| Fine-grained authorization | OpenFGA |
| Policy evaluation | Open Policy Agent (OPA) |
| Primary database | PostgreSQL |
| Cache and temporary state | Redis |
| Document parsing | Docling, PyMuPDF |
| Local OCR | PaddleOCR |
| Local embeddings | BGE-M3 or replaceable equivalent |
| Vector database | Qdrant |
| Local model serving | vLLM or replaceable local serving layer |
| Agent orchestration | LangGraph or replaceable stateful graph layer |
| Tool protocol | MCP-compatible internal architecture |
| Sandbox | Docker; gVisor where practical |
| Deliverables | `python-docx`, `openpyxl`, `python-pptx`, ReportLab |
| Observability | OpenTelemetry |
| Integrity | SHA-256 |
| Deployment | Linux, Docker Compose, NVIDIA CUDA where GPU is available |

## 4.1 Technology rules

1. Baseline technologies are implementation choices, not architectural boundaries.
2. Replaceable subsystems shall expose stable internal contracts.
3. Medha shall not depend on one vendor, one model, or one database.
4. Sovereign operation shall not require an external AI API.
5. External services must never weaken the sovereign security boundary.
6. Any replacement must be documented as an architecture decision.

---

# 5. Deployment Architecture

## 5.1 Deployment principle

The authoritative production deployment is **on-premise / self-hosted / sovereign**.

The complete confidential workflow shall operate inside the organization's controlled environment.

The following local components shall remain inside the sovereign boundary:

```text
Local UI
Local API
Local Authentication
Local RBAC
Local Permission Engine
Local RAG
Local OCR
Local Embeddings
Local Vector DB
Local LLMs
Local Vision Models
Local Agent
Local Tools
Local Workspace
Local Sandbox
Local Verifier
Local Deliverables
Local Audit
Local Handover
```

External AI APIs are not required.

External network access is denied by default.

---

## 5.2 Deployment profiles

### Profile A — Sovereign Production

**Purpose:** Real confidential industrial deployment.

```text
Organization Network
│
├── Reverse Proxy / Internal Gateway
│
├── Medha Frontend
│
├── Medha Backend
│   ├── Authentication
│   ├── RBAC
│   ├── Task Passport
│   ├── Permission Engine
│   ├── RAG
│   ├── Model Router
│   ├── Agent Planner
│   ├── Tool Registry
│   ├── Action Gate
│   ├── Workspace
│   ├── Sandbox
│   ├── Verifier
│   ├── Deliverables
│   ├── Audit
│   └── Handover
│
├── PostgreSQL
├── Redis
├── Qdrant
├── Local Model Server
├── Local OCR / Embedding Services
└── Docker / Hardened Sandbox
```

**Required properties:**

- No confidential data leaves the organization-controlled environment.
- Local model inference.
- Local OCR.
- Local embeddings.
- Local vector database.
- Local files.
- Local audit.
- External network denied by default.
- All consequential actions pass through policy enforcement.

---

## 5.3 Profile B — Air-Gapped Deployment

**Purpose:** Highest-isolation deployment where the environment has no external network access.

```text
AIR-GAPPED NETWORK
│
├── Medha UI
├── API
├── Keycloak
├── OPA
├── OpenFGA
├── PostgreSQL
├── Redis
├── Qdrant
├── Local Model Server
├── OCR
├── Embeddings
├── Agent
├── Tools
├── Sandbox
├── Verifier
├── Deliverables
└── Audit / Handover
```

All required model files, packages, containers, policies, and knowledge-base inputs must be provisioned through an approved offline process.

---

## 5.4 Profile C — Developer Local Deployment

**Purpose:** Local engineering and testing.

Recommended baseline:

```text
Developer Machine
│
├── frontend/
├── backend/
├── Docker Compose
│   ├── PostgreSQL
│   ├── Redis
│   ├── Qdrant
│   ├── Keycloak
│   └── OPA
├── Local Model Server
├── Local OCR
└── Sandbox
```

The developer profile shall preserve the same logical authorization, action-control, verification, and audit boundaries as the sovereign deployment.

---

## 5.5 Profile D — Frontend Preview / Vercel Deployment

**Purpose:** UI development, visual review, and non-confidential frontend demonstration.

The frontend may be deployed to **Vercel** as a deployment option because the baseline frontend is Next.js.

```text
Browser
   ↓
Vercel-hosted Next.js Frontend
   ↓
API endpoint
```

### Critical sovereignty rule

A Vercel-hosted frontend **must not be treated as the sovereign production environment**.

For confidential industrial work:

```text
Confidential Data
      X
      │
      └── must NOT be sent to Vercel
```

The Vercel profile is therefore limited to:

- UI development.
- Frontend preview.
- Non-confidential demo data.
- Mock API responses where required.
- Public-safe visual demonstrations.

The actual sovereign workflow remains on-premise/self-hosted.

For a real confidential deployment, the frontend shall be hosted inside the controlled organization environment.

---

## 5.6 Profile E — Hybrid Demonstration Deployment

If a public frontend is required for a demonstration:

```text
Vercel
  │
  └── Non-confidential Next.js UI
          │
          └── Demonstration API / approved demo environment

Organization-controlled environment
  │
  └── Real sovereign Medha deployment
```

The hybrid demonstration environment shall never silently route confidential industrial data through public infrastructure.

The demo dataset must be explicitly non-confidential.

---

## 5.7 Deployment separation rule

Deployment convenience must never redefine the architecture.

```text
Vercel = frontend hosting option
On-Prem = sovereign execution environment
Docker = application/container isolation mechanism
gVisor = optional hardened sandbox mechanism
```

Vercel, or any other frontend hosting service, must not become a dependency for sovereign operation.

---

# 6. UI Requirements

Medha must not imitate a normal ChatGPT interface.

The UI shall communicate:

- Control.
- Security.
- Task state.
- Model selection.
- Tools.
- Evidence.
- Verification.
- Review.
- Audit status.

## Required screens

- Login.
- Dashboard.
- New Task.
- Task Passport.
- Workspace.
- Knowledge.
- Agent Execution.
- Evidence.
- Review.
- Deliverables.
- Audit / Trace.
- Administration.

## Visible task information

Where authorized, show:

- Current user identity and role.
- Task ID and sensitivity.
- Task purpose.
- Allowed sources.
- Allowed tools.
- Network policy.
- Selected model.
- Model selection rationale.
- Execution plan.
- Current execution state.
- Evidence supporting important claims.
- Verification results.
- Verification failures.
- Review mode.
- Approval status.
- Deliverable manifest.
- Integrity status.
- Audit timeline.

The UI shall never expose unauthorized data, evidence, tools, or actions.

---

# 7. Authentication and Authorization

## 7.1 Authentication

Keycloak shall provide:

- Login.
- Identity.
- Sessions.
- Tokens.
- Role management.
- Administrator management.

## 7.2 Initial roles

```text
Operator
Engineer
Reviewer
Administrator
```

## 7.3 Authorization

Broad authorization:

```text
Keycloak RBAC
```

Fine-grained authorization:

```text
OpenFGA
```

Policy evaluation:

```text
OPA + OpenFGA
```

The LLM must never be the final authority for permissions.

---

# 8. Task Passport

Every task shall receive a persisted Task Passport before controlled execution.

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

## 8.1 Passport rules

1. Security-critical fields are immutable after execution begins.
2. If a security-critical field changes, the change must be versioned.
3. A changed security-critical field must trigger re-authorization.
4. The passport travels with the task context.
5. The passport is consulted by:
   - RAG.
   - Model Router.
   - Tool invocation.
   - Workspace access.
   - Sandbox policy.
   - Review routing.
   - Secure handover.

---

# 9. Permission Engine

The Permission Engine evaluates:

```text
User + Task + Resource + Action + Sensitivity + Policy
```

Every policy decision returns:

```text
ALLOW
DENY
REQUIRE_APPROVAL
```

## Required behavior

- Default deny.
- Deterministic decisions.
- Testable policies.
- Versioned policies.
- Auditable decisions.
- Decision explanations.
- Explicit conflict handling.
- Emergency-disable capability.

The LLM may propose an action but cannot:

- Grant itself permission.
- Expand task scope.
- Approve output release.
- Override network restrictions.
- Override policy decisions.

---

# 10. RAG and Multimodal Ingestion

## 10.1 Permission-aware RAG

Required sequence:

```text
QUERY
→ DETERMINE ALLOWED KNOWLEDGE
→ RETRIEVE RELEVANT KNOWLEDGE
→ APPLY PERMISSION FILTERING
→ RETURN AUTHORIZED EVIDENCE
```

Semantic relevance is not authorization.

Permission filtering must occur before evidence is exposed to the model or user.

## 10.2 Ingestion

Supported inputs:

- PDF.
- Scanned PDF.
- DOCX.
- TXT.
- Images.
- Industrial documents.

Pipeline:

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

## 10.3 OCR

OCR shall run locally and extract:

- Text.
- Tables.
- Page references.
- OCR confidence.
- Document metadata.

Low-confidence OCR must be flagged.

Low-confidence OCR must not silently become authoritative evidence.

## 10.4 Indexed representation

Each indexed representation shall retain at least:

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

## 10.5 Evidence model

Medha shall distinguish:

```text
Source fact
Inference
Calculation
Recommendation
```

Important claims shall support:

```text
SOURCE → EVIDENCE → CLAIM → ACTION → OUTPUT
```

An inference must never silently become an organizational fact.

---

# 11. Task Purpose and Work Separation

Task Purpose establishes:

- Identity.
- Sensitivity.
- Purpose.

These control:

- Model selection.
- Knowledge access.
- Tools.
- Actions.
- Approval.
- Output handling.

## Work types

| Work type | Controlled pipeline |
|---|---|
| Document | Parsing, evidence extraction, document generation |
| Spreadsheet | Workbook access and spreadsheet tools |
| Code | Coding tools, versioned workspace, tests, sandbox |
| Image | Multimodal processing and visual evidence |
| Calculation | Controlled calculator or execution tool |
| Analysis | Agent reasoning, evidence graph, verifier |

Tasks may combine work types.

The combination must be explicit in the Task Passport and execution plan.

---

# 12. Model Router

The Model Router shall explicitly check the task and select an appropriate local model.

Selection considers:

- Task type.
- Modality.
- Complexity.
- Sensitivity.
- Required tools.
- GPU availability.
- Latency.
- Model capability.

The system shall expose:

- Selected model.
- Selection rationale.
- Required tools.
- Execution plan.
- Constraints.
- Fallback behavior.

Model categories may include:

```text
Lightweight text
Reasoning
Multimodal
Coding
```

Model names remain replaceable implementation choices.

---

# 13. Agent Planner

The Agent Planner shall use a bounded stateful execution graph equivalent to:

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

## Agent stopping conditions

The agent must stop on:

- Policy denial.
- Missing authorization.
- Repeated verification failure.
- Excessive loops.
- Unsafe tool request.
- Ambiguous high-risk condition.

Retries and replanning must be bounded.

---

# 14. Tool Registry

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

---

# 15. Action Gate

Every consequential action shall follow:

```text
AGENT
→ ACTION GATE
→ POLICY CHECK
→ ALLOW / DENY / REQUIRE_APPROVAL
→ TOOL
```

The Action Gate is mandatory.

No agent-generated action may directly invoke a consequential tool without policy evaluation.

---

# 16. Controlled Workspace

The workspace shall support:

- Documents.
- PDFs.
- Images.
- Code.
- Excel files.
- Presentations.
- Generated files.
- Intermediate files.

Every working artifact shall track:

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

---

# 17. Sandbox

All generated code must execute inside a sandbox.

It must never execute directly on the host.

## Baseline

```text
Docker
```

## Optional hardened deployment

```text
gVisor
```

## Required sandbox controls

- Isolated filesystem.
- CPU limits.
- Memory limits.
- Execution timeout.
- Restricted permissions.
- Controlled mounts.
- No unrestricted host access.
- Network disabled by default.

A failed or interrupted execution must preserve logs and status without exposing host resources.

---

# 18. Verification

The Verifier shall check:

- Schema.
- Calculations.
- Evidence.
- Document consistency.
- Tool results.
- Policy compliance.
- Unsupported claims.
- Output completeness.

Verification types:

```text
Rule verification
Calculation verification
Execution verification
Evidence verification
Policy verification
```

Failure workflow:

```text
FAIL
→ FEEDBACK
→ REPLAN
→ EXECUTE
→ VERIFY
```

Retries must be bounded and visible in audit.

---

# 19. Deliverable Factory

Medha shall generate real work products:

- DOCX.
- XLSX.
- PPTX.
- PDF.
- Code where authorized.

A deliverable is a package, not merely a file.

It shall contain:

- Final output.
- Source references.
- Evidence.
- Verification result.
- Task ID.
- Audit reference.
- Manifest.

Example:

```text
MEDHA-PACKAGE/
├── approval_note.docx
├── evidence.json
├── verification.json
├── audit.json
└── manifest.json
```

---

# 20. Review System

Review mode is selected through policy.

| Mode | Use |
|---|---|
| Human | High-risk, sensitive, ambiguous, consequential |
| Minimal-change iterative | Limited corrections |
| Auto | Only low-risk work explicitly permitted by policy |

## Minimal-change rule

A minimal-change iteration shall:

1. Modify only the requested portion.
2. Rerun relevant verification.
3. Return to review.

The LLM cannot decide by itself that automatic release is safe.

---

# 21. Audit and Trace

Use:

- OpenTelemetry.
- PostgreSQL or equivalent durable audit storage.

Record:

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

The trace must reconstruct:

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

---

# 22. Sovereign Mode

Sovereign mode means the complete workflow operates inside the organization's controlled environment.

Local components include:

- LLMs.
- Vision.
- OCR.
- Embeddings.
- RAG.
- Agents.
- Tools.
- Sandbox.
- Verifier.
- Audit.
- Deliverables.

External network access is denied by default.

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

# 23. API and Service Contracts

The implementation shall expose stable internal service boundaries corresponding to the authoritative architecture.

Recommended logical API domains:

```text
/auth
/rbac
/tasks
/task-passport
/permissions
/knowledge
/rag
/models
/router
/agent
/tools
/actions
/workspace
/sandbox
/verify
/deliverables
/review
/audit
/handover
```

Every endpoint shall enforce:

```text
Identity
→ Authorization
→ Task Context
→ Policy
→ Action
→ Audit
```

## Error model

Errors must be machine-readable and auditable.

Recommended categories:

```text
AUTHENTICATION_FAILED
AUTHORIZATION_DENIED
APPROVAL_REQUIRED
TASK_INVALID
PASSPORT_INVALID
KNOWLEDGE_ACCESS_DENIED
RAG_NO_AUTHORIZED_EVIDENCE
MODEL_UNAVAILABLE
TOOL_NOT_AUTHORIZED
ACTION_DENIED
SANDBOX_FAILED
VERIFICATION_FAILED
DELIVERABLE_FAILED
HANDOVER_DENIED
POLICY_ERROR
INTERNAL_ERROR
```

Security-sensitive errors must not expose unauthorized information.

---

# 24. Data Model

The specification requires domain entities for:

- User.
- Role.
- Task.
- Task Passport.
- Resource.
- Permission.
- Policy.
- Policy Decision.
- Knowledge Document.
- Knowledge Chunk.
- Evidence.
- Model.
- Model Selection.
- Tool.
- Tool Invocation.
- Workspace Artifact.
- Sandbox Execution.
- Verification Result.
- Review.
- Audit Event.
- Deliverable.
- Package.
- Manifest.
- Handover.

Every security-sensitive entity must have appropriate ownership, classification, authorization, versioning, and audit relationships.

---

# 25. Repository Structure

Default target:

```text
medha-ai/
├── frontend/
│   ├── app/
│   ├── components/
│   ├── pages/
│   └── services/
├── backend/
│   ├── api/
│   ├── authentication/
│   ├── rbac/
│   ├── task_passport/
│   ├── permission_engine/
│   ├── rag/
│   │   ├── ingestion/
│   │   ├── ocr/
│   │   ├── embeddings/
│   │   ├── retrieval/
│   │   └── permission_filter/
│   ├── multimodal/
│   ├── work_separation/
│   ├── model_router/
│   ├── agent/
│   ├── tool_registry/
│   ├── action_gate/
│   ├── workspace/
│   ├── sandbox/
│   ├── verifier/
│   ├── deliverables/
│   ├── review/
│   ├── audit/
│   ├── handover/
│   └── security/
├── models/
├── policies/
├── knowledge_base/
├── workspace/
├── sandbox/
├── tests/
├── scripts/
├── configs/
├── docker/
├── docs/
├── .env.example
├── docker-compose.yml
├── README.md
└── LICENSE
```

---

# 26. MVP Vertical Slice

The first complete vertical slice shall be:

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

Primary workflow inputs:

- Scanned inspection report.
- Internal SOP/manual.
- Inspection photograph.

Expected result:

- Evidence-linked inspection analysis.
- Approval note.
- Classification.
- Authorization metadata.
- Verification metadata.
- Audit metadata.
- Integrity metadata.

## Secondary coding workflow

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

---

# 27. Development Phases

| Phase | Outcome |
|---:|---|
| 0 | Architecture and specification |
| 1 | Repository foundation |
| 2 | Authentication and RBAC |
| 3 | Task Passport |
| 4 | Permission Engine |
| 5 | RAG, ingestion, and OCR |
| 6 | Local models and Model Router |
| 7 | Work Separation |
| 8 | Agent Planner |
| 9 | Tool Registry and Action Gate |
| 10 | Workspace |
| 11 | Docker sandbox |
| 12 | Verifier |
| 13 | Deliverable Factory |
| 14 | Audit and trace |
| 15 | Review system |
| 16 | Secure handover |
| 17 | Frontend |
| 18 | Security testing |
| 19 | End-to-end demo |

Each phase must define:

- Interfaces.
- Tests.
- Security implications.
- Data migrations.
- Observability events.
- Exit criteria.

The vertical slice may interleave phases when that produces an end-to-end path sooner.

---

# 28. Security Testing

Tests must cover:

- Unauthorized document access.
- RBAC bypass.
- OpenFGA bypass.
- OPA policy bypass.
- RAG permission bypass.
- Prompt injection.
- Malicious documents.
- Malicious code.
- Sandbox escape.
- Tool abuse.
- Unauthorized file access.
- External network attempts.
- Data leakage.
- Approval bypass.
- Unauthorized output release.
- Excessive agent loops.
- Malicious multimodal inputs.

Every security failure must be traceable to:

```text
Task
→ Identity
→ Policy decision
→ Resource
→ Action
→ Audit event
```

Positive and negative cases shall be tested.

Security tests should run in CI where practical.

---

# 29. Performance and Quality Metrics

Measure experimentally:

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

The implementation shall define:

- Metric formula.
- Collection point.
- Test dataset.
- Reporting frequency.
- MVP threshold after baseline measurement.

Do not promise fixed performance values before benchmarking.

---

# 30. Definition of Done

The MVP is complete only when the vertical slice demonstrates:

- User authentication.
- RBAC.
- Fine-grained authorization.
- Persisted Task Passport.
- Task purpose.
- Sensitivity.
- Permission-aware knowledge access.
- Local document ingestion.
- Local OCR.
- Local embeddings.
- Permission-aware RAG.
- Work separation.
- Explainable model selection.
- Bounded agent plan.
- Controlled tools.
- Action Gate.
- Controlled workspace.
- Sandboxed code execution.
- Verification.
- Evidence linkage.
- Real deliverable.
- Audit trace.
- Human review.
- Minimal-change review.
- Policy-controlled automatic review path.
- Safe isolated execution.
- Classification and integrity metadata.
- Secure handover.
- Manifest.
- SHA-256 hash.
- No required external AI service.
- Visible proof of sovereignty.

---

# 31. Deployment Acceptance Criteria

## 31.1 Local deployment

- `docker-compose.yml` can start the required local infrastructure.
- Local model serving is functional.
- Local OCR is functional.
- Local embedding generation is functional.
- Qdrant is local.
- PostgreSQL is local.
- Authentication is local.
- Audit storage is local.
- Sandbox is local.
- External AI API is not required.

## 31.2 Air-gapped deployment

- Required runtime artifacts can be installed offline.
- No external AI endpoint is required.
- Network-denial behavior is demonstrable.
- Local models and supporting services remain functional.
- Audit records remain available locally.

## 31.3 Frontend deployment

For frontend preview:

```text
Next.js → Vercel
```

is permitted for non-confidential UI work.

For sovereign production:

```text
Next.js → Organization-controlled hosting
```

is required.

The frontend deployment choice must never cause confidential industrial data to leave the sovereign boundary.

---

# 32. Environment Configuration

The implementation shall maintain environment-specific configuration without changing the architecture.

Suggested environments:

```text
development
local-demo
staging
sovereign-production
air-gapped-production
```

Environment configuration must control:

- Model endpoints.
- Database endpoints.
- Vector DB endpoints.
- Authentication endpoints.
- Policy endpoints.
- Tool availability.
- Network policy.
- Sandbox limits.
- Logging level.
- Audit configuration.

Secrets must not be committed to source control.

Provide `.env.example` with placeholders only.

---

# 33. Observability

Use OpenTelemetry for application-level traces and metrics.

Observability shall support reconstruction of:

```text
User
→ Task
→ Passport
→ Permission
→ Evidence
→ Model
→ Plan
→ Action
→ Tool
→ Sandbox
→ Verification
→ Deliverable
→ Review
→ Handover
```

Sensitive content must not be unnecessarily duplicated into logs.

Audit and operational telemetry shall remain inside the intended security boundary.

---

# 34. Evidence-Bound Output Rules

Important generated claims must be classified as:

```text
FACT
INFERENCE
CALCULATION
RECOMMENDATION
```

Claims that require evidence must reference the corresponding evidence.

The output package should allow a reviewer to move from:

```text
OUTPUT
→ CLAIM
→ EVIDENCE
→ SOURCE
```

Unsupported claims must be surfaced by the Verifier.

---

# 35. Secure Handover

Required flow:

```text
OUTPUT
→ PACKAGE
→ HASH
→ ACCESS CONTROL
→ AUTHORIZED RECIPIENT
```

The secure package shall contain:

- Manifest.
- SHA-256 integrity hash.
- Task ID.
- Timestamp.
- Verification status.
- Access policy.

Handover must not release an unauthorized output.

---

# 36. Traceability Matrix

| Requirement area | Primary verification |
|---|---|
| Authentication | Authentication tests |
| RBAC | Positive/negative authorization tests |
| Fine-grained authorization | OpenFGA policy tests |
| Policy enforcement | OPA decision tests |
| Task Passport | Schema + lifecycle tests |
| Permission-aware RAG | Retrieval authorization tests |
| OCR | OCR benchmark/test set |
| Model Router | Routing benchmark |
| Agent Planner | State-machine tests |
| Tool Registry | Schema/permission tests |
| Action Gate | Policy bypass tests |
| Workspace | Access-control tests |
| Sandbox | Isolation and escape tests |
| Verifier | Verification test suite |
| Deliverables | Artifact/package tests |
| Review | Workflow tests |
| Audit | Trace reconstruction tests |
| Sovereignty | Network-isolation tests |
| Handover | Integrity/access-control tests |

Every requirement should have a stable identifier.

Examples:

```text
REQ-AUTH-001
REQ-RAG-001
REQ-MODEL-001
REQ-TOOL-001
REQ-SANDBOX-001
REQ-VERIFY-001
REQ-AUDIT-001
REQ-HANDOVER-001
```

Each requirement shall identify its verification method.

---

# 37. Implementation Rules for Coding Agents

The coding agent shall:

1. Inspect the repository before implementation.
2. Preserve compatible existing work.
3. Identify conflicts explicitly.
4. Never silently replace architecture.
5. Preserve the authoritative workflow order.
6. Treat security boundaries as mandatory.
7. Keep replaceable technologies behind stable interfaces.
8. Build the vertical slice before broad feature expansion.
9. Add tests with implementation.
10. Add audit events for security-sensitive actions.
11. Keep secrets outside source control.
12. Never introduce an external AI dependency into sovereign mode.
13. Never bypass the Action Gate.
14. Never execute generated code directly on the host.
15. Never expose unauthorized RAG evidence.
16. Never let the LLM make final security decisions.
17. Document deviations in `docs/decisions.md`.
18. Stop and request architectural approval when a proposed change would weaken the control model.

---

# 38. Required Supporting Documents

The repository shall contain:

```text
docs/
├── spec.md
├── architecture.md
├── security.md
├── threat-model.md
├── rag-policy.md
├── model-policy.md
├── tool-policy.md
├── audit-policy.md
├── deployment.md
└── decisions.md
```

This specification is the concrete implementation document derived from the Master `/plan`.

---

# 39. Ownership and License Notice

Do not represent SCITR as a legal copyright owner unless an applicable institutional policy, project rule, or written agreement establishes that ownership.

Initial notice:

> Copyright © 2026 Rahamath Ali. Medha AI is a research and prototype project developed by Rahamath Ali at Sri Chaitanya Institute of Technology and Research (SCITR), Khammam, Telangana, India. All rights reserved unless otherwise stated. Third-party libraries, frameworks, models, datasets, and dependencies remain subject to their respective licenses.

If verified institutional or joint ownership later applies, update the language according to the governing documentation.

---

# 40. Final Governing Principle

Medha must not behave like:

```text
USER → CHATBOX → LLM → ANSWER
```

Medha must behave like:

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

This workflow is authoritative.

Any implementation that bypasses these controls is out of scope unless the deviation is explicitly documented, approved, and shown not to weaken security or sovereignty.

---

# Appendix A — Deployment Summary

| Deployment | Frontend | Backend | Models | Data | Purpose |
|---|---|---|---|---|---|
| Developer Local | Next.js local | Local FastAPI | Local | Local | Development |
| Local Demo | Next.js local | Local FastAPI | Local | Local demo data | SIH prototype |
| Vercel Preview | Vercel | Demo/approved API only | No confidential model dependency | Non-confidential only | UI preview |
| Hybrid Demo | Vercel/non-confidential frontend | Approved demo environment | Demo/local | Non-confidential | Public demonstration |
| Sovereign Production | On-prem | On-prem | Local | On-prem | Confidential industrial work |
| Air-Gapped | On-prem | On-prem | Local | Air-gapped | Highest isolation |

**Rule:** The Vercel deployment is a frontend hosting option, not a replacement for sovereign execution.

---

# Appendix B — Primary Demo Flow

```text
USER
 ↓
LOGIN
 ↓
AUTHORIZATION GATE
 ↓
TASK PASSPORT
 ↓
KNOWLEDGE PERMISSION
 ↓
SCANNED INSPECTION REPORT
 ↓
LOCAL OCR
 ↓
PERMISSION-AWARE RAG
 ↓
INSPECTION PHOTOGRAPH
 ↓
MULTIMODAL ANALYSIS
 ↓
TASK PURPOSE
 ↓
WORK SEPARATION
 ↓
MODEL ROUTER
 ↓
AGENT PLANNER
 ↓
ACTION GATE
 ↓
CONTROLLED TOOL
 ↓
DOCKER SANDBOX
 ↓
VERIFIER
 ↓
DOCX APPROVAL NOTE
 ↓
EVIDENCE + VERIFICATION
 ↓
AUDIT / TRACE
 ↓
REVIEW
 ↓
SECURE HANDOVER
 ↓
OUTPUT
```

This is the preferred vertical slice for demonstrating controlled AI work execution.

---

# Appendix C — Master Plan Preservation Statement

This `docs/spec.md` intentionally preserves the Master `/plan` architecture, including:

- The authoritative component architecture.
- The 15-stage conceptual workflow.
- Authentication and RBAC.
- Task Passport.
- Permission Engine.
- Permission-aware RAG.
- Work Separation.
- Model Router.
- Agent Planner.
- Tool Registry.
- Action Gate.
- Workspace.
- Sandbox.
- Verifier.
- Deliverable Factory.
- Audit / Trace.
- Review.
- Safe and isolated execution.
- Output.
- Secure handover.
- Sovereign deployment.
- MVP vertical slice.
- Security testing.
- Performance metrics.
- Definition of done.

Deployment options such as Vercel are treated only as implementation/deployment choices and do not change the authoritative sovereign architecture.
