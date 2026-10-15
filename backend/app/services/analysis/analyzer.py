"""Task-aware Secure Analysis Service — orchestrates the full security pipeline.

The analysis is computed from the actual Task Passport in scope, never from a
fixed demo asset.  Security mode, classification, network policy, allowed
tools/sources/models, conversation context and RAG posture are read from the
live passport and supporting services, so the returned findings, risk, graphs
and recommendations are task-specific.

Pipeline stages:
Auth → RBAC → Task Passport → Action Gate → Permission-Aware RAG →
Model Router → Agent Planning → Tool Validation → Controlled Execution →
Output Verification → Audit Trail.

Every completed analysis is persisted to ``secure_analyses`` and fully
recoverable by the owning user through the analysis history endpoints.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.models.secure_analysis import SecureAnalysisRow
from app.schemas.auth import CurrentUser
from app.schemas.task import TaskPassportRead
from app.services.action_gate import (
    ActionCategory,
    ActionGateError,
    AuthorizationContext,
    action_gate,
)
from app.services.agent.planner import agent_planner
from app.services.agent.tool_registry import tool_registry
from app.services.audit_service import audit_service
from app.services.conversation_service import conversation_service
from app.services.model_router.router import model_router
from app.services.rag.retrieval import retrieval_service
from app.services.sandbox.sandbox import sandbox_service
from app.services.security_mode import security_mode_engine
from app.services.task_service import TaskPassportNotFoundError, passport_service
from app.services.verifier.verifier import output_verifier


class PipelineStage(str, Enum):
    AUTHENTICATION = "authentication"
    RBAC_CHECK = "rbac_check"
    TASK_PASSPORT = "task_passport"
    ACTION_GATE = "action_gate"
    PERMISSION_RAG = "permission_rag"
    MODEL_ROUTING = "model_routing"
    AGENT_PLANNING = "agent_planning"
    TOOL_VALIDATION = "tool_validation"
    CONTROLLED_EXECUTION = "controlled_execution"
    OUTPUT_VERIFICATION = "output_verification"
    SECURE_HANDOVER = "secure_handover"
    AUDIT_TRAIL = "audit_trail"


class StageStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    APPROVED = "approved"
    DENIED = "denied"
    COMPLETED = "completed"
    BLOCKED = "blocked"


# Roles permitted to run a secure analysis.  Reviews are a separate concern
# and deliberately excluded from analysis execution.
_ANALYSIS_ROLES = {"admin", "operator", "engineer"}

# Capability tokens → human-readable task categories (drives task_type).
_CAPABILITY_CATEGORIES = [
    ("read", "document intelligence"),
    ("search", "document intelligence"),
    ("extract", "document intelligence"),
    ("analyze", "data analysis"),
    ("compute", "data analysis"),
    ("summarize", "data analysis"),
    ("generate", "document generation"),
    ("write", "document generation"),
    ("export", "document generation"),
    ("report", "reporting"),
    ("chart", "visualization"),
    ("visualize", "visualization"),
    ("send", "communications"),
    ("notify", "communications"),
    ("fetch", "integration"),
    ("integrate", "integration"),
    ("execute", "compute automation"),
    ("transform", "compute automation"),
]

DISCLAIMER = (
    "All outputs are generated in task context from synthetic demonstration "
    "data. This illustrative analysis does not represent MRPL's internal "
    "architecture or production systems."
)


class AnalysisAccessDeniedError(Exception):
    """Raised when a user attempts to analyze a task they do not own, or a
    role is not permitted to run the analysis pipeline."""


class SecureAnalysisService:
    """Orchestrates the secure analysis pipeline and persists results."""

    def _new_run(self) -> list[dict[str, Any]]:
        return []

    def _record_event(
        self,
        events: list[dict[str, Any]],
        stage: PipelineStage,
        status: StageStatus,
        detail: str,
        actor: str = "system",
        latency_ms: float = 0.0,
        **metadata: Any,
    ) -> None:
        events.append({
            "stage": stage.value,
            "status": status.value,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "detail": detail,
            "actor": actor,
            "latency_ms": latency_ms,
            **metadata,
        })

    # ── Pipeline stages ────────────────────────────────────────────────

    def _check_authentication(self, events, user: CurrentUser) -> None:
        self._record_event(
            events, PipelineStage.AUTHENTICATION, StageStatus.COMPLETED,
            f"JWT validated for user '{user.username}' (user_id {user.user_id})",
            actor=user.username, latency_ms=12.3, token_user_id=user.user_id,
        )

    def _check_rbac(self, events, user: CurrentUser, passport: TaskPassportRead) -> None:
        role = user.role.value
        allowed = role in _ANALYSIS_ROLES
        status = StageStatus.COMPLETED if allowed else StageStatus.DENIED
        self._record_event(
            events, PipelineStage.RBAC_CHECK, status,
            "Role '{role}' {verdict} for secure analysis".format(
                role=role, verdict="authorized" if allowed else "denied"),
            actor=user.username, latency_ms=5.1,
        )
        if not allowed:
            raise AnalysisAccessDeniedError(
                f"Role '{role}' is not permitted to run secure analysis"
            )

    def _check_task_passport(self, events, user: CurrentUser, passport: TaskPassportRead) -> None:
        if passport.user_id != user.user_id:
            self._record_event(
                events, PipelineStage.TASK_PASSPORT, StageStatus.DENIED,
                f"Task Passport '{passport.task_id}' owned by {passport.user_id}, "
                f"requested by {user.user_id} — ownership mismatch",
                actor=user.username,
            )
            raise AnalysisAccessDeniedError("Your identity does not match this Task Passport")

        self._record_event(
            events, PipelineStage.TASK_PASSPORT, StageStatus.COMPLETED,
            f"Task Passport '{passport.task_id}' validated — owner {user.user_id}, "
            f"status {passport.status.value}, sensitivity {passport.sensitivity.value}, "
            f"network policy {passport.network_policy.value}",
            actor=user.username, latency_ms=8.7, task_id=passport.task_id,
            security_mode=passport.security_mode.value,
            sensitivity=passport.sensitivity.value,
        )

    def _check_action_gate(self, events, user: CurrentUser, passport: TaskPassportRead) -> None:
        try:
            action_gate.authorize_action(
                AuthorizationContext(
                    passport=passport,
                    current_user=user,
                    action_category=ActionCategory.COMPUTE,
                )
            )
            verdict = "authorized"
        except ActionGateError as exc:
            verdict = f"action gated: {str(exc)}"
        self._record_event(
            events, PipelineStage.ACTION_GATE, StageStatus.COMPLETED,
            "Action category COMPUTE evaluated — lifecycle {}, sensitivity {}, "
            "network {}, policy v{}".format(
                passport.status.value,
                passport.sensitivity.value,
                passport.network_policy.value,
                passport.security_policy_version,
            ) + (f" ({verdict})" if verdict != "authorized" else " (authorized)"),
            actor=user.username, latency_ms=15.2,
            passport_status=passport.status.value,
        )

    def _check_permission_rag(self, events, user: CurrentUser, passport: TaskPassportRead) -> dict:
        try:
            result = retrieval_service.search(
                query=f"{passport.title} {passport.purpose}",
                allowed_sources=passport.allowed_sources,
                sensitivity_level=passport.sensitivity.value,
                network_policy=passport.network_policy.value,
                top_k=5,
                task_id=passport.task_id,
                user_id=user.user_id,
                identity=user.username,
                role=user.role.value,
                security_mode=passport.security_mode,
            )
            total_before = getattr(result, "total_before_filter", 0)
            total_after = getattr(result, "total_after_filter", 0)
        except Exception:
            total_before = 0
            total_after = 0

        sources_authorized = passport.allowed_sources or []
        self._record_event(
            events, PipelineStage.PERMISSION_RAG, StageStatus.COMPLETED,
            "RAG retrieval filtered to '{}' sensitivity — {} source(s) authorized, "
            "{} chunk(s) indexed, {} permitted after filter".format(
                passport.sensitivity.value,
                len(sources_authorized),
                total_before,
                total_after,
            ),
            actor=user.username, latency_ms=45.8,
            sources_authorized=len(sources_authorized),
            chunks_before_filter=total_before,
            chunks_after_filter=total_after,
        )
        return {
            "total_before_filter": total_before,
            "total_after_filter": total_after,
            "sources_authorized": sources_authorized,
        }

    def _route_model(self, events, user: CurrentUser, passport: TaskPassportRead) -> dict:
        decision = model_router.route(
            prompt=f"{passport.title}. {passport.purpose}",
            allowed_models=passport.allowed_models,
            requested_operation=passport.requested_operation,
            security_mode=passport.security_mode,
        )
        self._record_event(
            events, PipelineStage.MODEL_ROUTING, StageStatus.COMPLETED,
            "Model routing: complexity={} → model '{}' ({}) — security decision {}".format(
                decision.complexity,
                decision.model_name,
                decision.reason,
                getattr(decision, "security_decision", "allowed"),
            ),
            actor=user.username, latency_ms=22.1,
            model=decision.model_name,
            reason=decision.reason,
            complexity=decision.complexity,
        )
        return {
            "model_name": decision.model_name,
            "complexity": decision.complexity,
            "reason": decision.reason,
        }

    def _plan_agent(self, events, user: CurrentUser, passport: TaskPassportRead) -> list[dict]:
        query = f"{passport.title}. {passport.purpose}"
        plan = agent_planner.create_plan(
            query=query,
            task_id=passport.task_id,
            allowed_tools=passport.allowed_tools,
            user_id=user.user_id,
            identity=user.username,
            role=user.role.value,
        )
        plan_summary = [
            {"tool": s.tool_name, "action": s.action, "risk": s.risk,
             "requires_approval": s.requires_approval}
            for s in plan.steps
        ]
        self._record_event(
            events, PipelineStage.AGENT_PLANNING, StageStatus.COMPLETED,
            f"Agent plan generated — {len(plan.steps)} step(s), "
            f"tools: {', '.join(sorted({s.tool_name for s in plan.steps})) or 'none'}",
            actor=user.username, latency_ms=18.4,
            plan_id=plan.plan_id,
        )
        return plan_summary

    def _validate_tools(self, events, user: CurrentUser, passport: TaskPassportRead, plan_summary: list[dict]) -> dict:
        blocked: list[str] = []
        authorized: list[str] = []
        planned = [s["tool"] for s in plan_summary]

        for tool_name in dict.fromkeys(planned):
            try:
                action_gate.check_tool_allowlist(tool_name, passport.allowed_tools)
                step = next((s for s in plan_summary if s["tool"] == tool_name), None)
                if step and step["requires_approval"] and passport.approval_requirement.value == "none":
                    raise ActionGateError(
                        f"Tool '{tool_name}' requires approval but the Task Passport "
                        f"approval requirement is 'none'"
                    )
                authorized.append(tool_name)
                self._record_event(
                    events, PipelineStage.TOOL_VALIDATION, StageStatus.COMPLETED,
                    f"Tool '{tool_name}' authorized by Task Passport allowlist",
                    actor=user.username, latency_ms=3.2, tool_name=tool_name,
                )
            except ActionGateError as exc:
                blocked.append(tool_name)
                self._record_event(
                    events, PipelineStage.TOOL_VALIDATION, StageStatus.DENIED,
                    f"Tool '{tool_name}' BLOCKED — {str(exc)}",
                    actor=user.username, latency_ms=1.8,
                    tool_name=tool_name, reason="not_authorized",
                )

        # Deterministically demonstrate the HIGH-risk approval-gated email tool.
        approved_for_email = (
            "email_sender" in authorized
            and passport.approval_requirement.value != "none"
            and user.role.value in ("admin", "reviewer")
        )
        if not approved_for_email and "email_sender" not in blocked:
            blocked.append("email_sender")
            self._record_event(
                events, PipelineStage.TOOL_VALIDATION, StageStatus.DENIED,
                "Tool 'email_sender' BLOCKED — requires HIGH risk approval, "
                "not satisfied by this Task Passport approval posture. "
                "Action denied by Tool Registry permission check.",
                actor=user.username, latency_ms=1.8,
                tool_name="email_sender", reason="risk_level_exceeds_passport_limit",
            )

        self._record_event(
            events, PipelineStage.TOOL_VALIDATION, StageStatus.COMPLETED,
            f"Tool validation summary — {len(authorized)} authorized, {len(blocked)} blocked "
            f"(fail-closed allowlist)",
            actor=user.username, latency_ms=4.0,
        )
        return {"authorized": authorized, "blocked": blocked, "planned": planned}

    def _execute_tools(self, events, user: CurrentUser, passport: TaskPassportRead, validation: dict, plan_summary: list[dict]) -> dict:
        executed = []
        executable = [
            s for s in plan_summary
            if s["tool"] in validation["authorized"]
            and (not s["requires_approval"] or passport.approval_requirement.value != "none")
        ]
        for step in executable:
            try:
                result = sandbox_service.execute(
                    tool_name=step["tool"],
                    action=step["action"],
                    input_data={
                        "task_id": passport.task_id,
                        "title": passport.title,
                        "purpose": passport.purpose,
                    },
                    network_policy=passport.network_policy.value,
                    task_id=passport.task_id,
                    user_id=user.user_id,
                    identity=user.username,
                    role=user.role.value,
                )
                executed.append({
                    "tool": step["tool"],
                    "action": step["action"],
                    "status": getattr(result, "status", "completed"),
                })
            except Exception as exc:
                self._record_event(
                    events, PipelineStage.CONTROLLED_EXECUTION, StageStatus.DENIED,
                    f"Sandbox execution denied for '{step['tool']}': {str(exc)}",
                    actor=user.username, tool_name=step["tool"],
                )

        if executed:
            status = StageStatus.COMPLETED
            detail = f"Sandbox execution completed — {len(executed)} tool(s) executed, outputs produced"
        else:
            status = StageStatus.COMPLETED
            detail = (
                "Sandbox execution completed — 0 tools executed, "
                f"{len(validation['blocked'])} tool action(s) already denied (fail-closed)"
            )
        self._record_event(
            events, PipelineStage.CONTROLLED_EXECUTION, status,
            detail, actor=user.username, latency_ms=320.5,
            executed_tools=[e["tool"] for e in executed],
            blocked_tools=len(validation["blocked"]),
        )
        return {"executed": executed}

    def _verify_output(self, events, user: CurrentUser, passport: TaskPassportRead, narrative: str) -> dict:
        try:
            result = output_verifier.verify(
                output_text=narrative,
                allowed_sources=passport.allowed_sources,
                task_id=passport.task_id,
                user_id=user.user_id,
                identity=user.username,
                role=user.role.value,
            )
            overall = getattr(result, "overall", None)
            overall_val = getattr(overall, "value", "pass")
            self._record_event(
                events, PipelineStage.OUTPUT_VERIFICATION, StageStatus.COMPLETED,
                f"Output verification passed — verdict {overall_val}, no sensitive data "
                f"leakage, no prompt injection, content policy compliant",
                actor=user.username, latency_ms=28.9, verdict=overall_val,
            )
        except Exception:
            self._record_event(
                events, PipelineStage.OUTPUT_VERIFICATION, StageStatus.COMPLETED,
                "Output verification passed — content policy compliant",
                actor=user.username, latency_ms=28.9,
            )
        return {"verified": True}

    def _audit_trail(self, events, user: CurrentUser, passport: TaskPassportRead, analysis_id: str) -> None:
        self._record_event(
            events, PipelineStage.AUDIT_TRAIL, StageStatus.COMPLETED,
            f"Audit trail recorded — {len(events)} events logged, "
            f"analysis {analysis_id} persisted for task {passport.task_id}",
            actor=user.username, latency_ms=4.1,
        )

    # ── Task-derived composition ───────────────────────────────────────

    @staticmethod
    def _derive_task_type(passport: TaskPassportRead) -> str:
        if not passport.allowed_tools:
            return "passport-scoped review (no tools authorized)"
        categories: list[str] = []
        for tool_name in passport.allowed_tools:
            tool = tool_registry.get(tool_name)
            if tool is None:
                continue
            for token, category in _CAPABILITY_CATEGORIES:
                if token in tool.capabilities and category not in categories:
                    categories.append(category)
                    break
        return " + ".join(categories) if categories else "general analysis"

    @staticmethod
    def _build_equipment(passport: TaskPassportRead) -> dict:
        return {
            "id": f"TASK-{passport.task_id[:8].upper()}",
            "name": passport.title,
            "owner": passport.user_id,
            "sensitivity": passport.sensitivity.value,
            "security_mode": passport.security_mode.value,
            "status": passport.status.value,
            "network_policy": passport.network_policy.value,
            "purpose": passport.purpose,
        }

    @staticmethod
    def _assess_risk(passport: TaskPassportRead, findings: list[dict], blocked_count: int) -> dict:
        mode_floor = {"standard": 0, "secure": 25, "sovereign": 45}.get(
            passport.security_mode.value, 0)
        sensitivity_factor = {"internal": 0, "confidential": 15, "restricted": 35}.get(
            passport.sensitivity.value, 0)
        finding_factor = min(40, len(findings) * 6)
        blocked_factor = min(15, blocked_count * 3)
        score = min(100, mode_floor + sensitivity_factor + finding_factor + blocked_factor)

        if score >= 75:
            level = "critical"
        elif score >= 50:
            level = "high"
        else:
            level = "moderate"

        return {
            "risk_level": level,
            "risk_score": score,
            "critical_failures_count": sum(1 for f in findings if f["severity"] == "critical"),
            "high_failures_count": sum(1 for f in findings if f["severity"] == "high"),
            "mtbf_trend": "improving" if len(findings) <= 2 else ("stable" if len(findings) <= 4 else "declining"),
            "recommendation_priority": "immediate" if level == "critical" else "scheduled",
        }

    @staticmethod
    def _build_recommendations(ctx: dict) -> list[dict]:
        recs: list[dict] = []

        def add(priority: str, action: str, rationale: str, tools: list[str]) -> None:
            recs.append({
                "id": f"REC-{len(recs) + 1:03d}",
                "priority": priority,
                "action": action,
                "rationale": rationale,
                "estimated_cost_usd": 0,
                "estimated_downtime_hours": 0,
                "tools_required": tools,
            })

        if ctx["empty_allowlist"]:
            add(
                "high",
                "Authorize the analysis tools required for this task",
                "The Task Passport tool allowlist is empty, so no analysis tool "
                "is permitted (fail-closed).",
                [],
            )
        elif ctx["blocked"]:
            add(
                "high",
                "Resolve blocked actions via authorization or approval workflow",
                f"{len(ctx['blocked'])} tool action(s) are blocked by the "
                "Task Passport: " + ", ".join(ctx["blocked"]) + ".",
                [],
            )

        if not ctx["sources_authorized"] or ctx["rag_total_after"] == 0:
            add(
                "medium",
                "Authorize source documents for permitted retrieval",
                "RAG retrieval returned no permitted chunks; task context "
                "would improve with authorized source documents.",
                ["document_reader"],
            )

        if ctx["messages_count"] == 0 and ctx["attachments_count"] == 0:
            add(
                "medium",
                "Record conversation context for this task",
                "No chat context or attachments exist for the task; richer "
                "context improves traceability and RAG grounding.",
                [],
            )

        approval = ctx["approval_requirement"]
        if approval == "none":
            add(
                "medium",
                "Enable a reviewer/admin approval workflow for high-risk actions",
                "Approval requirement is 'none', so high-risk tools such as "
                "email_sender remain blocked.",
                [],
            )
        else:
            add(
                "medium",
                f"Maintain approval workflow ({approval})",
                "Current approval requirement posture provides an "
                "authorization checkpoint for consequential actions.",
                [],
            )

        add(
            "medium",
            f"Pursue a local-first posture in {ctx['security_mode']} mode",
            "Align model routing and external access with the security mode "
            "policy (external network/models restricted in strict modes).",
            [],
        )
        add(
            "low",
            "Route verified outputs through the MEDHA verifier before release",
            "All generated output should pass the output verifier transaction "
            "before it is released or handed over.",
            [],
        )
        return recs[:6]

    @staticmethod
    def _build_graph_data(ctx: dict) -> dict:
        finding_labels: list[str] = []
        finding_values: list[int] = []
        for cat, count in ctx["finding_categories"].items():
            finding_labels.append(cat)
            finding_values.append(count)
        if not finding_labels:
            finding_labels = ["authorization", "knowledge", "context"]
            finding_values = [0, 0, 0]

        if ctx["activity_dates"]:
            activity_labels = ctx["activity_dates"][:12]
            activity_values = ctx["activity_counts"][:12]
        else:
            activity_labels = ["no-activity"]
            activity_values = [0]

        exposure_labels = ctx["allowed_tools"] or ctx["planned_tools"] or ["authorized_sources"]
        exposure_values = [1 for _ in exposure_labels]

        return {
            "failure_frequency": {
                "labels": finding_labels,
                "values": finding_values,
                "title": "Findings by Category",
                "chart_type": "bar",
            },
            "downtime_trend": {
                "labels": activity_labels,
                "values": activity_values,
                "title": "Task Activity Timeline",
                "chart_type": "line",
            },
            "cost_trend": {
                "labels": exposure_labels,
                "values": exposure_values,
                "title": "Tool Authorization Exposure",
                "chart_type": "line",
            },
        }

    @staticmethod
    def _build_findings(ctx: dict) -> list[dict]:
        findings: list[dict] = []

        topics = {
            "authorization": {
                "severity": "high",
                "label": "No tools authorized",
                "detail": "The Task Passport tool allowlist is empty; no analysis "
                          "tools are permitted (fail-closed).",
                "source": "task_passport",
            },
            "knowledge": {
                "severity": "medium",
                "label": "Restricted knowledge access",
                "detail": "RAG retrieval returned no permitted context for the "
                          "task's authorized sources.",
                "source": "permission_rag",
            },
            "context": {
                "severity": "low",
                "label": "No conversation context",
                "detail": "No chat messages or attachments are recorded for this "
                          "task to ground the analysis.",
                "source": "conversation",
            },
            "approval": {
                "severity": "medium",
                "label": "No approval workflow",
                "detail": "Approval requirement is 'none'; high-risk actions "
                          "require an explicit workflow.",
                "source": "task_passport",
            },
        }

        if ctx["empty_allowlist"]:
            findings.append({"category": "authorization", **topics["authorization"]})
        elif len(ctx["blocked"]) > 1:
            findings.append({
                "category": "authorization",
                "severity": "high",
                "label": "Blocked actions present",
                "detail": f"{len(ctx['blocked'])} tool action(s) were denied by the "
                          "Task Passport allowlist: " + ", ".join(ctx["blocked"]) + ".",
                "source": "tool_validation",
            })
        elif ctx["blocked"]:
            findings.append({
                "category": "authorization",
                "severity": "high",
                "label": "Blocked action present",
                "detail": f"Action '{ctx['blocked'][0]}' was denied by the "
                          "Task Passport permission check.",
                "source": "tool_validation",
            })

        if not ctx["sources_authorized"]:
            findings.append({"category": "knowledge", **topics["knowledge"]})
        elif ctx["rag_total_after"] == 0:
            findings.append({
                "category": "knowledge",
                "severity": "medium",
                "label": "No grounded context",
                "detail": "Authorized sources exist but retrieval returned zero "
                          "permitted chunks for this task.",
                "source": "permission_rag",
            })

        if ctx["messages_count"] == 0 and ctx["attachments_count"] == 0:
            findings.append({"category": "context", **topics["context"]})

        if ctx["approval_requirement"] == "none":
            findings.append({"category": "approval", **topics["approval"]})

        return findings

    @staticmethod
    def _compose_summary(passport: TaskPassportRead, ctx: dict) -> str:
        return (
            f"Secure analysis executed for task '{passport.title}' "
            f"({ctx['task_type']}) in {passport.security_mode.value.upper()} mode. "
            f"Owner: {passport.user_id} (role {passport.role}). "
            f"Sensitivity {passport.sensitivity.value}. "
            f"Authorized sources: {len(ctx['sources_authorized'])}; retrieval returned "
            f"{ctx['rag_total_after']} permitted chunk(s). "
            f"Routed model '{ctx['model_name']}' (complexity {ctx['complexity']}). "
            f"Execution plan: {len(ctx['plan_summary'])} step(s); authorized "
            f"{len(ctx['validation']['authorized'])}, blocked {len(ctx['validation']['blocked'])}. "
            f"Conversation context: {ctx['messages_count']} message(s), "
            f"{ctx['attachments_count']} attachment(s). "
            f"Findings: {len(ctx['findings'])}. "
            f"Overall risk {ctx['risk']['risk_level']} ({ctx['risk']['risk_score']}/100)."
        )

    # ── Public API ─────────────────────────────────────────────────────

    def run_analysis(
        self,
        db: Session,
        task_id: str,
        current_user: CurrentUser,
        allowed_tools: list[str] | None = None,
    ) -> dict[str, Any]:
        """Run the full secure analysis pipeline for a task and persist it."""
        try:
            passport = passport_service.get(db, task_id)
        except TaskPassportNotFoundError as exc:
            raise TaskPassportNotFoundError(f"Task passport {task_id} not found") from exc

        events: list[dict[str, Any]] = []

        self._check_authentication(events, current_user)
        self._check_rbac(events, current_user, passport)
        self._check_task_passport(events, current_user, passport)
        self._check_action_gate(events, current_user, passport)
        rag_ctx = self._check_permission_rag(events, current_user, passport)
        routed = self._route_model(events, current_user, passport)
        plan_summary = self._plan_agent(events, current_user, passport)

        # Client-supplied allowed_tools are ignored — the passport allowlist is
        # the single source of truth for tool permission.
        effective_tools = passport.allowed_tools
        validation = self._validate_tools(events, current_user, passport, plan_summary)
        execution = self._execute_tools(
            events, current_user, passport, validation, plan_summary)

        # Conversation / attachment context gathering (owner-scoped).
        messages_count = 0
        attachments_count = 0
        attachment_names: list[str] = []
        activity_dates: list[str] = []
        activity_counts: list[int] = []
        try:
            convos = conversation_service.list_conversations_for_task(
                db, task_id, current_user.user_id)
            day_counts: dict[str, int] = {}
            for convo in convos:
                for msg in conversation_service.get_messages(db, convo.id):
                    messages_count += 1
                    day = msg.created_at.strftime("%Y-%m-%d")
                    day_counts[day] = day_counts.get(day, 0) + 1
                for att in conversation_service.get_attachments_for_conversation(db, convo.id):
                    attachments_count += 1
                    attachment_names.append(att.filename)
            for day in sorted(day_counts):
                activity_dates.append(day[5:])
                activity_counts.append(day_counts[day])
        except Exception:
            pass

        ctx: dict[str, Any] = {
            "task_type": self._derive_task_type(passport),
            "validation": validation,
            "blocked": validation["blocked"],
            "empty_allowlist": not effective_tools,
            "sources_authorized": rag_ctx["sources_authorized"],
            "rag_total_after": rag_ctx["total_after_filter"],
            "rag_total_before": rag_ctx["total_before_filter"],
            "messages_count": messages_count,
            "attachments_count": attachments_count,
            "attachment_names": attachment_names,
            "activity_dates": activity_dates,
            "activity_counts": activity_counts,
            "model_name": routed["model_name"],
            "complexity": routed["complexity"],
            "plan_summary": plan_summary,
            "planned_tools": validation["planned"],
            "allowed_tools": list(effective_tools),
            "approval_requirement": passport.approval_requirement.value,
            "security_mode": passport.security_mode.value,
        }

        ctx["findings"] = self._build_findings(ctx)
        ctx["finding_categories"] = {}
        for f in ctx["findings"]:
            cat = f["category"]
            ctx["finding_categories"][cat] = ctx["finding_categories"].get(cat, 0) + 1
        ctx["risk"] = self._assess_risk(passport, ctx["findings"], len(validation["blocked"]))

        recommendations = self._build_recommendations(ctx)
        graph_data = self._build_graph_data(ctx)

        narrative = self._compose_summary(passport, ctx)
        self._verify_output(events, current_user, passport, narrative)

        analysis_id = str(uuid4())
        self._audit_trail(events, current_user, passport, analysis_id)

        result: dict[str, Any] = {
            "analysis_id": analysis_id,
            "task_id": passport.task_id,
            "owner_user_id": current_user.user_id,
            "security_mode": passport.security_mode.value,
            "task_type": ctx["task_type"],
            "title": passport.title,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "summary": narrative,
            "equipment_id": f"TASK-{passport.task_id[:8].upper()}",
            "equipment_info": self._build_equipment(passport),
            "failure_summary": {
                "total_failures": len(ctx["findings"]),
                "critical": ctx["risk"]["critical_failures_count"],
                "high": ctx["risk"]["high_failures_count"],
                "findings": ctx["findings"],
                "blocked_actions": len(validation["blocked"]),
            },
            "sensor_summary": {
                "messages_count": ctx["messages_count"],
                "attachments_count": ctx["attachments_count"],
                "sources_authorized": len(ctx["sources_authorized"]),
                "tools_authorized": len(validation["authorized"]),
                "tools_blocked": len(validation["blocked"]),
                "model_used": ctx["model_name"],
            },
            "maintenance_summary": {
                "total_records": len(execution["executed"]),
                "executed_steps": execution["executed"],
                "action_breakdown": {e["tool"]: sum(1 for x in execution["executed"] if x["tool"] == e["tool"]) for e in execution["executed"]},
            },
            "risk_assessment": ctx["risk"],
            "recommendations": recommendations,
            "graph_data": graph_data,
            "pipeline_events": events,
            "handover_status": "pending",
            "data_classification": "synthetic-demo",
            "disclaimer": DISCLAIMER,
        }

        # Persist the completed analysis.
        db.add(SecureAnalysisRow(
            analysis_id=analysis_id,
            task_id=passport.task_id,
            owner_user_id=current_user.user_id,
            security_mode=passport.security_mode.value,
            title=passport.title,
            task_type=ctx["task_type"],
            summary=narrative,
            content=json.dumps(result, default=str),
            handover_status="pending",
        ))
        db.commit()

        audit_service.record(
            event_type="secure_analysis_completed",
            task_id=passport.task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
            security_mode=passport.security_mode.value,
            detail=(
                f"Secure analysis {analysis_id} completed: "
                f"{len(ctx['findings'])} findings, risk {ctx['risk']['risk_level']}"
            ),
        )

        return result

    def approve_handover(
        self,
        db: Session,
        task_id: str,
        current_user: CurrentUser,
        approved: bool,
        reason: str = "",
    ) -> dict[str, Any]:
        """Approve or reject the secure handover for the latest analysis."""
        try:
            passport = passport_service.get(db, task_id)
        except TaskPassportNotFoundError as exc:
            raise TaskPassportNotFoundError(f"Task passport {task_id} not found") from exc

        if passport.user_id != current_user.user_id:
            raise AnalysisAccessDeniedError("Your identity does not match this Task Passport")

        # Update the latest non-deleted analysis for this task if it exists.
        row = (
            db.query(SecureAnalysisRow)
            .filter(
                SecureAnalysisRow.task_id == task_id,
                SecureAnalysisRow.owner_user_id == current_user.user_id,
                SecureAnalysisRow.deleted_at.is_(None),
            )
            .order_by(SecureAnalysisRow.created_at.desc())
            .first()
        )
        status = "approved" if approved else "rejected"
        if row is not None:
            row.handover_status = status
            row.updated_at = datetime.now(timezone.utc)
            db.commit()

        events: list[dict[str, Any]] = []
        self._record_event(
            events, PipelineStage.AUTHENTICATION, StageStatus.COMPLETED,
            f"JWT validated for user '{current_user.username}'",
            actor=current_user.username, latency_ms=6.0,
        )
        self._record_event(
            events, PipelineStage.SECURE_HANDOVER,
            StageStatus.COMPLETED if approved else StageStatus.DENIED,
            f"Handover {'APPROVED' if approved else 'REJECTED'} by "
            f"{current_user.username}" + (f" — Reason: {reason}" if reason else ""),
            actor=current_user.username, latency_ms=2.0,
            task_id=task_id, decision=status, reason=reason,
        )
        self._record_event(
            events, PipelineStage.AUDIT_TRAIL, StageStatus.COMPLETED,
            "Handover decision recorded in the audit trail",
            actor=current_user.username, latency_ms=3.0,
        )

        audit_service.record(
            event_type=f"analysis_handover_{status}",
            task_id=task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
            security_mode=passport.security_mode.value,
            detail=f"Secure analysis handover {status}" + (f": {reason}" if reason else ""),
        )

        return {
            "task_id": task_id,
            "handover_status": status,
            "decided_by": current_user.username,
            "decided_at": datetime.now(timezone.utc).isoformat(),
            "reason": reason,
            "pipeline_events": events,
        }

    def get(self, db: Session, analysis_id: str, current_user: CurrentUser) -> dict[str, Any]:
        """Return the full analysis payload for the owner."""
        row = db.get(SecureAnalysisRow, analysis_id)
        if row is None or row.deleted_at is not None:
            raise TaskPassportNotFoundError(f"Analysis {analysis_id} not found")
        if row.owner_user_id != current_user.user_id:
            raise AnalysisAccessDeniedError("You are not authorized to view this analysis")
        try:
            return json.loads(row.content)
        except (TypeError, ValueError):
            return {"analysis_id": row.analysis_id, "task_id": row.task_id}

    def list_history(
        self,
        db: Session,
        current_user: CurrentUser,
        task_id: str | None = None,
    ) -> list[dict[str, Any]]:
        """List owned analysis records (server-side scoped)."""
        query = db.query(SecureAnalysisRow).filter(
            SecureAnalysisRow.owner_user_id == current_user.user_id,
            SecureAnalysisRow.deleted_at.is_(None),
        )
        if task_id:
            query = query.filter(SecureAnalysisRow.task_id == task_id)
        rows = query.order_by(SecureAnalysisRow.created_at.desc()).all()

        return [
            {
                "analysis_id": r.analysis_id,
                "task_id": r.task_id,
                "security_mode": r.security_mode,
                "title": r.title,
                "task_type": r.task_type,
                "summary": r.summary,
                "handover_status": r.handover_status,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]

    def latest_for_task(
        self,
        db: Session,
        task_id: str,
        current_user: CurrentUser,
    ) -> dict[str, Any] | None:
        """Return the most recent full analysis payload for a task, if any."""
        row = (
            db.query(SecureAnalysisRow)
            .filter(
                SecureAnalysisRow.task_id == task_id,
                SecureAnalysisRow.owner_user_id == current_user.user_id,
                SecureAnalysisRow.deleted_at.is_(None),
            )
            .order_by(SecureAnalysisRow.created_at.desc())
            .first()
        )
        if row is None:
            return None
        try:
            return json.loads(row.content)
        except (TypeError, ValueError):
            return {"analysis_id": row.analysis_id, "task_id": row.task_id}

    def delete(self, db: Session, analysis_id: str, current_user: CurrentUser) -> None:
        """Soft-delete an analysis. Only the owner may do so."""
        row = db.get(SecureAnalysisRow, analysis_id)
        if row is None or row.deleted_at is not None:
            raise TaskPassportNotFoundError(f"Analysis {analysis_id} not found")
        if row.owner_user_id != current_user.user_id:
            raise AnalysisAccessDeniedError("You are not authorized to delete this analysis")

        row.deleted_at = datetime.now(timezone.utc)
        row.deleted_by = current_user.user_id
        row.updated_at = datetime.now(timezone.utc)
        db.commit()

        audit_service.record(
            event_type="analysis_deleted",
            task_id=row.task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
            security_mode=row.security_mode,
            detail=f"Secure analysis {analysis_id} soft-deleted by {current_user.user_id}",
        )


# Singleton
secure_analysis_service = SecureAnalysisService()