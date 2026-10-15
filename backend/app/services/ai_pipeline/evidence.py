"""Evidence assessment after authorized RAG — enough vs missing information.

Never fabricates: when evidence is insufficient the report states what is
known, what is missing, and why. Partial evidence (chunks returned but not
covering the information need) is reported as insufficient-with-known so
the final model input can combine INTERNAL EVIDENCE + PUBLIC RESEARCH.
Whether external research may proceed is decided separately by the privacy
gateway / security policy.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.services.ai_pipeline.intent import ChatIntent
from app.services.ai_pipeline.resource_planner import ResourcePlan

_STOPWORDS = frozenset({
    "the", "and", "for", "with", "this", "that", "what", "when", "where",
    "why", "how", "from", "into", "about", "should", "would", "could",
    "have", "been", "were", "they", "them", "their", "user", "need",
    "needs", "information", "documents", "matching", "authorized", "source",
    "sources", "question", "relevant", "task", "passport", "context",
    "history", "conversation", "knowledge", "reference", "engineering",
    "title", "purpose", "status",
})


def _significant_words(text: str) -> list[str]:
    return [
        w for w in text.lower().split()
        if len(w) >= 4 and w.strip(".,!?;:'\"") not in _STOPWORDS
    ]


@dataclass(frozen=True)
class EvidenceReport:
    attempted_rag: bool
    enough: bool
    known: list[str]
    missing_information: list[str]
    insufficiency_reason: str
    public_research_could_help: bool
    chunk_count: int
    partial: bool = False

    def to_metadata(self) -> dict:
        return {
            "attempted_rag": self.attempted_rag,
            "enough": self.enough,
            "partial": self.partial,
            "known_count": len(self.known),
            "missing_information": list(self.missing_information),
            "insufficiency_reason": self.insufficiency_reason,
            "public_research_could_help": self.public_research_could_help,
            "chunk_count": self.chunk_count,
        }


def _missing_doc_items(intent: ChatIntent, chunks: list[dict]) -> list[str]:
    """Document-knowledge items of required_information not covered by chunks.

    Passport/conversation context items are supplied by other pipeline
    sections and are not judged against RAG chunks.
    """
    need_words = set(_significant_words(intent.information_need))
    if not need_words:
        return []
    combined = " ".join(str(c.get("text", "")) for c in chunks).lower()
    covered = any(w in combined for w in need_words)

    doc_items = [
        item
        for item in intent.required_information
        if item.startswith("authorized local source documents")
        or item.startswith("engineering reference")
    ]
    if covered:
        return []
    return doc_items


def assess_evidence(
    intent: ChatIntent,
    plan: ResourcePlan,
    chunks: list[dict],
    attempted_rag: bool,
) -> EvidenceReport:
    """Decide whether authorized RAG evidence is sufficient for this turn."""
    known = [
        f"{c.get('source_name', '?')}: {str(c.get('text', ''))[:400]}"
        for c in chunks[:5]
    ]

    if not intent.evidence_required:
        return EvidenceReport(
            attempted_rag=attempted_rag,
            enough=True,
            known=known,
            missing_information=[],
            insufficiency_reason="",
            public_research_could_help=False,
            chunk_count=len(chunks),
        )

    if not chunks:
        if not plan.authorized_sources:
            reason = (
                "No RAG sources are authorized for this Task Passport "
                "(empty allowlist fails closed)."
            )
        elif attempted_rag:
            reason = (
                "Authorized RAG returned no permitted evidence for the "
                "information need."
            )
        else:
            reason = "RAG was not attempted under the current resource plan."
        return EvidenceReport(
            attempted_rag=attempted_rag,
            enough=False,
            known=[],
            missing_information=list(intent.required_information),
            insufficiency_reason=reason,
            public_research_could_help=intent.public_research_useful,
            chunk_count=0,
        )

    missing = _missing_doc_items(intent, chunks)
    if not missing:
        return EvidenceReport(
            attempted_rag=attempted_rag,
            enough=True,
            known=known,
            missing_information=[],
            insufficiency_reason="",
            public_research_could_help=False,
            chunk_count=len(chunks),
        )

    return EvidenceReport(
        attempted_rag=attempted_rag,
        enough=False,
        known=known,
        missing_information=missing,
        insufficiency_reason=(
            "Authorized RAG returned evidence but it does not fully cover "
            "the information need."
        ),
        public_research_could_help=intent.public_research_useful,
        chunk_count=len(chunks),
        partial=True,
    )
