# MEDHA — Sovereign Controlled Multimodal AI Workbench

**Multimodal Evidence-Driven Hybrid Assistant** for security-sensitive industrial environments.

MEDHA is a policy-controlled AI workbench implementing sovereign AI governance: every AI action is gated by Task Passports, permission-checked by an Action Gate, and recorded in a forensic audit trail.

---

## SIH Evaluator Demo (SIH26117)

**MEDHA — Sovereign On-Premise Agentic AI Workbench**

- **Problem:** Confidential industrial information cannot safely depend on cloud AI.
- **Solution:** Local open-weight AI + permission-aware knowledge + controlled agents + local OCR + sandbox + audit.
- **Evaluator demo:** Pump P-204 Inspection Analysis (synthetic data, no login required).
- **Key proof:** OCR → RAG → Qwen, controlled execution, local model, audit, DOCX deliverable.

### How to run

```bash
cd backend
pip install -r requirements.txt
export MEDHA_JWT_SECRET="your-secret-key-here"   # Windows: set MEDHA_JWT_SECRET=...
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173` → **TRY LIVE DEMO** → Start Analysis → Download DOCX Report.

The evaluator demo lives on the isolated `/demo` route and three public endpoints
(`/api/demo/evidence`, `/api/demo/analysis`, `/api/demo/report`). They accept no
user identity and no client input, write nothing to the database, and use only the
bundled synthetic Pump P-204 scan.

---

## Architecture Overview

```
User → Authentication (JWT) → RBAC → Task Passport → Action Gate
                                                          ↓
                         ┌──────────────────────────────────────────┐
                         │  RAG (source + sensitivity filter)       │
                         │  Model Router (allowed models filter)    │
                         │  Agent Planner (allowed tools filter)    │
                         │  Sandbox (network policy enforcement)    │
                         │  Verifier (output safety check)          │
                         │  Secure Handover (human approval)        │
                         └──────────────────────────────────────────┘
                                                          ↓
                                                  Audit Trail
```

### Security Model Flow

1. **Authentication** — JWT bearer tokens, PBKDF2 password hashing, short-lived tokens
2. **RBAC** — 4 roles: operator, engineer, reviewer, admin
3. **Task Passport** — Security contract per task: identity, sensitivity, allowed sources/tools/models, network policy, approval requirements
4. **Action Gate** — Centralized authorization: identity → lifecycle → tool allowlist → sensitivity → approval
5. **Permission-Aware RAG** — Documents filtered by source allowlist and sensitivity before retrieval
6. **Model Router** — Complexity-based routing with passport-constrained model selection
7. **Agent Authorization** — Step-by-step plans with per-tool permission checks
8. **Controlled Execution** — Network policy enforcement, tool allowlists, resource limits
9. **Output Verification** — Safety, hallucination, and compliance checks
10. **Forensic Audit Trail** — Persistent structured events answering WHO/WHAT/WHEN/TASK/RESOURCE/POLICY/RESULT

---

## Project Structure

```
Demo-Medha/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── routes/          # FastAPI route handlers
│   │   │   │   ├── auth.py      # Login, register, identity
│   │   │   │   ├── tasks.py     # Task Passport CRUD + lifecycle
│   │   │   │   ├── chat.py      # Conversations, messages, file upload
│   │   │   │   ├── knowledge.py # RAG document ingestion + search
│   │   │   │   ├── model_router.py # Model inference
│   │   │   │   ├── agent.py     # Plan creation, approval, execution
│   │   │   │   ├── sandbox.py   # Controlled tool execution
│   │   │   │   └── verifier.py  # Output verification + audit trail
│   │   │   └── dependencies.py  # Auth, RBAC, passport dependencies
│   │   ├── core/
│   │   │   ├── config.py        # Settings from environment
│   │   │   └── database.py      # SQLAlchemy engine + session
│   │   ├── models/              # SQLAlchemy ORM models
│   │   ├── schemas/             # Pydantic request/response schemas
│   │   └── services/
│   │       ├── action_gate.py       # Centralized authorization
│   │       ├── task_service.py      # Task Passport lifecycle
│   │       ├── audit_service.py     # Persistent audit events
│   │       ├── auth_service.py      # JWT issuance
│   │       ├── user_service.py      # User management + demo seeding
│   │       ├── conversation_service.py # Chat persistence
│   │       ├── rag/                 # Retrieval-Augmented Generation
│   │       │   ├── retrieval.py     # Orchestrator
│   │       │   ├── permission_filter.py # Source + sensitivity filtering
│   │       │   ├── vector_store.py  # In-memory TF-IDF vector store
│   │       │   ├── embeddings.py    # TF-IDF model (stdlib only)
│   │       │   ├── chunker.py       # Document chunking
│   │       │   └── document_parser.py # Text extraction
│   │       ├── model_router/        # Model routing
│   │       │   ├── router.py        # Complexity-based routing
│   │       │   ├── service.py       # End-to-end inference
│   │       │   ├── model_adapter.py # Local + API adapters (simulated)
│   │       │   └── filters.py       # Input/output safety filters
│   │       ├── agent/               # Agent planning
│   │       │   ├── planner.py       # Plan generation
│   │       │   ├── service.py       # Plan management
│   │       │   └── tool_registry.py # Tool definitions + permissions
│   │       ├── sandbox/
│   │       │   └── sandbox.py       # Controlled execution (simulated)
│   │       └── verifier/
│   │           └── verifier.py      # Output safety verification
│   ├── tests/                       # 232 tests
│   │   ├── test_security.py         # Security + failure validation
│   │   ├── test_e2e.py              # End-to-end pipeline
│   │   ├── test_auth.py             # Authentication
│   │   ├── test_passport.py         # Task Passport lifecycle
│   │   ├── test_rag.py              # RAG + permissions
│   │   ├── test_model_router.py     # Model routing
│   │   ├── test_agent.py            # Agent planning
│   │   ├── test_sandbox.py          # Sandbox execution
│   │   ├── test_chat.py             # Chat + conversations
│   │   └── test_verifier.py         # Output verification
│   └── sample_documents/            # Demo documents for RAG
├── frontend/
│   └── src/
│       ├── App.jsx                  # Router + AuthGate
│       ├── api.js                   # Backend API client
│       ├── pages/
│       │   ├── LandingPage.jsx      # Pre-auth AI entry
│       │   ├── LoginPage.jsx        # Login + signup
│       │   ├── Dashboard.jsx        # Task overview
│       │   ├── TasksPage.jsx        # Task list + filters
│       │   ├── TaskWorkspace.jsx    # Task detail + tabs
│       │   ├── ChatPage.jsx         # AI chat interface
│       │   └── AuditPage.jsx        # Audit trail viewer
│       ├── components/
│       │   ├── ProtectedRoute.jsx   # Auth route guard
│       │   ├── TopNav.jsx           # Navigation bar
│       │   ├── TaskCard.jsx         # Task card with actions
│       │   ├── LiveSecurityPipeline.jsx # Security stage visualization
│       │   ├── EnvironmentStatus.jsx    # System status
│       │   ├── Modal.jsx, Toast.jsx     # UI primitives
│       └── utils/helpers.js         # Shared utilities
├── IMPLEMENTATION_REPORT.md         # Detailed implementation history
└── README.md                        # This file
```

---

## Quick Start

### Backend

```bash
cd backend

# Install dependencies
pip install -r requirements.txt

# Set JWT secret (required)
export MEDHA_JWT_SECRET="your-secret-key-here"

# Run tests (232 tests)
python -m pytest tests/ -v

# Start server
uvicorn app.main:app --reload --port 8000
```

### Frontend

```bash
cd frontend

# Install dependencies
npm install

# Start dev server (proxies /api to backend)
npm run dev
```

### Demo Accounts

| Username | Password | Role |
|----------|----------|------|
| operator | medha-operator-2026 | operator |
| engineer | medha-engineer-2026 | engineer |
| reviewer | medha-reviewer-2026 | reviewer |
| admin | medha-admin-2026 | admin |

---

## Security Architecture

### Authentication

- JWT bearer tokens with HS256 signing
- PBKDF2-SHA256 password hashing (600,000 iterations)
- Short-lived tokens (configurable, default 30 minutes)
- Token validated against DB user on every request
- Role embedded in JWT and verified against DB

### RBAC (Role-Based Access Control)

| Action | operator | engineer | reviewer | admin |
|--------|----------|----------|----------|-------|
| Create Task Passport | ✅ | ✅ | ❌ | ✅ |
| Transition Task Status | ✅ | ✅ | ❌ | ✅ |
| Ingest Documents | ❌ | ✅ | ❌ | ✅ |
| Delete Documents | ❌ | ✅ | ❌ | ✅ |
| AI Chat | ✅ | ✅ | ✅ | ✅ |
| View Audit Trail | ✅ | ✅ | ✅ | ✅ |

### Task Passport

The Task Passport is the security contract for every AI operation:

- **Identity** — Who owns this task
- **Sensitivity** — `internal` | `confidential` | `restricted`
- **Allowed Sources** — Which documents can be accessed
- **Allowed Tools** — Which tools can be used (empty = none)
- **Allowed Models** — Which models can be used
- **Network Policy** — `deny_external` | `allow_internal`
- **Approval Requirement** — `none` | `reviewer` | `admin`
- **Status** — `draft` → `authorized` → `executing` → `completed` | `failed` | `denied`

Security-critical fields become **immutable** once the passport leaves `draft` status.

### Action Gate

Every consequential operation passes through the Action Gate, which checks:

1. **Ownership** — User identity matches passport identity
2. **Lifecycle** — Passport status permits the action category
3. **Tool Allowlist** — Tool is in passport's allowed list (fail-closed: empty = block all)
4. **Sensitivity** — Tool's max sensitivity >= passport sensitivity
5. **Approval** — High-risk tools require approval if passport demands it

### Forensic Audit Trail

Every consequential decision is recorded with:

- `event_id`, `timestamp`, `event_type`
- `task_id`, `user_id`, `identity`, `role`
- `previous_status`, `new_status` (for transitions)
- `detail` (structured context)

Events are persisted in SQLite/SQLAlchemy and survive server restarts.

---

## Frontend Features

### Pre-Authentication Landing Page (`/`)

- Evaluator-first: **MEDHA — Sovereign On-Premise Agentic AI Workbench**
- One-line value statement plus a single obvious primary CTA: **TRY LIVE DEMO**
- Secondary actions: Sign In / Sign Up
- "Try MEDHA in 60 seconds", "Why MEDHA?" and an architecture snapshot section
- Atmospheric dark navy/blue glow design

### Evaluator Demo (`/demo`) — no account required

- Guided 6-step flow: inspection → local evidence → local AI → controlled execution → result → DOCX report
- Live security status panel and real local model name/status (no hard-coded claims)
- Visible OCR → RAG → local Qwen pipeline proof and evidence list
- Honest failure messages when the local runtime, OCR or sandbox is unavailable

### Authenticated Application

- **Dashboard** — Greeting, search, pinned/recent tasks, Live Security Pipeline, environment status
- **Tasks** — Filter tabs (All/Pinned/Draft/Authorized/Executing/Completed/Failed/Denied), create, delete
- **Task Workspace** — Tabs: Overview, AI Analysis, Evidence, Conversation, Execution, Report
- **AI Chat** — Grouped conversations, task selector, file upload, plugins, model selector
- **Audit Trail** — Auto-loading task list with timeline view

### Authentication Flow

```
/ (Landing) → query → submit → Sign In / Create Account
                                    ↓
                               /login
                                    ↓
                              /dashboard (prefilled)
```

- `AuthGate` in `App.jsx` validates JWT on app load before rendering routes
- Stale/invalid tokens are cleared automatically
- All logout paths: `clearToken()` → navigate to `/`
- Protected routes redirect unauthenticated users to `/`

### Secure Industrial Analysis (`/analysis`)

End-to-end security pipeline demonstration: Pump P-204 Maintenance Failure Analysis.

- **Equipment Overview** — Pump specs, location, manufacturer details
- **Failure Data** — 24-month synthetic failure records with bar charts and sortable table
- **Sensor Analysis** — Vibration, temperature, pressure, flow rate, current averages + monthly downtime trend chart
- **Risk Assessment** — Visual gauge (score/100), risk level, MTBF trend
- **Recommendations** — Prioritized actions with cost/downtime estimates
- **Security Trace** — Full 12-stage pipeline visualization with timestamps (includes 1 blocked tool action)
- **Secure Handover** — Human approval workflow (Approve/Reject with reason)
- **About MEDHA** — Architecture diagram, implementation status, demonstration disclaimers
- **Excel Download** — `MEDHA_P204_Maintenance_Analysis.xlsx` with 8 sheets
- **Data Classification** — Clearly labeled "synthetic-demo" with MRPL disclaimer

### Security Mode Control (Server-Side Enforced)

Three security levels enforced backend-authorized:

- **Standard** — Normal task-scoped policy
- **Secure** — External network restricted, external models restricted, strict RAG, strict tool allowlist, enhanced audit
- **Sovereign** — External network denied, external LLMs denied, local model required, local-only RAG, controlled execution, human approval for consequential actions

Features:
- Top-right navigation indicator (◯ Standard / 🔐 SECURE / 🛡 SOVEREIGN)
- Security status panel showing all policy dimensions
- Automatic sensitivity enforcement (confidential → secure, restricted → sovereign)
- Users can only increase protection (no downgrade)
- Server-side authoritative — not a frontend toggle
- Mode changes recorded in audit trail
- Demo user: `arun.maintenance` / `medha-arun-2026` (Engineer role)

---

## Backend API Endpoints

### Authentication
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/auth/login` | No | Login, returns JWT |
| POST | `/api/auth/register` | No | Register new user |
| GET | `/api/auth/me` | Yes | Return current identity |

### Task Passports
| Method | Endpoint | Auth | Roles | Description |
|--------|----------|------|-------|-------------|
| GET | `/api/tasks` | Yes | any | List user's tasks |
| POST | `/api/tasks` | Yes | op/eng/admin | Create task passport |
| GET | `/api/tasks/{id}` | Yes | owner | Get task passport |
| PATCH | `/api/tasks/{id}/status` | Yes | op/eng/admin | Transition status |
| PATCH | `/api/tasks/{id}/security-fields` | Yes | op/eng/admin | Update security fields (draft only) |
| DELETE | `/api/tasks/{id}` | Yes | owner/admin | Soft-delete task |

### Knowledge / RAG
| Method | Endpoint | Auth | Roles | Description |
|--------|----------|------|-------|-------------|
| POST | `/api/knowledge/documents` | Yes | eng/admin | Ingest document |
| POST | `/api/knowledge/search` | Yes | any | Permission-aware search |
| GET | `/api/knowledge/sources` | Yes | any | List ingested sources |
| DELETE | `/api/knowledge/sources/{name}` | Yes | eng/admin | Delete source |

### Model Router
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/models/infer` | Yes | Model inference with Action Gate |
| GET | `/api/models/available` | Yes | List available model adapters |

### Agent
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/agent/plan` | Yes | Create execution plan |
| POST | `/api/agent/plan/approve-step` | Yes | Approve pending step |
| POST | `/api/agent/plan/execute-step` | Yes | Execute approved step |
| GET | `/api/agent/tools` | Yes | List registered tools |

### Sandbox
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/sandbox/execute` | Yes | Execute tool in sandbox |
| POST | `/api/sandbox/rollback` | Yes | Rollback execution |

### Verifier + Audit
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/verifier/verify` | Yes | Verify AI output |
| GET | `/api/verifier/audit/{task_id}` | Yes | Get audit trail for task |
| GET | `/api/verifier/audit` | Yes | Get tasks with audit summaries |

### Chat
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/chat/conversations-all` | Yes | List all user conversations |
| POST | `/api/chat/conversations` | Yes | Create conversation |
| GET | `/api/chat/conversations/{task_id}` | Yes | List conversations for task |
| DELETE | `/api/chat/conversations/{id}` | Yes | Delete conversation |
| GET | `/api/chat/messages/{conversation_id}` | Yes | List messages |
| POST | `/api/chat/send` | Yes | Send chat message |
| POST | `/api/chat/upload` | Yes | Upload file attachment |

### Evaluator Demo (synthetic Pump P-204 only)
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/demo/evidence` | No | Local OCR + demo-scoped RAG evidence |
| POST | `/api/demo/analysis` | No | Evidence-grounded finding + local model + sandbox run |
| POST | `/api/demo/report` | No | Real DOCX report built from synthetic demo data |

These three endpoints take no request body, accept no user identity, and never
write users, tasks, conversations or audit rows.

### Secure Analysis
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| POST | `/api/analysis/run` | Yes | Run full security pipeline analysis |
| POST | `/api/analysis/handover` | Yes | Approve/reject secure handover |
| GET | `/api/analysis/dataset` | No | Get synthetic Pump P-204 dataset |
| POST | `/api/analysis/excel` | Yes | Generate Excel workbook (8 sheets) |

### Security Mode
| Method | Endpoint | Auth | Description |
|--------|----------|------|-------------|
| GET | `/api/security-mode/status/{task_id}` | Yes | Get security mode status panel data |
| POST | `/api/security-mode/set` | Yes | Set security mode (increase only) |
| GET | `/api/security-mode/policy/{mode}` | No | Get security policy definition |

---

## Test Suite

**287 tests** across 17 test files:

| File | Tests | Coverage |
|------|-------|----------|
| `test_security.py` | 35 | Auth bypass, escalation, injection, passport lifecycle, network policy, failure modes |
| `test_e2e.py` | 5 | Full pipeline, permission enforcement, RBAC, network policy, injection blocking |
| `test_analysis_security.py` | 29 | Analysis pipeline auth, RBAC, stages, blocked tools, handover, Excel, input validation |
| `test_security_mode.py` | 18 | Security mode enforcement, downgrade prevention, sovereign policy, cross-user security |
| `test_auth.py` | 12 | Login, register, identity, role enforcement |
| `test_passport.py` | 19 | Lifecycle transitions, immutability, identity, audit events |
| `test_rag.py` | 34 | Parser, chunker, embeddings, vector store, permissions, API |
| `test_model_router.py` | 23 | Adapters, routing, filters, API |
| `test_agent.py` | 24 | Tool registry, planner, service, API |
| `test_sandbox.py` | 17 | Execution, network policy, rollback, API |
| `test_chat.py` | 30 | Conversations, messages, model selection, audit, file upload |
| `test_verifier.py` | 15 | Safety, hallucination, compliance, API |
| `test_health.py` | 1 | Health check |
| `test_tasks.py` | 12 | Task CRUD, transitions |
| `test_startup_and_persistence.py` | 5 | Startup, persistence |

Run all tests:
```bash
cd backend
python -m pytest tests/ -v
```

Run security tests only:
```bash
python -m pytest tests/test_security.py tests/test_e2e.py -v
```

---

## Security Audit Summary (2026-09-20)

### Controls Classification

| Category | Status | Details |
|----------|--------|---------|
| JWT Authentication | REAL | HS256, DB-backed, short-lived |
| RBAC | REAL | 4 roles, enforced on all restricted endpoints |
| Task Passport Lifecycle | REAL | State machine with immutability enforcement |
| Action Gate | REAL | 5-check centralized authorization |
| Tool Allowlist | REAL | Fail-closed (empty = block all) |
| Sensitivity Enforcement | REAL | Tool max sensitivity vs passport level |
| Prompt Injection Detection | REAL | 5 injection patterns blocked |
| PII Redaction | REAL | Email, phone, Aadhaar, PAN patterns |
| Output Safety | REAL | Unsafe content, hardcoded secrets detection |
| RAG Permission Filtering | REAL | Source allowlist + sensitivity filtering |
| Model Allowlist | REAL | Passport-constrained model selection |
| Network Policy | SIMULATED | Application-level only, no OS/container isolation |
| Sandbox Execution | SIMULATED | No actual code execution or resource limits |
| Model Adapters | SIMULATED | Mock responses, no real LLM inference |
| Secure Handover | IMPLEMENTED | Human approval workflow with approve/reject + reason |
| Security Mode | REAL | 3-level policy engine (Standard/Secure/Sovereign), server-side authoritative, auto-enforced by sensitivity |
| Passport Expiry | MISSING | Authorized passports valid indefinitely |
| Audit Hash Chain | MISSING | No tamper detection on audit events |
| Rate Limiting | MISSING | No request throttling |
| JWT Refresh/Revocation | MISSING | No token refresh or revocation list |

### Attack Test Results (87/87 PASS)

| Attack | Result |
|--------|--------|
| Horizontal privilege escalation | DENIED |
| Vertical privilege escalation | DENIED |
| Task ID tampering | DENIED |
| Direct endpoint bypass | DENIED |
| Unauthorized RAG source | DENIED |
| Unauthorized model | DENIED |
| Unauthorized tool | DENIED |
| Prompt injection (5 patterns) | DENIED |
| Passport lifecycle bypass | DENIED |
| Network policy bypass | DENIED |
| Completed task execution | DENIED |
| Cross-user audit access | DENIED |
| Cross-user conversation access | DENIED |

### Production Recommendations

1. Container-based sandboxing (Docker/Firecracker)
2. OS-level network isolation (iptables/nftables)
3. Passport expiry mechanism
4. Secure handover workflow
5. Audit event hash chain
6. JWT refresh tokens + revocation
7. Rate limiting on auth endpoints
8. Policy version tracking
9. Real model adapter integration
10. OpenTelemetry distributed tracing

---

## Technology Stack

### Backend
- **Framework:** FastAPI (Python 3.13)
- **Database:** SQLite (development) / PostgreSQL (production target)
- **ORM:** SQLAlchemy
- **Auth:** PyJWT (HS256)
- **Password Hashing:** PBKDF2-SHA256 (600k iterations)
- **Validation:** Pydantic v2
- **Testing:** pytest + httpx

### Frontend
- **Framework:** React 19 + Vite 8.3
- **Routing:** react-router-dom v7
- **Styling:** CSS (custom dark theme)
- **Linting:** Oxlint
- **Fonts:** Inter (Google Fonts)

### Dependencies
- **Backend:** No external dependencies beyond FastAPI/SQLAlchemy/PyJWT — all services use Python stdlib (TF-IDF, regex, dataclasses, hashlib)
- **Frontend:** React, react-router-dom, Vite

---

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `MEDHA_JWT_SECRET` | Yes | — | Secret key for JWT signing |
| `MEDHA_JWT_EXPIRATION_MINUTES` | No | 30 | Token expiry in minutes |
| `MEDHA_DATABASE_URL` | No | `sqlite:///medha.db` | Database connection string |
| `MEDHA_ENV` | No | `development` | Environment name |
| `MEDHA_APP_NAME` | No | `MEDHA Backend` | Application name |
| `MEDHA_APP_VERSION` | No | `0.1.0` | Application version |

---

## License

Internal project — SIH26117.
#   M e d h a - 1 . 0  
 