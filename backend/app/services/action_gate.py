"""Action Gate — centralized authorization for all consequential actions.

Every action that uses Task Passport permissions (RAG search, model inference,
agent planning, sandbox execution, verification) MUST go through this gate.

The gate enforces:
1. Task Passport existence and ownership (identity match)
2. Task Passport lifecycle status (must be authorized/executing for consequential actions)
3. Tool allowlist enforcement (fail-closed: empty list blocks all tools)
4. Sensitivity max enforcement (tool's allowed_sensitivity_max vs passport sensitivity)
5. Approval requirement enforcement (high-risk tools require approval)
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from sqlalchemy.orm import Session

from app.schemas.auth import CurrentUser
from app.schemas.task import (
    SecurityMode,
    TaskPassportRead,
    TaskSensitivity,
    TaskStatus,
)
from app.services.security_mode import PolicyDecision, security_mode_engine


class ActionGateError(Exception):
    """Raised when an action is denied by the Action Gate."""


class ActionGateDenied(ActionGateError):
    """Raised when an action is explicitly denied."""


class ActionGateLifecycleError(ActionGateError):
    """Raised when the passport lifecycle does not permit the action."""


class ActionGateToolError(ActionGateError):
    """Raised when a tool is not permitted by the passport."""


class ActionGateApprovalError(ActionGateError):
    """Raised when a tool requires approval but has not been approved."""


SENSITIVITY_ORDER = ["internal", "confidential", "restricted"]


class ActionCategory(str, Enum):
    """Categories of actions that require different authorization levels."""
    READ = "read"           # RAG search, document reading
    WRITE = "write"         # Generate reports, create documents
    COMPUTE = "compute"     # Model inference, data analysis
    EXECUTE = "execute"     # Sandbox execution, code execution
    EXTERNAL = "external"   # API calls, email sending


@dataclass
class AuthorizationContext:
    """Context for an authorization check."""
    passport: TaskPassportRead
    current_user: CurrentUser
    action_category: ActionCategory
    tool_name: str | None = None


@dataclass
class AuthorizationResult:
    """Result of an authorization check."""
    allowed: bool
    reason: str = ""
    requires_approval: bool = False


class ActionGate:
    """Centralized authorization gate for all consequential actions."""

    def check_passport_ownership(
        self,
        passport: TaskPassportRead,
        current_user: CurrentUser,
    ) -> None:
        """Verify the current user owns this Task Passport."""
        if passport.user_id != current_user.user_id:
            raise ActionGateDenied(
                "Your identity does not match this Task Passport"
            )

    def check_lifecycle_for_action(
        self,
        passport: TaskPassportRead,
        action_category: ActionCategory,
    ) -> None:
        """Verify the passport status permits the requested action.

        Lifecycle rules:
        - DRAFT: Only read/write updates allowed (security fields)
        - PENDING_APPROVAL: read/write/compute allowed (review prep); no execution
        - AUTHORIZED: All actions permitted
        - EXECUTING: All actions permitted
        - COMPLETED/FAILED/DENIED/REJECTED/VERIFIED/PENDING_VERIFICATION: No actions
        """
        allowed_statuses = {
            ActionCategory.READ: {
                TaskStatus.DRAFT,
                TaskStatus.PENDING_APPROVAL,
                TaskStatus.AUTHORIZED,
                TaskStatus.EXECUTING,
            },
            ActionCategory.WRITE: {
                TaskStatus.DRAFT,
                TaskStatus.PENDING_APPROVAL,
                TaskStatus.AUTHORIZED,
                TaskStatus.EXECUTING,
            },
            ActionCategory.COMPUTE: {
                TaskStatus.PENDING_APPROVAL,
                TaskStatus.AUTHORIZED,
                TaskStatus.EXECUTING,
            },
            ActionCategory.EXECUTE: {TaskStatus.AUTHORIZED, TaskStatus.EXECUTING},
            ActionCategory.EXTERNAL: {TaskStatus.AUTHORIZED, TaskStatus.EXECUTING},
        }

        permitted = allowed_statuses.get(action_category, set())
        if passport.status not in permitted:
            raise ActionGateLifecycleError(
                f"Task Passport status '{passport.status.value}' does not permit "
                f"'{action_category.value}' actions. Required status: "
                f"{', '.join(s.value for s in permitted)}"
            )

    def check_tool_allowlist(
        self,
        tool_name: str,
        allowed_tools: list[str],
    ) -> None:
        """Check if a tool is in the passport's allowlist.

        Security: An EMPTY allowed_tools list means NO tools are permitted.
        This is fail-closed behavior.
        """
        if not allowed_tools:
            raise ActionGateToolError(
                f"Tool '{tool_name}' is not permitted: "
                f"Task Passport has an empty tool allowlist (no tools permitted)"
            )
        if tool_name not in allowed_tools:
            raise ActionGateToolError(
                f"Tool '{tool_name}' is not in the Task Passport's allowed tools: "
                f"{allowed_tools}"
            )

    def check_tool_sensitivity(
        self,
        tool_name: str,
        tool_sensitivity_max: str,
        passport_sensitivity: TaskSensitivity,
    ) -> None:
        """Check if the tool's sensitivity level is compatible with the passport.

        The tool's allowed_sensitivity_max must be >= the passport's sensitivity.
        """
        try:
            tool_max_idx = SENSITIVITY_ORDER.index(tool_sensitivity_max)
        except ValueError:
            raise ActionGateToolError(
                f"Tool '{tool_name}' has invalid sensitivity max: {tool_sensitivity_max}"
            )

        passport_idx = SENSITIVITY_ORDER.index(passport_sensitivity.value)
        if passport_idx > tool_max_idx:
            raise ActionGateToolError(
                f"Tool '{tool_name}' (max sensitivity: {tool_sensitivity_max}) "
                f"cannot be used with passport sensitivity '{passport_sensitivity.value}'"
            )

    def check_approval_requirement(
        self,
        tool_name: str,
        requires_approval: bool,
        approval_requirement: str,
        step_approved: bool = False,
    ) -> None:
        """Check if a tool requires approval based on the passport's approval requirement.

        If the passport requires approval (reviewer/admin) and the tool is high-risk,
        the step must be approved before execution.
        """
        if requires_approval and approval_requirement != "none" and not step_approved:
            raise ActionGateApprovalError(
                f"Tool '{tool_name}' requires approval "
                f"(passport approval_requirement: {approval_requirement})"
            )

    def check_security_mode_network(
        self,
        passport: TaskPassportRead,
        action_category: ActionCategory,
    ) -> None:
        """Check if the security mode permits external network actions."""
        if action_category == ActionCategory.EXTERNAL:
            decision, reason = security_mode_engine.check_network_allowed(
                passport.security_mode, "external"
            )
            if decision == PolicyDecision.DENY:
                raise ActionGateDenied(reason)

    def check_security_mode_tool(
        self,
        tool_name: str,
        passport: TaskPassportRead,
    ) -> None:
        """Check if the security mode permits the tool."""
        decision, reason = security_mode_engine.check_tool_allowed(
            tool_name, passport.allowed_tools, passport.security_mode
        )
        if decision == PolicyDecision.DENY:
            raise ActionGateToolError(reason)

    def authorize_action(
        self,
        ctx: AuthorizationContext,
        step_approved: bool = False,
    ) -> AuthorizationResult:
        """Perform a full authorization check for an action.

        Returns AuthorizationResult if allowed, raises ActionGateError if denied.
        """
        # 1. Ownership check
        self.check_passport_ownership(ctx.passport, ctx.current_user)

        # 2. Lifecycle check
        self.check_lifecycle_for_action(ctx.passport, ctx.action_category)

        # 2b. Human verification check — consequential execution of an
        # approval-required task demands a valid manager/admin approval
        # (bound to the current, unmodified task plan).
        if ctx.action_category in (
            ActionCategory.EXECUTE,
            ActionCategory.EXTERNAL,
        ) and ctx.passport.approval_requirement.value != "none":
            from app.services.human_verification import human_verification_service

            ok, reason = human_verification_service.check_pre_execution(ctx.passport)
            if not ok:
                raise ActionGateApprovalError(reason)

        # 3. Security mode network check
        self.check_security_mode_network(ctx.passport, ctx.action_category)

        # 4. Tool checks (if a tool is specified)
        if ctx.tool_name:
            from app.services.agent.tool_registry import tool_registry

            tool_def = tool_registry.get(ctx.tool_name)
            if tool_def is None:
                raise ActionGateToolError(f"Unknown tool: {ctx.tool_name}")

            # Security mode tool check (before allowlist)
            self.check_security_mode_tool(ctx.tool_name, ctx.passport)

            # Tool allowlist (fail-closed)
            self.check_tool_allowlist(ctx.tool_name, ctx.passport.allowed_tools)

            # Sensitivity check
            self.check_tool_sensitivity(
                ctx.tool_name,
                tool_def.allowed_sensitivity_max,
                ctx.passport.sensitivity,
            )

            # Approval check
            self.check_approval_requirement(
                ctx.tool_name,
                tool_def.requires_approval,
                ctx.passport.approval_requirement.value,
                step_approved,
            )

        return AuthorizationResult(
            allowed=True,
            requires_approval=(
                ctx.tool_name is not None
                and ctx.passport.approval_requirement.value != "none"
            ),
        )


action_gate = ActionGate()
