"""Secure Analysis API — task-aware pipeline, persistence, history, and handover."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.schemas.auth import CurrentUser
from app.services.analysis.analyzer import (
    AnalysisAccessDeniedError,
    secure_analysis_service,
)
from app.services.audit_service import audit_service
from app.services.task_service import passport_service

router = APIRouter(prefix="/analysis", tags=["analysis"])


class AnalysisRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=36)
    allowed_tools: list[str] | None = None


class HandoverRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=36)
    approved: bool
    reason: str = Field(default="", max_length=1000)


def _run_for_user(
    db: Session,
    task_id: str,
    current_user: CurrentUser,
) -> dict:
    try:
        return secure_analysis_service.run_analysis(db, task_id, current_user)
    except AnalysisAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        if str(exc).startswith("Task passport"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise


@router.post("/run", status_code=status.HTTP_200_OK)
def run_analysis(
    payload: AnalysisRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Run the secure analysis pipeline for a task and persist its result.

    The Task Passport is the single source of truth: security mode,
    sensitivity, network policy and the tool/source/model allowlists all come
    from the passport. Client-supplied ``allowed_tools`` are ignored.
    """
    return _run_for_user(db, payload.task_id, current_user)


@router.get("/history")
def get_analysis_history(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    task_id: str | None = None,
) -> dict:
    """List the current user's secure analyses (optionally for one task).

    Server-side scoped: only analyses owned by the authenticated user and not
    soft-deleted are returned.
    """
    records = secure_analysis_service.list_history(db, current_user, task_id=task_id)
    return {"records": records, "total": len(records)}


@router.get("/dataset")
async def get_dataset():
    """Return the synthetic Pump P-204 demonstration dataset (public utility)."""
    from app.services.analysis.dataset import generate_synthetic_dataset

    return generate_synthetic_dataset()


@router.get("/{analysis_id}")
def get_analysis(
    analysis_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Return the full payload of an owned analysis."""
    try:
        return secure_analysis_service.get(db, analysis_id, current_user)
    except AnalysisAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        if str(exc).startswith("Analysis"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise


@router.delete("/{analysis_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_analysis(
    analysis_id: str,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> None:
    """Soft-delete an owned analysis. The audit trail is preserved."""
    try:
        secure_analysis_service.delete(db, analysis_id, current_user)
    except AnalysisAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        if str(exc).startswith("Analysis"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise


@router.post("/handover", status_code=status.HTTP_200_OK)
def approve_handover(
    payload: HandoverRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> dict:
    """Approve or reject the secure handover for a task's latest analysis."""
    try:
        return secure_analysis_service.approve_handover(
            db,
            task_id=payload.task_id,
            current_user=current_user,
            approved=payload.approved,
            reason=payload.reason,
        )
    except AnalysisAccessDeniedError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except Exception as exc:
        if str(exc).startswith("Task passport"):
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        raise


@router.post("/excel")
def generate_excel(
    payload: AnalysisRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Generate and return the Excel workbook for the task's analysis."""
    result = secure_analysis_service.latest_for_task(db, payload.task_id, current_user)
    if result is None:
        # No stored analysis yet — run (and persist) it first.
        result = _run_for_user(db, payload.task_id, current_user)

    from app.services.analysis.excel_generator import generate_excel as build_workbook

    excel_bytes = build_workbook(result)

    label = "".join(c if c.isalnum() else "_" for c in result.get("title", task_slug(result)))[:40]
    filename = f"MEDHA_{label}_Secure_Analysis.xlsx"

    return Response(
        content=excel_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


def _collect_evidence(db: Session, passport) -> list[dict]:
    """Retrieve evidence snippets limited to this passport's authorized sources."""
    try:
        from app.services.rag.retrieval import retrieval_service

        search = retrieval_service.search(
            query=f"{passport.title} {passport.purpose}",
            allowed_sources=passport.allowed_sources,
            sensitivity_level=passport.sensitivity.value,
            network_policy=passport.network_policy.value,
            top_k=5,
            task_id=passport.task_id,
            user_id=passport.user_id,
            identity="report_export",
            role="system",
            security_mode=passport.security_mode,
        )
        evidence: list[dict] = []
        seen: set[str] = set()
        for chunk in search.chunks or []:
            source = str(chunk.get("source_name", ""))
            snippet = str(chunk.get("text", ""))
            key = f"{source}:{snippet[:80]}"
            if not source or key in seen:
                continue
            seen.add(key)
            evidence.append({"source": source, "snippet": snippet[:600]})
        return evidence
    except Exception:
        return []


@router.post("/docx")
def generate_docx_report(
    payload: AnalysisRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
):
    """Generate and download a real .docx report for an owned task."""
    from app.services.analysis.docx_generator import generate_docx as build_docx
    from app.services.task_service import TaskPassportNotFoundError

    try:
        passport = passport_service.get(db, payload.task_id)
    except TaskPassportNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    if passport.user_id != current_user.user_id:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Your identity does not match this Task Passport",
        )

    result = secure_analysis_service.latest_for_task(db, passport.task_id, current_user)
    if result is None:
        result = _run_for_user(db, passport.task_id, current_user)

    evidence = _collect_evidence(db, passport)
    equipment = result.get("equipment_info", {}) or {}
    failure = result.get("failure_summary", {}) or {}
    sensor = result.get("sensor_summary", {}) or {}
    risk = result.get("risk_assessment", {}) or {}

    from datetime import datetime, timezone

    report = {
        "task_id": passport.task_id,
        "analysis_id": result.get("analysis_id", ""),
        "title": passport.title or result.get("title", "Task Report"),
        "purpose": passport.purpose or equipment.get("purpose", ""),
        "security_mode": passport.security_mode.value,
        "sensitivity": passport.sensitivity.value,
        "status": passport.status.value,
        "generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
        "summary": result.get("summary", ""),
        "findings": failure.get("findings", []) or [],
        "recommendations": result.get("recommendations", []) or [],
        "evidence": evidence,
        "execution": {
            "pipeline": "MEDHA secure analysis pipeline",
            "model": sensor.get("model_used", ""),
            "sources_authorized": sensor.get("sources_authorized", len(passport.allowed_sources or [])),
            "tools_authorized": sensor.get("tools_authorized", 0),
            "risk_level": risk.get("risk_level", ""),
            "risk_score": risk.get("risk_score", 0),
        },
        "disclaimer": result.get("disclaimer", ""),
    }

    docx_bytes = build_docx(report)

    label = "".join(c if c.isalnum() else "_" for c in str(report["title"]))[:40] or "TASK"
    filename = f"MEDHA_{label}_Report.docx"

    audit_service.record(
        event_type="docx_report_generated",
        task_id=passport.task_id,
        user_id=current_user.user_id,
        identity=current_user.username,
        role=current_user.role.value,
        security_mode=passport.security_mode.value,
        detail=(
            f"DOCX report generated ({len(docx_bytes)} bytes, "
            f"{len(evidence)} evidence source(s))"
        ),
    )

    return Response(
        content=docx_bytes,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={
            "Content-Disposition": f"attachment; filename={filename}",
        },
    )


def task_slug(result: dict) -> str:
    task_id = result.get("task_id", "")
    return f"TASK_{task_id[:8] if task_id else 'ANALYSIS'}"