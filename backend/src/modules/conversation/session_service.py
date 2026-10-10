"""Session lifecycle management — create, reuse, archive, force-new.

Implements the 4-hour auto-new policy: if last_active_at >= 4h ago,
the old session is archived and a new one is created.

Session Lifecycle:
    User sends message
        -> get_or_create_session()
        -> last_active_at < 4h: reuse
        -> last_active_at >= 4h: archive old + create new
            -> archive triggers memory extraction (best-effort)
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone as tz
from typing import List, Optional, Tuple
from uuid import UUID

from sqlalchemy import select, update, desc, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AssistantChatSession, ConversationMessage
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)

SESSION_TIMEOUT_HOURS = 4


class SessionService:
    """Manages session lifecycle with automatic timeout-based archival."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_or_create_session(
        self,
        user_id: UUID,
        family_id: UUID,
        session_id: Optional[UUID] = None,
    ) -> Tuple[AssistantChatSession, bool]:
        """Get active session or create a new one.

        Returns (session, is_new_session).
        """
        existing = await self._find_active_session(user_id, session_id)

        if existing is not None:
            if self._is_session_expired(existing):
                logger.info(
                    "Session %s expired (last_active: %s), archiving",
                    existing.id,
                    existing.last_active_at,
                )
                await self.archive_session(existing.id, user_id, family_id)
                new_session = await self._create_session(user_id, family_id)
                return new_session, True

            return existing, False

        new_session = await self._create_session(user_id, family_id)
        return new_session, True

    async def force_new_session(
        self,
        user_id: UUID,
        family_id: UUID,
    ) -> AssistantChatSession:
        """Force-create a new session, archiving any current one."""
        existing = await self._find_active_session(user_id, session_id=None)
        if existing is not None:
            await self.archive_session(existing.id, user_id, family_id)
        return await self._create_session(user_id, family_id)

    async def archive_session(
        self,
        session_id: UUID,
        user_id: UUID,
        family_id: UUID,
    ) -> None:
        """Archive a session and trigger memory extraction."""
        now = utc_now()
        await self._db.execute(
            update(AssistantChatSession)
            .where(AssistantChatSession.id == session_id)
            .values(status="archived", archived_at=now, updated_at=now)
        )
        await self._db.flush()
        logger.info("Archived session %s", session_id)

        await self._extract_memories_background(session_id, user_id, family_id)
        # Post-Session Reflection: fire-and-forget focused curation
        await self._trigger_post_session_reflection(session_id, user_id, family_id)

    async def get_history_messages(
        self,
        user_id: UUID,
        before_timestamp: Optional[datetime] = None,
        before_id: Optional[UUID] = None,
        limit: int = 20,
    ) -> List[dict]:
        """Lazy-load history messages across sessions for app display."""
        query = (
            select(ConversationMessage)
            .join(
                AssistantChatSession,
                ConversationMessage.session_id == AssistantChatSession.id,
            )
            .where(AssistantChatSession.user_id == user_id)
        )

        if before_id is not None:
            cursor_result = await self._db.execute(
                select(ConversationMessage.created_at).where(
                    ConversationMessage.id == before_id
                )
            )
            cursor_ts = cursor_result.scalar_one_or_none()
            if cursor_ts is not None:
                query = query.where(
                    ConversationMessage.created_at < cursor_ts
                )
        elif before_timestamp is not None:
            query = query.where(
                ConversationMessage.created_at < before_timestamp
            )

        query = query.order_by(desc(ConversationMessage.created_at)).limit(
            limit
        )

        result = await self._db.execute(query)
        messages = list(result.scalars().all())

        output: List[dict] = []
        prev_session_id: Optional[UUID] = None

        for msg in reversed(messages):
            if (
                prev_session_id is not None
                and msg.session_id != prev_session_id
            ):
                divider_data = self._format_divider_label(msg.created_at)
                output.append(
                    {
                        "type": "session_divider",
                        "label": divider_data["label"],
                        "timestamp": divider_data["timestamp"],
                        "session_id": str(msg.session_id),
                    }
                )
            output.append(msg.to_dict())
            prev_session_id = msg.session_id

        return output

    async def get_context_before_message(
        self,
        message_id: UUID,
        user_id: UUID,
    ) -> Optional[dict]:
        """Load context needed to regenerate a response."""
        result = await self._db.execute(
            select(ConversationMessage).where(
                ConversationMessage.id == message_id
            )
        )
        target_msg = result.scalar_one_or_none()
        if target_msg is None:
            return None

        session_result = await self._db.execute(
            select(AssistantChatSession).where(
                AssistantChatSession.id == target_msg.session_id,
                AssistantChatSession.user_id == user_id,
            )
        )
        session = session_result.scalar_one_or_none()
        if session is None:
            return None

        if target_msg.role == "assistant":
            user_msg_result = await self._db.execute(
                select(ConversationMessage)
                .where(
                    ConversationMessage.session_id == target_msg.session_id,
                    ConversationMessage.role == "user",
                    ConversationMessage.created_at <= target_msg.created_at,
                )
                .order_by(desc(ConversationMessage.created_at))
                .limit(1)
            )
            user_msg = user_msg_result.scalar_one_or_none()
            user_content = user_msg.content if user_msg else ""
        else:
            user_content = target_msg.content

        return {
            "session_id": str(target_msg.session_id),
            "message_id": str(target_msg.id),
            "user_message": user_content,
            "path_type": target_msg.path_type or "slow",
        }

    async def mark_message_superseded(self, message_id: UUID) -> None:
        """Mark a message as superseded (replaced by regeneration)."""
        from sqlalchemy import update as sql_update

        await self._db.execute(
            sql_update(ConversationMessage)
            .where(ConversationMessage.id == message_id)
            .values(
                message_metadata=func.coalesce(
                    ConversationMessage.message_metadata,
                    func.cast("{}", JSONB),
                ).concat(func.cast('{"superseded": true}', JSONB))
            )
        )
        await self._db.flush()

    # ── Private helpers ──────────────────────────────────────────────

    def _is_session_expired(self, session: AssistantChatSession) -> bool:
        if session.last_active_at is None:
            return True
        now = utc_now()
        last_active = session.last_active_at
        if last_active.tzinfo is None:
            last_active = last_active.replace(tzinfo=tz.utc)
        threshold = timedelta(hours=SESSION_TIMEOUT_HOURS)
        return (now - last_active) >= threshold

    async def _find_active_session(
        self,
        user_id: UUID,
        session_id: Optional[UUID],
    ) -> Optional[AssistantChatSession]:
        if session_id is not None:
            result = await self._db.execute(
                select(AssistantChatSession).where(
                    AssistantChatSession.id == session_id,
                    AssistantChatSession.user_id == user_id,
                    AssistantChatSession.status == "active",
                )
            )
            session = result.scalar_one_or_none()
            if session is not None:
                return session

        result = await self._db.execute(
            select(AssistantChatSession)
            .where(
                AssistantChatSession.user_id == user_id,
                AssistantChatSession.status == "active",
            )
            .order_by(desc(AssistantChatSession.last_active_at))
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _create_session(
        self,
        user_id: UUID,
        family_id: UUID,
    ) -> AssistantChatSession:
        now = utc_now()
        session = AssistantChatSession(
            user_id=user_id,
            family_id=family_id,
            status="active",
            started_at=now,
            last_active_at=now,
            message_count=0,
            created_at=now,
            updated_at=now,
        )
        self._db.add(session)
        await self._db.flush()
        await self._db.refresh(session)
        logger.info(
            "Created new session %s for user %s", session.id, user_id
        )
        return session


    async def _trigger_post_session_reflection(
        self,
        session_id: UUID,
        user_id: UUID,
        family_id: UUID,
    ) -> None:
        """Dispatch Post-Session Reflection Celery task (fire-and-forget)."""
        try:
            from ..curation.tasks import post_session_reflection_task
            post_session_reflection_task.delay(
                str(session_id), str(user_id), str(family_id)
            )
            logger.debug(
                "Dispatched post_session_reflection for session %s", session_id
            )
        except Exception as exc:
            logger.warning(
                "post_session_reflection dispatch failed for session %s: %s",
                session_id,
                exc,
            )

    _MEMORY_EXTRACTION_TIMEOUT_SECONDS = 30

    async def _extract_memories_background(
        self,
        session_id: UUID,
        user_id: UUID,
        family_id: UUID,
    ) -> None:
        ok = await self._extract_memories(session_id, user_id, family_id)
        if not ok:
            logger.warning(
                "Memory extraction failed for session %s", session_id
            )

    async def _extract_memories(
        self,
        session_id: UUID,
        user_id: UUID,
        family_id: UUID,
    ) -> bool:
        try:
            from ...db.session import get_db_session
            from ..memory.bridge import MemoryBridge

            async with get_db_session() as db:
                bridge = MemoryBridge(db)
                count = await asyncio.wait_for(
                    bridge.on_session_archive(
                        session_id=session_id,
                        user_id=user_id,
                        family_id=family_id,
                    ),
                    timeout=self._MEMORY_EXTRACTION_TIMEOUT_SECONDS,
                )
            logger.info(
                "Memory extraction completed for session %s: %d memories",
                session_id,
                count,
            )
            return True
        except ImportError:
            logger.warning(
                "MemoryBridge not available, skipping extraction for session %s",
                session_id,
            )
            return False
        except asyncio.TimeoutError:
            logger.error(
                "Memory extraction timed out after %ds for session %s",
                self._MEMORY_EXTRACTION_TIMEOUT_SECONDS,
                session_id,
            )
            return False
        except Exception as e:
            logger.error(
                "Memory extraction failed for session %s: %s",
                session_id,
                e,
            )
            return False

    async def save_async_push_message(
        self,
        user_id: UUID,
        family_id: UUID,
        content: str,
        async_source: str,
    ) -> Optional[ConversationMessage]:
        """Save an async push message (briefing/discovery/reminder)."""
        try:
            session, _ = await self.get_or_create_session(user_id, family_id)
            await self._db.flush()

            from .message_service import MessageService

            saver = MessageService(self._db)
            msg = await saver.save_assistant_message(
                session_id=session.id,
                content=content,
                path_type="async",
                metadata={"async_source": async_source},
            )
            await self._db.commit()

            try:
                from ...core.pubsub import (
                    get_pubsub_manager,
                    PubSubMessage,
                    MessageType,
                )

                pubsub = get_pubsub_manager()
                await pubsub.connect()
                await pubsub.publish(
                    user_id=str(user_id),
                    message=PubSubMessage(
                        user_id=str(user_id),
                        message_type=MessageType.COMPLETE,
                        payload={
                            "content": content,
                            "is_final": True,
                            "session_id": str(session.id),
                            "message_id": str(msg.id),
                            "async_source": async_source,
                        },
                        trace_id=f"async-{async_source}-{msg.id}",
                    ),
                )
            except Exception as ws_err:
                logger.warning(
                    "Failed to publish async push WS notification: %s",
                    ws_err,
                )

            logger.info(
                "Saved async push message: user=%s, source=%s, msg_id=%s",
                user_id,
                async_source,
                msg.id,
            )
            return msg
        except Exception as e:
            logger.error(
                "Failed to save async push message: user=%s, source=%s, error=%s",
                user_id,
                async_source,
                e,
            )
            return None

    @staticmethod
    def _format_divider_label(dt: Optional[datetime]) -> dict:
        if dt is None:
            return {"label": "\u2500\u2500 \u65b0\u4f1a\u8bdd \u2500\u2500", "timestamp": None}
        return {
            "label": f"\u2500\u2500 \u65b0\u4f1a\u8bdd \u00b7 {dt.month}\u6708{dt.day}\u65e5 {dt.strftime('%H:%M')} \u2500\u2500",
            "timestamp": dt.isoformat(),
        }
