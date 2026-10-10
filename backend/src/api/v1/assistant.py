"""Assistant API routes - /api/v1/assistant/*

Onboarding and assistant-level endpoints that don't belong
to a specific domain module.
"""
import logging
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from ...core.auth import get_current_user, get_current_family
from ...db.session import get_db
from ...modules.conversation.models import AssistantChatSession
from ...modules.conversation.onboarding_service import (
    OnboardingService,
    OnboardingStage,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/assistant", tags=["Assistant"])


@router.get("/onboarding")
async def get_onboarding(
    db: AsyncSession = Depends(get_db),
    user_id: UUID = Depends(get_current_user),
    family_id: UUID = Depends(get_current_family),
):
    """Return onboarding stage and welcome card if applicable.

    Determines the user's onboarding stage based on registration date
    and conversation count, then returns:
      - stage: current OnboardingStage value
      - welcome_card: V8 welcome card (only during FIRST_CHAT)
      - daily_question: guided question (only during FIRST_WEEK)
      - suppress_proactive: whether to suppress proactive suggestions
    """
    from ...modules.member.models.user import User as UserModel

    # Fetch user registration date
    result = await db.execute(
        select(UserModel.created_at).where(UserModel.id == user_id)
    )
    created_at = result.scalar_one_or_none()
    if created_at is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="User not found",
        )

    from ...core.utils.timezone import utc_now

    now = utc_now()
    days_since_registration = (now - created_at).days

    # Count conversations for this user
    count_result = await db.execute(
        select(func.count()).select_from(AssistantChatSession).where(
            AssistantChatSession.user_id == user_id,
        )
    )
    conversation_count = count_result.scalar() or 0

    svc = OnboardingService()
    stage = svc.get_onboarding_stage(days_since_registration, conversation_count)

    response = {
        "stage": stage.value,
        "suppress_proactive": svc.should_suppress_proactive(stage),
    }

    if stage == OnboardingStage.FIRST_CHAT:
        response["welcome_card"] = svc.get_welcome_card()

    if stage == OnboardingStage.FIRST_WEEK:
        day_number = max(1, min(days_since_registration, 7))
        question = svc.get_daily_question(day_number)
        if question is not None:
            response["daily_question"] = question

    return response
