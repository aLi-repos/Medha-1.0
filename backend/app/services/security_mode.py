"""Security Mode Policy Engine — enforces STANDARD/SECURE/SOVEREIGN policies.

This is NOT a frontend toggle. It is a backend-enforced policy that changes
how tasks are processed across all security components.

Do NOT claim this creates a physical air gap. Use wording:
- "Reduced external attack surface"
- "Local-first security policy"
- "Policy-controlled connectivity"
- "Strongest available sovereign policy"
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum

from app.schemas.task import SecurityMode, TaskPassportRead


class PolicyDecision(str, Enum):
    ALLOW = "allow"
    DENY = "deny"
    RESTRICT = "restrict"


@dataclass
class SecurityPolicy:
    """Effective security policy for a task based on its security mode."""
    mode: SecurityMode
    external_network: PolicyDecision
    external_models: PolicyDecision
    local_model: str  # "allow", "required", "preferred"
    rag_policy: str  # "task_authorized", "all", "local_only"
    tool_policy: str  # "strict_allowlist", "passenger_allowlist"
    execution_policy: str  # "controlled", "sandboxed"
    human_approval: str  # "consequential", "all", "none"
    audit_level: str  # "enhanced", "standard"


# Policy definitions per security mode
POLICIES: dict[SecurityMode, SecurityPolicy] = {
    SecurityMode.STANDARD: SecurityPolicy(
        mode=SecurityMode.STANDARD,
        external_network=PolicyDecision.ALLOW,
        external_models=PolicyDecision.ALLOW,
        local_model="allow",
        rag_policy="all",
        tool_policy="passport_allowlist",
        execution_policy="controlled",
        human_approval="none",
        audit_level="standard",
    ),
    SecurityMode.SECURE: SecurityPolicy(
        mode=SecurityMode.SECURE,
        external_network=PolicyDecision.RESTRICT,
        external_models=PolicyDecision.RESTRICT,
        local_model="preferred",
        rag_policy="task_authorized",
        tool_policy="strict_allowlist",
        execution_policy="controlled",
        human_approval="consequential",
        audit_level="enhanced",
    ),
    SecurityMode.SOVEREIGN: SecurityPolicy(
        mode=SecurityMode.SOVEREIGN,
        external_network=PolicyDecision.DENY,
        external_models=PolicyDecision.DENY,
        local_model="required",
        rag_policy="local_only",
        tool_policy="strict_allowlist",
        execution_policy="sandboxed",
        human_approval="consequential",
        audit_level="enhanced",
    ),
}


# Known local models (not external API)
LOCAL_MODELS = {"local-qwen2", "local-llama", "local-mistral"}

# Known external models (API-based)
EXTERNAL_MODEL_PREFIXES = ("api-", "openai-", "claude-", "gpt-")


class SecurityModeEngine:
    """Evaluates security mode policies for authorization decisions."""

    def get_policy(self, mode: SecurityMode) -> SecurityPolicy:
        return POLICIES[mode]

    def get_policy_for_passport(self, passport: TaskPassportRead) -> SecurityPolicy:
        return POLICIES[passport.security_mode]

    def is_external_model(self, model_name: str) -> bool:
        return any(model_name.startswith(p) for p in EXTERNAL_MODEL_PREFIXES)

    def is_local_model(self, model_name: str) -> bool:
        return model_name in LOCAL_MODELS or not self.is_external_model(model_name)

    def check_model_allowed(
        self,
        model_name: str,
        mode: SecurityMode,
    ) -> tuple[PolicyDecision, str]:
        """Check if a model is allowed under the given security mode."""
        policy = POLICIES[mode]

        if self.is_external_model(model_name):
            if policy.external_models == PolicyDecision.DENY:
                return (
                    PolicyDecision.DENY,
                    f"External model '{model_name}' is denied by "
                    f"{mode.value} security mode. "
                    f"Local-first security policy restricts external AI services.",
                )
            if policy.external_models == PolicyDecision.RESTRICT:
                return (
                    PolicyDecision.RESTRICT,
                    f"External model '{model_name}' is restricted by "
                    f"{mode.value} security mode. "
                    f"Local model is preferred.",
                )
        else:
            if policy.local_model == "required":
                return (
                    PolicyDecision.ALLOW,
                    f"Local model '{model_name}' is required and allowed "
                    f"by {mode.value} security mode.",
                )

        return (
            PolicyDecision.ALLOW,
            f"Model '{model_name}' is allowed by {mode.value} security mode.",
        )

    def check_network_allowed(
        self,
        mode: SecurityMode,
        target: str = "external",
    ) -> tuple[PolicyDecision, str]:
        """Check if network access is allowed under the given security mode."""
        policy = POLICIES[mode]

        if target == "external":
            if policy.external_network == PolicyDecision.DENY:
                return (
                    PolicyDecision.DENY,
                    f"External network communication is denied by "
                    f"{mode.value} security mode. "
                    f"Reduced external attack surface.",
                )
            if policy.external_network == PolicyDecision.RESTRICT:
                return (
                    PolicyDecision.RESTRICT,
                    f"External network communication is restricted by "
                    f"{mode.value} security mode. "
                    f"Policy-controlled connectivity.",
                )

        return (
            PolicyDecision.ALLOW,
            f"Network access to '{target}' is allowed by {mode.value} security mode.",
        )

    def check_tool_allowed(
        self,
        tool_name: str,
        allowed_tools: list[str],
        mode: SecurityMode,
    ) -> tuple[PolicyDecision, str]:
        """Check if a tool is allowed under the given security mode."""
        policy = POLICIES[mode]

        # In SOVEREIGN/SECURE mode with strict allowlist, fail-closed
        if policy.tool_policy == "strict_allowlist":
            if not allowed_tools:
                return (
                    PolicyDecision.DENY,
                    f"Tool '{tool_name}' is denied: {mode.value} mode requires "
                    f"explicit tool authorization. Empty allowlist means no tools permitted.",
                )
            if tool_name not in allowed_tools:
                return (
                    PolicyDecision.DENY,
                    f"Tool '{tool_name}' is not in the strict allowlist "
                    f"for {mode.value} security mode. "
                    f"Allowed: {allowed_tools}",
                )

        return (
            PolicyDecision.ALLOW,
            f"Tool '{tool_name}' is allowed by {mode.value} security mode.",
        )

    def check_rag_allowed(
        self,
        source_name: str,
        allowed_sources: list[str],
        mode: SecurityMode,
    ) -> tuple[PolicyDecision, str]:
        """Check if a RAG source is allowed under the given security mode."""
        policy = POLICIES[mode]

        if policy.rag_policy == "local_only":
            # In SOVEREIGN mode, only task-authorized/local sources
            if allowed_sources and source_name not in allowed_sources:
                return (
                    PolicyDecision.DENY,
                    f"RAG source '{source_name}' is denied by {mode.value} mode. "
                    f"Only task-authorized local sources are permitted.",
                )
            if not allowed_sources and source_name.startswith("external-"):
                return (
                    PolicyDecision.DENY,
                    f"External RAG source '{source_name}' is denied by "
                    f"{mode.value} mode. Local-first security policy.",
                )

        if policy.rag_policy == "task_authorized":
            if allowed_sources and source_name not in allowed_sources:
                return (
                    PolicyDecision.DENY,
                    f"RAG source '{source_name}' is not in task-authorized "
                    f"sources for {mode.value} mode.",
                )

        return (
            PolicyDecision.ALLOW,
            f"RAG source '{source_name}' is allowed by {mode.value} security mode.",
        )

    def get_mode_display(self, mode: SecurityMode) -> dict:
        """Return display properties for the security mode indicator."""
        displays = {
            SecurityMode.STANDARD: {
                "icon": "◯",
                "label": "Standard",
                "color": "#6b7280",
                "glow": False,
                "description": "Normal task-scoped policy",
            },
            SecurityMode.SECURE: {
                "icon": "🔐",
                "label": "SECURE",
                "color": "#3b82f6",
                "glow": False,
                "description": "Enhanced security with restricted external access",
            },
            SecurityMode.SOVEREIGN: {
                "icon": "🛡",
                "label": "SOVEREIGN",
                "color": "#10b981",
                "glow": True,
                "description": "Strongest available sovereign policy. "
                "Reduced external attack surface.",
            },
        }
        return displays[mode]

    def get_status_panel_data(self, passport: TaskPassportRead) -> dict:
        """Return data for the security status panel."""
        policy = self.get_policy_for_passport(passport)
        display = self.get_mode_display(passport.security_mode)

        return {
            "mode": passport.security_mode.value,
            "display": display,
            "task_title": passport.title,
            "sensitivity": passport.sensitivity.value,
            "external_network": {
                "status": policy.external_network.value,
                "label": "BLOCKED" if policy.external_network == PolicyDecision.DENY
                    else "RESTRICTED" if policy.external_network == PolicyDecision.RESTRICT
                    else "ALLOWED",
                "color": "#ef4444" if policy.external_network == PolicyDecision.DENY
                    else "#f59e0b" if policy.external_network == PolicyDecision.RESTRICT
                    else "#10b981",
            },
            "external_models": {
                "status": policy.external_models.value,
                "label": "BLOCKED" if policy.external_models == PolicyDecision.DENY
                    else "RESTRICTED" if policy.external_models == PolicyDecision.RESTRICT
                    else "ALLOWED",
                "color": "#ef4444" if policy.external_models == PolicyDecision.DENY
                    else "#f59e0b" if policy.external_models == PolicyDecision.RESTRICT
                    else "#10b981",
            },
            "local_model": {
                "status": policy.local_model,
                "label": policy.local_model.upper(),
                "color": "#10b981" if policy.local_model in ("required", "preferred") else "#6b7280",
            },
            "rag_policy": {
                "status": policy.rag_policy,
                "label": policy.rag_policy.replace("_", " ").upper(),
                "color": "#10b981",
            },
            "tool_policy": {
                "status": policy.tool_policy,
                "label": "STRICT ALLOWLIST" if policy.tool_policy == "strict_allowlist" else "PASSPORT ALLOWLIST",
                "color": "#10b981",
            },
            "execution_policy": {
                "status": policy.execution_policy,
                "label": policy.execution_policy.upper(),
                "color": "#10b981",
            },
            "human_approval": {
                "status": policy.human_approval,
                "label": "REQUIRED" if policy.human_approval in ("consequential", "all") else "NONE",
                "color": "#10b981" if policy.human_approval != "none" else "#6b7280",
            },
            "audit_level": {
                "status": policy.audit_level,
                "label": policy.audit_level.upper(),
                "color": "#10b981",
            },
            "policy_version": passport.security_policy_version,
        }


security_mode_engine = SecurityModeEngine()
