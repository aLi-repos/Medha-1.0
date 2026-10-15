"""Verifier service — output safety, hallucination detection, and compliance checks."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum

from app.services.audit_service import audit_service


class Verdict(str, Enum):
    PASS = "pass"
    WARN = "warn"
    FAIL = "fail"


@dataclass
class CheckResult:
    check_name: str
    verdict: Verdict
    detail: str


@dataclass
class VerificationResult:
    overall: Verdict
    checks: list[CheckResult]
    summary: str


class OutputVerifier:
    """Verifies AI outputs against safety, hallucination, and compliance criteria."""

    _UNSAFE_OUTPUT_PATTERNS = [
        (re.compile(r"\b(bypass|disable)\b.{0,20}?\b(security|firewall|auth)", re.I), "Unsafe security bypass instruction"),
        (re.compile(r"\bdelete\s+(all|everything|database)\b", re.I), "Dangerous mass deletion instruction"),
        (re.compile(r"\bpassword\s*[:=]\s*\S+", re.I), "Hardcoded password in output"),
        (re.compile(r"\b(api[_-]?key|secret[_-]?key)\s*[:=]\s*\S+", re.I), "Hardcoded secret in output"),
    ]

    _HALLUCINATION_INDICATORS = [
        re.compile(r"\b(I think|I believe|probably|maybe|might be)\b", re.I),
        re.compile(r"\baccording to (my|the) (knowledge|training)\b", re.I),
    ]

    _HALLUCINATION_PHRASES = re.compile(
        r"\b(I think|I believe|probably|maybe|might be|according to (?:my|the) (?:knowledge|training))\b", re.I
    )

    def verify(
        self,
        output_text: str,
        allowed_sources: list[str] | None = None,
        task_id: str = "",
        user_id: str = "",
        identity: str = "",
        role: str = "",
    ) -> VerificationResult:
        checks: list[CheckResult] = []

        checks.append(self._check_safety(output_text))
        checks.append(self._check_hallucination(output_text))
        checks.append(self._check_compliance(output_text))
        checks.append(self._check_length(output_text))

        overall = Verdict.PASS
        for c in checks:
            if c.verdict == Verdict.FAIL:
                overall = Verdict.FAIL
                break
            if c.verdict == Verdict.WARN:
                overall = Verdict.WARN

        summary = f"{len(checks)} checks: {sum(1 for c in checks if c.verdict == Verdict.PASS)} passed, {sum(1 for c in checks if c.verdict == Verdict.WARN)} warnings, {sum(1 for c in checks if c.verdict == Verdict.FAIL)} failed"

        audit_service.record(
            event_type="output_verified",
            task_id=task_id,
            user_id=user_id,
            identity=identity,
            role=role,
            detail=f"verdict={overall.value} — {summary}",
        )

        return VerificationResult(overall=overall, checks=checks, summary=summary)

    def _check_safety(self, text: str) -> CheckResult:
        for pattern, reason in self._UNSAFE_OUTPUT_PATTERNS:
            if pattern.search(text):
                return CheckResult(check_name="safety", verdict=Verdict.FAIL, detail=reason)
        return CheckResult(check_name="safety", verdict=Verdict.PASS, detail="No unsafe content detected")

    def _check_hallucination(self, text: str) -> CheckResult:
        indicators = len(self._HALLUCINATION_PHRASES.findall(text))
        if indicators >= 2:
            return CheckResult(
                check_name="hallucination",
                verdict=Verdict.WARN,
                detail=f"Multiple hedging phrases detected ({indicators}); output may be uncertain",
            )
        return CheckResult(check_name="hallucination", verdict=Verdict.PASS, detail="No hallucination indicators")

    def _check_compliance(self, text: str) -> CheckResult:
        if re.search(r"\b(classified|top.secret|eyes.only)\b", text, re.I):
            return CheckResult(
                check_name="compliance",
                verdict=Verdict.WARN,
                detail="Output references classified material — review required",
            )
        return CheckResult(check_name="compliance", verdict=Verdict.PASS, detail="Compliance check passed")

    def _check_length(self, text: str) -> CheckResult:
        if len(text) < 10:
            return CheckResult(
                check_name="length",
                verdict=Verdict.WARN,
                detail="Output is very short and may be incomplete",
            )
        if len(text) > 50000:
            return CheckResult(
                check_name="length",
                verdict=Verdict.WARN,
                detail="Output is very long and may exceed expected bounds",
            )
        return CheckResult(check_name="length", verdict=Verdict.PASS, detail="Output length within bounds")


output_verifier = OutputVerifier()
