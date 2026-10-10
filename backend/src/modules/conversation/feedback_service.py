"""Message-level feedback service.

Handles thumbs-up/down feedback on assistant messages by updating
the message_metadata JSONB column on ConversationMessage.

This is distinct from the memory module's FeedbackService which handles
insight-level feedback (InsightFeedback model).
"""

from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from .models import AssistantChatSession, ConversationMessage

logger = get_logger(__name__)


class MessageFeedbackService:
    """Service for recording thumbs-up/down feedback on messages."""

    VALID_FEEDBACK = ("positive", "negative")

    def __init__(self, db: AsyncSession):
        self._db = db

    async def submit_feedback(
        self,
        message_id: UUID,
        user_id: UUID,
        feedback: str,
        reason: Optional[str] = None,
    ) -> None:
        """Submit feedback for a message.

        Args:
            message_id: The message to rate.
            user_id: The user submitting feedback (used for ownership check).
            feedback: Either "positive" or "negative".
            reason: Optional free-text reason.

        Raises:
            ValueError: If feedback value is invalid.
            LookupError: If message not found or user has no access.
        """
        if feedback not in self.VALID_FEEDBACK:
            raise ValueError(
                f"Invalid feedback value: {feedback!r}. "
                f"Must be one of {self.VALID_FEEDBACK}"
            )

        message = await self._get_message_for_user(message_id, user_id)
        if message is None:
            raise LookupError(
                f"Message {message_id} not found or access denied"
            )

        meta = dict(message.message_metadata or {})
        meta["feedback"] = feedback
        if reason:
            meta["feedback_reason"] = reason
        else:
            meta.pop("feedback_reason", None)

        message.message_metadata = meta
        await self._db.commit()

        logger.info(
            "Message feedback recorded: message=%s, feedback=%s",
            message_id,
            feedback,
        )

    async def get_feedback(
        self,
        message_id: UUID,
        user_id: UUID,
    ) -> Optional[dict]:
        """Get existing feedback for a message.

        Returns:
            Dict with 'feedback' and optional 'feedback_reason', or None.
        """
        message = await self._get_message_for_user(message_id, user_id)
        if message is None:
            return None

        meta = message.message_metadata or {}
        fb = meta.get("feedback")
        if fb is None:
            return None

        result = {"feedback": fb}
        reason = meta.get("feedback_reason")
        if reason:
            result["feedback_reason"] = reason
        return result

    async def _get_message_for_user(
        self,
        message_id: UUID,
        user_id: UUID,
    ) -> Optional[ConversationMessage]:
        """Load a message, verifying the user owns the session."""
        result = await self._db.execute(
            select(ConversationMessage)
            .join(
                AssistantChatSession,
                ConversationMessage.session_id == AssistantChatSession.id,
            )
            .where(
                ConversationMessage.id == message_id,
                AssistantChatSession.user_id == user_id,
            )
        )
        return result.scalar_one_or_none()
