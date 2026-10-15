"""Pydantic schemas for Sandbox API."""

from pydantic import BaseModel, Field


class ExecuteRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=36)
    tool_name: str = Field(min_length=1, max_length=50)
    action: str = Field(min_length=1, max_length=500)
    input_data: dict = Field(default_factory=dict)
    code: str | None = Field(default=None, max_length=20_000)


class ExecuteResponse(BaseModel):
    execution_id: str
    tool_name: str
    status: str
    output: str
    error: str
    cpu_ms: float
    memory_mb: float
    network_calls: int
    sandbox: str = ""
    network: str = ""


class RollbackRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=36)
    execution_id: str = Field(min_length=1, max_length=36)


class RollbackResponse(BaseModel):
    execution_id: str
    tool_name: str
    status: str
    output: str
