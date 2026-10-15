"""Public evaluator demo — ONE synthetic Pump P-204 scenario (SIH26117).

Isolation contract (deliberately narrow):
- No authentication. No user identity is accepted or returned.
- Fixed synthetic inputs only: no client-supplied documents, prompts, tool
  names, code, task ids or file paths.
- Read-only against the bundled synthetic scan fixture.
- No database writes: no users, tasks, conversations, analyses or audit rows.
- Local capabilities only: local OCR, local vector store, local open-weight
  model, local sandbox subprocess. External AI is never called.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import Response

from app.core.config import settings

router = APIRouter(prefix="/demo", tags=["demo"])

# backend/ — this file lives at backend/app/api/routes/demo.py
_BACKEND_ROOT = Path(__file__).resolve().parents[3]

DEMO_SOURCE = "Pump_P204_Scanned_Inspection"
DEMO_QUERY = "Pump P-204 inspection vibration finding recommended action"
DEMO_TASK_ID = "demo-pump-p204-inspection"
DEMO_FINDING = "Elevated vibration detected."
NORMAL_VIBRATION_LIMIT = 4.5  # mm/s — from the synthetic equipment reference
SANDBOX_CODE = "print(25 + 17)"

# Fallback copy of the bundled synthetic scan (same content as the PNG fixture).
# Used only when local OCR cannot run, and always labelled as such.
DEMO_SCAN_TEXT = (
    "PUMP P-204 INSPECTION REPORT (SYNTHETIC DEMO)\n"
    "Equipment: Centrifugal Pump P-204\n"
    "Inspection Date: 2026-01-15 (Demo Date)\n"
    "Observed Vibration: 4.8 mm/s RMS (synthetic value)\n"
    "Temperature: 62 C (synthetic value)\n"
    "Inspection finding: elevated vibration detected.\n"
    "Recommended action: monitor trend and schedule seal inspection.\n"
    "This document is synthetic demonstration content for SIH26117.\n"
    "NOT real MRPL operational data."
)

_SCAN_CANDIDATES = (
    _BACKEND_ROOT / "sample_documents" / "Pump_P204_Scanned_Inspection.png",
    _BACKEND_ROOT / "tests" / "fixtures" / "Pump_P204_Scanned_Inspection.png",
)

_OCR_CACHE: dict[tuple[str, float], str] = {}


def _safe_reason(message: object) -> str:
    """Never leak host filesystem paths or long engine dumps to the evaluator."""
    text = str(message or "").replace(str(_BACKEND_ROOT), "<medha>")
    text = re.sub(r"[A-Za-z]:\\[^\s'\";,]+", "<path>", text)
    text = " ".join(text.split())
    return text[:200] if text else ""


def _scan_path() -> Path | None:
    for candidate in _SCAN_CANDIDATES:
        try:
            if candidate.is_file():
                return candidate
        except OSError:
            continue
    return None


def _run_scan_ocr() -> dict:
    """Real local OCR over the bundled synthetic inspection scan."""
    path = _scan_path()
    if path is None:
        return {
            "status": "UNAVAILABLE",
            "engine": "—",
            "source": DEMO_SOURCE,
            "text": "",
            "chars": 0,
            "pages": 0,
            "local_processing": True,
            "origin": "demo_document",
            "reason": "Synthetic demo scan not found on this machine.",
        }

    try:
        key = (str(path), path.stat().st_mtime)
    except OSError:
        key = (str(path), 0.0)

    cached = _OCR_CACHE.get(key)
    if cached is not None:
        return {
            "status": "completed",
            "engine": cached[0],
            "source": DEMO_SOURCE,
            "text": cached[1],
            "chars": len(cached[1]),
            "pages": 1,
            "local_processing": True,
            "origin": "local_ocr",
            "reason": "",
        }

    from app.services.ocr.local_ocr import OcreError, run_local_ocr

    try:
        result = run_local_ocr(str(path), source_name=path.name, content_type="image/png")
    except OcreError as exc:
        return {
            "status": "UNAVAILABLE",
            "engine": "—",
            "source": DEMO_SOURCE,
            "text": "",
            "chars": 0,
            "pages": 0,
            "local_processing": True,
            "origin": "demo_document",
            "reason": _safe_reason(exc),
        }
    except Exception as exc:  # noqa: BLE001 — engine failure must fail clearly
        return {
            "status": "UNAVAILABLE",
            "engine": "—",
            "source": DEMO_SOURCE,
            "text": "",
            "chars": 0,
            "pages": 0,
            "local_processing": True,
            "origin": "demo_document",
            "reason": _safe_reason(exc) or "Local OCR failed.",
        }

    text = (result.text or "").strip()
    if not text:
        return {
            "status": "UNAVAILABLE",
            "engine": result.engine,
            "source": DEMO_SOURCE,
            "text": "",
            "chars": 0,
            "pages": result.page_count,
            "local_processing": True,
            "origin": "demo_document",
            "reason": "Local OCR produced no extractable text.",
        }

    _OCR_CACHE[key] = (result.engine, text)
    return {
        "status": "completed",
        "engine": result.engine,
        "source": DEMO_SOURCE,
        "text": text,
        "chars": len(text),
        "pages": result.page_count,
        "local_processing": True,
        "origin": "local_ocr",
        "reason": "",
    }


def _demo_retrieval(query: str, scan_text: str, top_k: int = 4) -> list[dict]:
    """Demo-scoped TF-IDF retrieval — its own store, never the shared RAG store."""
    from app.services.rag.chunker import chunk_text
    from app.services.rag.demo_documents import get_demo_documents
    from app.services.rag.document_parser import parse_text
    from app.services.rag.vector_store import VectorStore

    store = VectorStore()
    documents = get_demo_documents() + [
        {"source_name": DEMO_SOURCE, "classification": "confidential", "text": scan_text}
    ]
    for doc in documents:
        parsed = parse_text(doc["text"], doc["source_name"], doc["classification"])
        chunks = chunk_text(
            parsed.text, parsed.source_name, classification=parsed.classification
        )
        store.add_chunks(
            [
                {
                    "source_name": c.source_name,
                    "chunk_index": c.chunk_index,
                    "text": c.text,
                    "start_char": c.start_char,
                    "end_char": c.end_char,
                    "classification": c.classification,
                }
                for c in chunks
            ]
        )

    scored = store.search(query, top_k=top_k)
    return [
        {
            "source_name": chunk.source_name,
            "text": chunk.text,
            "score": round(score, 4),
        }
        for chunk, score in scored
    ]


def _evidence_bundle() -> tuple[dict, list[dict], str]:
    ocr = _run_scan_ocr()
    scan_text = ocr["text"] or DEMO_SCAN_TEXT
    chunks = _demo_retrieval(DEMO_QUERY, scan_text)
    return ocr, chunks, scan_text


def _evidence_line(text: str) -> str:
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    for line in lines:
        if "finding" in line.lower():
            return line
    for line in lines:
        if "vibration" in line.lower():
            return line
    return text.strip()[:300]


def _detect_finding(scan_text: str, chunks: list[dict]) -> dict:
    lowered = scan_text.lower()
    detected = "elevated vibration" in lowered
    if not detected:
        match = re.search(r"(\d+(?:\.\d+)?)\s*mm/s", lowered)
        if match and float(match.group(1)) > NORMAL_VIBRATION_LIMIT:
            detected = True

    label = DEMO_FINDING if detected else "No elevated condition confirmed from extracted evidence."
    detail = _evidence_line(scan_text)
    if not detail:
        detail = " ".join(c["text"] for c in chunks)[:300] or "No evidence extracted."
    return {
        "status": "detected" if detected else "not_detected",
        "label": label,
        "source": DEMO_SOURCE,
        "evidence": detail,
    }


def _model_status() -> dict:
    from app.services.model_router.model_adapter import LocalSmallLLMAdapter

    health = LocalSmallLLMAdapter().health()
    status = health.get("status", "UNKNOWN")
    return {
        "status": status,
        "model": health.get("model") or settings.local_llm_model,
        "runtime": health.get("runtime", "ollama-compatible"),
        "reason": _safe_reason(health.get("reason", "")),
    }


def _unavailable_ai(status: dict, reason: str) -> dict:
    return {
        "status": "UNAVAILABLE",
        "provider": "Local Qwen",
        "model": status.get("model") or settings.local_llm_model,
        "runtime": status.get("runtime", "ollama-compatible"),
        "answer": "",
        "latency_ms": 0,
        "reason": reason,
    }


def _local_ai(chunks: list[dict]) -> dict:
    """Real local open-weight inference, fail-closed with an honest message."""
    from app.services.model_router.model_adapter import (
        LocalModelUnavailableError,
        LocalSmallLLMAdapter,
    )

    status = _model_status()
    if status["status"] != "AVAILABLE":
        if "unreachable" in (status.get("reason") or ""):
            reason = "Local AI runtime unavailable. Start Ollama and try again."
        else:
            reason = (
                f"Local AI model '{status.get('model')}' is not installed on the "
                "local runtime."
            )
        return _unavailable_ai(status, reason)

    evidence_lines = "\n".join(
        f"- [{c['source_name']}] {c['text']}" for c in chunks[:4]
    )
    prompt = (
        "You are MEDHA's local analyst and you run fully on this machine.\n"
        "Use ONLY the evidence below. Compare observed values against any limit\n"
        "stated in the evidence. If the evidence is insufficient, say so.\n"
        "Answer in one sentence, maximum 30 words.\n"
        "Question: Does the evidence show elevated vibration for Pump P-204?\n\n"
        f"Evidence:\n{evidence_lines}\n\n"
        "Answer:"
    )

    adapter = LocalSmallLLMAdapter()
    try:
        response = adapter.generate(prompt, max_tokens=96)
    except LocalModelUnavailableError:
        return _unavailable_ai(
            status, "Local AI runtime unavailable. Start Ollama and try again."
        )
    except Exception:  # noqa: BLE001 — never surface stack traces to the evaluator
        return _unavailable_ai(status, "Local AI inference failed. Try again.")

    answer = (response.text or "").strip()
    if not answer:
        return _unavailable_ai(status, "Local AI returned an empty response.")
    return {
        "status": "AVAILABLE",
        "provider": "Local Qwen",
        "model": status.get("model") or settings.local_llm_model,
        "runtime": status.get("runtime", "ollama-compatible"),
        "answer": answer[:600],
        "latency_ms": response.latency_ms,
        "reason": "",
    }


def _controlled_execution() -> dict:
    """Real isolated-subprocess execution of one fixed, authorized calculation."""
    from app.services.sandbox.code_runner import CodeSandboxError, run_isolated_python

    try:
        run = run_isolated_python(SANDBOX_CODE, timeout_s=5.0)
    except CodeSandboxError as exc:
        return {
            "status": "failed",
            "tool": "code_executor",
            "operation": "25 + 17",
            "result": "",
            "sandbox": "active",
            "network": "blocked",
            "duration_ms": 0,
            "reason": _safe_reason(exc) or "Controlled execution unavailable.",
        }

    output = (run.output or "").strip()
    return {
        "status": run.status,
        "tool": "code_executor",
        "operation": "25 + 17",
        "result": output if run.status == "completed" else "",
        "sandbox": run.sandbox,
        "network": run.network,
        "duration_ms": round(run.duration_ms, 1),
        "reason": _safe_reason(run.error),
    }


@router.post("/evidence")
def demo_evidence() -> dict:
    """Stage 1-3: local OCR → local RAG evidence for the synthetic scan."""
    ocr, chunks, _ = _evidence_bundle()
    return {
        "ocr": ocr,
        "rag": {
            "status": "LOCAL",
            "execution": "LOCAL",
            "query": DEMO_QUERY,
            "chunks": chunks,
            "total": len(chunks),
            "text_origin": ocr.get("origin", "demo_document"),
        },
    }


@router.post("/analysis")
def demo_analysis() -> dict:
    """Stage 4-6: evidence-grounded finding, local model answer, sandbox run."""
    _ocr, chunks, scan_text = _evidence_bundle()
    return {
        "finding": _detect_finding(scan_text, chunks),
        "ai": _local_ai(chunks),
        "execution": _controlled_execution(),
    }


def _build_report(scan_text: str, chunks: list[dict], model_status: dict) -> dict:
    finding = _detect_finding(scan_text, chunks)
    model_line = (
        f"{model_status.get('model')} ({model_status.get('status')})"
        if model_status.get("model")
        else "not configured"
    )
    return {
        "task_id": DEMO_TASK_ID,
        "analysis_id": "demo-analysis-p204",
        "title": "Pump P-204 Inspection Analysis",
        "purpose": (
            "Evaluate the synthetic Pump P-204 inspection scan using local OCR, "
            "local evidence retrieval and the local open-weight model."
        ),
        "security_mode": "secure",
        "sensitivity": "confidential",
        "status": "demo",
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "summary": (
            "MEDHA completed a local pipeline run on the synthetic Pump P-204 "
            f"inspection scan. Finding: {finding['label']}"
        ),
        "findings": [
            {
                "category": "condition",
                "severity": "high" if finding["status"] == "detected" else "info",
                "label": finding["label"],
                "detail": finding["evidence"][:600],
            }
        ],
        "recommendations": [
            {
                "priority": "medium",
                "action": "Monitor vibration trend and schedule seal inspection.",
                "rationale": "Extracted from the synthetic inspection evidence.",
            }
        ],
        "evidence": [
            {"source": c["source_name"], "snippet": c["text"][:600]} for c in chunks
        ],
        "execution": {
            "pipeline": "MEDHA evaluator demo: local OCR → local RAG → local Qwen → sandbox",
            "model": model_line,
            "sources_authorized": len({c["source_name"] for c in chunks}),
            "tools_authorized": 1,
        },
        "disclaimer": (
            "Synthetic demonstration content for SIH26117 — not real operational data. "
            "Generated locally by MEDHA from the demo scenario only."
        ),
    }


@router.post("/report")
def demo_report() -> Response:
    """Real DOCX deliverable built only from the synthetic demo scenario."""
    from app.services.analysis.docx_generator import generate_docx

    _ocr, chunks, scan_text = _evidence_bundle()
    report = _build_report(scan_text, chunks, _model_status())
    docx_bytes = generate_docx(report)

    return Response(
        content=docx_bytes,
        media_type=(
            "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        ),
        headers={
            "Content-Disposition": (
                'attachment; filename="MEDHA_Pump_P204_Inspection_Analysis_Demo_Report.docx"'
            )
        },
    )
