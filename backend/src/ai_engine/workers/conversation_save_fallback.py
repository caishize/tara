"""Fallback conversation saver using direct ORM.

Used when UnifiedMessageSaver fails, to ensure the assistant
response is always persisted.
"""

import logging
from datetime import datetime, timezone

from ...core.utils.timezone import utc_now
from typing import Any, Dict, List, Optional
from uuid import UUID

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)


async def save_conversation_fallback(
    db: AsyncSession,
    user_id: str,
    family_id: str,
    session_id: Optional[str],
    job_id: Optional[str],
    route_type: Optional[str],
    user_input: str,
    collected_text: List[str],
    collected_tool_calls: List[Dict[str, Any]],
) -> None:
    """Save conversation to database using direct ORM (fallback path).

    This bypasses UnifiedMessageSaver and writes directly via SQLAlchemy
    when the primary saver encounters an error.
    """
    # Normalize path_type: hybrid_background → hybrid (column is VARCHAR(10))
    _PATH_TYPE_MAP = {"hybrid_background": "hybrid"}
    normalized_route_type = _PATH_TYPE_MAP.get(route_type, route_type) if route_type else "slow"

    try:
        # Rollback any prior failed transaction on this session
        await db.rollback()

        from ...modules.conversation.models import (
            AssistantChatSession,
            ConversationMessage,
        )

        session = None
        if session_id:
            try:
                session_uuid = UUID(session_id)
                result = await db.execute(
                    select(AssistantChatSession)
                    .where(AssistantChatSession.id == session_uuid)
                )
                session = result.scalar_one_or_none()
            except (ValueError, AttributeError):
                pass

        if not session:
            result = await db.execute(
                select(AssistantChatSession)
                .where(AssistantChatSession.user_id == UUID(user_id))
                .order_by(AssistantChatSession.created_at.desc())
                .limit(1)
            )
            session = result.scalar_one_or_none()

        if not session:
            session = AssistantChatSession(
                user_id=UUID(user_id),
                family_id=UUID(family_id),
                title=user_input[:50],
            )
            db.add(session)
            await db.flush()

        seq_result = await db.execute(
            select(func.coalesce(func.max(ConversationMessage.sequence_number), 0))
            .where(ConversationMessage.session_id == session.id)
        )
        next_seq = (seq_result.scalar() or 0) + 1

        assistant_content = "".join(collected_text)
        if assistant_content or collected_tool_calls:
            assistant_msg = ConversationMessage(
                session_id=session.id,
                role="assistant",
                content=assistant_content,
                sequence_number=next_seq,
                path_type=normalized_route_type,
                tool_calls=collected_tool_calls if collected_tool_calls else None,
                message_metadata={
                    "job_id": job_id,
                    "route_type": route_type,
                },
            )
            db.add(assistant_msg)

        now = utc_now()
        await db.execute(
            update(AssistantChatSession)
            .where(AssistantChatSession.id == session.id)
            .values(
                last_active_at=now,
                updated_at=now,
                message_count=next_seq,
            )
        )

        await db.commit()
        logger.debug("Saved conversation via fallback for job_id=%s", job_id)

    except Exception as e:
        logger.warning("Fallback conversation save failed: %s", e)
