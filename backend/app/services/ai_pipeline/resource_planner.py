"""Resource planning for task-aware chat.

After intent classification, decide which authorized resources this turn
may use: conversation context, RAG over the passport allowlist, permitted
tools (informational), and whether public research could be relevant.
All decisions respect task ownership, sensitivity, security mode and
network policy as encoded in the Task Passport.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.task import NetworkPolicy, SecurityMode, TaskPassportRead
from app.services.ai_pipeline.intent import ChatIntent


@dataclass(frozen=True)
class ResourcePlan:
    task_id: str
    use_conversation: bool
    rag_enabled: bool
    rag_query: str
    authorized_sources: list[str]
    authorized_tools: list[str]
    external_research_candidate: bool
    restrictions: list[str]

    def to_metadata(self) -> dict:
        return {
            "task_id": self.task_id,
            "use_conversation": self.use_conversation,
            "rag_enabled": self.rag_enabled,
            "rag_query": self.rag_query,
            "authorized_sources": list(self.authorized_sources),
            "authorized_tools": list(self.authorized_tools),
            "external_research_candidate": self.external_research_candidate,
            "restrictions": list(self.restrictions),
        }


def plan_resources(intent: ChatIntent, passport: TaskPassportRead) -> ResourcePlan:
    """Build the authorized resource plan for one chat turn."""
    authorized_sources = list(passport.allowed_sources)
    authorized_tools = list(passport.allowed_tools)

    restrictions: list[str] = [
        "task ownership enforced (passport.user_id only)",
        "conversation scoped to this task + user",
    ]

    # Fail closed: empty allowlist means NO RAG source is authorized.
    rag_enabled = intent.evidence_required and bool(authorized_sources)
    if intent.evidence_required and not authorized_sources:
        restrictions.append(
            "empty source allowlist fails closed — no RAG retrieval"
        )

    if passport.security_mode == SecurityMode.SOVEREIGN:
        restrictions.append(
            "sovereign mode: external research policy-controlled "
            "(sanitized query only)"
        )
    if passport.network_policy == NetworkPolicy.DENY_EXTERNAL:
        restrictions.append("network policy deny_external: no external egress")

    # RAG query = user's actual information need (already includes any
    # prior-turn subject resolved for follow-ups) + authoritative task
    # context (never merely title + purpose).
    rag_query = (
        f"{intent.information_need} {passport.title} {passport.purpose}"
    ).strip()

    return ResourcePlan(
        task_id=passport.task_id,
        use_conversation=True,
        rag_enabled=rag_enabled,
        rag_query=rag_query,
        authorized_sources=authorized_sources,
        authorized_tools=authorized_tools,
        external_research_candidate=intent.public_research_useful,
        restrictions=restrictions,
    )
