"""Deterministic backend task-relevance detection for AI Chat.

Produces a structured internal result used by the chat pipeline BEFORE any
RAG, external research, or local-model answering:

    {relevant, information_need, reason}

The decision is made server-side from authoritative Task Passport fields
(title, purpose, requested_operation) plus conversation context — never
from free-form LLM output. Any LLM intent classification remains advisory;
this gate is the enforcement point.

User-facing refusal (sovereign mode only) is decided by the chat route
from this result; internal reasons here are for audit/diagnostics.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.task import TaskPassportRead

# Clearly off-topic markers for a task-scoped industrial assistant.
_OFF_TOPIC_MARKERS = (
    "weather", "forecast", "joke", "funny", "recipe", "bake a",
    "football", "soccer", "cricket", "basketball", "horoscope",
    "dating", "lyrics", "stock market", "cryptocurrency", "bitcoin",
    "celebrity", "video game", "box office", "lottery",
)

# Phrases that explicitly reference the active task context.
_TASK_REFERENCE_MARKERS = (
    "this task", "the task", "current task", "this project",
    "status", "progress", "current status", "task update",
)

_GREETING_WORDS = frozenset({
    "hi", "hello", "hey", "thanks", "thank", "ok", "okay", "bye",
    "goodbye", "good", "morning", "afternoon", "evening",
})

_STOPWORDS = frozenset({
    "the", "and", "for", "with", "this", "that", "what", "when", "where",
    "why", "how", "from", "into", "about", "should", "would", "could",
    "have", "been", "were", "they", "them", "their", "you", "your", "are",
    "was", "will", "can", "not", "but", "any", "all", "our", "out", "get",
    "got", "does", "did", "tell", "give", "make", "made", "just", "like",
    "over", "here", "there", "then", "than", "also", "only", "very",
    "purpose", "task", "please", "want", "need", "would", "could",
})


def _significant_tokens(text: str) -> set[str]:
    tokens = set()
    for raw in text.lower().split():
        word = raw.strip(".,!?;:'\"()[]")
        if len(word) >= 3 and word not in _STOPWORDS:
            tokens.add(word)
    return tokens


@dataclass(frozen=True)
class TaskRelevance:
    """Structured internal relevance result (audit/diagnostic safe)."""

    relevant: bool
    information_need: str
    reason: str

    def to_metadata(self) -> dict:
        return {
            "relevant": self.relevant,
            "information_need": self.information_need,
            "reason": self.reason,
        }


def check_task_relevance(
    user_prompt: str,
    passport: TaskPassportRead,
    prior_messages,
) -> TaskRelevance:
    """Decide whether the user message is relevant to the current task.

    Deterministic, backend-side, Task-Passport-driven. Defaults to relevant
    when no off-topic signal exists (avoids false refusals), but clearly
    off-topic questions with no task-field alignment are marked irrelevant.
    """
    text = user_prompt.strip()
    lowered = f" {text.lower()} "

    task_blob = (
        f"{passport.title} {passport.purpose} {passport.requested_operation}"
    )
    prompt_tokens = _significant_tokens(text)
    task_tokens = _significant_tokens(task_blob)
    overlap = prompt_tokens & task_tokens

    off_topic = any(marker in lowered for marker in _OFF_TOPIC_MARKERS)

    if off_topic and not overlap:
        return TaskRelevance(
            relevant=False,
            information_need=text,
            reason="off-topic markers with no task-field alignment",
        )

    if overlap:
        preview = ", ".join(sorted(overlap)[:4])
        return TaskRelevance(
            relevant=True,
            information_need=text,
            reason=f"aligned with task fields (matched: {preview})",
        )

    if any(marker in lowered for marker in _TASK_REFERENCE_MARKERS):
        return TaskRelevance(
            relevant=True,
            information_need=text,
            reason="references the active task context",
        )

    words = lowered.split()
    if words and any(w in _GREETING_WORDS for w in words[:2]):
        return TaskRelevance(
            relevant=True,
            information_need=text,
            reason="conversational turn within the task",
        )

    if prior_messages:
        return TaskRelevance(
            relevant=True,
            information_need=text,
            reason="continues an existing task conversation",
        )

    return TaskRelevance(
        relevant=True,
        information_need=text,
        reason="no off-topic indicators; defaulting to task-relevant",
    )


# High-risk answer domains: safety, process integrity, mission, data ownership.
_HIGH_RISK_MARKERS = (
    "safety", "safe to", "process integrity", "mission critical",
    "mission", "data ownership", "confidential", "shutdown", "emergency",
    "hazard", "regulatory", "compliance", "injury", "personnel",
    "critical failure", "release authorization", "air gap",
    "sovereign data", "chain of custody",
)

_VAGUE_REFERENCE_RE = re.compile(
    r"\b(?:is|are|was|were|will|can|should|do|does)\s+"
    r"(?:it|this|that|they)\b",
    re.IGNORECASE,
)

_CONCRETE_OBJECTS = (
    "pump", "motor", "valve", "bearing", "sensor", "line", "system",
    "equipment", "process", "unit", "compressor", "turbine", "vibration",
    "temperature", "pressure", "flow", "task", "status", "report",
    "handbook", "document", "source", "pipeline", "reactor", "boiler",
)

_LIMITS_RE = re.compile(
    r"\b(?:within limits?|too high|too low|acceptable|okay|ok|normal|fine)\b",
    re.IGNORECASE,
)

_CONTRADICTORY_PAIRS = (
    ("increase", "decrease"),
    ("increase", "reduce"),
    ("maximize", "minimize"),
    ("raise", "lower"),
    ("speed up", "slow down"),
    ("faster", "slower"),
)


def classify_response_risk(user_prompt: str) -> str:
    """Return 'high' for safety/process/mission/data-ownership asks, else 'standard'."""
    lowered = user_prompt.lower()
    if any(marker in lowered for marker in _HIGH_RISK_MARKERS):
        return "high"
    return "standard"


def detect_prompt_ambiguity(user_prompt: str) -> list[str]:
    """Return missing aspects that force a clarification reply.

    Conservative heuristics: vague pronoun without a named object, a limit
    judgment with no measurable value, or contradictory direction words.
    """
    text = user_prompt.strip()
    lowered = text.lower()
    missing: list[str] = []

    if _VAGUE_REFERENCE_RE.search(lowered) and not any(
        obj in lowered for obj in _CONCRETE_OBJECTS
    ):
        missing.append("equipment or process affected")

    if _LIMITS_RE.search(lowered) and not re.search(r"\d", text):
        missing.append("measurable")

    for left, right in _CONTRADICTORY_PAIRS:
        if left in lowered and right in lowered:
            missing.append("desired outcome (contradictory requirements)")
            break

    return missing
