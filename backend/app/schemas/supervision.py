"""Pydantic schemas for the Supervision & Verification API."""

from pydantic import BaseModel, Field

from app.schemas.verifier import AuditEventResponse


class DecisionRequest(BaseModel):
    """Manager/Admin verification decision payload."""

    reason: str = Field(default="", max_length=1000)


class StrictDecisionRequest(BaseModel):
    """Decision payload that requires a non-empty reason (rejections)."""

    reason: str = Field(min_length=1, max_length=1000)


class VerificationRecordResponse(BaseModel):
    kind: str
    decision: str
    reason: str
    actor_user_id: str
    actor_username: str
    actor_role: str
    target_user_id: str
    created_at: str


class SupervisedTaskItem(BaseModel):
    """Worker activity row on the supervision page."""

    task_id: str
    title: str
    purpose: str
    status: str
    security_mode: str
    sensitivity: str
    approval_requirement: str
    requested_operation: str
    allowed_tools: list[str]
    allowed_sources: list[str]
    allowed_models: list[str]
    network_policy: str
    created_at: str
    updated_at: str
    # Worker identity (user_id is authoritative; username is display).
    user_id: str
    username: str
    role: str
    # Derived supervision state
    execution_status: str
    verification_status: str
    total_audit_events: int
    latest_event_type: str | None
    latest_event_timestamp: str | None


class SupervisedTaskListResponse(BaseModel):
    tasks: list[SupervisedTaskItem]
    total: int


class PlanStepSupervision(BaseModel):
    step_id: str
    order: int
    tool_name: str
    action: str
    description: str
    status: str
    risk: str
    requires_approval: bool


class PlanSupervision(BaseModel):
    plan_id: str
    task_id: str
    user_query: str
    status: str
    steps: list[PlanStepSupervision]


class SupervisionDetailResponse(BaseModel):
    task: SupervisedTaskItem
    plan: PlanSupervision | None
    verifications: list[VerificationRecordResponse]
    audit_events: list[AuditEventResponse]
