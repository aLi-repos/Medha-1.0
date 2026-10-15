"""Pydantic schemas for the Task Passport."""

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


# --- Enums ---

class TaskSensitivity(str, Enum):
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class TaskStatus(str, Enum):
    DRAFT = "draft"
    PENDING_APPROVAL = "pending_approval"
    AUTHORIZED = "authorized"
    EXECUTING = "executing"
    COMPLETED = "completed"
    PENDING_VERIFICATION = "pending_verification"
    VERIFIED = "verified"
    REJECTED = "rejected"
    FAILED = "failed"
    DENIED = "denied"


class ApprovalRequirement(str, Enum):
    NONE = "none"
    REVIEWER = "reviewer"
    ADMIN = "admin"


class NetworkPolicy(str, Enum):
    DENY_EXTERNAL = "deny_external"
    ALLOW_INTERNAL = "allow_internal"


class SecurityMode(str, Enum):
    STANDARD = "standard"
    SECURE = "secure"
    SOVEREIGN = "sovereign"


SECURITY_POLICY_VERSION = "1.0"

# Security mode enforcement rules per sensitivity level
SENSITIVITY_SECURITY_REQUIREMENTS: dict[str, SecurityMode] = {
    "internal": SecurityMode.STANDARD,
    "confidential": SecurityMode.SECURE,
    "restricted": SecurityMode.SOVEREIGN,
}


# --- Valid status transitions ---
#
# Human-verification lifecycle (when approval_requirement != "none"):
#   draft → pending_approval → authorized → executing → completed
#        → pending_verification → verified
# Decisions on pending_approval / pending_verification are ONLY made through
# the supervision endpoints (manager/admin); task_service.transition_status
# refuses owner transitions out of those states.

VALID_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.DRAFT: {
        TaskStatus.AUTHORIZED,
        TaskStatus.PENDING_APPROVAL,
        TaskStatus.DENIED,
    },
    TaskStatus.PENDING_APPROVAL: {
        TaskStatus.AUTHORIZED,
        TaskStatus.REJECTED,
    },
    TaskStatus.AUTHORIZED: {TaskStatus.EXECUTING, TaskStatus.DENIED},
    TaskStatus.EXECUTING: {TaskStatus.COMPLETED, TaskStatus.FAILED},
    TaskStatus.COMPLETED: set(),
    TaskStatus.PENDING_VERIFICATION: {
        TaskStatus.VERIFIED,
        TaskStatus.REJECTED,
    },
    TaskStatus.VERIFIED: set(),
    TaskStatus.REJECTED: set(),
    TaskStatus.FAILED: {TaskStatus.AUTHORIZED},
    TaskStatus.DENIED: set(),
}

# Security-critical fields that become immutable once status leaves DRAFT.
SECURITY_CRITICAL_FIELDS = frozenset({
    "user_id",
    "identity",
    "role",
    "sensitivity",
    "allowed_sources",
    "allowed_tools",
    "allowed_models",
    "network_policy",
    "security_mode",
})


# --- Request schemas ---

class TaskCreate(BaseModel):
    """Input for creating a Task Passport (all fields the creator must supply)."""

    title: str = Field(min_length=1, max_length=200)
    purpose: str = Field(min_length=1, max_length=500)
    sensitivity: TaskSensitivity = TaskSensitivity.INTERNAL
    security_mode: SecurityMode = SecurityMode.STANDARD
    requested_operation: str = Field(default="", max_length=500)
    allowed_sources: list[str] = Field(default_factory=list)
    allowed_tools: list[str] = Field(default_factory=list)
    allowed_models: list[str] = Field(default_factory=list)
    approval_requirement: ApprovalRequirement = ApprovalRequirement.NONE
    network_policy: NetworkPolicy = NetworkPolicy.DENY_EXTERNAL


class TaskStatusUpdate(BaseModel):
    """Input for transitioning a Task Passport to a new status."""

    new_status: TaskStatus
    detail: str = Field(default="", max_length=500)


# --- Response schemas ---

class TaskPassportRead(BaseModel):
    """Full Task Passport as returned by the API."""

    model_config = ConfigDict(frozen=True)

    task_id: str
    user_id: str
    identity: str
    role: str
    title: str
    purpose: str
    sensitivity: TaskSensitivity
    security_mode: SecurityMode = SecurityMode.STANDARD
    security_policy_version: str = SECURITY_POLICY_VERSION
    requested_operation: str
    allowed_sources: list[str]
    allowed_tools: list[str]
    allowed_models: list[str]
    approval_requirement: ApprovalRequirement
    network_policy: NetworkPolicy
    status: TaskStatus
    created_at: datetime
    updated_at: datetime
