"""
Actions API - Endpoints for action confirmation flow.

Handles the Human-in-the-Loop pattern for sensitive operations:
1. Agent creates pending action
2. User reviews and confirms/rejects
3. Tool Gateway executes confirmed actions
"""

import json
import logging
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.session import get_db
from ...core.auth import require_auth
from ...core.cache import redis_client
from ...modules.conversation.pending_action_service import (
    PendingActionService,
    ActionNotFoundError,
    ActionExpiredError,
    ActionAlreadyProcessedError,
)


logger = logging.getLogger(__name__)

router = APIRouter(prefix="/actions", tags=["Actions"])


# ============ Request/Response Models ============

class ActionDetailItem(BaseModel):
    """A single detail item for display."""
    label: str
    value: str


class PendingActionResponse(BaseModel):
    """Response model for a pending action."""
    id: str
    action_type: str
    status: str
    display_title: str = ""
    description: str = ""
    display_details: List[ActionDetailItem] = []
    expires_at: Optional[str] = None
    created_at: Optional[str] = None
    can_confirm: bool = False
    is_expired: bool = False

    class Config:
        from_attributes = True


class ActionExecutionResponse(BaseModel):
    """Response model for action execution."""
    success: bool
    action_id: str
    status: str
    result: Optional[dict] = None
    error: Optional[str] = None


class ActionConfirmRequest(BaseModel):
    """Request model for confirming an action."""
    execute_immediately: bool = Field(
        default=True,
        description="Whether to execute immediately after confirmation",
    )
    payload_overrides: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Override payload fields (e.g. new_start, new_end) before execution",
    )


class AnswerQuestionRequest(BaseModel):
    """Request model for answering an agent question."""
    question_id: str = Field(..., description="The question_id from the ask_user_question event")
    answers: List[Dict[str, str]] = Field(
        ...,
        description="List of {question, answer} dicts matching the questions asked",
    )


# ============ Request Models ============

class CreateActionFromInsightRequest(BaseModel):
    """Request to create a PendingAction originating from an insight card."""
    insight_id: str = Field(..., description="ID of the source insight")
    action_type: str = Field(..., description="One of the canonical ActionType values")
    action_data: Optional[Dict[str, Any]] = Field(
        default=None,
        description="Rich context from the insight (person, days_until, etc.)",
    )


# ============ Endpoints ============

@router.post("/from-insight", response_model=PendingActionResponse, status_code=status.HTTP_201_CREATED)
async def create_action_from_insight(
    request: CreateActionFromInsightRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Create a PendingAction from an insight card tap.

    This bridges the insight feed to the PendingAction confirmation flow:
    1. Mobile taps action chip on insight card
    2. This endpoint creates a PENDING action with display_data assembled from insight context
    3. Mobile shows confirmation UI
    4. User confirms via POST /actions/{id}/confirm
    """
    user_id, family_id = require_auth()

    service = PendingActionService(db)

    # Build display_data from insight context
    action_data = request.action_data or {}
    display_data = {
        "title": action_data.get("display_title", request.action_type),
        "description": action_data.get("display_description", ""),
        "source": "insight",
        "source_id": request.insight_id,
        "details": [
            {"label": k, "value": str(v)}
            for k, v in action_data.items()
            if k not in ("display_title", "display_description")
            and v is not None
        ],
    }

    try:
        action = await service.create(
            user_id=user_id,
            family_id=family_id,
            action_type=request.action_type,
            payload={
                "source": "insight",
                "source_id": request.insight_id,
                **action_data,
            },
            display_data=display_data,
            ttl_minutes=30,
        )
    except Exception as e:
        logger.error("Failed to create action from insight: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create action: {str(e)}",
        )

    return PendingActionResponse(
        id=str(action.id),
        action_type=action.action_type,
        status=action.status,
        display_title=display_data.get("title", ""),
        description=display_data.get("description", ""),
        display_details=[
            ActionDetailItem(label=d["label"], value=d["value"])
            for d in display_data.get("details", [])
        ],
        expires_at=action.expires_at.isoformat() if action.expires_at else None,
        created_at=action.created_at.isoformat() if action.created_at else None,
        can_confirm=action.can_confirm,
        is_expired=action.is_expired,
    )


@router.get("/pending", response_model=List[PendingActionResponse])
async def list_pending_actions(
    limit: int = 20,
    db: AsyncSession = Depends(get_db),
):
    """
    List user's pending actions.

    Returns actions awaiting confirmation that haven't expired.
    """
    user_id, _ = require_auth()

    service = PendingActionService(db)
    actions = await service.list_pending(user_id=user_id, limit=limit)

    return [
        PendingActionResponse(
            id=str(action.id),
            action_type=action.action_type,
            status=action.status,
            display_title=action.display_data.get("title", "") if action.display_data else "",
            description=action.display_data.get("description", "") if action.display_data else "",
            display_details=[
                ActionDetailItem(label=d["label"], value=d["value"])
                for d in action.display_data.get("details", [])
            ] if action.display_data else [],
            expires_at=action.expires_at.isoformat() if action.expires_at else None,
            created_at=action.created_at.isoformat() if action.created_at else None,
            can_confirm=action.can_confirm,
            is_expired=action.is_expired,
        )
        for action in actions
    ]


@router.get("/{action_id}", response_model=PendingActionResponse)
async def get_action(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Get details of a specific action.
    """
    user_id, _ = require_auth()

    service = PendingActionService(db)
    action = await service.get(action_id, user_id)

    if not action:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found",
        )

    return PendingActionResponse(
        id=str(action.id),
        action_type=action.action_type,
        status=action.status,
        display_title=action.display_data.get("title", "") if action.display_data else "",
        description=action.display_data.get("description", "") if action.display_data else "",
        display_details=[
            ActionDetailItem(label=d["label"], value=d["value"])
            for d in action.display_data.get("details", [])
        ] if action.display_data else [],
        expires_at=action.expires_at.isoformat() if action.expires_at else None,
        created_at=action.created_at.isoformat() if action.created_at else None,
        can_confirm=action.can_confirm,
        is_expired=action.is_expired,
    )


@router.post("/{action_id}/confirm", response_model=ActionExecutionResponse)
async def confirm_action(
    action_id: UUID,
    request: ActionConfirmRequest = ActionConfirmRequest(),
    db: AsyncSession = Depends(get_db),
):
    """
    Confirm and optionally execute an action.

    If execute_immediately is True (default), the action will be
    executed via Tool Gateway after confirmation.
    """
    user_id, _ = require_auth()

    service = PendingActionService(db)

    try:
        if request.execute_immediately:
            # Confirm and execute
            result = await service.confirm_and_execute(
                action_id, user_id,
                payload_overrides=request.payload_overrides,
            )
            return ActionExecutionResponse(
                success=True,
                action_id=str(action_id),
                status="executed",
                result=result,
            )
        else:
            # Just confirm, don't execute
            action = await service.confirm(action_id, user_id)
            return ActionExecutionResponse(
                success=True,
                action_id=str(action_id),
                status="confirmed",
            )

    except ActionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found",
        )
    except ActionExpiredError:
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=f"Action {action_id} has expired",
        )
    except ActionAlreadyProcessedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Action confirm/execute failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}",
        )


@router.post("/{action_id}/reject")
async def reject_action(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Reject a pending action.
    """
    user_id, _ = require_auth()

    service = PendingActionService(db)

    try:
        action = await service.reject(action_id, user_id)
        return {
            "success": True,
            "action_id": str(action_id),
            "status": "rejected",
        }

    except ActionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found",
        )
    except ActionAlreadyProcessedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )


@router.post("/{action_id}/execute", response_model=ActionExecutionResponse)
async def execute_action(
    action_id: UUID,
    db: AsyncSession = Depends(get_db),
):
    """
    Execute a confirmed action.

    Use this if you confirmed with execute_immediately=False
    and want to execute later.
    """
    user_id, _ = require_auth()

    service = PendingActionService(db)

    try:
        # Verify action belongs to user
        action = await service.get(action_id, user_id)
        if not action:
            raise ActionNotFoundError(f"Action {action_id} not found")

        result = await service.execute(action_id)
        return ActionExecutionResponse(
            success=True,
            action_id=str(action_id),
            status="executed",
            result=result,
        )

    except ActionNotFoundError:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Action {action_id} not found",
        )
    except ActionAlreadyProcessedError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )
    except Exception as e:
        logger.error("Action execution failed: %s", e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Execution failed: {str(e)}",
        )


# ============ AskUserQuestion Answer Endpoint ============

_ASK_USER_ANSWER_PREFIX = "ask_user_answer:"


@router.post("/answer-question")
async def answer_question(request: AnswerQuestionRequest):
    """Submit answer to an agent's AskUserQuestion.

    The agent hook is blocked (BLPOP) waiting for this answer on Redis.
    Writing the answer unblocks the hook and lets the agent continue.
    """
    require_auth()

    answer_key = f"{_ASK_USER_ANSWER_PREFIX}{request.question_id}"

    try:
        payload = json.dumps({"answers": request.answers}, ensure_ascii=False)
        r = redis_client.client
        if r is None:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Redis not available",
            )
        await r.lpush(answer_key, payload)
        # Set TTL to auto-clean in case nobody is listening
        await r.expire(answer_key, 300)
    except HTTPException:
        raise
    except Exception as e:
        logger.error("Failed to submit answer for %s: %s", request.question_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to submit answer",
        )

    return {"success": True, "question_id": request.question_id}
