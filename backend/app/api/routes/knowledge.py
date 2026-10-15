"""Knowledge / RAG API routes — permission-aware document ingestion and retrieval."""

import os
import tempfile
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.dependencies import (
    get_current_user,
    get_db,
    require_roles,
)
from app.schemas.auth import CurrentUser, Role
from app.schemas.knowledge import (
    DocumentIngestRequest,
    DocumentIngestResponse,
    OcrPageInfo,
    OcrResponse,
    SearchRequest,
    SearchResponse,
    SearchResultChunk,
    SourceInfo,
    SourcesResponse,
)
from app.schemas.task import TaskPassportRead
from app.services.action_gate import (
    ActionCategory,
    ActionGateError,
    AuthorizationContext,
    action_gate,
)
from app.services.audit_service import audit_service
from app.services.ocr.local_ocr import OcreError, is_supported, run_local_ocr, sanitize_source_name
from app.services.rag.retrieval import retrieval_service

router = APIRouter(prefix="/knowledge", tags=["knowledge"])


@router.post(
    "/documents",
    response_model=DocumentIngestResponse,
    status_code=status.HTTP_201_CREATED,
)
def ingest_document(
    payload: DocumentIngestRequest,
    current_user: Annotated[CurrentUser, Depends(require_roles(Role.ENGINEER, Role.ADMIN))],
) -> DocumentIngestResponse:
    """Ingest a document into the permission-aware vector store."""
    chunks = retrieval_service.ingest_document(
        text=payload.text,
        source_name=payload.source_name,
        classification=payload.classification,
    )
    return DocumentIngestResponse(
        source_name=payload.source_name,
        chunks_created=chunks,
    )


@router.post("/search", response_model=SearchResponse)
def search_knowledge(
    payload: SearchRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> SearchResponse:
    """Search ingested knowledge — filtered by the Task Passport permissions."""
    from app.services.task_service import TaskPassportNotFoundError, passport_service

    try:
        passport = passport_service.get(db, payload.task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        )

    # Action Gate: authorize RAG search
    try:
        action_gate.authorize_action(
            AuthorizationContext(
                passport=passport,
                current_user=current_user,
                action_category=ActionCategory.READ,
            )
        )
    except ActionGateError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    result = retrieval_service.search(
        query=payload.query,
        allowed_sources=passport.allowed_sources,
        sensitivity_level=passport.sensitivity.value,
        network_policy=passport.network_policy.value,
        top_k=payload.top_k,
        task_id=passport.task_id,
        user_id=current_user.user_id,
        identity=current_user.username,
        role=current_user.role.value,
        security_mode=passport.security_mode,
    )
    return SearchResponse(
        chunks=[SearchResultChunk(**c) for c in result.chunks],
        total_before_filter=result.total_before_filter,
        total_after_filter=result.total_after_filter,
    )


@router.get("/sources", response_model=SourcesResponse)
def list_sources(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> SourcesResponse:
    """List all ingested document sources."""
    return SourcesResponse(
        sources=retrieval_service.get_sources(),
        total_chunks=retrieval_service.total_chunks(),
    )


@router.delete(
    "/sources/{source_name}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_source(
    source_name: str,
    current_user: Annotated[CurrentUser, Depends(require_roles(Role.ENGINEER, Role.ADMIN))],
) -> None:
    """Delete an ingested document and all its chunks."""
    removed = retrieval_service.delete_source(source_name)
    if removed == 0:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Source '{source_name}' not found",
        )


def _authorize_ocr(passport: TaskPassportRead, current_user: CurrentUser) -> None:
    """Action Gate for OCR: ownership + lifecycle COMPUTE (local text extraction).

    COMPUTE is not permitted in DRAFT — OCR cannot bypass the passport lifecycle.
    """
    try:
        action_gate.authorize_action(
            AuthorizationContext(
                passport=passport,
                current_user=current_user,
                action_category=ActionCategory.COMPUTE,
            )
        )
    except ActionGateError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc


@router.post("/ocr", response_model=OcrResponse, status_code=status.HTTP_200_OK)
async def ocr_document(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
    task_id: str = Form(...),
    file: UploadFile = File(...),
    ingest: str = Form("true"),
) -> OcrResponse:
    """Local OCR on a scanned image/PDF, optional ingest into existing RAG.

    Path: upload → local RapidOCR/PyMuPDF → extracted text → (optional)
    retrieval_service.ingest_document → existing RAG retrieval.
    Fully local. No cloud OCR. Task Passport + Action Gate enforced.
    """
    from app.services.task_service import TaskPassportNotFoundError, passport_service

    try:
        passport = passport_service.get(db, task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Task passport not found")

    if passport.user_id != current_user.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Identity mismatch")

    _authorize_ocr(passport, current_user)

    filename = sanitize_source_name(file.filename)
    content_type = (file.content_type or "").split(";")[0].strip().lower()
    if not is_supported(filename, content_type):
        audit_service.record(
            event_type="ocr_rejected",
            task_id=task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
            security_mode=passport.security_mode.value,
            detail=f"Unsupported OCR input: {filename} ({content_type or 'unknown'})",
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Unsupported input for local OCR. Supported: PNG, JPEG, PDF",
        )

    tmp_path = ""
    try:
        suffix = os.path.splitext(filename)[1].lower() or ".bin"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await file.read())
            tmp_path = tmp.name

        try:
            result = run_local_ocr(
                tmp_path,
                source_name=filename,
                content_type=content_type or None,
            )
        except OcreError as exc:
            audit_service.record(
                event_type="ocr_failed",
                task_id=task_id,
                user_id=current_user.user_id,
                identity=current_user.username,
                role=current_user.role.value,
                security_mode=passport.security_mode.value,
                detail=f"Local OCR failed for {filename}: {exc}",
            )
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail=str(exc),
            ) from exc

        chunks_created = 0
        ingested = False
        want_ingest = ingest.strip().lower() in {"1", "true", "yes", "on"}
        if want_ingest and result.text.strip():
            chunks_created = retrieval_service.ingest_document(
                text=result.text,
                source_name=result.source_name,
                classification=passport.sensitivity.value,
            )
            ingested = True

        audit_service.record(
            event_type="ocr_completed",
            task_id=task_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
            security_mode=passport.security_mode.value,
            detail=(
                f"Local OCR completed source={result.source_name} "
                f"engine={result.engine} pages={result.page_count} "
                f"chars={result.char_count} ingested={str(ingested).lower()} "
                f"chunks={chunks_created}"
            ),
        )
        if ingested:
            audit_service.record(
                event_type="ocr_ingested",
                task_id=task_id,
                user_id=current_user.user_id,
                identity=current_user.username,
                role=current_user.role.value,
                security_mode=passport.security_mode.value,
                detail=(
                    f"OCR text ingested into RAG source={result.source_name} "
                    f"chunks={chunks_created} classification={passport.sensitivity.value}"
                ),
            )

        return OcrResponse(
            source_name=result.source_name,
            text=result.text,
            status=result.status,
            engine=result.engine,
            content_type=result.content_type,
            page_count=result.page_count,
            char_count=result.char_count,
            local_processing=result.local_processing,
            pages=[
                OcrPageInfo(
                    page_number=p.page_number,
                    char_count=p.char_count,
                    source=p.source,
                )
                for p in result.pages
            ],
            ingested=ingested,
            chunks_created=chunks_created,
        )
    finally:
        if tmp_path and os.path.isfile(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass
