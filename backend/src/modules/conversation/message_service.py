"""Unified message persistence with concurrency control.

All paths (Fast, Slow, Hybrid) save messages through this service,
ensuring consistent sequence_number, path_type, and tool_calls tracking.
"""

import asyncio
import logging
import time
from datetime import datetime, timezone as tz
from typing import Any, Dict, List, Optional, Tuple
from uuid import UUID, uuid4

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession

from .models import AssistantChatSession, ConversationMessage
from ...core.utils.timezone import utc_now

logger = logging.getLogger(__name__)


class MessageService:
    """Unified message saving across all routing paths."""

    def __init__(self, db: AsyncSession):
        self._db = db

    async def save_user_message(
        self,
        session_id: UUID,
        content: str,
        path_type: str = "fast",
        intent: Optional[str] = None,
        entities: Optional[dict] = None,
        metadata: Optional[dict] = None,
    ) -> ConversationMessage:
        """Save a user message with sequence number and path type."""
        seq = await self._next_sequence_number(session_id)
        message = ConversationMessage(
            session_id=session_id,
            role="user",
            content=content,
            intent=intent,
            entities=entities,
            message_metadata=metadata,
            sequence_number=seq,
            path_type=path_type,
        )
        self._db.add(message)
        await self._update_session_activity(session_id)
        await self._db.flush()
        await self._db.refresh(message)
        # C5: Invalidate context cache so subsequent requests see this message
        await self._invalidate_context_cache(session_id)
        return message

    async def save_assistant_message(
        self,
        session_id: UUID,
        content: str,
        path_type: str = "fast",
        tool_calls: Optional[List[Dict[str, Any]]] = None,
        intent: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> ConversationMessage:
        """Save an assistant message with tool call summaries."""
        seq = await self._next_sequence_number(session_id)
        message = ConversationMessage(
            session_id=session_id,
            role="assistant",
            content=content,
            intent=intent,
            message_metadata=metadata,
            sequence_number=seq,
            path_type=path_type,
            tool_calls=tool_calls,
        )
        self._db.add(message)
        await self._update_session_activity(session_id)
        await self._db.flush()
        await self._db.refresh(message)
        # C5: Invalidate context cache so subsequent requests see this message
        await self._invalidate_context_cache(session_id)
        return message

    async def get_history(
        self,
        session_id: UUID,
        limit: int = 50,
        before: Optional[datetime] = None,
        before_id: Optional[UUID] = None,
    ) -> Tuple[List[ConversationMessage], bool]:
        """Retrieve message history for a session.

        Returns a tuple of (messages, has_more) where has_more indicates
        there may be additional messages before the returned set.
        Prefers cursor-based pagination via before_id over timestamp-based
        pagination via before when both are provided.
        """
        query = select(ConversationMessage).where(
            ConversationMessage.session_id == session_id
        )

        if before_id is not None:
            # Look up the sequence_number of the cursor message.
            cursor_result = await self._db.execute(
                select(
                    ConversationMessage.sequence_number,
                    ConversationMessage.created_at,
                ).where(
                    ConversationMessage.id == before_id,
                    ConversationMessage.session_id == session_id,
                )
            )
            cursor_row = cursor_result.one_or_none()
            if cursor_row is not None:
                cursor_seq, cursor_ts = cursor_row
                if cursor_seq is not None:
                    query = query.where(
                        ConversationMessage.sequence_number < cursor_seq
                    )
                    query = query.order_by(
                        ConversationMessage.sequence_number.desc()
                    ).limit(limit)
                    result = await self._db.execute(query)
                    messages = list(result.scalars().all())
                    has_more = len(messages) == limit
                    return list(reversed(messages)), has_more
                else:
                    # sequence_number not set on cursor row — fall back to created_at
                    query = query.where(
                        ConversationMessage.created_at < cursor_ts
                    )
            # If cursor message not found, fall through without any extra filter.

        elif before is not None:
            query = query.where(ConversationMessage.created_at < before)

        query = query.order_by(ConversationMessage.created_at.desc()).limit(
            limit
        )
        result = await self._db.execute(query)
        messages = list(result.scalars().all())
        has_more = len(messages) == limit
        return list(reversed(messages)), has_more

    async def _next_sequence_number(self, session_id: UUID) -> int:
        """Get next sequence number via an autonomous micro-transaction.

        Uses a **separate short-lived DB session** to atomically increment
        ``message_count`` on the session row.  The micro-transaction commits
        immediately, so the row-level lock lives for <1 ms and never spills
        into the caller's (potentially long-lived) outer transaction.

        After the micro-tx, cross-validates against the actual
        ``MAX(sequence_number)`` in the messages table.  If ``message_count``
        drifted (e.g. a previous save used the fallback path without updating
        the counter, or a pre-migration session started at 0), the returned
        value is corrected to ``MAX + 1`` and ``message_count`` is repaired
        in a follow-up micro-tx.
        """
        from ...db.session import async_session_maker

        seq: Optional[int] = None
        try:
            async with async_session_maker() as seq_db:
                result = await seq_db.execute(
                    update(AssistantChatSession)
                    .where(AssistantChatSession.id == session_id)
                    .values(
                        message_count=func.coalesce(
                            AssistantChatSession.message_count, 0
                        )
                        + 1,
                    )
                    .returning(AssistantChatSession.message_count)
                )
                seq = result.scalar()
                await seq_db.commit()
        except Exception:
            logger.warning(
                "Micro-tx sequence failed for session %s, falling back",
                session_id,
                exc_info=True,
            )

        # Cross-validate: ensure seq doesn't collide with existing messages.
        actual_max_result = await self._db.execute(
            select(
                func.coalesce(
                    func.max(ConversationMessage.sequence_number), 0
                )
            ).where(ConversationMessage.session_id == session_id)
        )
        actual_max = actual_max_result.scalar() or 0

        if seq is not None and seq > actual_max:
            return seq

        # Desync detected (or micro-tx failed): use MAX + 1 and repair counter.
        corrected = actual_max + 1
        logger.warning(
            "Sequence desync for session %s: micro_tx_seq=%s actual_max=%d corrected=%d",
            session_id,
            seq,
            actual_max,
            corrected,
        )
        try:
            async with async_session_maker() as fix_db:
                await fix_db.execute(
                    update(AssistantChatSession)
                    .where(AssistantChatSession.id == session_id)
                    .values(message_count=corrected)
                )
                await fix_db.commit()
        except Exception:
            logger.warning(
                "Failed to repair message_count for session %s",
                session_id,
                exc_info=True,
            )

        return corrected


    async def _update_session_activity(self, session_id: UUID) -> None:
        """Update session timestamps.  message_count is already incremented
        atomically by ``_next_sequence_number``, so only timestamps are
        updated here to avoid double-counting.
        """
        now = utc_now()
        await self._db.execute(
            update(AssistantChatSession)
            .where(AssistantChatSession.id == session_id)
            .values(
                last_active_at=now,
                updated_at=now,
            )
        )

    async def _invalidate_context_cache(self, session_id: UUID) -> None:
        """C5: Invalidate ContextAssembler cache after message writes.

        Queries the session's user_id and delegates to ContextAssembler.
        Best-effort — failures are logged but do not propagate.
        """
        try:
            result = await self._db.execute(
                select(AssistantChatSession.user_id).where(
                    AssistantChatSession.id == session_id
                )
            )
            user_id = result.scalar_one_or_none()
            if user_id is None:
                return
            from ...ai_engine.context_assembler import ContextAssembler
            await ContextAssembler.invalidate_context_cache(user_id)
        except Exception:
            logger.debug(
                "C5: Failed to invalidate context cache for session %s",
                session_id,
                exc_info=True,
            )


class SessionLock:
    """Redis-based distributed lock for session-level concurrency control."""

    _RELEASE_SCRIPT = """
    if redis.call("get", KEYS[1]) == ARGV[1] then
        return redis.call("del", KEYS[1])
    else
        return 0
    end
    """

    def __init__(self, redis_client, session_id: UUID, timeout: int = 300):
        self._redis = redis_client
        self._key = f"session:lock:{session_id}"
        self._timeout = timeout
        self._owner = str(uuid4())

    async def _resolve_client(self):
        if self._redis is None:
            return None
        if hasattr(self._redis, "client"):
            client = getattr(self._redis, "client", None)
            if client is None and hasattr(self._redis, "connect"):
                try:
                    await self._redis.connect()
                    client = getattr(self._redis, "client", None)
                except Exception:
                    client = None
            if client is not None:
                return client
        return self._redis

    async def acquire(self, blocking: bool = True) -> bool:
        client = await self._resolve_client()
        if client is None:
            return True

        try:

            async def _try_set() -> bool:
                try:
                    result = await client.set(
                        self._key, self._owner, nx=True, ex=self._timeout
                    )
                except TypeError:
                    result = await client.set(self._key, self._owner)
                    try:
                        await client.expire(self._key, self._timeout)
                    except Exception:
                        pass
                return bool(result)

            if blocking:
                if await _try_set():
                    return True
                deadline = asyncio.get_event_loop().time() + 5.0
                wait = 0.1
                while asyncio.get_event_loop().time() < deadline:
                    await asyncio.sleep(wait)
                    if await _try_set():
                        return True
                    wait = min(wait * 1.5, 0.5)
                return False
            else:
                return await _try_set()
        except Exception as e:
            logger.error(
                "Failed to acquire session lock %s: %s", self._key, e
            )
            return not blocking

    async def release(self) -> None:
        client = await self._resolve_client()
        if client is None:
            return
        try:
            try:
                await client.eval(
                    self._RELEASE_SCRIPT, 1, self._key, self._owner
                )
            except AttributeError:
                value = await client.get(self._key)
                if value == self._owner:
                    await client.delete(self._key)
        except Exception as e:
            logger.warning(
                "Failed to release session lock %s: %s", self._key, e
            )
