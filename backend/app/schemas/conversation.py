"""Pydantic schemas for Conversation and Message API."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class ConversationCreate(BaseModel):
    """Input for creating a new conversation.

    task_id is optional: null/omitted creates a General Chat conversation
    (no Task Passport). A non-empty string must be a real task id.
    """
    task_id: str | None = Field(default=None, max_length=36)
    title: str = Field(default="New Conversation", max_length=200)


class ConversationRead(BaseModel):
    """Conversation as returned by the API."""
    model_config = ConfigDict(frozen=True)

    id: str
    # Empty string indicates a General Chat conversation (no active task).
    task_id: str
    user_id: str
    title: str
    created_at: datetime
    updated_at: datetime


class MessageCreate(BaseModel):
    """Input for sending a message in a conversation."""
    role: str = Field(pattern=r"^(user|assistant)$")
    content: str = Field(min_length=1, max_length=50000)
    model: str | None = Field(default=None, max_length=100)


class MessageRead(BaseModel):
    """Message as returned by the API."""
    model_config = ConfigDict(frozen=True)

    id: str
    conversation_id: str
    role: str
    content: str
    model: str | None
    created_at: datetime


class AttachmentRead(BaseModel):
    """Attachment as returned by the API."""
    model_config = ConfigDict(frozen=True)

    id: str
    message_id: str
    conversation_id: str
    task_id: str
    filename: str
    content_type: str
    file_size: int
    created_at: datetime


class ChatRequest(BaseModel):
    """Chat request with optional model selection and attachments.

    task_id is optional: null/omitted means General Chat (no Task Passport,
    no task-relevance gate, no task RAG). A non-empty string activates the
    full task-aware pipeline.
    """
    task_id: str | None = Field(default=None, max_length=36)
    conversation_id: str | None = Field(default=None, max_length=36)
    prompt: str = Field(min_length=1, max_length=50000)
    model: str | None = Field(default=None, max_length=100)
    max_tokens: int = Field(default=512, ge=1, le=4096)


class SourceReference(BaseModel):
    """A single authorized RAG evidence source returned with a chat answer."""
    name: str
    snippet: str


class ChatResponse(BaseModel):
    """Chat response with model info, conversation context, and RAG sources."""
    conversation_id: str
    message_id: str
    model_used: str
    response_text: str
    complexity: str
    routing_reason: str
    tokens_used: int
    latency_ms: float
    execution_mode: str = "simulation"
    sources: list[SourceReference] = Field(default_factory=list)


class ConversationListResponse(BaseModel):
    """List of conversations for a task."""
    conversations: list[ConversationRead]
    total: int


class MessageListResponse(BaseModel):
    """List of messages in a conversation."""
    messages: list[MessageRead]
    attachments: list[AttachmentRead]
    total: int
