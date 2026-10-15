"""Agent service — orchestrates plan creation, step permission checks, and execution tracking."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.agent.planner import (
    ExecutionPlan,
    PlanStep,
    PlanStatus,
    StepStatus,
    agent_planner,
)
from app.services.agent.tool_registry import tool_registry
from app.services.audit_service import audit_service


@dataclass
class PlanSummary:
    plan_id: str
    task_id: str
    user_query: str
    status: str
    steps: list[dict]
    created_at: str


class AgentService:
    """Manages agent plans and step execution with permission enforcement."""

    _plans: dict[str, ExecutionPlan] = {}

    def create_plan(
        self,
        query: str,
        task_id: str,
        allowed_tools: list[str] | None = None,
        user_id: str = "",
        identity: str = "",
        role: str = "",
    ) -> ExecutionPlan:
        plan = agent_planner.create_plan(query, task_id, allowed_tools, user_id, identity, role)
        self._plans[plan.plan_id] = plan
        return plan

    def get_plan(self, plan_id: str) -> ExecutionPlan | None:
        return self._plans.get(plan_id)

    def approve_step(
        self,
        plan_id: str,
        step_id: str,
        user_id: str = "",
        identity: str = "",
        role: str = "",
    ) -> PlanStep:
        plan = self._plans.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")
        step = self._find_step(plan, step_id)
        if step.status != StepStatus.PENDING:
            raise ValueError(f"Step {step_id} is not in pending status")
        step.status = StepStatus.APPROVED
        audit_service.record(
            event_type="plan_step_approved",
            task_id=plan.task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            detail=f"Step {step.order} ({step.tool_name}) approved",
        )
        return step

    def execute_step(
        self,
        plan_id: str,
        step_id: str,
        user_id: str = "",
        identity: str = "",
        role: str = "",
        input_data: dict | None = None,
    ) -> dict:
        plan = self._plans.get(plan_id)
        if plan is None:
            raise ValueError(f"Plan {plan_id} not found")
        step = self._find_step(plan, step_id)

        if step.requires_approval and step.status != StepStatus.APPROVED:
            raise ValueError(f"Step {step_id} requires approval before execution")

        if step.status not in (StepStatus.PENDING, StepStatus.APPROVED):
            raise ValueError(f"Step {step_id} cannot be executed in status {step.status.value}")

        step.status = StepStatus.EXECUTING
        audit_service.record(
            event_type="plan_step_executing",
            task_id=plan.task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            detail=f"Step {step.order} ({step.tool_name}) executing",
        )

        from app.services.agent.tools.data_analyzer import DataAnalyzerError, analyze

        output = ""
        success = True
        failed = False
        sandbox_meta = ""
        network_meta = ""

        if step.tool_name == "data_analyzer":
            try:
                output = analyze(step.action, input_data or {})
                success = True
            except DataAnalyzerError as exc:
                failed = True
                success = False
                output = f"Tool execution failed: {exc}"
        elif step.tool_name == "code_executor":
            from app.services.sandbox.code_runner import (
                CodeSandboxError,
                run_isolated_python,
            )
            from app.services.sandbox.sandbox import ResourceLimits

            payload = input_data or {}
            code = payload.get("code")
            try:
                if not isinstance(code, str) or not code.strip():
                    raise CodeSandboxError("code is required for code_executor")
                run = run_isolated_python(
                    code,
                    input_data=payload,
                    timeout_s=ResourceLimits().max_execution_time_s,
                    max_output_bytes=ResourceLimits().max_output_bytes,
                )
                sandbox_meta = run.sandbox
                network_meta = run.network
                if run.status == "completed":
                    output = run.output
                    success = True
                else:
                    output = run.output or run.error
                    success = False
                    failed = True
            except CodeSandboxError as exc:
                failed = True
                success = False
                output = f"Tool execution failed: {exc}"
        else:
            output = f"[Simulated] {step.tool_name} completed: {step.action}"
            success = True

        if failed:
            step.status = StepStatus.FAILED
            audit_service.record(
                event_type="plan_step_failed",
                task_id=plan.task_id,
                user_id=user_id,
                identity=identity,
                role=role,
                detail=(
                    f"Step {step.order} ({step.tool_name}) failed: {output[:200]}"
                    + (f"; sandbox={sandbox_meta}" if sandbox_meta else "")
                    + (f"; network={network_meta}" if network_meta else "")
                ),
            )
            return {
                "step_id": step.step_id,
                "tool_name": step.tool_name,
                "action": step.action,
                "output": f"Tool execution failed: {output}" if not output.startswith("Tool execution failed") else output,
                "success": False,
                "sandbox": sandbox_meta,
                "network": network_meta,
            }

        result = {
            "step_id": step.step_id,
            "tool_name": step.tool_name,
            "action": step.action,
            "output": output,
            "success": success,
            "sandbox": sandbox_meta,
            "network": network_meta,
        }

        step.status = StepStatus.COMPLETED
        audit_service.record(
            event_type="plan_step_completed",
            task_id=plan.task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            detail=(
                f"Step {step.order} ({step.tool_name}) completed"
                + (" — real data_analyzer stats produced" if step.tool_name == "data_analyzer" else "")
                + (f" — sandbox={sandbox_meta} network={network_meta}" if step.tool_name == "code_executor" else "")
            ),
        )

        if all(s.status == StepStatus.COMPLETED for s in plan.steps):
            plan.status = PlanStatus.COMPLETED
            audit_service.record(
                event_type="plan_completed",
                task_id=plan.task_id,
                user_id=user_id,
                identity=identity,
                role=role,
                detail=f"Plan {plan.plan_id} completed",
            )

        return result

    def _find_step(self, plan: ExecutionPlan, step_id: str) -> PlanStep:
        for step in plan.steps:
            if step.step_id == step_id:
                return step
        raise ValueError(f"Step {step_id} not found in plan {plan.plan_id}")

    def reset(self) -> None:
        self._plans.clear()


agent_service = AgentService()
