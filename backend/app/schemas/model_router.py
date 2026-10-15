"""Pydantic schemas for Model Router API."""

from pydantic import BaseModel, Field


class InferenceRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=36)
    prompt: str = Field(min_length=1, max_length=5000)
    max_tokens: int = Field(default=512, ge=1, le=4096)


class InferenceResponse(BaseModel):
    model_used: str
    response_text: str
    complexity: str
    routing_reason: str
    tokens_used: int
    latency_ms: float
    input_filtered: bool
    output_filtered: bool


class ModelsResponse(BaseModel):
    available_models: list[str]
