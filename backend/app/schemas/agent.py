"""Pydantic schemas for Agent Planner API."""

from pydantic import BaseModel, Field


class PlanCreateRequest(BaseModel):
    task_id: str = Field(min_length=1, max_length=36)
    query: str = Field(min_length=1, max_length=2000)


class PlanStepResponse(BaseModel):
    step_id: str
    order: int
    tool_name: str
    action: str
    description: str
    status: str
    risk: str
    requires_approval: bool


class PlanResponse(BaseModel):
    plan_id: str
    task_id: str
    user_query: str
    status: str
    steps: list[PlanStepResponse]


class StepActionRequest(BaseModel):
    plan_id: str = Field(min_length=1, max_length=36)
    step_id: str = Field(min_length=1, max_length=36)
    input_data: dict = Field(default_factory=dict)


class StepActionResult(BaseModel):
    step_id: str
    tool_name: str
    action: str
    output: str
    success: bool
    sandbox: str = ""
    network: str = ""


class ToolsResponse(BaseModel):
    tools: list[dict]
