# Medha AI — Deployment Specification

**Document:** `docs/deployment.md`  
**Project:** Medha AI  
**Subtitle:** Sovereign Controlled Multimodal AI Workbench for Confidential Industrial Work  
**Status:** Normative deployment guidance derived from the Master Plan  
**Year:** 2026

---

## 1. Purpose

This document defines how Medha AI is deployed, operated, upgraded, backed up, tested, and demonstrated in local, on-premise, and air-gapped environments.

The deployment model must preserve the authoritative Medha workflow:

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

Deployment must not introduce a path that bypasses authorization, policy enforcement, verification, audit, sandboxing, or secure handover.

---

## 2. Deployment Principles

Medha deployment SHALL be:

- Local and self-hostable.
- Suitable for organization-controlled on-premise infrastructure.
- Capable of air-gapped operation.
- Modular and replaceable at defined subsystem boundaries.
- GPU-compatible where local model inference requires acceleration.
- Network-deny-by-default for sovereign operation.
- Observable and auditable.
- Reproducible from versioned configuration and deployment artifacts.
- Fail-closed for security-sensitive controls.
- Independent of any single model, vendor, or database.

The baseline deployment stack is Linux + Docker Compose, with NVIDIA CUDA where a compatible GPU is available.

Baseline technologies defined by the Master Plan include Python/FastAPI, React/Next.js, Keycloak, OpenFGA, OPA, PostgreSQL, Redis, Docling/PyMuPDF, PaddleOCR, BGE-M3, Qdrant, vLLM, LangGraph, MCP-compatible tooling, Docker/gVisor, OpenTelemetry, and SHA-256 integrity. These are baseline choices rather than permanent vendor dependencies.

---

## 3. Deployment Modes

### 3.1 Developer Local Mode

Purpose:

- Development.
- Interface testing.
- Unit/integration testing.
- Local vertical-slice construction.

Characteristics:

- Docker Compose may run core infrastructure.
- Local filesystem may hold non-production test data.
- A local model-serving endpoint is preferred.
- Security controls remain enabled.
- Test credentials and synthetic documents SHALL be used.

Developer mode MUST NOT be treated as proof of production sovereignty unless external connectivity and local-processing controls are explicitly demonstrated.

### 3.2 On-Premise Production Mode

Purpose:

- Organization-controlled confidential workloads.

Characteristics:

- Services run inside the organization's controlled network.
- Models, OCR, embeddings, RAG, tools, sandbox, verifier, audit, and deliverables remain inside the controlled environment.
- External AI APIs are not required.
- Network egress is denied by default.
- Access is mediated by identity, RBAC, OpenFGA, OPA, Task Passport, and policy controls.
- Persistent data is stored on organization-controlled infrastructure.

### 3.3 Air-Gapped Mode

Purpose:

- Environments where external network connectivity is prohibited.

Requirements:

- All runtime images and packages are imported before isolation.
- Model weights are transferred through an approved controlled process.
- OCR and embedding models are local.
- Vector and relational databases are local.
- No runtime dependency may require public internet access.
- External package/model downloads are disabled.
- DNS and outbound network access are restricted according to the environment.
- Deployment manifests, image digests, model manifests, checksums, configuration, and approved artifacts are retained locally.

Air-gapped operation SHALL be testable without depending on an external service.

### 3.4 Prototype / Single-Workstation Mode

The MVP is expected to be demonstrable on a single workstation or server with a mid-range GPU.

The prototype should prioritize the complete vertical slice over infrastructure scale.

---

## 4. Reference Deployment Topology

A logical deployment may be represented as:

```text
                         ┌──────────────────────┐
                         │      User Browser    │
                         └──────────┬───────────┘
                                    │
                              HTTPS / Internal
                                    │
                         ┌──────────▼───────────┐
                         │      UI / Frontend   │
                         │ React / Next.js      │
                         └──────────┬───────────┘
                                    │
                         ┌──────────▼───────────┐
                         │      API Gateway     │
                         │ FastAPI              │
                         └──────────┬───────────┘
                                    │
          ┌─────────────────────────┼─────────────────────────┐
          │                         │                         │
┌─────────▼────────┐     ┌──────────▼──────────┐    ┌────────▼─────────┐
│ Authentication   │     │ Permission / Policy │    │ Task Passport   │
│ Keycloak         │     │ OpenFGA + OPA       │    │ Service         │
└──────────────────┘     └──────────┬──────────┘    └────────┬─────────┘
                                    │                        │
                          ┌─────────▼────────────────────────▼─────┐
                          │           Controlled Agent Plane       │
                          │ Work Separation / Model Router        │
                          │ Agent Planner / Action Gate            │
                          └───────────────┬────────────────────────┘
                                          │
             ┌────────────────────────────┼────────────────────────────┐
             │                            │                            │
    ┌────────▼────────┐          ┌────────▼────────┐          ┌────────▼────────┐
    │ RAG / Knowledge │          │ Local Model     │          │ Tool / Sandbox  │
    │ OCR / Embedding │          │ Serving         │          │ Execution       │
    │ Qdrant          │          │ vLLM / local    │          │ Docker/gVisor   │
    └─────────────────┘          └─────────────────┘          └─────────────────┘
             │                            │                            │
             └────────────────────────────┼────────────────────────────┘
                                          │
                             ┌────────────▼────────────┐
                             │ Verifier / Deliverables │
                             └────────────┬────────────┘
                                          │
                    ┌─────────────────────┼─────────────────────┐
                    │                     │                     │
             ┌──────▼───────┐     ┌──────▼───────┐     ┌──────▼────────┐
             │ Audit / Trace│     │ Review       │     │ Secure         │
             │ OTel + DB    │     │ Approval     │     │ Handover       │
             └──────────────┘     └──────────────┘     └───────────────┘
```

The topology is logical. Services may be combined for the MVP when doing so does not weaken security boundaries or make controls impossible to test.

---

## 5. Host Requirements

### 5.1 Baseline Host

The deployment target SHALL support:

- Linux.
- Docker and Docker Compose.
- NVIDIA CUDA when GPU acceleration is used.
- Persistent storage for application data and audit records.
- Storage for local model weights.
- Storage for the knowledge base.
- Controlled workspace storage.
- Sufficient CPU and RAM for infrastructure services.
- A compatible GPU for the selected local models when GPU inference is required.

Exact production CPU, RAM, GPU, and storage thresholds SHALL be established through benchmarking rather than assumed fixed values.

### 5.2 GPU Requirements

GPU allocation SHALL account for:

- Model size.
- Quantization or precision.
- Context length.
- Concurrent users/tasks.
- Multimodal model requirements.
- OCR/vision workloads where GPU acceleration is enabled.
- Embedding throughput.
- Available VRAM.
- Latency requirements.

The Model Router SHALL consider GPU availability as one input to model selection.

If a selected model cannot safely run on available hardware, the system SHALL use a documented fallback or fail safely rather than silently switching to an unauthorized external service.

---

## 6. Containerization

Docker Compose is the baseline deployment mechanism.

A deployment SHOULD organize services by responsibility, for example:

```text
docker/
├── compose/
│   ├── docker-compose.yml
│   ├── docker-compose.dev.yml
│   └── docker-compose.airgap.yml
├── configs/
├── healthchecks/
└── scripts/
```

A conceptual service set is:

```text
frontend
api
keycloak
openfga
opa
postgres
redis
qdrant
ocr
embedding
model-server
agent
sandbox
worker
audit
```

Services may be merged for the MVP if the resulting architecture still preserves policy boundaries and traceability.

### 6.1 Container Rules

Containers SHALL:

- Run with only required capabilities.
- Avoid privileged mode unless explicitly justified and documented.
- Use controlled mounts.
- Avoid host filesystem access.
- Use non-root execution where practical.
- Have resource limits where appropriate.
- Have explicit health checks.
- Have explicit network membership.
- Avoid unnecessary package installation at runtime.
- Use pinned or digest-controlled images in controlled deployments.

---

## 7. Network Security

Sovereign mode SHALL use deny-by-default network egress.

Conceptually:

```text
Internet
   X
   │
   │ BLOCKED
   ▼
Medha Network
   │
   ├── UI
   ├── API
   ├── Identity
   ├── Policy
   ├── RAG
   ├── Models
   ├── Tools
   ├── Sandbox
   ├── Audit
   └── Deliverables
```

### 7.1 Network Rules

- External AI APIs are not required.
- Local model endpoints SHALL remain internal.
- OCR SHALL remain local.
- Embedding generation SHALL remain local.
- Vector database access SHALL remain internal.
- Sandbox networking SHALL be disabled by default.
- Tool network permissions SHALL be explicitly registered.
- A tool SHALL NOT obtain network capability merely because the agent requests it.
- Policy decisions SHALL precede network-enabled actions.
- Failed external network attempts SHALL be observable and auditable.

The prototype should visibly demonstrate a blocked external-network attempt.

---

## 8. Identity and Authorization Deployment

Keycloak provides identity, sessions, roles, tokens, and administrator management.

Initial roles:

```text
Operator
Engineer
Reviewer
Administrator
```

OpenFGA provides fine-grained relationships such as:

- Department membership.
- Document access.
- Task execution.
- Tool invocation.
- Deliverable approval.

OPA provides policy evaluation.

The deployment SHALL preserve this distinction:

```text
Authentication → Who are you?
RBAC          → What broad role do you have?
OpenFGA       → What relationship-based resource access exists?
OPA           → What does policy allow for this action?
```

The LLM SHALL NOT be deployed as a security authority.

---

## 9. Task Passport Deployment

The Task Passport is persisted before controlled execution.

Minimum fields:

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

Security-critical passport changes after execution begins SHALL either be prohibited or require versioning, audit, and re-authorization.

Every downstream service that can affect confidentiality or action scope SHALL receive the relevant task context.

---

## 10. Knowledge and RAG Deployment

The local ingestion pipeline is:

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

Baseline components:

- Docling / PyMuPDF for parsing.
- PaddleOCR for local OCR.
- BGE-M3 or replaceable local embedding model.
- Qdrant for vector storage.
- PostgreSQL for durable metadata and application state where applicable.

Each indexed representation SHALL preserve at least:

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

Retrieval SHALL preserve the authorization boundary:

```text
QUERY
→ DETERMINE ALLOWED KNOWLEDGE
→ RETRIEVE RELEVANT KNOWLEDGE
→ APPLY PERMISSION FILTERING
→ RETURN AUTHORIZED EVIDENCE
```

Permission filtering must occur before evidence is exposed to the model or user.

Low-confidence OCR must remain marked as uncertain and must not silently become authoritative evidence.

---

## 11. Local Model Serving

The model-serving layer SHALL be replaceable.

Baseline:

```text
Local Model Router
       │
       ├── lightweight text model
       ├── reasoning model
       ├── multimodal model
       └── coding model
```

vLLM is the baseline local serving layer where suitable.

Model registration SHOULD include:

```text
model_id
name
version
modality
capabilities
context_limit
resource_requirements
sensitivity_constraints
supported_work_types
endpoint
status
```

The Model Router SHALL consider:

- Task type.
- Modality.
- Complexity.
- Sensitivity.
- Required tools.
- GPU availability.
- Latency.
- Model capability.

The UI and audit trace SHALL expose the selected model, rationale, constraints, and fallback behavior.

No production deployment may silently fall back from a local sovereign model to an external AI API.

---

## 12. Agent Runtime

LangGraph or another replaceable stateful graph layer may implement the Agent Planner.

The runtime SHALL support:

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

The deployment SHALL enforce:

- Bounded retries.
- Bounded replanning.
- Maximum execution loops.
- Action Gate checks.
- Task-scoped workspace access.
- Tool registration.
- Policy decisions before consequential actions.
- Stop conditions for unsafe or ambiguous situations.

A deployment must never expose an unrestricted agent loop with unrestricted host access.

---

## 13. Tool Registry and Action Gate

Tools SHALL be registered with:

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

Initial tool categories:

- Document reader.
- Document search.
- Calculator.
- Spreadsheet reader.
- Spreadsheet writer.
- File manager.
- DOCX generator.
- PPTX generator.
- Code executor.

Every consequential tool action SHALL follow:

```text
AGENT
→ ACTION GATE
→ POLICY CHECK
→ ALLOW / DENY / REQUIRE_APPROVAL
→ TOOL
```

Tool configuration must be versioned and auditable.

---

## 14. Controlled Workspace

The workspace stores:

- Source documents.
- PDFs.
- Images.
- Code.
- Excel files.
- Presentations.
- Generated deliverables.
- Intermediate artifacts.

Each artifact SHALL track:

```text
owner
task_id
classification
permissions
version
source
status
```

Workspace access must be task-scoped.

Persistent storage SHOULD be separated into logical areas:

```text
data/
├── application/
├── knowledge_base/
├── models/
├── workspace/
├── sandbox/
├── deliverables/
├── audit/
└── backups/
```

Actual paths may vary by deployment environment.

---

## 15. Sandbox Deployment

Docker is the baseline sandbox. gVisor may be used for hardened deployments.

Generated code SHALL never execute directly on the host.

The sandbox SHALL enforce:

- Isolated filesystem.
- CPU limits.
- Memory limits.
- Execution timeout.
- Restricted permissions.
- Controlled mounts.
- No unrestricted host access.
- Network disabled by default.
- Task-scoped working directory.
- Captured stdout/stderr and execution status.

A failed or interrupted execution must preserve status and logs without exposing host resources.

Sandbox escape and host-access tests are mandatory security tests.

---

## 16. Verification and Deliverable Deployment

The Verifier SHALL check:

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
RULE
CALCULATION
EXECUTION
EVIDENCE
POLICY
```

On failure:

```text
FAIL
→ FEEDBACK
→ REPLAN
→ EXECUTE
→ VERIFY
```

Retries must be bounded.

Deliverables are packages rather than isolated files:

```text
MEDHA-PACKAGE/
├── approval_note.docx
├── evidence.json
├── verification.json
├── audit.json
└── manifest.json
```

The package SHALL preserve source references, verification status, Task ID, audit reference, and manifest information.

---

## 17. Secure Handover

Handover SHALL occur only after required verification and review.

The controlled sequence is:

```text
OUTPUT
→ PACKAGE
→ SHA-256 HASH
→ ACCESS CONTROL
→ AUTHORIZED RECIPIENT
```

The handover manifest SHALL include, at minimum:

```text
task_id
timestamp
verification_status
classification
access_policy
integrity_hash
package_contents
audit_reference
```

The recipient must be authorized for the output.

Unauthorized output release SHALL fail closed and generate an audit event.

---

## 18. Audit and Observability Deployment

OpenTelemetry is the baseline observability layer.

PostgreSQL or an equivalent durable audit store is the baseline audit persistence option.

The deployment must make this sequence reconstructable:

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

Audit records SHOULD capture:

- Who.
- When.
- What.
- Why.
- Data/resource.
- Model.
- Tool.
- Action.
- Policy decision.
- Evidence.
- Verification.
- Approval/review.
- Output.
- Handover.

Observability and audit are distinct:

- **Observability** answers whether the system is operating.
- **Audit** answers what happened, under whose authority, against which resource, under which policy, and with what result.

---

## 19. Storage, Backup, and Restore

### 19.1 Backup Scope

Backups SHOULD cover:

```text
PostgreSQL
Qdrant data
Knowledge metadata
Application configuration
Policy configuration
Tool registry
Model registry
Task Passport records
Audit records
Deliverable metadata
Approved model manifests
Deployment manifests
```

Large model weights may use a separate controlled artifact backup process.

### 19.2 Backup Rules

- Backups must remain within the organization's approved storage boundary.
- Backup access must be authorized.
- Sensitive data must not be copied to uncontrolled external services.
- Backup integrity should be verified.
- Backup jobs and restore operations should be auditable.
- Retention periods SHALL follow organizational policy rather than an invented fixed value.

### 19.3 Restore

Restore procedures SHALL be tested, not merely documented.

A restore test should verify:

1. Infrastructure starts.
2. Database state is recoverable.
3. Qdrant collections are recoverable.
4. Policies and tool registry are present.
5. Audit records remain accessible.
6. Knowledge permissions remain intact.
7. Model registry remains consistent.
8. A test Task Passport can execute.
9. Security boundaries remain enforced.

---

## 20. Configuration and Secrets

Configuration SHALL be separated from application code.

Example:

```text
configs/
├── application.yaml
├── models.yaml
├── tools.yaml
├── policies/
├── network.yaml
└── deployment.yaml
```

Secrets SHALL NOT be committed to source control.

`.env.example` may document required variables without containing production secrets.

Sensitive configuration includes:

- Database credentials.
- Identity provider secrets.
- Signing keys.
- Internal service credentials.
- Encryption material where used.
- Model-serving credentials if applicable.

Secret handling SHALL follow the organization's approved secret-management mechanism.

---

## 21. Air-Gapped Artifact Preparation

Before disconnecting the deployment environment:

### Step 1 — Build inventory

Record:

```text
OS packages
Container images
Python dependencies
Frontend dependencies
Model weights
OCR models
Embedding models
Configuration
Policy bundles
Database initialization
Migration files
Deployment scripts
```

### Step 2 — Verify artifacts

Generate and record checksums for approved artifacts.

### Step 3 — Transfer through approved media/process

Move only approved artifacts into the isolated environment.

### Step 4 — Load locally

Import:

- Container images.
- Model weights.
- OCR assets.
- Embedding assets.
- Configuration.
- Policy bundles.

### Step 5 — Disable external dependency paths

Verify that runtime services do not attempt public downloads or external AI calls.

### Step 6 — Run sovereignty tests

Verify:

```text
Local model endpoint        PASS
Local OCR                   PASS
Local embeddings            PASS
Local vector DB             PASS
Local files                 PASS
External network blocked    PASS
Audit trace                 PASS
```

---

## 22. Deployment Lifecycle

### 22.1 Installation

1. Prepare Linux host.
2. Install approved container runtime.
3. Install GPU/CUDA components where required.
4. Import application images and artifacts.
5. Configure persistent storage.
6. Configure identity.
7. Initialize PostgreSQL.
8. Initialize Qdrant.
9. Load policies.
10. Register tools.
11. Register models.
12. Start services.
13. Run health checks.
14. Run security checks.
15. Run the MVP vertical slice.

### 22.2 Startup Order

A conceptual dependency order is:

```text
Storage
  ↓
PostgreSQL / Redis / Qdrant
  ↓
Keycloak / OpenFGA / OPA
  ↓
OCR / Embeddings / Model Serving
  ↓
Backend / Agent / Tools / Sandbox
  ↓
Frontend
```

Actual startup may be parallelized where health dependencies permit.

A service must not report healthy merely because its process is running; readiness must verify required dependencies.

### 22.3 Shutdown

Shutdown SHALL:

- Stop new task intake.
- Allow or safely terminate active work according to policy.
- Preserve task state.
- Preserve audit events.
- Preserve sandbox results/logs.
- Flush telemetry where applicable.
- Stop services in dependency-safe order.

---

## 23. Health Checks and Degraded States

Every critical service should expose a health/readiness signal.

Examples:

```text
HEALTHY
DEGRADED
BLOCKED
FAILED
```

### Examples

**Model unavailable**

```text
MODEL UNAVAILABLE
→ ROUTER CHECKS AUTHORIZED FALLBACK
→ FALLBACK OR SAFE FAILURE
```

**Qdrant unavailable**

```text
RAG UNAVAILABLE
→ DO NOT RELEASE UNVERIFIED KNOWLEDGE
→ TASK BLOCKED / SAFE FAILURE
```

**OPA unavailable**

```text
POLICY UNAVAILABLE
→ FAIL CLOSED
→ CONSEQUENTIAL ACTION BLOCKED
```

**OpenFGA unavailable**

```text
FINE-GRAINED AUTHORIZATION UNAVAILABLE
→ ACCESS BLOCKED
```

**Sandbox unavailable**

```text
CODE EXECUTION UNAVAILABLE
→ DO NOT RUN CODE ON HOST
→ TASK BLOCKED OR ALTERNATIVE SAFE PATH
```

**Verifier unavailable**

```text
VERIFICATION UNAVAILABLE
→ CONSEQUENTIAL OUTPUT RELEASE BLOCKED
```

The system SHALL not replace a missing security control with an unrestricted fallback.

---

## 24. Upgrade Strategy

Upgrades SHALL be versioned and reversible.

Components that may require independent versioning include:

- Application services.
- Database schema.
- Policies.
- Tool definitions.
- Model versions.
- OCR models.
- Embedding models.
- Frontend.
- Container images.

Before upgrade:

1. Record current deployment version.
2. Back up persistent state.
3. Record image/model/configuration digests.
4. Review security and compatibility impact.
5. Validate migrations.
6. Test in a non-production environment where available.
7. Define rollback conditions.

After upgrade:

1. Run health checks.
2. Run authorization tests.
3. Run RAG permission tests.
4. Run sandbox tests.
5. Run verifier tests.
6. Run audit reconstruction tests.
7. Run the vertical slice.

---

## 25. Rollback

Rollback must restore a known-good combination of:

```text
Application version
Database schema/state
Policy version
Tool registry version
Model registry version
Configuration
Container images
```

Database migrations must have a documented rollback or recovery strategy.

A model rollback must not silently change task authorization or sensitivity behavior.

If a security-critical component cannot be restored safely, the system SHALL remain blocked rather than operating without that control.

---

## 26. Monitoring and Metrics

The deployment must collect the metrics defined by the Master Plan:

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

Metrics SHALL be collected at identifiable pipeline points.

No fixed performance threshold should be claimed before benchmarking.

---

## 27. Deployment Security Testing

Deployment validation SHALL include positive and negative cases.

Required areas include:

```text
Unauthorized document access
RBAC bypass
OpenFGA bypass
OPA bypass
RAG permission bypass
Prompt injection
Malicious documents
Malicious code
Sandbox escape
Tool abuse
Unauthorized file access
External network attempts
Data leakage
Approval bypass
Unauthorized output release
Excessive agent loops
Malicious multimodal inputs
```

Every security failure must be traceable to:

```text
Task
→ Identity
→ Policy Decision
→ Resource
→ Action
→ Audit Event
```

Security tests should run in CI where practical.

---

## 28. MVP Deployment Procedure

The first complete deployment target is the Master Plan vertical slice:

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

Primary demonstration inputs:

- Scanned inspection report.
- Internal SOP/manual.
- Inspection photograph.

Expected result:

- Evidence-linked inspection analysis.
- Approval note.
- Classification metadata.
- Authorization metadata.
- Verification result.
- Audit trace.
- Integrity-preserving handover package.

The deployment should demonstrate the complete path on the available prototype workstation/server rather than implementing many disconnected services.

---

## 29. Sovereignty Demonstration Checklist

The demonstration SHALL visibly prove:

| Check | Evidence |
|---|---|
| Local model | Internal model endpoint |
| Local OCR | Local OCR service/log |
| Local embeddings | Local embedding service/log |
| Local vector DB | Local Qdrant instance |
| Local files | Controlled workspace |
| No external AI dependency | Configuration + blocked request test |
| External network blocked | Visible failed/denied request |
| Authorization | Task Passport + policy decision |
| RAG permissions | Allowed/denied evidence example |
| Action control | Action Gate event |
| Sandbox | Docker execution record |
| Verification | Verification result |
| Audit | End-to-end trace |
| Integrity | SHA-256 manifest |
| Secure handover | Authorized package release |

“Everything is local” is not sufficient by itself. The prototype must show observable evidence of sovereignty.

---

## 30. Deployment Requirements

### REQ-DEPLOY-001 — Local Operation
Medha SHALL support operation inside an organization-controlled environment.

**Verification:** Deployment test.

### REQ-DEPLOY-002 — Air-Gap Capability
The deployment SHALL support operation without runtime dependency on public internet services.

**Verification:** Air-gapped deployment test.

### REQ-DEPLOY-003 — Container Baseline
The baseline deployment SHALL use Linux and Docker Compose, with NVIDIA CUDA where GPU acceleration is required.

**Verification:** Environment inspection.

### REQ-DEPLOY-004 — Local AI Components
Sovereign deployment SHALL keep LLM, vision, OCR, embeddings, RAG, agent execution, tools, sandbox, verifier, audit, and deliverable generation inside the controlled environment.

**Verification:** Network and process inspection.

### REQ-DEPLOY-005 — Egress Default Deny
External network access SHALL be denied by default in sovereign mode.

**Verification:** Negative network test.

### REQ-DEPLOY-006 — No External AI Fallback
The system SHALL NOT silently use an external AI service when a local model is unavailable.

**Verification:** Model failure test.

### REQ-DEPLOY-007 — GPU Awareness
Model routing SHALL account for available GPU resources.

**Verification:** Routing test.

### REQ-DEPLOY-008 — Resource Isolation
Sandbox execution SHALL be isolated from the host.

**Verification:** Sandbox security test.

### REQ-DEPLOY-009 — Task Context
Deployment SHALL preserve Task Passport context across controlled services.

**Verification:** End-to-end trace test.

### REQ-DEPLOY-010 — Policy Enforcement
Consequential actions SHALL be policy-checked before execution.

**Verification:** Action Gate negative test.

### REQ-DEPLOY-011 — RAG Authorization
Deployment SHALL enforce knowledge permissions before evidence release.

**Verification:** Unauthorized retrieval test.

### REQ-DEPLOY-012 — Local OCR
OCR SHALL execute locally in sovereign mode.

**Verification:** OCR service/process inspection.

### REQ-DEPLOY-013 — Local Embeddings
Embedding generation SHALL execute locally without an external embedding API.

**Verification:** Network-isolation test.

### REQ-DEPLOY-014 — Durable State
Required application, knowledge, and audit state SHALL use persistent storage.

**Verification:** Restart and persistence test.

### REQ-DEPLOY-015 — Backup
Deployment SHALL provide a documented backup procedure for critical state.

**Verification:** Backup test.

### REQ-DEPLOY-016 — Restore
Deployment SHALL provide a tested restore procedure.

**Verification:** Restore test.

### REQ-DEPLOY-017 — Upgrade
Component upgrades SHALL be versioned and tested.

**Verification:** Upgrade test.

### REQ-DEPLOY-018 — Rollback
A known-good deployment version SHALL be restorable after a failed upgrade.

**Verification:** Rollback exercise.

### REQ-DEPLOY-019 — Health Checks
Critical services SHALL expose health/readiness state.

**Verification:** Service health test.

### REQ-DEPLOY-020 — Fail Closed
Missing security controls such as policy or fine-grained authorization SHALL cause sensitive operations to fail closed.

**Verification:** Dependency-failure test.

### REQ-DEPLOY-021 — Auditability
Deployment SHALL preserve an auditable trace across the controlled workflow.

**Verification:** Trace reconstruction test.

### REQ-DEPLOY-022 — Integrity
Secure handover SHALL use SHA-256 integrity metadata.

**Verification:** Hash verification.

### REQ-DEPLOY-023 — Artifact Verification
Air-gapped deployments SHALL verify approved deployment artifacts before use.

**Verification:** Checksum validation.

### REQ-DEPLOY-024 — Security Testing
Deployment validation SHALL include required positive and negative security tests.

**Verification:** Security test report.

### REQ-DEPLOY-025 — Sovereignty Evidence
The prototype SHALL visibly demonstrate local processing and blocked external network access.

**Verification:** Demonstration checklist.

### REQ-DEPLOY-026 — MVP Vertical Slice
Deployment SHALL support the complete scanned-inspection vertical slice.

**Verification:** End-to-end demonstration.

---

## 31. Operational Runbook

### Daily / routine checks

- Service health.
- GPU availability.
- Disk capacity.
- Database health.
- Qdrant health.
- Model-serving health.
- Audit ingestion.
- Failed policy decisions.
- Sandbox failures.
- Blocked network attempts.
- Backup status.

### Incident response

When a security boundary fails:

```text
DETECT
→ BLOCK AFFECTED ACTION
→ PRESERVE TASK/AUDIT CONTEXT
→ ISOLATE COMPONENT
→ INVESTIGATE
→ PATCH / CONFIGURE
→ TEST
→ RESTORE
→ VERIFY
```

Security incidents SHALL NOT be resolved by simply disabling authorization, policy enforcement, sandboxing, or audit controls.

### Maintenance

Maintenance should be performed using approved change procedures with:

- Version recorded.
- Change reason recorded.
- Impact assessed.
- Backup available.
- Rollback path defined.
- Verification completed.

---

## 32. Deployment Acceptance Criteria

A deployment is accepted only when:

- Core services start successfully.
- Identity works.
- RBAC works.
- Fine-grained authorization works.
- OPA policy evaluation works.
- Task Passport is persisted.
- Local OCR works.
- Local embeddings work.
- Permission-aware RAG works.
- Local model serving works.
- Model routing records rationale.
- Agent planning is bounded.
- Action Gate blocks unauthorized actions.
- Workspace is task-scoped.
- Code runs only in the sandbox.
- Verification works.
- Deliverables are generated.
- Audit trace is reconstructable.
- Review routing works.
- Secure handover produces manifest and SHA-256 hash.
- Backup and restore have been tested.
- Security negative tests pass.
- External AI services are not required.
- External network attempts are blocked in sovereign mode.
- The complete MVP vertical slice succeeds.

---

## 33. Definition of Done for Deployment

Deployment documentation and implementation are complete when:

1. Local deployment procedure is reproducible.
2. On-premise topology is defined.
3. Air-gapped preparation is documented.
4. GPU deployment considerations are documented.
5. Docker deployment is defined.
6. Persistent storage is defined.
7. Backup and restore are tested.
8. Upgrade and rollback are defined.
9. Network policy is enforced.
10. Security-sensitive dependencies fail closed.
11. Health and degraded states are defined.
12. Model, tool, and policy registries are deployable.
13. The MVP vertical slice runs end-to-end.
14. Sovereignty is visibly demonstrated.
15. Audit and integrity evidence are preserved.
16. Deployment requirements have verification methods.
17. No deployment path bypasses the authoritative Medha control workflow.

---

## 34. Baseline vs Replaceable Components

| Area | Baseline | Replaceable Contract |
|---|---|---|
| Backend | Python / FastAPI | HTTP/API service contract |
| Frontend | React / Next.js | Authenticated UI/API contract |
| Identity | Keycloak | OIDC-compatible identity boundary |
| Fine-grained auth | OpenFGA | Authorization relationship interface |
| Policy | OPA | Policy decision interface |
| Database | PostgreSQL | Durable relational persistence interface |
| Cache | Redis | Cache/state interface |
| Parsing | Docling / PyMuPDF | Document extraction interface |
| OCR | PaddleOCR | Local OCR interface |
| Embeddings | BGE-M3 | Local embedding interface |
| Vector DB | Qdrant | Vector retrieval interface |
| Model serving | vLLM | Local model-serving interface |
| Agent | LangGraph | Stateful execution-graph interface |
| Tools | MCP-compatible | Tool registry/action interface |
| Sandbox | Docker | Isolated execution interface |
| Observability | OpenTelemetry | Telemetry interface |
| Integrity | SHA-256 | Integrity verification contract |

A replacement is acceptable only when it preserves security, sovereignty, interface behavior, observability, and documented degradation behavior.

---

## 35. Traceability to Master Plan

This deployment specification directly operationalizes the Master Plan requirements for:

- Baseline technology and deployment principles.
- Authoritative component architecture.
- Identity and authorization.
- Task Passport.
- Permission-aware RAG.
- Local multimodal processing.
- Model routing.
- Agent planning.
- Tool Registry and Action Gate.
- Controlled workspace.
- Docker sandbox.
- Verification.
- Deliverable generation.
- Audit and trace.
- Sovereign mode.
- Repository deployment structure.
- MVP vertical slice.
- Security testing.
- Performance/quality measurement.
- Definition of done.

The Master Plan remains authoritative. Where this document adds operational detail, that detail must not weaken the Master Plan's control model.

---

## 36. Final Deployment Principle

Medha deployment is successful only when the system can demonstrate not merely that AI runs locally, but that confidential work remains inside a controlled execution boundary.

```text
LOCAL AI
   +
IDENTITY
   +
AUTHORIZATION
   +
KNOWLEDGE PERMISSION
   +
TASK PURPOSE
   +
ACTION CONTROL
   +
SANDBOX
   +
VERIFICATION
   +
AUDIT
   +
SECURE HANDOVER
   =
SOVEREIGN CONTROLLED DEPLOYMENT
```

Any deployment configuration that bypasses these boundaries is out of scope unless the deviation is explicitly documented, approved, and shown not to weaken security or sovereignty.
