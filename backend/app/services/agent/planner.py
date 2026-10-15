"""Agent Planner — converts user queries into step-by-step execution plans with permission checks."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from app.services.audit_service import audit_service
from app.services.agent.tool_registry import ToolRisk, tool_registry


class StepStatus(str, Enum):
    PENDING = "pending"
    APPROVED = "approved"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class PlanStatus(str, Enum):
    CREATED = "created"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
    DENIED = "denied"


@dataclass
class PlanStep:
    step_id: str
    order: int
    tool_name: str
    action: str
    description: str
    status: StepStatus = StepStatus.PENDING
    risk: str = "low"
    requires_approval: bool = False


@dataclass
class ExecutionPlan:
    plan_id: str
    task_id: str
    user_query: str
    steps: list[PlanStep]
    status: PlanStatus = PlanStatus.CREATED
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


class AgentPlanner:
    """Creates execution plans from user queries, respecting Task Passport constraints."""

    def create_plan(
        self,
        query: str,
        task_id: str,
        allowed_tools: list[str] | None = None,
        user_id: str = "",
        identity: str = "",
        role: str = "",
    ) -> ExecutionPlan:
        plan_id = str(uuid4())
        steps = self._generate_steps(query, task_id, allowed_tools, user_id, identity, role)
        plan = ExecutionPlan(
            plan_id=plan_id,
            task_id=task_id,
            user_query=query,
            steps=steps,
        )

        audit_service.record(
            event_type="plan_created",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            detail=f"Plan {plan_id} created with {len(steps)} steps",
        )
        return plan

    def _generate_steps(
        self,
        query: str,
        task_id: str,
        allowed_tools: list[str] | None,
        user_id: str,
        identity: str,
        role: str,
    ) -> list[PlanStep]:
        steps: list[PlanStep] = []
        order = 0
        query_lower = query.lower()

        if any(kw in query_lower for kw in ["read", "find", "search", "look", "document"]):
            tool = tool_registry.get("document_reader")
            if tool and tool_registry.is_tool_allowed(tool.name, allowed_tools or []):
                steps.append(self._make_step(order, tool, "Read relevant documents", task_id, user_id, identity, role))
                order += 1

        if any(kw in query_lower for kw in ["analyze", "compute", "calculate", "data", "statistics"]):
            tool = tool_registry.get("data_analyzer")
            if tool and tool_registry.is_tool_allowed(tool.name, allowed_tools or []):
                steps.append(self._make_step(order, tool, "Analyze relevant data", task_id, user_id, identity, role))
                order += 1

        if any(kw in query_lower for kw in ["report", "generate", "create", "write", "export"]):
            tool = tool_registry.get("docx_generator")
            if tool and tool_registry.is_tool_allowed(tool.name, allowed_tools or []):
                steps.append(self._make_step(order, tool, "Generate output report", task_id, user_id, identity, role))
                order += 1

        if any(kw in query_lower for kw in ["send", "email", "notify", "share"]):
            tool = tool_registry.get("email_sender")
            if tool and tool_registry.is_tool_allowed(tool.name, allowed_tools or []):
                steps.append(self._make_step(order, tool, "Send notification", task_id, user_id, identity, role))
                order += 1

        if any(kw in query_lower for kw in ["execute", "run", "code", "script"]):
            tool = tool_registry.get("code_executor")
            if tool and tool_registry.is_tool_allowed(tool.name, allowed_tools or []):
                steps.append(self._make_step(order, tool, "Execute code", task_id, user_id, identity, role))
                order += 1

        if not steps:
            tool = tool_registry.get("document_reader")
            if tool and tool_registry.is_tool_allowed(tool.name, allowed_tools or []):
                steps.append(self._make_step(order, tool, "Read relevant documents (default)", task_id, user_id, identity, role))

        return steps

    def _make_step(
        self,
        order: int,
        tool_def,
        action: str,
        task_id: str,
        user_id: str,
        identity: str,
        role: str,
    ) -> PlanStep:
        step = PlanStep(
            step_id=str(uuid4()),
            order=order,
            tool_name=tool_def.name,
            action=action,
            description=tool_def.description,
            risk=tool_def.risk.value,
            requires_approval=tool_def.requires_approval,
        )
        audit_service.record(
            event_type="plan_step_added",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            detail=f"Step {order}: {tool_def.name} — {action}",
        )
        return step


agent_planner = AgentPlanner()
