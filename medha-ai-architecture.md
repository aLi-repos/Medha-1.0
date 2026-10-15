# Medha AI — Architecture

**Project:** Medha AI  
**Subtitle:** Sovereign Controlled Multimodal AI Workbench for Confidential Industrial Work  
**Architecture status:** Authoritative architecture document derived from the Master `/plan`  
**Year:** 2026

> **Architecture rule:** This document does not alter, weaken, remove, reorder, or bypass the authoritative workflow, security boundaries, component boundaries, MVP scope, or governing principles defined in the Master `/plan`.

---

## 1. Purpose

This document defines the component boundaries, logical architecture, data flows, execution flow, deployment topology, trust boundaries, and major interaction sequences for Medha AI.

Medha AI is a controlled, sovereign, on-premise AI workbench for confidential industrial work using open-weight multimodal models and controlled agentic execution.

Medha is **not** an unrestricted prompt-to-answer chatbot.

---

## 2. Authoritative System Behavior

The complete Medha workflow is:

```text
INPUT
  ↓
IDENTITY
  ↓
AUTHORIZATION
  ↓
KNOWLEDGE AUTHORIZATION
  ↓
TASK CONTEXT
  ↓
WORK SEPARATION
  ↓
ACTION CONTROL
  ↓
MODEL + TOOL PLANNING
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
ISOLATED EXECUTION
  ↓
OUTPUT
  ↓
SECURE HANDOVER
```

No component may bypass authorization, policy, verification, audit, isolation, or secure handover.

---

## 3. High-Level Component Architecture

```text
                                  ┌──────────────────────┐
                                  │        USER          │
                                  │ Task + Doc/Code/     │
                                  │ Image/Multimodal     │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │         UI           │
                                  │ Next.js / React      │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │     API GATEWAY      │
                                  │ FastAPI / Pydantic   │
                                  └──────────┬───────────┘
                                             │
                         ┌───────────────────┴───────────────────┐
                         │                                       │
                         ▼                                       ▼
              ┌──────────────────────┐              ┌──────────────────────┐
              │   AUTHENTICATION      │              │     RBAC / POLICY    │
              │      Keycloak         │              │ Keycloak + OPA +    │
              │                       │              │ OpenFGA              │
              └──────────┬───────────┘              └──────────┬───────────┘
                         │                                       │
                         └───────────────────┬───────────────────┘
                                             ▼
                                  ┌──────────────────────┐
                                  │    TASK PASSPORT     │
                                  │ identity / purpose / │
                                  │ sensitivity / scope  │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │   PERMISSION ENGINE  │
                                  │ User + Task +        │
                                  │ Resource + Action +  │
                                  │ Sensitivity + Policy │
                                  └───────┬────────┬─────┘
                                          │        │
                         ┌────────────────┘        └────────────────┐
                         ▼                                         ▼
              ┌──────────────────────┐                  ┌──────────────────────┐
              │         RAG          │                  │   WORK SEPARATION    │
              │ ingestion / OCR /    │                  │ document / sheet /   │
              │ embeddings /         │                  │ code / image /       │
              │ retrieval /          │                  │ calculation /        │
              │ permission filter    │                  │ analysis             │
              └──────────┬───────────┘                  └──────────┬───────────┘
                         │                                         │
                         └──────────────────┬──────────────────────┘
                                            ▼
                                  ┌──────────────────────┐
                                  │     MODEL ROUTER     │
                                  │ model + tool + plan  │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │    AGENT PLANNER     │
                                  │ Understand → Retrieve│
                                  │ → Plan → Act →       │
                                  │ Observe → Verify →    │
                                  │ Replan → Deliver      │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │     ACTION GATE      │
                                  │ policy check before  │
                                  │ consequential action │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │     TOOL REGISTRY    │
                                  │ registered, scoped,  │
                                  │ risk-aware tools     │
                                  └──────────┬───────────┘
                                             │
                         ┌───────────────────┴───────────────────┐
                         │                                       │
                         ▼                                       ▼
              ┌──────────────────────┐              ┌──────────────────────┐
              │      WORKSPACE       │              │       SANDBOX        │
              │ task-scoped files    │              │ Docker / gVisor     │
              │ and artifacts        │              │ isolated execution   │
              └──────────┬───────────┘              └──────────┬───────────┘
                         │                                       │
                         └───────────────────┬───────────────────┘
                                             ▼
                                  ┌──────────────────────┐
                                  │       VERIFIER       │
                                  │ evidence / rules /   │
                                  │ calculation / policy │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │ DELIVERABLE FACTORY  │
                                  │ DOCX / XLSX / PPTX / │
                                  │ PDF / Code           │
                                  └──────────┬───────────┘
                                             │
                         ┌───────────────────┴───────────────────┐
                         │                                       │
                         ▼                                       ▼
              ┌──────────────────────┐              ┌──────────────────────┐
              │    AUDIT / TRACE     │              │       REVIEW         │
              │ OpenTelemetry + DB   │              │ Human / Minimal /   │
              │ reconstructable trace│              │ Policy-approved Auto │
              └──────────┬───────────┘              └──────────┬───────────┘
                         │                                       │
                         └───────────────────┬───────────────────┘
                                             ▼
                                  ┌──────────────────────┐
                                  │ SAFE & ISOLATED AI   │
                                  │     ENVIRONMENT      │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │       OUTPUT         │
                                  │ classified +         │
                                  │ integrity metadata   │
                                  └──────────┬───────────┘
                                             │
                                             ▼
                                  ┌──────────────────────┐
                                  │   SECURE HANDOVER    │
                                  │ Package → Hash →     │
                                  │ Access Control →     │
                                  │ Authorized Recipient │
                                  └──────────────────────┘
```

---

## 4. Core Component Boundaries

### 4.1 UI

Responsibilities:

- Login and identity presentation.
- Task creation.
- Task Passport display.
- Workspace interaction.
- Knowledge access.
- Agent execution status.
- Evidence inspection.
- Verification results.
- Review and approval.
- Deliverable access.
- Audit/trace visibility.
- Administration.

The UI must not expose unauthorized data, evidence, tools, or actions.

---

### 4.2 API Gateway

Responsibilities:

- Expose controlled backend APIs.
- Validate request schemas.
- Establish task context.
- Route requests to internal services.
- Propagate authenticated identity and Task Passport context.
- Enforce API-level security boundaries.

Baseline:

- FastAPI
- Pydantic
- Uvicorn

The gateway is not the final authorization authority; authorization remains an explicit policy decision.

---

### 4.3 Authentication

Baseline: **Keycloak**

Responsibilities:

- Identity.
- Login.
- Sessions.
- Tokens.
- Role management.
- Administrator management.

Initial roles:

- Operator
- Engineer
- Reviewer
- Administrator

---

### 4.4 RBAC and Fine-Grained Authorization

Broad role-based authorization uses Keycloak.

Fine-grained relationships use **OpenFGA** for cases such as:

- Department membership.
- Document access.
- Task execution.
- Tool invocation.
- Deliverable approval.

**OPA + OpenFGA** provide policy evaluation.

The LLM cannot grant permissions.

---

### 4.5 Task Passport

Every controlled task receives a persisted Task Passport before execution.

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

Security-critical fields are immutable after execution begins, or any change must create a versioned audit event and trigger re-authorization.

The Task Passport travels with task context across:

```text
RAG
Model Router
Tool Registry
Action Gate
Workspace
Sandbox
Review
Secure Handover
```

---

### 4.6 Permission Engine

The Permission Engine evaluates:

```text
User
+ Task
+ Resource
+ Action
+ Sensitivity
+ Policy
```

Possible outcomes:

```text
ALLOW
DENY
REQUIRE_APPROVAL
```

Default behavior is deny unless policy explicitly allows the operation.

The Permission Engine is deterministic, testable, versioned, and auditable.

---

## 5. Permission-Aware RAG Architecture

Medha RAG is not ordinary vector search.

Authoritative flow:

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

### 5.1 Ingestion

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

Supported inputs:

- PDF
- Scanned PDF
- DOCX
- TXT
- Images
- Industrial documents

Baseline:

- Docling
- PyMuPDF
- PaddleOCR
- BGE-M3 or replaceable equivalent
- Qdrant

Each indexed representation retains:

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

OCR must retain OCR confidence and relevant document metadata.

Low-confidence OCR must be flagged rather than silently treated as authoritative evidence.

### 5.2 Evidence Model

Evidence types:

- Source fact
- Inference
- Calculation
- Recommendation

Important claims follow:

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

An inference must not silently become an organizational fact.

---

## 6. Multimodal Architecture

Medha supports local processing of:

- Scanned documents.
- Photographs.
- Visual evidence.
- Diagrams.
- Engineering images.

Conceptual path:

```text
IMAGE / SCANNED DOCUMENT
        ↓
   LOCAL OCR / VISION
        ↓
  STRUCTURED OBSERVATIONS
        ↓
     VERIFICATION
        ↓
 AUTHORIZED EVIDENCE
```

Vision output is a model-generated observation. It must be verified before becoming an authoritative claim.

---

## 7. Task Purpose and Work Separation

Task Purpose establishes:

```text
Identity
Sensitivity
Purpose
```

These attributes influence:

- Knowledge access.
- Model selection.
- Tool access.
- Actions.
- Approval.
- Output handling.

Work Separation explicitly classifies the task.

| Work type | Controlled path |
|---|---|
| Document | Parsing, evidence extraction, document generation |
| Spreadsheet | Workbook access and spreadsheet tools |
| Code | Coding tools, versioned workspace, tests, sandbox |
| Image | Multimodal processing and visual evidence |
| Calculation | Controlled calculator or execution tool |
| Analysis | Agent reasoning, evidence graph, verifier |

Combined tasks must explicitly declare their work types in the Task Passport and execution plan.

---

## 8. Model Router Architecture

The Model Router selects an appropriate local model according to:

- Task type.
- Modality.
- Complexity.
- Sensitivity.
- Required tools.
- GPU availability.
- Latency.
- Model capability.

The routing decision must expose:

```text
Selected model
Selection rationale
Required tools
Execution plan
Constraints
Fallback behavior
```

Model categories may include:

- Lightweight text model.
- Reasoning model.
- Multimodal model.
- Coding model.

Models are replaceable through a stable internal interface.

Baseline local serving:

- vLLM or replaceable local serving layer.

Sovereign mode requires local model serving.

---

## 9. Agent Planner Architecture

The Agent Planner is a bounded stateful execution graph.

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

The planner may replan only within authorized task scope.

It must stop when:

- Policy denies an action.
- Authorization is missing.
- Verification repeatedly fails.
- Agent loops exceed limits.
- Tool request is unsafe.
- A high-risk ambiguity cannot be resolved safely.

Baseline orchestration:

- LangGraph or replaceable stateful graph layer.

---

## 10. Tool Registry and Action Gate

### 10.1 Tool Registry

Every tool is registered with:

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

### 10.2 Action Gate

Every consequential action must follow:

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

The agent cannot directly invoke consequential tools outside this boundary.

Tool architecture is MCP-compatible internally where practical, while preserving Medha's authorization and policy boundaries.

---

## 11. Controlled Workspace

The workspace handles:

- Documents.
- PDFs.
- Images.
- Code.
- Excel files.
- Presentations.
- Generated files.
- Intermediate artifacts.

Each artifact tracks:

```text
owner
task_id
classification
permissions
version
source
status
```

Workspace access is task-scoped and policy-checked.

---

## 12. Sandbox Architecture

Generated code must never execute directly on the host.

Baseline:

- Docker.
- gVisor where practical.

Required controls:

- Isolated filesystem.
- CPU limits.
- Memory limits.
- Execution timeout.
- Restricted permissions.
- Controlled mounts.
- No unrestricted host access.
- Network disabled by default.

Conceptual boundary:

```text
AGENT / CODE
     ↓
ACTION GATE
     ↓
SANDBOX POLICY
     ↓
DOCKER / gVISOR
     ↓
CONTROLLED EXECUTION
     ↓
RESULT + LOGS
```

Failed or interrupted executions must preserve status and logs without exposing host resources.

---

## 13. Verification Architecture

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
Rule Verification
Calculation Verification
Execution Verification
Evidence Verification
Policy Verification
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

Retries are bounded and visible in the audit trail.

---

## 14. Evidence-Bound Deliverable Architecture

The Deliverable Factory produces real work products:

- DOCX.
- XLSX.
- PPTX.
- PDF.
- Code, where authorized.

A deliverable is a package rather than only a file.

Example:

```text
MEDHA-PACKAGE/
├── approval_note.docx
├── evidence.json
├── verification.json
├── audit.json
└── manifest.json
```

The package preserves:

- Final output.
- Source references.
- Evidence.
- Verification result.
- Task ID.
- Audit reference.
- Manifest.

---

## 15. Review Architecture

Review mode is policy-controlled.

```text
                 ┌──────────────┐
                 │  DELIVERABLE │
                 └──────┬───────┘
                        ↓
                 ┌──────────────┐
                 │ REVIEW POLICY│
                 └──────┬───────┘
              ┌─────────┼─────────┐
              ↓         ↓         ↓
           HUMAN     MINIMAL      AUTO
                      CHANGE
```

### Human

For:

- High-risk work.
- Sensitive work.
- Ambiguous work.
- Consequential work.

### Minimal-change iterative

Only the requested portion is modified.

Relevant verification is rerun before returning to review.

### Auto

Only for low-risk work explicitly allowed by policy.

The LLM cannot independently declare a task safe for automatic release.

---

## 16. Audit and Trace Architecture

Baseline:

- OpenTelemetry.
- PostgreSQL or equivalent durable audit store.

The trace records:

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

Required reconstructable sequence:

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

Audit events must be tied to task and identity context.

---

## 17. Secure Handover Architecture

The final handover follows:

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

The handover package contains:

- Manifest.
- SHA-256 integrity hash.
- Task ID.
- Timestamp.
- Verification status.
- Access policy.

The handover layer prevents unauthorized output release.

---

## 18. Sovereign Runtime Boundary

Sovereign mode keeps the complete workflow inside the organization's controlled environment.

Local components include:

```text
LLM
Vision
OCR
Embeddings
RAG
Agent
Tools
Sandbox
Verifier
Audit
Deliverables
```

External AI APIs are not required.

External network access is denied by default.

The architecture must support air-gapped deployment.

### Observable sovereignty

The prototype must visibly demonstrate:

- Local model endpoint.
- Local vector database.
- Local OCR.
- Local embeddings.
- Local files.
- Blocked external network attempts.
- Audit logs.

The statement “everything is local” is not sufficient without observable proof.

---

## 19. Deployment Topology

### 19.1 Sovereign Production

```text
Organization Network
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  User → Frontend → API Gateway → Medha Services            │
│                                      │                      │
│       ┌──────────────────────────────┼──────────────┐       │
│       ↓                              ↓              ↓       │
│   Keycloak / RBAC               RAG / Qdrant    PostgreSQL  │
│       │                              │              │       │
│       └──────────────┬───────────────┴──────┬───────┘       │
│                      ↓                      ↓               │
│                 Model Router           Agent / Tools       │
│                      │                      │               │
│                      └──────────┬───────────┘               │
│                                 ↓                           │
│                       Action Gate / Sandbox                 │
│                                 ↓                           │
│                    Verifier / Deliverables                  │
│                                 ↓                           │
│                      Audit / Secure Handover                │
│                                                             │
│                  External network: DENIED                   │
└─────────────────────────────────────────────────────────────┘
```

All confidential processing remains inside the organization's controlled environment.

### 19.2 Air-Gapped Deployment

The same logical architecture runs without external network dependency.

Required local assets include:

- Models.
- Model runtimes.
- OCR packages/models.
- Embedding models.
- Python dependencies.
- Container images.
- Frontend/backend artifacts.
- Knowledge base.
- Database storage.

Updates must be brought into the environment through an approved controlled process.

### 19.3 Developer Local Deployment

For development:

```text
Developer Machine
├── Next.js frontend
├── FastAPI backend
├── Keycloak
├── PostgreSQL
├── Redis
├── Qdrant
├── Local model serving
├── OCR
├── Docker sandbox
└── Test knowledge base
```

Docker Compose is the baseline deployment mechanism.

### 19.4 Frontend Preview Deployment

A hosted frontend such as Vercel may be used for a **non-confidential frontend preview/demo**.

This does not change sovereign architecture.

```text
Vercel / Preview Frontend
          ↓
     Approved Demo API
```

Confidential industrial data must not be sent to a third-party frontend hosting environment unless that deployment has been explicitly approved under the organization's security model.

For sovereign production, the frontend should remain inside the organization's controlled environment.

### 19.5 Deployment Separation Rule

```text
Vercel        = optional frontend preview/hosting
On-Prem       = sovereign production environment
Docker        = execution isolation
gVisor        = optional hardened sandbox
```

Convenience hosting must never be represented as sovereign production.

---

## 20. Primary MVP Architecture

The first complete vertical slice is:

```text
SCANNED INSPECTION PDF
        ↓
LOCAL OCR
        ↓
PERMISSION-AWARE RAG
        ↓
TASK PASSPORT
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
DOCX DELIVERABLE
        ↓
AUDIT
        ↓
REVIEW
        ↓
SECURE HANDOVER
```

Primary industrial demo inputs:

1. Scanned inspection report.
2. Internal SOP/manual.
3. Inspection photograph.

Expected output:

- Evidence-linked inspection analysis.
- Approval note.
- Classification metadata.
- Authorization context.
- Verification result.
- Audit reference.
- Integrity metadata.

The MVP prioritizes demonstrable control behavior over broad feature count.

---

## 21. Secondary Coding Workflow

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

Generated code must remain within the controlled workspace and sandbox boundaries.

---

## 22. Trust Boundaries

Medha's critical trust boundaries are:

### Boundary A — User to Medha

Identity must be established before controlled operations.

### Boundary B — User/Task to Knowledge

Knowledge must be permission-filtered before release.

### Boundary C — Agent to Tool

The Action Gate must mediate consequential actions.

### Boundary D — Agent/Code to Host

Sandbox isolation must prevent unrestricted host access.

### Boundary E — AI Output to Organizational Deliverable

Verification must occur before deliverable release.

### Boundary F — Deliverable to Recipient

Secure handover must enforce access control and integrity.

### Boundary G — Medha to External Network

External access is denied by default in sovereign mode.

---

## 23. Data Flow Principles

### Confidential data flow

```text
INPUT
 ↓
AUTHORIZED TASK CONTEXT
 ↓
AUTHORIZED KNOWLEDGE
 ↓
LOCAL PROCESSING
 ↓
CONTROLLED TOOL EXECUTION
 ↓
VERIFICATION
 ↓
AUDITED DELIVERABLE
 ↓
SECURE HANDOVER
```

Confidential information must not leave the sovereign environment through:

- External AI APIs.
- Unapproved embedding APIs.
- Unapproved OCR services.
- Unapproved model endpoints.
- Uncontrolled tool network access.
- Unauthorized output channels.

---

## 24. Technology Baseline

| Layer | Baseline |
|---|---|
| Backend | Python |
| API | FastAPI, Pydantic, Uvicorn |
| Frontend | TypeScript, React, Next.js, Tailwind CSS |
| Identity | Keycloak |
| RBAC | Keycloak roles |
| Fine-grained authorization | OpenFGA |
| Policy | OPA |
| Database | PostgreSQL |
| Cache / temporary state | Redis |
| Document parsing | Docling, PyMuPDF |
| OCR | PaddleOCR |
| Embeddings | BGE-M3 or replaceable equivalent |
| Vector database | Qdrant |
| Model serving | vLLM or replaceable local serving |
| Agent orchestration | LangGraph or replaceable stateful graph |
| Tool protocol | MCP-compatible internal architecture |
| Sandbox | Docker; gVisor where practical |
| Deliverables | python-docx, openpyxl, python-pptx, ReportLab |
| Observability | OpenTelemetry |
| Integrity | SHA-256 |
| Deployment | Linux, Docker Compose, NVIDIA CUDA where GPU is available |

Baseline technologies are implementation choices, not reasons to break component contracts. Replaceable subsystems must preserve stable internal interfaces.

---

## 25. Repository Architecture

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

## 26. Architecture Invariants

The following are non-negotiable architecture invariants:

1. The LLM cannot grant itself permission.
2. Knowledge retrieval cannot bypass permission filtering.
3. Consequential tools cannot bypass the Action Gate.
4. Generated code cannot execute directly on the host.
5. External network access is denied by default in sovereign mode.
6. Verification must precede release of important deliverables.
7. Important claims must remain evidence-linked.
8. Review mode is policy-controlled.
9. Secure handover must preserve access control and integrity.
10. Audit trace must reconstruct the task lifecycle.
11. Models and replaceable infrastructure components must not become hard architectural dependencies.
12. Any deviation from the architecture must be explicitly documented and must not weaken security or sovereignty.

---

## 27. Architecture-to-MVP Traceability

| Architecture capability | MVP evidence |
|---|---|
| Identity | Authenticated demo user |
| RBAC | Role-based access decision |
| Task Passport | Persisted task record |
| Permission Engine | Allow/deny/approval decision |
| Permission-aware RAG | Unauthorized evidence blocked |
| Local OCR | Scanned report processed locally |
| Local embeddings | Local embedding generation |
| Model Router | Model + rationale shown |
| Agent Planner | Bounded execution graph |
| Action Gate | Tool request policy decision |
| Workspace | Task-scoped artifacts |
| Sandbox | Code/tool execution isolated |
| Verifier | Verification result |
| Evidence | Claim-to-evidence links |
| Deliverable Factory | Real DOCX output |
| Audit | Reconstructable trace |
| Review | Human/policy review path |
| Secure Handover | Package + hash + access control |
| Sovereignty | Local endpoint + blocked external network |

---

## 28. Architecture Decision Discipline

Before changing a core component:

1. Identify the affected boundary.
2. Identify the affected security invariant.
3. Identify affected interfaces.
4. Identify affected MVP behavior.
5. Record the decision in `docs/decisions.md`.
6. Update dependent documentation.
7. Add or update tests.
8. Verify that sovereignty and security are not weakened.

The architecture should be treated as a controlled system design, not as a collection of interchangeable UI features.

---

## 29. Governing Architecture Principle

Medha must not become:

```text
USER → CHATBOX → LLM → ANSWER
```

It must remain:

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

This is the authoritative conceptual architecture of Medha AI.

