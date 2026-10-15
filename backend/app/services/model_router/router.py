"""Model routing logic — complexity-based selection with Task Passport
and security mode constraints."""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.task import SecurityMode
from app.services.security_mode import PolicyDecision, security_mode_engine


@dataclass
class RoutingDecision:
    model_name: str
    reason: str
    complexity: str
    security_mode: str = "standard"
    security_decision: str = "allow"
    # Reporting fields: routing category and local execution status.
    category: str = ""
    local_execution: bool = False


class ModelRouter:
    """Decides which model handles a task based on complexity, passport
    constraints, and security mode policy."""

    _COMPLEXITY_KEYWORDS = {
        "low": ["list", "check", "verify", "count", "simple", "basic"],
        "medium": ["analyze", "summarize", "compare", "explain", "review"],
        "high": ["generate", "create", "design", "plan", "complex", "reason", "multi-step"],
    }

    # Intent-aware bias: cheap pipelines for light conversational turns,
    # richer pipelines for analysis-shaped intents. Keywords still win
    # when they signal higher complexity.
    _INTENT_BASELINE = {
        "conversational": "low",
        "status": "low",
        "summarize": "medium",
        "investigation": "medium",
        "comparison": "medium",
        "recommendation": "medium",
    }

    _MODEL_TIERS = {
        "low": "local-qwen2",
        "medium": "local-qwen2",
        "high": "api-openai",
    }

    def classify_complexity(
        self,
        prompt: str,
        requested_operation: str = "",
        intent_category: str = "",
    ) -> str:
        text = f"{prompt} {requested_operation}".lower()
        scores = {"low": 0, "medium": 0, "high": 0}
        for level, keywords in self._COMPLEXITY_KEYWORDS.items():
            for kw in keywords:
                if kw in text:
                    scores[level] += 1
        best = max(scores, key=scores.get)
        keyword_result = best if scores[best] > 0 else ""

        baseline = self._INTENT_BASELINE.get(intent_category, "")
        if not keyword_result:
            return baseline or "medium"
        if not baseline:
            return keyword_result
        order = ["low", "medium", "high"]
        return keyword_result if order.index(keyword_result) >= order.index(baseline) else baseline

    def route(
        self,
        prompt: str,
        allowed_models: list[str] | None = None,
        requested_operation: str = "",
        security_mode: SecurityMode = SecurityMode.STANDARD,
        intent_category: str = "",
    ) -> RoutingDecision:
        complexity = self.classify_complexity(prompt, requested_operation, intent_category)
        preferred = self._MODEL_TIERS[complexity]

        # Apply security mode policy
        policy_decision, policy_reason = security_mode_engine.check_model_allowed(
            preferred, security_mode
        )

        if policy_decision == PolicyDecision.DENY:
            # In SOVEREIGN mode, force local model
            if security_mode == SecurityMode.SOVEREIGN:
                preferred = "local-qwen2"
                reason = (
                    f"Sovereign mode: external model denied. "
                    f"{policy_reason} Using approved local model: {preferred}"
                )
            else:
                reason = policy_reason
        elif policy_decision == PolicyDecision.RESTRICT:
            # In SECURE mode, prefer local but allow external if no local available
            if security_mode == SecurityMode.SECURE:
                preferred = "local-qwen2"
                reason = (
                    f"Secure mode: external model restricted. "
                    f"{policy_reason} Using preferred local model: {preferred}"
                )
            else:
                reason = policy_reason
        else:
            # Apply passport allowed_models constraint
            if allowed_models and preferred not in allowed_models:
                if allowed_models:
                    preferred = allowed_models[0]
                    reason = f"Preferred model not in allowed list; using {preferred}"
                else:
                    reason = f"No allowed models; using {preferred}"
            else:
                reason = f"Complexity={complexity}; selected {preferred}"

        return RoutingDecision(
            model_name=preferred,
            reason=reason,
            complexity=complexity,
            security_mode=security_mode.value,
            security_decision=policy_decision.value,
            category=complexity,
            local_execution=not preferred.startswith(("api-", "openai-", "claude-", "gpt-")),
        )


model_router = ModelRouter()
