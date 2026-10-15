"""Sandbox service — code_executor runs in a real isolated child process;
other tools remain lightweight controlled handlers."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from uuid import uuid4

from app.services.audit_service import audit_service
from app.services.sandbox.code_runner import (
    MAX_CODE_BYTES,
    CodeSandboxError,
    run_isolated_python,
)


class ExecutionStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"
    ROLLED_BACK = "rolled_back"


class NetworkPolicy(str, Enum):
    DENY_EXTERNAL = "deny_external"
    ALLOW_INTERNAL = "allow_internal"


@dataclass
class ResourceLimits:
    max_cpu_ms: int = 5000
    max_memory_mb: int = 256
    max_network_calls: int = 0
    max_execution_time_s: float = 10.0
    max_output_bytes: int = 64_000
    max_code_bytes: int = MAX_CODE_BYTES


@dataclass
class ExecutionResult:
    execution_id: str
    tool_name: str
    status: ExecutionStatus
    output: str
    error: str = ""
    cpu_ms: float = 0.0
    memory_mb: float = 0.0
    network_calls: int = 0
    started_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    completed_at: datetime | None = None
    rollback_data: dict = field(default_factory=dict)
    sandbox: str = ""
    network: str = ""


class SandboxService:
    """Simulates a sandboxed tool execution environment."""

    def __init__(self) -> None:
        self._executions: dict[str, ExecutionResult] = {}

    def execute(
        self,
        tool_name: str,
        action: str,
        input_data: dict,
        network_policy: str = "deny_external",
        resource_limits: ResourceLimits | None = None,
        task_id: str = "",
        user_id: str = "",
        identity: str = "",
        role: str = "",
    ) -> ExecutionResult:
        limits = resource_limits or ResourceLimits()
        execution_id = str(uuid4())

        self._validate_network(tool_name, network_policy)

        result = ExecutionResult(
            execution_id=execution_id,
            tool_name=tool_name,
            status=ExecutionStatus.RUNNING,
            output="",
        )
        self._executions[execution_id] = result

        audit_service.record(
            event_type="sandbox_execution_started",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            detail=f"Execution {execution_id}: {tool_name} — {action}",
        )

        start = time.monotonic()
        try:
            if tool_name == "code_executor":
                output = self._execute_code(
                    input_data=input_data,
                    limits=limits,
                    result=result,
                )
            else:
                output = self._simulate_tool_execution(tool_name, action, input_data)
            elapsed_ms = (time.monotonic() - start) * 1000
            result.cpu_ms = elapsed_ms
            result.memory_mb = len(str(input_data).encode()) / (1024 * 1024)

            if result.status in (ExecutionStatus.COMPLETED, ExecutionStatus.TIMEOUT, ExecutionStatus.FAILED):
                pass
            elif elapsed_ms > limits.max_execution_time_s * 1000:
                result.status = ExecutionStatus.TIMEOUT
                result.error = f"Execution exceeded {limits.max_execution_time_s}s limit"
            else:
                result.status = ExecutionStatus.COMPLETED
                result.output = output
        except CodeSandboxError as exc:
            result.status = ExecutionStatus.FAILED
            result.error = str(exc)
        except Exception as exc:
            result.status = ExecutionStatus.FAILED
            result.error = str(exc)

        result.completed_at = datetime.now(timezone.utc)

        audit_service.record(
            event_type="sandbox_execution_completed",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            detail=(
                f"Execution {execution_id}: status={result.status.value}"
                + (f", sandbox={result.sandbox}" if result.sandbox else "")
                + (f", network={result.network}" if result.network else "")
                + (f", error={result.error[:120]}" if result.error else "")
            ),
        )

        return result

    def _execute_code(
        self,
        *,
        input_data: dict,
        limits: ResourceLimits,
        result: ExecutionResult,
    ) -> str:
        """Run user code inside the real isolated subprocess sandbox."""
        payload = input_data or {}
        code = payload.get("code")
        if not isinstance(code, str) or not code.strip():
            raise CodeSandboxError("code is required for code_executor")
        if len(code.encode("utf-8", errors="replace")) > limits.max_code_bytes:
            raise CodeSandboxError(
                f"code exceeds {limits.max_code_bytes} byte limit"
            )

        run = run_isolated_python(
            code,
            input_data=payload,
            timeout_s=limits.max_execution_time_s,
            max_output_bytes=limits.max_output_bytes,
        )
        result.sandbox = run.sandbox
        result.network = run.network
        result.network_calls = 0
        if run.status == "completed":
            result.status = ExecutionStatus.COMPLETED
            result.output = run.output
            result.error = ""
        elif run.status == "timeout":
            result.status = ExecutionStatus.TIMEOUT
            result.output = run.output
            result.error = run.error
        else:
            result.status = ExecutionStatus.FAILED
            result.output = run.output
            result.error = run.error
        return run.output

    def rollback(self, execution_id: str, task_id: str = "", user_id: str = "", identity: str = "", role: str = "") -> ExecutionResult:
        result = self._executions.get(execution_id)
        if result is None:
            raise ValueError(f"Execution {execution_id} not found")
        if result.status != ExecutionStatus.COMPLETED:
            raise ValueError(f"Cannot rollback execution in status {result.status.value}")

        result.status = ExecutionStatus.ROLLED_BACK
        result.completed_at = datetime.now(timezone.utc)

        audit_service.record(
            event_type="sandbox_execution_rolled_back",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            detail=f"Execution {execution_id} rolled back",
        )
        return result

    def get_execution(self, execution_id: str) -> ExecutionResult | None:
        return self._executions.get(execution_id)

    def _validate_network(self, tool_name: str, policy: str) -> None:
        if policy == NetworkPolicy.DENY_EXTERNAL.value:
            if tool_name == "api_caller":
                raise PermissionError(
                    "Network policy 'deny_external' blocks external API calls"
                )

    def _simulate_tool_execution(self, tool_name: str, action: str, input_data: dict) -> str:
        if tool_name == "document_reader":
            return f"[DocumentReader] Read {input_data.get('source_count', 1)} document(s): {action}"
        elif tool_name == "data_analyzer":
            from app.services.agent.tools.data_analyzer import analyze

            return analyze(action, input_data or {})
        elif tool_name == "docx_generator":
            return f"[DocxGenerator] Report generated: {action}"
        elif tool_name == "email_sender":
            return f"[EmailSender] Notification sent: {action}"
        elif tool_name == "code_executor":
            raise CodeSandboxError("code_executor requires sandbox code input")
        else:
            return f"[{tool_name}] Action completed: {action}"

    def reset(self) -> None:
        self._executions.clear()


sandbox_service = SandboxService()
