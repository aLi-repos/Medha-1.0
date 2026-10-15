"""Pydantic schemas for Knowledge / RAG API."""

from pydantic import BaseModel, Field


class DocumentIngestRequest(BaseModel):
    text: str = Field(min_length=1)
    source_name: str = Field(min_length=1, max_length=200)
    classification: str = Field(default="internal", pattern="^(internal|confidential|restricted)$")


class DocumentIngestResponse(BaseModel):
    source_name: str
    chunks_created: int


class SearchRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=36)
    query: str = Field(min_length=1, max_length=500)
    top_k: int = Field(default=5, ge=1, le=20)


class SearchResultChunk(BaseModel):
    source_name: str
    chunk_index: int
    text: str
    classification: str
    score: float


class SearchResponse(BaseModel):
    chunks: list[SearchResultChunk]
    total_before_filter: int
    total_after_filter: int


class SourceInfo(BaseModel):
    source_name: str


class SourcesResponse(BaseModel):
    sources: list[str]
    total_chunks: int


class OcrPageInfo(BaseModel):
    page_number: int
    char_count: int
    source: str


class OcrResponse(BaseModel):
    """Structured local OCR extraction suitable for the RAG pipeline."""

    source_name: str
    text: str
    status: str
    engine: str
    content_type: str
    page_count: int
    char_count: int
    local_processing: bool = True
    pages: list[OcrPageInfo] = Field(default_factory=list)
    ingested: bool = False
    chunks_created: int = 0
    error: str | None = None
