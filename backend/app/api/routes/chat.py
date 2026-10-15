"""Conversation and Chat API routes — persistent chat history with Task Passport gating."""

import os
import shutil
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db, require_task_passport
from app.schemas.auth import CurrentUser
from app.schemas.conversation import (
    ChatRequest,
    ChatResponse,
    ConversationCreate,
    ConversationListResponse,
    ConversationRead,
    MessageCreate,
    MessageListResponse,
    MessageRead,
    SourceReference,
)
from app.services.action_gate import (
    ActionCategory,
    ActionGateError,
    AuthorizationContext,
    action_gate,
)
from app.services.ai_pipeline.evidence import EvidenceReport, assess_evidence
from app.services.ai_pipeline.intent import ChatIntent, classify_intent
from app.services.ai_pipeline.relevance import (
    TaskRelevance,
    check_task_relevance,
    classify_response_risk,
    detect_prompt_ambiguity,
)
from app.services.ai_pipeline.resource_planner import ResourcePlan, plan_resources
from app.services.audit_service import audit_service
from app.services.conversation_service import UPLOAD_DIR, _conversation_to_read, _ensure_upload_dir, conversation_service
from app.services.model_router.model_adapter import (
    UNAVAILABLE_MESSAGE,
    LocalModelUnavailableError,
    ModelAdapterFactory,
)
from app.services.model_router.router import model_router
from app.services.privacy_gateway import ResearchOutcome, privacy_gateway
from app.services.rag.retrieval import retrieval_service
from app.schemas.task import SecurityMode
from app.services.task_service import TaskPassportNotFoundError, passport_service

router = APIRouter(prefix="/chat", tags=["chat"])

# Maximum number of prior conversation messages included in model context.
_MAX_CONTEXT_MESSAGES = 12

TASK_SCOPE_MESSAGE = "I can only answer questions relevant to the current task."
INSUFFICIENT_VERIFIED_MESSAGE = (
    "I don't have enough verified information to answer that."
)
AMBIGUOUS_REQUEST_MESSAGE = (
    "I need clarification. Tell me: (1) the measurable, "
    "(2) the equipment or process affected, "
    "and (3) the risk or desired outcome."
)


def _build_response_guidance(
    user_prompt: str,
    passport,
    intent: ChatIntent,
    evidence: EvidenceReport,
) -> list[str]:
    """Prompt-construction rules for the local model (task-relevance gate).

    Intent-first: the CURRENT USER MESSAGE is the primary task. Passport
    and resource-plan fields are background metadata only — never the
    reply. Guidance shapes natural conversational reasoning; it never
    injects question→answer mappings.
    """
    risk = classify_response_risk(user_prompt)
    ambiguous = detect_prompt_ambiguity(user_prompt)
    guidance: list[str] = []

    guidance.append(
        "Primary intent: answer the CURRENT USER MESSAGE. TASK CONTEXT, "
        "RESOURCE PLAN, INTENT and PROVENANCE are background metadata for "
        "grounding only — never recite passport fields, plan fields, or "
        "section labels as the reply."
    )
    guidance.append(
        "Respond in natural prose shaped to the question. Do not force a "
        "Task/Purpose/Status/Analysis/Recommendation template unless the "
        "user explicitly asked for that structure."
    )
    guidance.append(
        "Ground claims in INTERNAL EVIDENCE (and PUBLIC RESEARCH when "
        "present). Name a source only when it naturally clarifies where "
        "information came from — do not append citation tags after every "
        "sentence."
    )
    guidance.append(
        "Separate what authorized evidence shows (FACT) from your reading "
        "of it (INTERPRETATION) and from untested ideas (POSSIBILITY). "
        "Mark gaps as UNKNOWN rather than guessing. If the user's stated "
        "assumption conflicts with authorized evidence, say so plainly."
    )
    guidance.append(
        "Match depth to the question: brief factual asks get a short "
        "direct answer; analysis or why-asks get structured reasoning "
        "with evidence; status asks get a concise progress readout."
    )

    if intent.category in ("investigation", "recommendation", "comparison"):
        guidance.append(
            "When useful, offer one concrete alternative or next step the "
            "user can act on within this task's authorized tools and "
            "sources."
        )

    if intent.follow_up or intent.conversation_turns:
        guidance.append(
            "Follow-ups and short references (for example 'the vibration' "
            "or 'what about that') refer to the same subject as RECENT "
            "CONVERSATION — resolve them from history before answering."
        )

    if evidence.missing_information:
        missing = ", ".join(evidence.missing_information)
        guidance.append(
            "If verified information remains incomplete, state what can "
            "already be determined from authorized context, what is "
            f"missing and why it matters ({missing}), and the concrete "
            "next step to obtain it. Do not reply with only "
            "'insufficient information' and do not fabricate."
        )

    if intent.category == "conversational" and risk == "standard" and not ambiguous:
        guidance.append(
            "Low-risk conversational request: reply briefly and politely; "
            "no technical elaboration required."
        )

    if risk == "high":
        guidance.append(
            "High-risk domain (safety, process integrity, mission, or data "
            "ownership): never improvise. Ground every claim in authorized "
            "evidence only."
        )
        if not evidence.enough:
            missing = ", ".join(evidence.missing_information) or (
                "verified inputs listed under MISSING INFORMATION"
            )
            guidance.append(
                f"If verified information remains insufficient, respond with: "
                f"{INSUFFICIENT_VERIFIED_MESSAGE} Then list missing verified "
                f"inputs: {missing}."
            )
        else:
            guidance.append(
                "Answer only from INTERNAL EVIDENCE above."
            )

    if ambiguous:
        missing = ", ".join(ambiguous)
        guidance.append(
            f"If the request stays ambiguous, respond with: "
            f"{AMBIGUOUS_REQUEST_MESSAGE} Detected gaps: {missing}."
        )

    if passport.security_mode == SecurityMode.SOVEREIGN:
        guidance.append(
            "Sovereign mode: use only verified task-authorized evidence; "
            "do not use unverified public information."
        )

    if not guidance:
        guidance.append(
            "Answer within task scope; do not fabricate facts beyond "
            "authorized evidence."
        )
    return guidance


def _policy_reply(
    *,
    db,
    conversation_id: str,
    content: str,
    model_name: str,
    routing_reason: str,
    decision: str,
    information_need: str,
    audit_base: dict,
) -> ChatResponse:
    """Persist and return a policy-gate reply (no local model call)."""
    assistant_msg = conversation_service.add_message(
        db,
        conversation_id=conversation_id,
        role="assistant",
        content=content,
        model=model_name,
    )
    audit_service.record(
        event_type="final_decision",
        detail=(
            f"decision={decision} "
            f"information_need={information_need[:200]!r}"
        ),
        **audit_base,
    )
    return ChatResponse(
        conversation_id=conversation_id,
        message_id=assistant_msg.id,
        model_used=model_name,
        response_text=content,
        complexity="policy",
        routing_reason=routing_reason,
        tokens_used=0,
        latency_ms=0.0,
        execution_mode="policy",
        sources=[],
    )


def _extract_sources(rag_chunks: list[dict]) -> list[SourceReference]:
    """Build the ChatResponse sources list from authorized RAG chunks.

    Deduplicates by source_name, keeping the highest-scored snippet first
    (rag_chunks arrive already permission-filtered and score-sorted).
    Never invents sources — returns [] when no authorized evidence exists.
    """
    seen: dict[str, SourceReference] = {}
    for chunk in rag_chunks:
        name = str(chunk.get("source_name") or "").strip()
        if not name or name in seen:
            continue
        text = str(chunk.get("text") or "").strip()
        snippet = text if len(text) <= 240 else text[:237].rstrip() + "..."
        seen[name] = SourceReference(name=name, snippet=snippet)
    return list(seen.values())


def _build_pipeline_model_input(
    passport,
    prior_messages,
    user_prompt: str,
    intent: ChatIntent,
    plan: ResourcePlan,
    evidence: EvidenceReport,
    research: ResearchOutcome | None,
    response_guidance: list[str] | None = None,
) -> str:
    """Compose structured model input for the full chat pipeline.

    Sections: TASK CONTEXT → RECENT CONVERSATION → INTENT → RESOURCE PLAN →
    INTERNAL EVIDENCE → PUBLIC RESEARCH → MISSING INFORMATION → PROVENANCE →
    RESPONSE GUIDANCE → CURRENT USER MESSAGE. All context is loaded
    backend-side from the database; the client supplies only the current
    user message.
    """
    task_lines = [
        "TASK CONTEXT:",
        "role: background authorization context — not the reply; the "
        "user's question is primary",
        f"task_id: {passport.task_id}",
        f"title: {passport.title}",
        f"purpose: {passport.purpose}",
        f"status: {passport.status.value}",
        f"security_mode: {passport.security_mode.value}",
        f"sensitivity: {passport.sensitivity.value}",
        f"network_policy: {passport.network_policy.value}",
        f"requested_operation: {passport.requested_operation or 'none'}",
        f"authorized_tools: {', '.join(passport.allowed_tools) or 'none'}",
        f"authorized_sources: {', '.join(passport.allowed_sources) or 'none'}",
    ]

    conv_lines = ["RECENT CONVERSATION:"]
    recent = prior_messages[-_MAX_CONTEXT_MESSAGES:]
    if recent:
        for msg in recent:
            conv_lines.append(f"{msg.role}: {msg.content}")
    else:
        conv_lines.append("(none)")

    intent_lines = [
        "INTENT:",
        f"objective: {intent.objective}",
        f"category: {intent.category}",
        f"answer_type: {intent.answer_type}",
        f"evidence_required: {str(intent.evidence_required).lower()}",
        f"public_research_useful: {str(intent.public_research_useful).lower()}",
        f"conversation_turns: {intent.conversation_turns}",
        f"follow_up: {str(intent.follow_up).lower()}",
        "required_information:",
        *[f"  - {item}" for item in intent.required_information],
    ]

    if research is not None:
        external_status = f"{research.status} ({research.reason})"
    elif evidence.enough:
        external_status = "not needed (internal evidence sufficient)"
    else:
        external_status = "not requested"

    plan_lines = [
        "RESOURCE PLAN:",
        "conversation_context: authorized (this task + user only)",
        f"rag_enabled: {str(plan.rag_enabled).lower()}",
        f"rag_query: {plan.rag_query}",
        f"authorized_sources: {', '.join(plan.authorized_sources) or 'none (fail-closed)'}",
        f"authorized_tools: {', '.join(plan.authorized_tools) or 'none'}",
        f"external_research: {external_status}",
        "restrictions:",
        *[f"  - {r}" for r in plan.restrictions],
    ]

    if evidence.known:
        internal_lines = ["INTERNAL EVIDENCE (authorized local RAG):"]
        internal_lines += [f"  - {k}" for k in evidence.known]
    elif plan.rag_enabled:
        internal_lines = [
            "INTERNAL EVIDENCE (authorized local RAG):",
            "(none — no permitted evidence returned)",
        ]
    else:
        internal_lines = [
            "INTERNAL EVIDENCE (authorized local RAG):",
            "(none — no RAG sources authorized; fail-closed)",
        ]

    if research is not None and research.results:
        public_lines = [
            "PUBLIC RESEARCH (external, sanitized query, unverified for this task):",
            f"sanitized_query: {research.sanitized_query}",
            f"provider: {research.provider}",
        ]
        for r in research.results:
            public_lines.append(
                f"  - [{r.get('title', 'untitled')}] {r.get('url', '')} "
                f"{r.get('snippet', '')}"
            )
    elif research is not None:
        public_lines = [
            "PUBLIC RESEARCH (external, sanitized query, unverified for this task):",
            f"(blocked: {research.reason})",
        ]
    else:
        public_lines = [
            "PUBLIC RESEARCH (external, sanitized query, unverified for this task):",
            "(not requested)",
        ]

    if evidence.missing_information:
        missing_lines = ["MISSING INFORMATION:"]
        missing_lines += [f"  - {m}" for m in evidence.missing_information]
        missing_lines.append(f"reason: {evidence.insufficiency_reason}")
        missing_lines.append(
            "instruction: do not fabricate — state what is missing if "
            "evidence remains insufficient."
        )
    else:
        missing_lines = ["MISSING INFORMATION:", "(none)"]

    provenance_lines = [
        "PROVENANCE:",
        "  - INTERNAL EVIDENCE: authorized local documents for this task only",
        "  - PUBLIC RESEARCH: external public sources, unverified for this task",
        "  - AI INFERENCE: model reasoning — not verified fact unless grounded above",
    ]

    if response_guidance:
        guidance_lines = ["RESPONSE GUIDANCE:"] + [
            f"  - {g}" for g in response_guidance
        ]
    else:
        guidance_lines = ["RESPONSE GUIDANCE:", "(none)"]

    sections = [
        "\n".join(task_lines),
        "\n".join(conv_lines),
        "\n".join(intent_lines),
        "\n".join(plan_lines),
        "\n".join(internal_lines),
        "\n".join(public_lines),
        "\n".join(missing_lines),
        "\n".join(provenance_lines),
        "\n".join(guidance_lines),
        "CURRENT USER MESSAGE:\n" + user_prompt,
    ]
    return "\n\n".join(sections)


@router.get("/conversations-all", response_model=ConversationListResponse)
def list_all_conversations(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationListResponse:
    """List all conversations for the current user across all tasks."""
    from app.models.conversation import ConversationRow

    rows = (
        db.query(ConversationRow)
        .filter(ConversationRow.user_id == current_user.user_id)
        .order_by(ConversationRow.updated_at.desc())
        .all()
    )
    convos = [_conversation_to_read(r) for r in rows]
    return ConversationListResponse(conversations=convos, total=len(convos))


@router.post("/conversations", response_model=ConversationRead, status_code=status.HTTP_201_CREATED)
def create_conversation(
    payload: ConversationCreate,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    _passport=None,
) -> ConversationRead:
    """Create a new conversation linked to a Task Passport, or General Chat.

    General Chat (task_id null/omitted) creates a conversation with no
    active task and does not create or require a Task Passport.
    """
    task_id = (payload.task_id or "").strip()

    if task_id:
        try:
            passport = passport_service.get(db, task_id)
        except TaskPassportNotFoundError:
            raise HTTPException(status_code=404, detail="Task passport not found")

        if passport.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Identity mismatch")
    else:
        # General Chat — no Task Passport is created or required.
        task_id = ""

    return conversation_service.create_conversation(
        db,
        task_id=task_id,
        user_id=current_user.user_id,
        title=payload.title,
    )


@router.get("/conversations/{task_id}", response_model=ConversationListResponse)
def list_conversations(
    task_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ConversationListResponse:
    """List conversations for a task, scoped to the current user.

    Special path value `general` lists General Chat conversations
    (no active task).
    """
    if task_id == "general":
        convos = conversation_service.list_general_conversations(db, current_user.user_id)
        return ConversationListResponse(conversations=convos, total=len(convos))

    try:
        passport = passport_service.get(db, task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(status_code=404, detail="Task passport not found")

    if passport.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Identity mismatch")

    convos = conversation_service.list_conversations_for_task(db, task_id, current_user.user_id)
    return ConversationListResponse(conversations=convos, total=len(convos))


@router.delete("/conversations/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Delete a conversation and its messages. Only the owner can delete."""
    convo = conversation_service.get_conversation(db, conversation_id, current_user.user_id)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")

    conversation_service.delete_conversation(db, conversation_id, current_user.user_id)


@router.get("/messages/{conversation_id}", response_model=MessageListResponse)
def list_messages(
    conversation_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> MessageListResponse:
    """List messages and attachments in a conversation."""
    convo = conversation_service.get_conversation(db, conversation_id, current_user.user_id)
    if convo is None:
        raise HTTPException(status_code=404, detail="Conversation not found or access denied")

    messages = conversation_service.get_messages(db, conversation_id)
    attachments = conversation_service.get_attachments_for_conversation(db, conversation_id)
    return MessageListResponse(messages=messages, attachments=attachments, total=len(messages))


ALLOWED_FILE_TYPES = {
    "application/pdf": "pdf",
    "text/plain": "txt",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "docx",
    "image/png": "png",
    "image/jpeg": "jpg",
}


@router.post("/upload", response_model=dict)
async def upload_file(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    task_id: str = Form(""),
    conversation_id: str = Form(""),
    file: UploadFile = File(...),
) -> dict:
    """Upload a file attachment associated with a task conversation."""
    if not task_id:
        raise HTTPException(status_code=400, detail="task_id is required")

    try:
        passport = passport_service.get(db, task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(status_code=404, detail="Task passport not found")

    if passport.user_id != current_user.user_id:
        raise HTTPException(status_code=403, detail="Identity mismatch")

    try:
        action_gate.authorize_action(
            AuthorizationContext(
                passport=passport,
                current_user=current_user,
                action_category=ActionCategory.READ,
            )
        )
    except ActionGateError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    if file.content_type not in ALLOWED_FILE_TYPES:
        raise HTTPException(
            status_code=400,
            detail=f"File type '{file.content_type}' not allowed. Supported: PDF, TXT, DOCX, PNG, JPG",
        )

    _ensure_upload_dir()
    task_upload_dir = os.path.join(UPLOAD_DIR, task_id)
    os.makedirs(task_upload_dir, exist_ok=True)

    ext = ALLOWED_FILE_TYPES[file.content_type]
    safe_filename = f"{conversation_id or 'shared'}_{file.filename}"
    file_path = os.path.join(task_upload_dir, safe_filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_size = os.path.getsize(file_path)

    attachment = conversation_service.add_attachment(
        db,
        message_id="",
        conversation_id=conversation_id or "",
        task_id=task_id,
        filename=file.filename or "unknown",
        content_type=file.content_type,
        file_size=file_size,
        storage_path=file_path,
    )

    audit_service.record(
        event_type="file_attached",
        task_id=task_id,
        user_id=current_user.user_id,
        identity=current_user.username,
        role=current_user.role.value,
        security_mode=passport.security_mode if hasattr(passport, 'security_mode') else "standard",
        detail=f"File uploaded: {file.filename} ({file.content_type}, {file_size} bytes)",
    )

    return {
        "attachment_id": attachment.id,
        "filename": attachment.filename,
        "content_type": attachment.content_type,
        "file_size": attachment.file_size,
    }


def _build_general_model_input(
    prior_messages,
    user_prompt: str,
    intent: ChatIntent,
    security_mode: SecurityMode,
) -> str:
    """Compose structured model input for General Chat (no Task Passport).

    Sections: SECURITY MODE → RECENT CONVERSATION → INTENT →
    RESPONSE GUIDANCE → CURRENT USER MESSAGE. No task relevance gate,
    no task RAG, no task-scope restrictions — normal general AI chat
    under the selected security mode's general policy.
    """
    conv_lines = ["RECENT CONVERSATION:"]
    recent = prior_messages[-_MAX_CONTEXT_MESSAGES:]
    if recent:
        for msg in recent:
            conv_lines.append(f"{msg.role}: {msg.content}")
    else:
        conv_lines.append("(none)")

    intent_lines = [
        "INTENT:",
        f"objective: {intent.objective}",
        f"category: {intent.category}",
        f"answer_type: {intent.answer_type}",
        f"conversation_turns: {intent.conversation_turns}",
        f"follow_up: {str(intent.follow_up).lower()}",
    ]

    conversation_rules = [
        "Primary intent: answer the CURRENT USER MESSAGE in natural "
        "prose; do not force a fixed answer template.",
        "Use RECENT CONVERSATION for follow-ups and short references; "
        "keep depth matched to the question.",
        "Separate FACT from INTERPRETATION; never fabricate facts.",
    ]

    if security_mode == SecurityMode.SOVEREIGN:
        guidance = [
            "General Chat under sovereign mode: local model only; "
            "no external model calls.",
            "Answer helpfully within general conversation scope; "
            "do not fabricate facts.",
            *conversation_rules,
        ]
    elif security_mode == SecurityMode.SECURE:
        guidance = [
            "General Chat under secure mode: prefer local model; "
            "no task-scoped evidence requirements.",
            "Answer helpfully within general conversation scope.",
            *conversation_rules,
        ]
    else:
        guidance = [
            "General Chat: normal general AI conversation; "
            "no task scope, no task evidence requirements.",
            "Answer helpfully and briefly.",
            *conversation_rules,
        ]

    sections = [
        f"SECURITY MODE: {security_mode.value}",
        "CONTEXT: General Chat (no active task)",
        "\n".join(conv_lines),
        "\n".join(intent_lines),
        "RESPONSE GUIDANCE:\n" + "\n".join(f"  - {g}" for g in guidance),
        "CURRENT USER MESSAGE:\n" + user_prompt,
    ]
    return "\n\n".join(sections)


async def _send_general_chat(
    *,
    db,
    payload: ChatRequest,
    current_user: CurrentUser,
    conversation_id: str,
    prior_messages,
) -> ChatResponse:
    """General Chat path: no Task Passport, no task-relevance gate, no RAG.

    Works in Standard / Secure / Sovereign. Sovereign forces local model
    via the existing security-mode engine. No Task Passport is created.
    """
    from app.services.security_mode import PolicyDecision, security_mode_engine

    try:
        security_mode = SecurityMode(current_user.preferred_security_mode)
    except ValueError:
        security_mode = SecurityMode.STANDARD

    task_id_for_audit = ""  # General Chat — no active task
    audit_base = dict(
        task_id=task_id_for_audit,
        user_id=current_user.user_id,
        identity=current_user.username,
        role=current_user.role.value,
        security_mode=security_mode.value,
    )

    conversation_service.record_chat_audit(
        event_type="chat_message_sent",
        task_id=task_id_for_audit,
        user_id=current_user.user_id,
        role="",
        detail=f"General Chat message in conversation {conversation_id}",
    )

    intent = classify_intent(payload.prompt, _general_chat_intent_passport(current_user), prior_messages)
    audit_service.record(
        event_type="CHAT_INTENT_CLASSIFIED",
        detail=(
            f"category={intent.category} answer_type={intent.answer_type} "
            f"general_chat=true"
        ),
        **audit_base,
    )

    selected_model = payload.model
    if selected_model:
        sec_decision, sec_reason = security_mode_engine.check_model_allowed(
            selected_model, security_mode
        )
        if sec_decision == PolicyDecision.DENY:
            audit_service.record(
                event_type="model_denied_by_security_mode",
                task_id=task_id_for_audit,
                user_id=current_user.user_id,
                identity=current_user.username,
                role="",
                security_mode=security_mode.value,
                detail=sec_reason,
            )
            raise HTTPException(status_code=403, detail=sec_reason)

    decision = model_router.route(
        payload.prompt,
        [],  # no Task Passport allowed_models for General Chat
        "",
        security_mode,
        intent_category=intent.category,
    )

    if selected_model and selected_model in ModelAdapterFactory.available():
        model_name = selected_model
    else:
        model_name = decision.model_name

    is_local_model = not model_name.startswith(
        ("api-", "openai-", "claude-", "gpt-")
    )

    # Sovereign always forces local even if a selected external model
    # somehow passed the check above.
    if security_mode == SecurityMode.SOVEREIGN and not is_local_model:
        model_name = "local-qwen2"
        is_local_model = True

    audit_service.record(
        event_type="MODEL_ROUTED",
        detail=(
            f"selected={model_name} category={decision.complexity} "
            f"local_execution={is_local_model} "
            f"general_chat=true "
            f"security_decision={decision.security_decision} "
            f"reason={decision.reason}"
        ),
        **audit_base,
    )

    adapter = ModelAdapterFactory.get(model_name)
    model_input = _build_general_model_input(
        prior_messages, payload.prompt, intent, security_mode,
    )

    if is_local_model:
        audit_service.record(
            event_type="LOCAL_MODEL_REQUESTED",
            detail=f"model={model_name} runtime=ollama-compatible general_chat=true",
            **audit_base,
        )

    try:
        model_response = adapter.generate(model_input, payload.max_tokens)
    except LocalModelUnavailableError as exc:
        audit_service.record(
            event_type="LOCAL_MODEL_UNAVAILABLE",
            detail=f"model={model_name} error={str(exc)[:200]}",
            **audit_base,
        )
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE)

    if is_local_model:
        audit_service.record(
            event_type="LOCAL_MODEL_INFERENCE",
            detail=(
                f"model={model_name} tokens={model_response.tokens_used} "
                f"latency={model_response.latency_ms}ms "
                f"input_chars={len(model_input)} general_chat=true"
            ),
            **audit_base,
        )

    if model_name.startswith(("api-", "openai-", "claude-", "gpt-")):
        execution_mode = "simulation"
        mode_label = "simulation"
    else:
        execution_mode = "local"
        mode_label = "local"

    assistant_content = f"[{model_name} {mode_label}] {model_response.text}"

    assistant_msg = conversation_service.add_message(
        db,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        model=model_name,
    )

    conversation_service.record_chat_audit(
        event_type="model_inference",
        task_id=task_id_for_audit,
        user_id=current_user.user_id,
        role="",
        detail=(
            f"model={model_name} complexity={decision.complexity} "
            f"tokens={model_response.tokens_used} "
            f"latency={model_response.latency_ms}ms "
            f"execution_mode={execution_mode} general_chat=true "
            f"context_messages={len(prior_messages)}"
        ),
    )

    audit_service.record(
        event_type="CHAT_RESPONSE_GENERATED",
        detail=(
            f"model={model_name} general_chat=true "
            f"intent={intent.category} input_chars={len(model_input)}"
        ),
        **audit_base,
    )

    audit_service.record(
        event_type="final_decision",
        detail=(
            f"decision=answered_via_model general_chat=true "
            f"model={model_name} security_mode={security_mode.value}"
        ),
        **audit_base,
    )

    return ChatResponse(
        conversation_id=conversation_id,
        message_id=assistant_msg.id,
        model_used=model_name,
        response_text=model_response.text,
        complexity=decision.complexity,
        routing_reason=decision.reason,
        tokens_used=model_response.tokens_used,
        latency_ms=model_response.latency_ms,
        execution_mode=execution_mode,
        sources=[],
    )


def _general_chat_intent_passport(current_user: CurrentUser):
    """Minimal synthetic passport stand-in for intent classification only.

    Never used for Action Gate, RAG, relevance gate, or external research —
    General Chat skips all task-scoped pipeline stages.
    """
    from datetime import datetime, timezone

    from app.schemas.task import (
        ApprovalRequirement,
        NetworkPolicy,
        TaskPassportRead,
        TaskSensitivity,
        TaskStatus,
    )

    now = datetime.now(timezone.utc)
    try:
        mode = SecurityMode(current_user.preferred_security_mode)
    except ValueError:
        mode = SecurityMode.STANDARD
    return TaskPassportRead(
        task_id="",
        user_id=current_user.user_id,
        identity=current_user.username,
        role=current_user.role.value,
        title="General Chat",
        purpose="General AI conversation without an active task",
        sensitivity=TaskSensitivity.INTERNAL,
        security_mode=mode,
        security_policy_version="1.0",
        requested_operation="",
        allowed_sources=[],
        allowed_tools=[],
        allowed_models=[],
        approval_requirement=ApprovalRequirement.NONE,
        network_policy=NetworkPolicy.DENY_EXTERNAL
        if mode == SecurityMode.SOVEREIGN
        else NetworkPolicy.ALLOW_INTERNAL,
        status=TaskStatus.EXECUTING,
        created_at=now,
        updated_at=now,
    )


@router.post("/send", response_model=ChatResponse)
async def send_chat_message(
    payload: ChatRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> ChatResponse:
    """Send a chat message with Task Passport + Action Gate enforcement.

    General Chat (task_id null/omitted) skips Task Passport, Action Gate
    task checks, task-relevance gate, and task RAG — normal general chat
    under the selected security mode. Task-scoped sends keep the full
    task-aware pipeline unchanged.
    """
    raw_task_id = (payload.task_id or "").strip()
    is_general_chat = not raw_task_id

    if not is_general_chat:
        try:
            passport = passport_service.get(db, raw_task_id)
        except TaskPassportNotFoundError:
            raise HTTPException(status_code=404, detail="Task passport not found")

        if passport.user_id != current_user.user_id:
            raise HTTPException(status_code=403, detail="Identity mismatch")

        try:
            action_gate.authorize_action(
                AuthorizationContext(
                    passport=passport,
                    current_user=current_user,
                    action_category=ActionCategory.COMPUTE,
                )
            )
        except ActionGateError as exc:
            raise HTTPException(status_code=403, detail=str(exc))
    else:
        passport = None

    # Resolve / create conversation.
    if payload.conversation_id:
        convo = conversation_service.get_conversation(db, payload.conversation_id, current_user.user_id)
        if convo is None:
            raise HTTPException(status_code=404, detail="Conversation not found or access denied")
        # General Chat conversations must not be bound to a task id later.
        if is_general_chat and convo.task_id:
            raise HTTPException(
                status_code=400,
                detail="Conversation is bound to a task; select that task or start a new General Chat",
            )
        conversation_id = convo.id
    else:
        convo_read = conversation_service.create_conversation(
            db,
            task_id=raw_task_id,  # "" for General Chat — no Task Passport created
            user_id=current_user.user_id,
            title=payload.prompt[:80],
        )
        conversation_id = convo_read.id

    # Load prior authorized messages for this conversation BEFORE appending
    # the new user turn so history is not duplicated.
    prior_messages = conversation_service.get_messages(db, conversation_id)

    conversation_service.add_message(
        db,
        conversation_id=conversation_id,
        role="user",
        content=payload.prompt,
    )

    if is_general_chat:
        # ── General Chat: no task pipeline (no relevance gate / RAG /
        #    controlled external verification / Task Passport audits). ──
        return await _send_general_chat(
            db=db,
            payload=payload,
            current_user=current_user,
            conversation_id=conversation_id,
            prior_messages=prior_messages,
        )

    conversation_service.record_chat_audit(
        event_type="chat_message_sent",
        task_id=raw_task_id,
        user_id=current_user.user_id,
        role="",
        detail=f"User message in conversation {conversation_id}",
    )

    # ── Phase 2/3 pipeline: intent → resource plan → RAG → evidence →
    #    external research policy → privacy gateway ─────────────────────
    audit_base = dict(
        task_id=raw_task_id,
        user_id=current_user.user_id,
        identity=current_user.username,
        role=current_user.role.value,
        security_mode=passport.security_mode.value,
    )

    # ── Task-relevance gate (deterministic, backend-side) ───────────────
    # Runs before intent/RAG/external/model so sovereign off-topic turns
    # never reach retrieval, egress, or local inference.
    relevance: TaskRelevance = check_task_relevance(
        payload.prompt, passport, prior_messages
    )
    audit_service.record(
        event_type="task_relevance_checked",
        detail=(
            f"relevant={str(relevance.relevant).lower()} "
            f"information_need={relevance.information_need[:200]!r} "
            f"reason={relevance.reason!r}"
        ),
        **audit_base,
    )

    if passport.security_mode == SecurityMode.SOVEREIGN and not relevance.relevant:
        audit_service.record(
            event_type="task_scope_denied",
            detail=(
                f"decision=task_scope_denied "
                f"information_need={relevance.information_need[:200]!r} "
                f"reason={relevance.reason!r}"
            ),
            **audit_base,
        )
        return _policy_reply(
            db=db,
            conversation_id=conversation_id,
            content=TASK_SCOPE_MESSAGE,
            model_name="task-relevance-gate",
            routing_reason="task-scope refusal (sovereign relevance gate)",
            decision="task_scope_denied",
            information_need=relevance.information_need,
            audit_base=audit_base,
        )

    intent = classify_intent(payload.prompt, passport, prior_messages)
    audit_service.record(
        event_type="CHAT_INTENT_CLASSIFIED",
        detail=(
            f"category={intent.category} answer_type={intent.answer_type} "
            f"evidence_required={intent.evidence_required} "
            f"public_research_useful={intent.public_research_useful} "
            f"turns={intent.conversation_turns}"
        ),
        **audit_base,
    )

    plan = plan_resources(intent, passport)
    audit_service.record(
        event_type="CHAT_RESOURCE_PLAN_CREATED",
        detail=(
            f"rag_enabled={plan.rag_enabled} "
            f"sources={len(plan.authorized_sources)} "
            f"tools={len(plan.authorized_tools)} "
            f"external_candidate={plan.external_research_candidate} "
            f"restrictions={len(plan.restrictions)}"
        ),
        **audit_base,
    )

    rag_chunks: list[dict] = []
    rag_attempted = False
    rag_before = 0
    if plan.rag_enabled:
        rag_attempted = True
        rag_result = retrieval_service.search(
            query=plan.rag_query,
            allowed_sources=plan.authorized_sources,
            sensitivity_level=passport.sensitivity.value,
            network_policy=passport.network_policy.value,
            top_k=5,
            task_id=passport.task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
            security_mode=passport.security_mode,
        )
        rag_chunks = rag_result.chunks
        rag_before = rag_result.total_before_filter
        audit_service.record(
            event_type="CHAT_RAG_SEARCH",
            detail=(
                f"results_before={rag_before} "
                f"permitted={len(rag_chunks)} "
                f"authorized_sources={len(plan.authorized_sources)}"
            ),
            **audit_base,
        )
        if not rag_chunks:
            audit_service.record(
                event_type="CHAT_RAG_NO_RESULT",
                detail="Authorized RAG returned no permitted evidence",
                **audit_base,
            )
    elif intent.evidence_required:
        audit_service.record(
            event_type="CHAT_RAG_NO_RESULT",
            detail=(
                "RAG not attempted: no authorized sources "
                "(empty allowlist fails closed)"
            ),
            **audit_base,
        )

    evidence = assess_evidence(intent, plan, rag_chunks, rag_attempted)

    research: ResearchOutcome | None = None
    if not evidence.enough and evidence.public_research_could_help:
        # Explicit gated external research — never automatic egress.
        # Sovereign: continue through policy-controlled verification when
        # the passport permits; not an automatic refusal of public research.
        research = privacy_gateway.conduct_research(
            intent=intent,
            passport=passport,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
            missing_count=len(evidence.missing_information),
        )

    # ── Sovereign evidence gate: only refuse when verified evidence is
    #    insufficient AND controlled external research could not complete
    #    with results (blocked, denied, unsafe, unavailable, or empty).
    #    Successful sanitized public research → combine evidence → local
    #    model answer (fall through). ─────────────────────────────────────
    if passport.security_mode == SecurityMode.SOVEREIGN and not evidence.enough:
        external_completed = bool(
            research is not None and research.completed and research.results
        )
        if not external_completed:
            external_status = research.status if research else "not_requested"
            return _policy_reply(
                db=db,
                conversation_id=conversation_id,
                content=INSUFFICIENT_VERIFIED_MESSAGE,
                model_name="evidence-verification-gate",
                routing_reason=(
                    "sovereign evidence gate: insufficient verified evidence "
                    f"and external research not completed "
                    f"(external_research={external_status})"
                ),
                decision="insufficient_verified_evidence",
                information_need=relevance.information_need,
                audit_base=audit_base,
            )

    selected_model = payload.model
    if selected_model:
        allowed = passport.allowed_models
        if allowed and selected_model not in allowed:
            audit_service.record(
                event_type="model_blocked",
                task_id=payload.task_id,
                user_id=current_user.user_id,
                identity=current_user.username,
                role="",
                security_mode=passport.security_mode if hasattr(passport, 'security_mode') else "standard",
                detail=f"Model '{selected_model}' not in allowed models: {allowed}",
            )
            raise HTTPException(
                status_code=403,
                detail=f"Model '{selected_model}' is not permitted by this Task Passport",
            )

        if passport.network_policy.value == "deny_external" and selected_model.startswith("api-"):
            audit_service.record(
                event_type="model_blocked",
                task_id=payload.task_id,
                user_id=current_user.user_id,
                identity=current_user.username,
                role="",
                security_mode=passport.security_mode if hasattr(passport, 'security_mode') else "standard",
                detail=f"External model '{selected_model}' blocked by network policy deny_external",
            )
            raise HTTPException(
                status_code=403,
                detail=f"External model '{selected_model}' is blocked by network policy (deny_external)",
            )

    # Security mode: block external models in SOVEREIGN mode
    from app.services.security_mode import security_mode_engine, PolicyDecision
    sec_decision, sec_reason = security_mode_engine.check_model_allowed(
        selected_model or "local-qwen2", passport.security_mode
    )
    if sec_decision == PolicyDecision.DENY:
        audit_service.record(
            event_type="model_denied_by_security_mode",
            task_id=payload.task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role="",
            security_mode=passport.security_mode if hasattr(passport, 'security_mode') else "standard",
            detail=sec_reason,
        )
        raise HTTPException(status_code=403, detail=sec_reason)

    decision = model_router.route(
        payload.prompt,
        passport.allowed_models,
        passport.requested_operation,
        passport.security_mode,
        intent_category=intent.category,
    )

    if selected_model and selected_model in ModelAdapterFactory.available():
        model_name = selected_model
    else:
        model_name = decision.model_name

    is_local_model = not model_name.startswith(
        ("api-", "openai-", "claude-", "gpt-")
    )

    audit_service.record(
        event_type="MODEL_ROUTED",
        detail=(
            f"selected={model_name} category={decision.complexity} "
            f"local_execution={is_local_model} "
            f"security_decision={decision.security_decision} "
            f"reason={decision.reason}"
        ),
        **audit_base,
    )

    adapter = ModelAdapterFactory.get(model_name)
    # Structured input: task context + conversation + intent + resource plan
    # + RAG evidence + public research (when permitted) + response guidance
    # + current message. Routing/complexity still classifies the raw user
    # prompt; only the model adapter receives the full structured context.
    response_guidance = _build_response_guidance(
        payload.prompt, passport, intent, evidence,
    )
    model_input = _build_pipeline_model_input(
        passport, prior_messages, payload.prompt, intent, plan, evidence, research,
        response_guidance=response_guidance,
    )

    if is_local_model:
        audit_service.record(
            event_type="LOCAL_MODEL_REQUESTED",
            detail=f"model={model_name} runtime=ollama-compatible",
            **audit_base,
        )

    try:
        model_response = adapter.generate(model_input, payload.max_tokens)
    except LocalModelUnavailableError as exc:
        # Fail closed: clear system status, no fabricated/echo response,
        # no silent fallback to any external provider.
        audit_service.record(
            event_type="LOCAL_MODEL_UNAVAILABLE",
            detail=f"model={model_name} error={str(exc)[:200]}",
            **audit_base,
        )
        raise HTTPException(status_code=503, detail=UNAVAILABLE_MESSAGE)

    if is_local_model:
        audit_service.record(
            event_type="LOCAL_MODEL_INFERENCE",
            detail=(
                f"model={model_name} tokens={model_response.tokens_used} "
                f"latency={model_response.latency_ms}ms "
                f"input_chars={len(model_input)}"
            ),
            **audit_base,
        )

    if model_name.startswith(("api-", "openai-", "claude-", "gpt-")):
        execution_mode = "simulation"  # external proxy remains simulated
        mode_label = "simulation"
    else:
        execution_mode = "local"
        mode_label = "local"

    assistant_content = (
        f"[{model_name} {mode_label}] "
        f"{model_response.text}"
    )

    assistant_msg = conversation_service.add_message(
        db,
        conversation_id=conversation_id,
        role="assistant",
        content=assistant_content,
        model=model_name,
    )

    conversation_service.record_chat_audit(
        event_type="model_inference",
        task_id=payload.task_id,
        user_id=current_user.user_id,
        role="",
        detail=(
            f"model={model_name} complexity={decision.complexity} "
            f"tokens={model_response.tokens_used} latency={model_response.latency_ms}ms "
            f"execution_mode={execution_mode} "
            f"context_messages={len(prior_messages)} "
            f"model_input_chars={len(model_input)}"
        ),
    )

    audit_service.record(
        event_type="CHAT_RESPONSE_GENERATED",
        detail=(
            f"model={model_name} "
            f"intent={intent.category} "
            f"evidence_chunks={evidence.chunk_count} "
            f"enough_evidence={evidence.enough} "
            f"public_research={research.status if research else 'none'} "
            f"input_chars={len(model_input)}"
        ),
        **audit_base,
    )

    audit_service.record(
        event_type="final_decision",
        detail=(
            f"decision=answered_via_model "
            f"information_need={relevance.information_need[:200]!r} "
            f"model={model_name} "
            f"enough_evidence={evidence.enough} "
            f"public_research={research.status if research else 'none'}"
        ),
        **audit_base,
    )

    sources = _extract_sources(rag_chunks)

    return ChatResponse(
        conversation_id=conversation_id,
        message_id=assistant_msg.id,
        model_used=model_name,
        response_text=model_response.text,
        complexity=decision.complexity,
        routing_reason=decision.reason,
        tokens_used=model_response.tokens_used,
        latency_ms=model_response.latency_ms,
        execution_mode=execution_mode,
        sources=sources,
    )
