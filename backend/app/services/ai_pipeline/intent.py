"""Structured intent understanding for task-aware chat.

Produces a machine-readable intent object — never a canned answer. The
classifier is deterministic so it can later be replaced/enriched by a real
local LLM behind the same schema. Only structured decision metadata is
exposed (no chain-of-thought is shown to users).
"""

from __future__ import annotations

from dataclasses import dataclass

from app.schemas.task import TaskPassportRead

_GREETINGS = frozenset({
    "hi", "hello", "hey", "yo", "thanks", "thank you", "thx", "ok", "okay",
    "bye", "goodbye", "good morning", "good afternoon", "good evening", "sup",
})

_INVESTIGATE_MARKERS = (
    "why", "what is causing", "what's causing", "cause", "causes", "causing",
    "diagnos", "investigat", "root cause", "failing", "failure", "abnormal",
    "problem", "issue", "error", "fault", "anomaly", "vibration",
)
_STATUS_MARKERS = ("status", "progress", "update", "when will", "how far", "eta")
_COMPARISON_MARKERS = ("compare", "comparison", "versus", " vs ", "difference")
_RECOMMENDATION_MARKERS = (
    "recommend", "should i", "what should", "next step", "suggest", "propose",
)
_SUMMARY_MARKERS = ("summarize", "summary", "tldr", "recap", "overview")

_QUESTION_STARTS = (
    "why", "what", "when", "where", "who", "how", "which", "should", "can",
    "do", "does", "is", "are", "would", "could", "explain",
)

_FOLLOW_UP_STARTS = (
    "what about", "how about", "and the", "also the", "same", "again",
    "that", "this", "it", "those", "these", "them",
)


@dataclass(frozen=True)
class ChatIntent:
    """Structured internal intent for one chat turn."""

    objective: str
    category: str
    answer_type: str
    required_information: list[str]
    evidence_required: bool
    public_research_useful: bool
    information_need: str
    task_id: str
    conversation_turns: int
    follow_up: bool = False
    referenced_subject: str = ""

    def to_metadata(self) -> dict:
        return {
            "objective": self.objective,
            "category": self.category,
            "answer_type": self.answer_type,
            "required_information": list(self.required_information),
            "evidence_required": self.evidence_required,
            "public_research_useful": self.public_research_useful,
            "information_need": self.information_need,
            "task_id": self.task_id,
            "conversation_turns": self.conversation_turns,
            "follow_up": self.follow_up,
            "referenced_subject": self.referenced_subject,
        }


def _is_conversational(text: str, lowered: str) -> bool:
    stripped = lowered.strip(" .!?")
    if stripped in _GREETINGS:
        return True
    words = stripped.split()
    if len(words) <= 4 and words and words[0] in _GREETINGS:
        return True
    return False


def _is_question(text: str) -> bool:
    stripped = text.strip()
    if "?" in stripped:
        return True
    first = stripped.split(" ", 1)[0].lower().strip(".,!?") if stripped else ""
    return first in _QUESTION_STARTS


def _detect_follow_up(text: str, prior_messages) -> tuple[bool, str]:
    """Detect ellipsis / short references that continue a prior turn.

    Returns (follow_up, referenced_subject). referenced_subject is the
    last user turn's text when a follow-up is detected — used only to
    anchor RAG and continuity, never as a canned answer.
    """
    if not prior_messages:
        return False, ""

    stripped = text.strip()
    words = stripped.split()
    if not words:
        return False, ""

    token = words[0].lower().strip(".,!?")
    lowered = stripped.lower()
    multi_word_hit = any(
        lowered.startswith(m) for m in _FOLLOW_UP_STARTS if " " in m
    )
    single_word_starts = {
        m for m in _FOLLOW_UP_STARTS if " " not in m
    } | {"the", "that", "this", "those", "these", "it", "they", "them"}
    short_reference = token in single_word_starts and len(words) <= 8

    if not (multi_word_hit or short_reference):
        return False, ""

    last_user = ""
    for msg in reversed(list(prior_messages)):
        if getattr(msg, "role", "") == "user":
            last_user = getattr(msg, "content", "") or ""
            break
    return True, last_user


def classify_intent(
    user_prompt: str,
    passport: TaskPassportRead,
    prior_messages,
) -> ChatIntent:
    """Build a structured intent from the user message + authoritative task.

    Classification is marker-based and task-scoped: it decides what kind of
    answer is needed and what information must be gathered. It does NOT
    produce task-specific canned answers.
    """
    text = user_prompt.strip()
    lowered = " " + text.lower() + " "

    conversation_turns = len(prior_messages)
    follow_up, referenced_subject = _detect_follow_up(text, prior_messages)

    if _is_conversational(text, lowered):
        category = "conversational"
        answer_type = "conversational_reply"
    elif any(m in lowered for m in _SUMMARY_MARKERS):
        category = "summarize"
        answer_type = "summary"
    elif any(m in lowered for m in _COMPARISON_MARKERS):
        category = "comparison"
        answer_type = "comparison"
    elif any(m in lowered for m in _RECOMMENDATION_MARKERS):
        category = "recommendation"
        answer_type = "recommendation"
    elif any(m in lowered for m in _STATUS_MARKERS):
        category = "status"
        answer_type = "status_report"
    elif any(m in lowered for m in _INVESTIGATE_MARKERS) or _is_question(text):
        category = "investigation"
        answer_type = "technical_analysis"
    else:
        category = "conversational"
        answer_type = "conversational_reply"

    evidence_required = category != "conversational"

    required_information = [
        "task passport context (title, purpose, status)",
        "authorized conversation history for this task",
        f"user information need: {text}",
    ]
    if follow_up and referenced_subject:
        required_information.append(
            "prior user turn referenced by this follow-up: "
            f"{referenced_subject[:200]}"
        )
    if evidence_required:
        required_information.append(
            "authorized local source documents matching the information need"
        )
    if category in ("investigation", "comparison"):
        required_information.append(
            "engineering reference knowledge relevant to the question"
        )

    public_research_useful = evidence_required

    # Information need for retrieval includes the referenced subject so
    # short follow-ups ("the vibration") resolve against prior context.
    information_need = text
    if follow_up and referenced_subject:
        information_need = f"{text} {referenced_subject}".strip()

    return ChatIntent(
        objective=text,
        category=category,
        answer_type=answer_type,
        required_information=required_information,
        evidence_required=evidence_required,
        public_research_useful=public_research_useful,
        information_need=information_need,
        task_id=passport.task_id,
        conversation_turns=conversation_turns,
        follow_up=follow_up,
        referenced_subject=referenced_subject,
    )
