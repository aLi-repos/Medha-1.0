"""Privacy gateway for external public research.

Local MEDHA runtime decides whether external research is permitted by
policy, then derives a sanitized PUBLIC research query locally. Only the
sanitized query may leave MEDHA. The gateway never forwards task context,
task IDs, user IDs, private measurements, file contents, equipment
identifiers, conversation, or confidential intention to any provider.

If a safe public query cannot be confidently generated, the request is
BLOCKED ("external research blocked because a safe public query could not
be generated") and nothing is sent.

No production search provider is configured by default — the default
provider is Unavailable, so production external research is NOT claimed
to work. A deterministic test provider exists for behavioral tests only.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.schemas.task import NetworkPolicy, SecurityMode, TaskPassportRead
from app.services.ai_pipeline.intent import ChatIntent
from app.services.audit_service import audit_service
from app.services.security_mode import PolicyDecision, security_mode_engine

# ── Forbidden content patterns (must never leave MEDHA) ──────────────────

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_USER_ID_RE = re.compile(r"\bUSR-[A-Za-z0-9]+\b|\b[A-Z]{2}\d{5,}\b")
_EQUIPMENT_ID_RE = re.compile(r"\b[A-Za-z]{1,4}-\d{2,4}\b")
_MEASUREMENT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*(?:mm/s|mm|cm|°C|°F|bar|psi|rpm|kWh|kPa|MPa|m/s|%)\b",
    re.IGNORECASE,
)
_FIRST_PERSON_RE = re.compile(
    r"\b(our|ours|we|us|our's|my|mine|i|the plant|in-house|internally)\b",
    re.IGNORECASE,
)
_ORG_RE = re.compile(r"\bMRPL\b")
_TASK_ID_FIELD_RE = re.compile(r"\btask_id\b", re.IGNORECASE)
_USER_ID_FIELD_RE = re.compile(r"\buser_id\b", re.IGNORECASE)

_MIN_QUERY_CHARS = 12
_MAX_QUERY_CHARS = 400


def _find_forbidden(text: str) -> list[str]:
    """Return labels of forbidden content still present in text."""
    found: list[str] = []
    if _UUID_RE.search(text):
        found.append("uuid")
    if _USER_ID_RE.search(text):
        found.append("user_id")
    if _EQUIPMENT_ID_RE.search(text):
        found.append("equipment_id")
    if _MEASUREMENT_RE.search(text):
        found.append("measurement")
    if _ORG_RE.search(text):
        found.append("organization")
    if _TASK_ID_FIELD_RE.search(text):
        found.append("task_id_field")
    if _USER_ID_FIELD_RE.search(text):
        found.append("user_id_field")
    return found


def _scrub(text: str) -> tuple[str, list[str]]:
    """Remove private tokens from candidate public query text."""
    removed: list[str] = []
    out = text
    for pattern, label in (
        (_UUID_RE, "uuid"),
        (_USER_ID_RE, "user_id"),
        (_EQUIPMENT_ID_RE, "equipment_id"),
        (_MEASUREMENT_RE, "measurement"),
        (_ORG_RE, "organization"),
        (_TASK_ID_FIELD_RE, "task_id_field"),
        (_USER_ID_FIELD_RE, "user_id_field"),
        (_FIRST_PERSON_RE, "first_person"),
    ):
        out, n = pattern.subn(" ", out)
        if n:
            removed.append(f"{label}x{n}")
    out = re.sub(r"\s+", " ", out).strip(" .,:;-")
    return out, removed


@dataclass(frozen=True)
class SanitizationResult:
    safe: bool
    query: str
    reason: str
    removed_tokens: list[str] = field(default_factory=list)


def sanitize_research_query(
    intent: ChatIntent,
    passport: TaskPassportRead,
) -> SanitizationResult:
    """Derive a public research query locally. Fail closed if unsafe.

    Inputs are the intent information need and passport purpose (never
    task_id/user_id values — they are structurally excluded and also
    scrubbed defensively).
    """
    candidate = f"{intent.information_need} {passport.purpose}"

    # Defensive: never allow identity fields even if they appear in text.
    candidate = candidate.replace(passport.task_id, " ")
    candidate = candidate.replace(passport.user_id, " ")

    query, removed = _scrub(candidate)

    if len(query) < _MIN_QUERY_CHARS or not re.search(r"[A-Za-z]{3,}", query):
        return SanitizationResult(
            safe=False,
            query="",
            reason=(
                "external research blocked because a safe public query "
                "could not be generated"
            ),
            removed_tokens=removed,
        )

    residual = _find_forbidden(query)
    if residual:
        return SanitizationResult(
            safe=False,
            query="",
            reason=(
                "external research blocked because a safe public query "
                f"could not be generated (residual private tokens: "
                f"{', '.join(residual)})"
            ),
            removed_tokens=removed,
        )

    if len(query) > _MAX_QUERY_CHARS:
        query = query[:_MAX_QUERY_CHARS].rsplit(" ", 1)[0]

    return SanitizationResult(
        safe=True, query=query, reason="sanitized public query generated",
        removed_tokens=removed,
    )


def decide_external_research(passport: TaskPassportRead) -> tuple[bool, str]:
    """Explicit external-research policy decision from existing engines.

    Passport network_policy is authoritative for egress. Sovereign mode is
    NOT an automatic refusal of all public verification: when the passport
    permits egress (allow_internal), sanitized public research may run under
    policy control (task-bound + privacy-preserving). deny_external always
    denies. Standard/secure decisions are unchanged.
    """
    if passport.network_policy == NetworkPolicy.DENY_EXTERNAL:
        return (
            False,
            "Task Passport network policy 'deny_external' blocks external "
            "research for this task.",
        )

    mode_decision, mode_reason = security_mode_engine.check_network_allowed(
        passport.security_mode, "external"
    )

    if passport.security_mode == SecurityMode.SOVEREIGN:
        # Policy-controlled external verification: sanitized public query
        # only; never task context, identity, or private content.
        return True, (
            "Sovereign mode: policy-controlled public research permitted "
            "with sanitized query only (reduced external attack surface). "
            f"{mode_reason}"
        )

    if mode_decision == PolicyDecision.DENY:
        return False, mode_reason

    if mode_decision == PolicyDecision.RESTRICT:
        return True, f"Restricted public research permitted: {mode_reason}"

    return True, mode_reason


# ── Provider interface ───────────────────────────────────────────────────


class PublicSearchProvider(ABC):
    """External public search provider — receives ONLY sanitized queries."""

    name: str = "abstract"

    @abstractmethod
    def search(self, sanitized_query: str) -> list[dict]:
        """Return public results: [{title, url, snippet}, ...]."""


class UnavailablePublicSearchProvider(PublicSearchProvider):
    """Default production provider: no external search is configured."""

    name = "unavailable"

    def search(self, sanitized_query: str) -> list[dict]:
        raise RuntimeError(
            "No external public search provider is configured in this "
            "MEDHA environment."
        )


class DeterministicTestSearchProvider(PublicSearchProvider):
    """Deterministic provider for behavioral tests only — not production."""

    name = "deterministic-test"

    def __init__(self) -> None:
        self.received_queries: list[str] = []

    def search(self, sanitized_query: str) -> list[dict]:
        self.received_queries.append(sanitized_query)
        return [
            {
                "title": "Public industry study: bearing failure vibration indicators",
                "url": "https://example.org/public/bearing-failure-study",
                "snippet": (
                    "Public reference on vibration and temperature "
                    "indicators for rotating equipment bearing failures."
                ),
            },
            {
                "title": "Public maintenance practices review",
                "url": "https://example.org/public/maintenance-review",
                "snippet": (
                    "Survey of common maintenance practices referenced in "
                    "public engineering literature."
                ),
            },
        ]


@dataclass
class ResearchOutcome:
    status: str  # denied | blocked_unsafe_query | completed | unavailable | failed
    reason: str
    sanitized_query: str
    results: list[dict]
    provider: str
    retrieved_at: str | None = None

    @property
    def completed(self) -> bool:
        return self.status == "completed"


class PrivacyGateway:
    """Boundary between MEDHA and any external public research provider."""

    def __init__(self) -> None:
        self._provider: PublicSearchProvider = UnavailablePublicSearchProvider()

    def set_provider(self, provider: PublicSearchProvider) -> None:
        self._provider = provider

    @property
    def provider(self) -> PublicSearchProvider:
        return self._provider

    def conduct_research(
        self,
        *,
        intent: ChatIntent,
        passport: TaskPassportRead,
        user_id: str,
        identity: str,
        role: str,
        missing_count: int,
    ) -> ResearchOutcome:
        """Full gated flow: policy → sanitize → provider → outcome + audit."""
        base = dict(
            task_id=passport.task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            security_mode=passport.security_mode.value,
        )

        audit_service.record(
            event_type="EXTERNAL_RESEARCH_REQUESTED",
            detail=(
                f"missing_information_items={missing_count} "
                f"mode={passport.security_mode.value} "
                f"network_policy={passport.network_policy.value}"
            ),
            **base,
        )

        allowed, decision_reason = decide_external_research(passport)
        if not allowed:
            audit_service.record(
                event_type="EXTERNAL_RESEARCH_DENIED",
                detail=decision_reason,
                **base,
            )
            return ResearchOutcome(
                status="denied",
                reason=decision_reason,
                sanitized_query="",
                results=[],
                provider=self._provider.name,
            )

        sanitization = sanitize_research_query(intent, passport)
        if not sanitization.safe:
            audit_service.record(
                event_type="EXTERNAL_RESEARCH_DENIED",
                detail=sanitization.reason,
                **base,
            )
            return ResearchOutcome(
                status="blocked_unsafe_query",
                reason=sanitization.reason,
                sanitized_query="",
                results=[],
                provider=self._provider.name,
            )

        audit_service.record(
            event_type="EXTERNAL_RESEARCH_ALLOWED",
            detail=decision_reason,
            **base,
        )
        # Only the sanitized public query is logged/sent — never raw context.
        audit_service.record(
            event_type="EXTERNAL_QUERY_SANITIZED",
            detail=(
                f"query='{sanitization.query}' "
                f"removed={','.join(sanitization.removed_tokens) or 'none'}"
            ),
            **base,
        )

        try:
            results = self._provider.search(sanitization.query)
        except Exception as exc:  # provider unavailable / network failure
            status = (
                "unavailable" if isinstance(exc, RuntimeError) else "failed"
            )
            event = (
                "EXTERNAL_RESEARCH_FAILED"
            )
            audit_service.record(
                event_type=event,
                detail=f"provider={self._provider.name} status={status} error={exc}",
                **base,
            )
            return ResearchOutcome(
                status=status,
                reason=str(exc),
                sanitized_query=sanitization.query,
                results=[],
                provider=self._provider.name,
            )

        retrieved_at = datetime.now(timezone.utc).isoformat()
        audit_service.record(
            event_type="EXTERNAL_RESEARCH_COMPLETED",
            detail=(
                f"provider={self._provider.name} results={len(results)} "
                f"query_chars={len(sanitization.query)}"
            ),
            **base,
        )
        return ResearchOutcome(
            status="completed",
            reason="public research completed",
            sanitized_query=sanitization.query,
            results=results,
            provider=self._provider.name,
            retrieved_at=retrieved_at,
        )


privacy_gateway = PrivacyGateway()
