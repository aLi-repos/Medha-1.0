"""Agent Planner API routes — task plan creation, step approval, and execution."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.api.dependencies import get_current_user, get_db
from app.schemas.agent import (
    PlanCreateRequest,
    PlanResponse,
    PlanStepResponse,
    StepActionRequest,
    StepActionResult,
    ToolsResponse,
)
from app.schemas.auth import CurrentUser
from app.services.action_gate import (
    ActionCategory,
    ActionGateError,
    AuthorizationContext,
    action_gate,
)
from app.services.agent.service import agent_service
from app.services.agent.tool_registry import tool_registry
from app.services.task_service import TaskPassportNotFoundError, passport_service

router = APIRouter(prefix="/agent", tags=["agent"])


@router.post("/plan", response_model=PlanResponse, status_code=status.HTTP_201_CREATED)
def create_plan(
    payload: PlanCreateRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PlanResponse:
    """Create an execution plan from a user query, gated by the Task Passport."""
    try:
        passport = passport_service.get(db, payload.task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        )

    # Action Gate: authorize agent planning
    try:
        action_gate.authorize_action(
            AuthorizationContext(
                passport=passport,
                current_user=current_user,
                action_category=ActionCategory.COMPUTE,
            )
        )
    except ActionGateError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    plan = agent_service.create_plan(
        query=payload.query,
        task_id=passport.task_id,
        allowed_tools=passport.allowed_tools,
        user_id=current_user.user_id,
        identity=current_user.username,
        role=current_user.role.value,
    )

    return _plan_to_response(plan)


@router.post("/plan/approve-step", response_model=PlanStepResponse)
def approve_step(
    payload: StepActionRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> PlanStepResponse:
    """Approve a pending step that requires approval."""
    plan = agent_service.get_plan(payload.plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    # Action Gate: verify passport ownership and lifecycle
    try:
        passport = passport_service.get(db, plan.task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        )

    try:
        action_gate.check_passport_ownership(passport, current_user)
    except ActionGateError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    try:
        step = agent_service.approve_step(
            payload.plan_id,
            payload.step_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return PlanStepResponse(
        step_id=step.step_id,
        order=step.order,
        tool_name=step.tool_name,
        action=step.action,
        description=step.description,
        status=step.status.value,
        risk=step.risk,
        requires_approval=step.requires_approval,
    )


@router.post("/plan/execute-step", response_model=StepActionResult)
def execute_step(
    payload: StepActionRequest,
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
    db: Annotated[Session, Depends(get_db)],
) -> StepActionResult:
    """Execute an approved (or non-approval) step."""
    plan = agent_service.get_plan(payload.plan_id)
    if plan is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Plan not found",
        )

    # Action Gate: verify passport ownership, lifecycle, and tool authorization
    try:
        passport = passport_service.get(db, plan.task_id)
    except TaskPassportNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Task passport not found",
        )

    # Find the step to check its tool
    step = agent_service._find_step(plan, payload.step_id)

    # Human verification: execution must match the approved task plan AND
    # (when one was reviewed) the approved agent execution plan.
    from app.services.human_verification import human_verification_service

    ok, reason = human_verification_service.check_plan_approval(passport, plan)
    if not ok:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=reason,
        )

    try:
        action_gate.authorize_action(
            AuthorizationContext(
                passport=passport,
                current_user=current_user,
                action_category=ActionCategory.EXECUTE,
                tool_name=step.tool_name,
            ),
            step_approved=(step.status.value == "approved"),
        )
    except ActionGateError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(exc),
        ) from exc

    try:
        result = agent_service.execute_step(
            payload.plan_id,
            payload.step_id,
            user_id=current_user.user_id,
            identity=current_user.username,
            role=current_user.role.value,
            input_data=payload.input_data,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        ) from exc

    return StepActionResult(**result)


@router.get("/tools", response_model=ToolsResponse)
def list_tools(
    current_user: Annotated[CurrentUser, Depends(get_current_user)],
) -> ToolsResponse:
    """List all registered tools with their metadata."""
    tools = tool_registry.list_all()
    return ToolsResponse(
        tools=[
            {
                "name": t.name,
                "description": t.description,
                "capabilities": t.capabilities,
                "risk": t.risk.value,
                "requires_approval": t.requires_approval,
            }
            for t in tools
        ]
    )


def _plan_to_response(plan) -> PlanResponse:
    return PlanResponse(
        plan_id=plan.plan_id,
        task_id=plan.task_id,
        user_query=plan.user_query,
        status=plan.status.value,
        steps=[
            PlanStepResponse(
                step_id=s.step_id,
                order=s.order,
                tool_name=s.tool_name,
                action=s.action,
                description=s.description,
                status=s.status.value,
                risk=s.risk,
                requires_approval=s.requires_approval,
            )
            for s in plan.steps
        ],
    )
