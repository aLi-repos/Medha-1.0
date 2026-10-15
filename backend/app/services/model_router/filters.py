"""Input/output filters — PII redaction, prompt injection detection, output validation."""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass
class FilterResult:
    passed: bool
    cleaned_text: str
    blocked_reason: str = ""


class InputFilter:
    """Validates and cleans prompts before model inference."""

    _PII_PATTERNS = {
        "email": re.compile(r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}"),
        "phone": re.compile(r"\b\d{10,13}\b"),
        "aadhaar": re.compile(r"\b\d{4}\s?\d{4}\s?\d{4}\b"),
        "pan": re.compile(r"\b[A-Z]{5}\d{4}[A-Z]\b"),
    }

    _INJECTION_PATTERNS = [
        re.compile(r"ignore\s+(previous|all|prior)\s+(instructions?|prompts?)", re.IGNORECASE),
        re.compile(r"you\s+are\s+now\s+", re.IGNORECASE),
        re.compile(r"system\s*:\s*", re.IGNORECASE),
        re.compile(r"<\|system\|>", re.IGNORECASE),
        re.compile(r"jailbreak", re.IGNORECASE),
    ]

    def check(self, text: str) -> FilterResult:
        for pattern in self._INJECTION_PATTERNS:
            if pattern.search(text):
                return FilterResult(
                    passed=False,
                    cleaned_text="",
                    blocked_reason="Prompt injection attempt detected",
                )
        cleaned = text
        for pii_type, pattern in self._PII_PATTERNS.items():
            cleaned = pattern.sub(f"[REDACTED_{pii_type.upper()}]", cleaned)
        return FilterResult(passed=True, cleaned_text=cleaned)


class OutputFilter:
    """Validates and cleans model outputs before returning to user."""

    _UNSAFE_PATTERNS = [
        re.compile(r"\b(hack|exploit|bypass)\s+(the\s+)?(system|security|firewall)", re.IGNORECASE),
        re.compile(r"sudo\s+rm\s+-rf", re.IGNORECASE),
        re.compile(r"drop\s+table\s+", re.IGNORECASE),
    ]

    def check(self, text: str) -> FilterResult:
        for pattern in self._UNSAFE_PATTERNS:
            if pattern.search(text):
                return FilterResult(
                    passed=False,
                    cleaned_text="",
                    blocked_reason="Unsafe content detected in model output",
                )
        return FilterResult(passed=True, cleaned_text=text)


input_filter = InputFilter()
output_filter = OutputFilter()
