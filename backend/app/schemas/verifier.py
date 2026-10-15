"""Pydantic schemas for Verifier and Audit Trail API."""

from pydantic import BaseModel, Field


class VerifyRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=36)
    output_text: str = Field(min_length=1, max_length=50000)
    allowed_sources: list[str] = Field(default_factory=list)


class CheckResultResponse(BaseModel):
    check_name: str
    verdict: str
    detail: str


class VerifyResponse(BaseModel):
    overall: str
    checks: list[CheckResultResponse]
    summary: str


class AuditEventResponse(BaseModel):
    event_id: str
    timestamp: str
    event_type: str
    task_id: str
    user_id: str
    identity: str
    role: str
    security_mode: str = "standard"
    previous_status: str | None
    new_status: str | None
    detail: str


class AuditTrailResponse(BaseModel):
    task_id: str
    events: list[AuditEventResponse]
    total_events: int


class TaskWithAuditSummary(BaseModel):
    """Task summary with latest audit event for auto-loading."""
    task_id: str
    title: str
    status: str
    sensitivity: str
    security_mode: str = "standard"
    created_at: str
    updated_at: str
    latest_event_type: str | None
    latest_event_timestamp: str | None
    latest_event_detail: str | None
    total_events: int


class TasksAuditSummaryResponse(BaseModel):
    """Response with all tasks and their audit summaries."""
    tasks: list[TaskWithAuditSummary]
    total: int
