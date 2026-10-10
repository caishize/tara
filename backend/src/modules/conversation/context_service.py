"""Context rehydration + compression for ephemeral agent workers.

Combines context_rehydration_service and context_compression_service
into a single focused module. Only lightweight data is preloaded;
business data (trips, memories, schedules) is fetched on-demand via tools.
"""

import asyncio
import logging
from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone as tz
from typing import Any, Dict, List, Optional, TYPE_CHECKING
from uuid import UUID

from sqlalchemy import select, desc, func, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from ...config.settings import settings
from ...config.logging import get_logger
from ...core.utils.timezone import utc_now, DEFAULT_TIMEZONE_NAME
from .models import (
    AssistantChatSession,
    ConversationMessage,
    SessionSummary,
)

from anthropic import AsyncAnthropic

if TYPE_CHECKING:
    from ...ai_engine.agent_context import AgentContext

logger = get_logger(__name__)

# Compression thresholds
MIN_MESSAGES_FOR_COMPRESSION = 10

# Default active-window size (replaced by compute_window_size for dynamic sizing)
_DEFAULT_WINDOW_SIZE = 10
_MAX_WINDOW_SIZE = 25

# Intent categories that increase the active window
_COMPLEX_INTENTS = frozenset({
    "complex_analysis",
    "trip_planning",
    "schedule_planning",
    "conflict_resolution",
    "gift_recommendation",
})


def compute_window_size(
    intent_classification: Optional[str] = None,
    active_tool_count: int = 0,
) -> int:
    """Compute the number of recent messages to keep in the active window.

    The window expands beyond the base of 10 when the current turn is
    complex (needs more prior context) or when many tools are active
    (tool-call / tool-result pairs consume message slots).

    Rules (additive):
        base                              = 10
        complex / multi-step intents      + 5
        active_tool_count >= 3            + 5
        active_tool_count >= 5            + 5  (additional)
        cap                               = 25
    """
    base = _DEFAULT_WINDOW_SIZE

    if intent_classification and intent_classification in _COMPLEX_INTENTS:
        base += 5

    if active_tool_count >= 3:
        base += 5
    if active_tool_count >= 5:
        base += 5

    return min(_MAX_WINDOW_SIZE, base)


@dataclass(frozen=True)
class RehydratedContext:
    """Complete rehydrated context for ephemeral agent workers."""

    user_profile: Dict[str, Any]
    family_members_raw: List[Dict[str, Any]]
    recent_messages: List[Dict[str, Any]]
    user_preferences: Dict[str, Any]
    # Identity fields set by build_context()
    _user_id: Optional[UUID] = None
    _family_id: Optional[UUID] = None
    _session_id: Optional[str] = None
    data_summary: Dict[str, int] = field(default_factory=dict)
    cross_session_memories: str = ""
    person_profiles: str = ""
    # Optional preface inserted before normal conversation context.
    # Used by Fast→Slow upgrade to carry forward condensed prior reasoning.
    conversation_preface: str = ""
    compressed_summary: Optional[str] = None
    rehydration_time_ms: float = 0.0

    @property
    def agent_context(self) -> "AgentContext":
        """Build an AgentContext from the rehydrated raw data."""
        from ...ai_engine.agent_context import AgentContext, FamilyMemberInfo

        family_members = []
        for m in self.family_members_raw:
            mid = m.get("id", UUID(int=0))
            if isinstance(mid, str):
                mid = UUID(mid)
            family_members.append(FamilyMemberInfo(
                id=mid,
                name=m.get("name", ""),
                nickname=m.get("nickname"),
                relation_type=m.get("relation_type"),
                age=m.get("age"),
                gender=m.get("gender"),
            ))

        return AgentContext(
            family_id=self._family_id or UUID(int=0),
            user_id=self._user_id or UUID(int=0),
            session_id=self._session_id or "",
            timezone=self.user_preferences.get("timezone", DEFAULT_TIMEZONE_NAME),
            family_members=family_members,
            data_summary=self.data_summary or {},
            conversation_summary=self._build_conversation_context(),
        )

    def _build_conversation_context(self) -> str:
        """Build full session context text from compression summary + tail messages."""
        sections: List[str] = []
        if self.conversation_preface:
            sections.append(self.conversation_preface)
        if self.compressed_summary:
            sections.append(f"【历史压缩摘要】\n{self.compressed_summary}")
        if self.recent_messages:
            lines: List[str] = []
            for msg in self.recent_messages:
                role = msg.get("role")
                content = (msg.get("content") or "").strip()
                if not content or role not in ("user", "assistant"):
                    continue
                role_label = "用户" if role == "user" else "助手"
                lines.append(f"{role_label}: {content}")
            if lines:
                sections.append("【压缩点之后的完整会话】\n" + "\n".join(lines))
        return "\n\n".join(sections)

    def with_conversation_preface(self, preface: str) -> "RehydratedContext":
        """Return a new context with preface prepended to conversation context."""
        text = (preface or "").strip()
        if not text:
            return self
        merged = (
            text
            if not self.conversation_preface
            else f"{text}\n\n{self.conversation_preface}"
        )
        return replace(self, conversation_preface=merged)


class ContextService:
    """Context rehydration and compression for sessions.

    For rehydration, pass in an async_sessionmaker so the service
    can open its own DB sessions (agent workers run off-request).

    For compression, use compress_if_needed() with a direct session.
    """

    def __init__(
        self,
        session_factory: Optional[async_sessionmaker] = None,
        db: Optional[AsyncSession] = None,
        client: Optional[AsyncAnthropic] = None,
    ):
        self._session_factory = session_factory
        self._db = db
        self._client = client

    # ── Compression ──────────────────────────────────────────────────

    async def build_compressed_history(
        self,
        session_id: UUID,
        user_id: UUID,
    ) -> List[Dict[str, str]]:
        """Build message history with compression applied."""
        db = self._db
        if db is None:
            raise ValueError("db required for compression operations")

        summary = await self._get_summary(db, session_id)

        if summary is not None:
            messages = await self._get_messages_after(
                db, session_id, summary.compressed_up_to
            )
        else:
            messages = await self._get_all_messages(db, session_id)

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
            if msg.role in ("user", "assistant")
        ]

    async def get_summary_text(self, session_id: UUID) -> Optional[str]:
        db = self._db
        if db is None:
            raise ValueError("db required for compression operations")
        summary = await self._get_summary(db, session_id)
        return summary.content if summary is not None else None

    async def compress_if_needed(
        self,
        session_id: UUID,
        user_id: UUID,
        family_id: UUID,
        intent_classification: Optional[str] = None,
        active_tool_count: int = 0,
    ) -> bool:
        """Perform rolling compression if message count exceeds threshold."""
        db = self._db
        if db is None:
            raise ValueError("db required for compression operations")

        total_count = await self._count_messages(db, session_id)
        if total_count <= MIN_MESSAGES_FOR_COMPRESSION:
            return False

        summary = await self._get_summary(db, session_id)
        compressed_up_to = summary.compressed_up_to if summary else 0

        uncompressed = await self._get_messages_after(
            db, session_id, compressed_up_to
        )
        if len(uncompressed) <= MIN_MESSAGES_FOR_COMPRESSION:
            return False

        window = compute_window_size(intent_classification, active_tool_count)
        messages_to_compress = uncompressed[:-window]
        if not messages_to_compress:
            return False

        existing_summary = summary.content if summary else None
        new_summary = await self._generate_summary(
            existing_summary, messages_to_compress
        )
        if new_summary is None:
            return False

        last_compressed_seq = max(
            (m.sequence_number or 0) for m in messages_to_compress
        )
        token_estimate = len(new_summary) // 2

        if summary is not None:
            await db.execute(
                update(SessionSummary)
                .where(SessionSummary.session_id == summary.session_id)
                .values(
                    content=new_summary,
                    compressed_up_to=last_compressed_seq,
                    token_count=token_estimate,
                )
            )
        else:
            new_record = SessionSummary(
                session_id=session_id,
                user_id=user_id,
                family_id=family_id,
                content=new_summary,
                compressed_up_to=last_compressed_seq,
                token_count=token_estimate,
            )
            db.add(new_record)

        await db.commit()
        logger.info(
            "Compressed session %s: %d messages -> summary (%d tokens)",
            session_id,
            len(messages_to_compress),
            token_estimate,
        )
        return True

    # ── Rehydration ──────────────────────────────────────────────────

    async def build_context(
        self,
        user_id: UUID,
        family_id: UUID,
        session_id: Optional[str] = None,
        max_conversation_turns: int = 20,
        timezone: str = DEFAULT_TIMEZONE_NAME,
    ) -> RehydratedContext:
        """Build lightweight context for agent from database."""
        if self._session_factory is None:
            raise ValueError(
                "session_factory required for rehydration operations"
            )

        start_time = utc_now()

        _fetch_names = [
            "user_profile",
            "family_members",
            "recent_messages",
            "data_summary",
            "user_preferences",
            "compressed_summary",
            "cross_session_memories",
            "person_profiles",
        ]
        _raw_results = await asyncio.gather(
            self._fetch_user_profile(user_id),
            self._fetch_family_members(family_id),
            self._fetch_recent_messages(
                user_id, session_id, max_conversation_turns
            ),
            self._fetch_data_summary(family_id, user_id),
            self._fetch_user_preferences(user_id),
            self._fetch_compressed_summary(session_id),
            self._fetch_cross_session_memories(user_id, family_id),
            self._fetch_person_profiles(user_id, family_id),
            return_exceptions=True,
        )

        _safe_results = []
        for i, result in enumerate(_raw_results):
            if isinstance(result, BaseException):
                logger.warning(
                    "Rehydration fetch '%s' failed: %s",
                    _fetch_names[i],
                    result,
                )
                _safe_results.append(None)
            else:
                _safe_results.append(result)

        (
            user_profile,
            family_members,
            recent_messages,
            data_summary,
            user_preferences,
            compressed_summary,
            cross_session_memories,
            person_profiles,
        ) = _safe_results

        end_time = utc_now()
        rehydration_time_ms = (end_time - start_time).total_seconds() * 1000

        return RehydratedContext(
            user_profile=user_profile or {},
            family_members_raw=family_members or [],
            recent_messages=recent_messages or [],
            user_preferences=user_preferences or {},
            _user_id=user_id,
            _family_id=family_id,
            _session_id=session_id,
            data_summary=data_summary or {},
            cross_session_memories=cross_session_memories or "",
            person_profiles=person_profiles or "",
            compressed_summary=compressed_summary,
            rehydration_time_ms=rehydration_time_ms,
        )

    async def get_message_history_for_api(
        self,
        user_id: UUID,
        session_id: Optional[str],
        limit: int = 20,
    ) -> List[Dict[str, str]]:
        """Get message history formatted for Anthropic API."""
        if session_id and self._session_factory:
            try:
                async with self._session_factory() as session:
                    ctx = ContextService(db=session)
                    compressed = await ctx.build_compressed_history(
                        session_id=(
                            UUID(session_id)
                            if isinstance(session_id, str)
                            else session_id
                        ),
                        user_id=user_id,
                    )
                    if compressed:
                        return [
                            m
                            for m in compressed
                            if m["role"] in ("user", "assistant")
                        ]
            except Exception as e:
                logger.debug(
                    "Compression-based history unavailable: %s", e
                )

        messages = await self._fetch_recent_messages(
            user_id, session_id, limit
        )
        return [
            {"role": m["role"], "content": m["content"]}
            for m in (messages or [])
            if m["role"] in ("user", "assistant")
        ]

    # ── Cold-start conversation rebuild ─────────────────────────────

    # Conservative chars-per-token estimate for budget enforcement.
    # Chinese text is ~1-2 chars/token, English ~4 chars/token.
    # Using 2 as a middle-ground that slightly over-budgets (safer than exceeding).
    _CHARS_PER_TOKEN = 2
    _MAX_CONTENT_CHARS = 2000

    async def build_cold_start_conversation(
        self,
        session_id: str,
        user_id: UUID,
        family_id: UUID,
        current_user_input: str,
        max_tokens: int = 20_000,
        max_days: int = 7,
    ) -> str:
        """Rebuild conversation context for a cold-started SDK CLI.

        When the backend restarts and the SDK subprocess is gone, the new
        CLI has no multi-turn state.  This method rebuilds a textual
        prompt containing the session history so that the model can
        continue the conversation seamlessly.

        Returns a formatted prompt string with history + current user input.
        If no history is available, returns just *current_user_input*.

        Note: The system prompt's L2 conversation_summary section may
        contain overlapping history.  This minor redundancy (~2k tokens)
        is intentional (Option A from the design) — simpler and lower
        risk than conditionally suppressing L2 on cold-start paths.
        """
        if self._session_factory is None:
            raise ValueError(
                "session_factory required for cold-start operations"
            )

        try:
            session_uuid = UUID(str(session_id))
        except (ValueError, AttributeError):
            return current_user_input

        budget_chars = max_tokens * self._CHARS_PER_TOKEN
        cutoff = utc_now() - timedelta(days=max_days)

        sections: List[str] = []
        used_chars = 0

        async with self._session_factory() as db:
            # 1. Try to fetch compressed summary (projected columns only)
            result = await db.execute(
                select(SessionSummary.content, SessionSummary.compressed_up_to).where(
                    SessionSummary.session_id == session_uuid
                )
            )
            row = result.one_or_none()

            if row is not None and row[0]:
                summary_text = row[0].strip()
                # Truncate summary if it alone exceeds the budget
                if len(summary_text) > budget_chars:
                    summary_text = summary_text[:budget_chars] + "..."
                sections.append(f"【对话摘要】\n{summary_text}")
                used_chars += len(summary_text) + 20

                # Fetch messages AFTER the compression watermark
                tail_messages = await self._get_messages_after(
                    db, session_uuid, row[1]
                )
            else:
                # No summary — fetch all messages within time window
                tail_messages = await self._get_session_messages_since(
                    db, session_uuid, cutoff
                )

            # 2. Format tail messages with Layer 1 tool summaries
            #    Skip superseded (edited) and partial (interrupted) messages
            if tail_messages:
                msg_lines: List[str] = []
                for msg in tail_messages:
                    if used_chars >= budget_chars:
                        break

                    if getattr(msg, "is_superseded", False):
                        continue
                    if getattr(msg, "is_partial", False):
                        continue

                    role = msg.role
                    if role not in ("user", "assistant"):
                        continue

                    content = (msg.content or "").strip()
                    if len(content) > self._MAX_CONTENT_CHARS:
                        content = content[: self._MAX_CONTENT_CHARS] + "..."

                    role_label = "用户" if role == "user" else "助手"
                    line = f"{role_label}: {content}"

                    # Append Layer 1 tool call summaries inline
                    tool_calls = msg.tool_calls
                    if tool_calls and isinstance(tool_calls, list):
                        for tc in tool_calls:
                            if not isinstance(tc, dict):
                                continue
                            tool_name = tc.get("tool_name", "unknown")
                            tool_summary = tc.get("summary", "")
                            if tool_summary:
                                line += (
                                    f"\n[工具: {tool_name} → {tool_summary}]"
                                )
                            else:
                                status = tc.get("status", "")
                                line += f"\n[工具: {tool_name} ({status})]"

                    msg_lines.append(line)
                    used_chars += len(line) + 1

                if msg_lines:
                    sections.append(
                        "【近期对话】\n" + "\n".join(msg_lines)
                    )

        # 3. If no history was found, return just the user input
        if not sections:
            return current_user_input

        # 4. Build final prompt with XML tags for structural separation
        #    (prevents user input from "escaping" into the history section)
        history_block = "\n\n".join(sections)
        return (
            f"<conversation_history>\n"
            f"{history_block}\n"
            f"</conversation_history>\n\n"
            f"<current_user_message>\n"
            f"{current_user_input}\n"
            f"</current_user_message>\n\n"
            f"请基于以上对话历史继续回复用户的最新消息。"
        )

    @staticmethod
    async def _get_session_messages_since(
        db: "AsyncSession",
        session_id: UUID,
        cutoff: datetime,
        limit: int = 100,
    ) -> List["ConversationMessage"]:
        """Fetch messages for a session created after *cutoff*, capped at *limit*."""
        result = await db.execute(
            select(ConversationMessage)
            .where(
                ConversationMessage.session_id == session_id,
                ConversationMessage.created_at >= cutoff,
            )
            .order_by(ConversationMessage.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    # ── Private compression helpers ──────────────────────────────────

    async def _generate_summary(
        self,
        existing_summary: Optional[str],
        messages: List[ConversationMessage],
    ) -> Optional[str]:
        try:
            if self._client is None:
                from ...core.llm.haiku_client import get_haiku_client
                self._client = get_haiku_client()

            conversation_text = self._format_messages_for_compression(
                messages
            )
            system_prompt = (
                "\u4f60\u662f\u4e00\u4e2a\u5bf9\u8bdd\u6458\u8981\u52a9\u624b\u3002\u8bf7\u5c06\u4ee5\u4e0b\u5bf9\u8bdd\u5185\u5bb9\u538b\u7f29\u4e3a\u7b80\u6d01\u7684\u6458\u8981\uff0c"
                "\u4fdd\u7559\u5173\u952e\u4fe1\u606f\u3001\u51b3\u7b56\u548c\u4e0a\u4e0b\u6587\u3002\n\n"
                "\u8981\u6c42\uff1a\n1. \u4fdd\u7559\u6240\u6709\u91cd\u8981\u4e8b\u5b9e\u548c\u51b3\u7b56\n"
                "2. \u4fdd\u7559\u5de5\u5177\u8c03\u7528\u7684\u5173\u952e\u7ed3\u679c\n"
                "3. \u4fdd\u7559\u7528\u6237\u7684\u504f\u597d\u548c\u9700\u6c42\n"
                "4. \u5220\u9664\u5bd2\u6684\u548c\u91cd\u590d\u5185\u5bb9\n"
                "5. \u4f7f\u7528\u7b80\u6d01\u7684\u4e2d\u6587\n"
                "6. \u4e0d\u8d85\u8fc7 500 \u5b57"
            )
            user_content = ""
            if existing_summary:
                user_content += f"## \u4e4b\u524d\u7684\u6458\u8981\n{existing_summary}\n\n"
            user_content += f"## \u9700\u8981\u538b\u7f29\u7684\u65b0\u5bf9\u8bdd\n{conversation_text}"

            compression_model = (
                settings.intent_router_model or settings.fast_worker_model
            )
            response = await self._client.messages.create(
                model=compression_model,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_content}],
            )
            if response.content and len(response.content) > 0:
                return response.content[0].text
            return None
        except Exception as e:
            logger.error("Failed to generate compression summary: %s", e)
            return None

    @staticmethod
    async def _get_summary(
        db: AsyncSession, session_id: UUID
    ) -> Optional[SessionSummary]:
        result = await db.execute(
            select(SessionSummary).where(
                SessionSummary.session_id == session_id
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _count_messages(db: AsyncSession, session_id: UUID) -> int:
        result = await db.execute(
            select(func.count())
            .select_from(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
        )
        return result.scalar() or 0

    @staticmethod
    async def _get_all_messages(
        db: AsyncSession, session_id: UUID
    ) -> List[ConversationMessage]:
        result = await db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at)
        )
        return list(result.scalars().all())

    @staticmethod
    async def _get_messages_after(
        db: AsyncSession, session_id: UUID, after_sequence: int
    ) -> List[ConversationMessage]:
        query = select(ConversationMessage).where(
            ConversationMessage.session_id == session_id
        )
        if after_sequence > 0:
            query = query.where(
                ConversationMessage.sequence_number > after_sequence
            )
        query = query.order_by(ConversationMessage.created_at)
        result = await db.execute(query)
        return list(result.scalars().all())

    @staticmethod
    def _format_messages_for_compression(
        messages: List[ConversationMessage],
    ) -> str:
        lines = []
        for msg in messages:
            role_label = "\u7528\u6237" if msg.role == "user" else "\u52a9\u624b"
            content = msg.content or ""
            tool_info = ""
            if msg.tool_calls:
                tool_names = [
                    tc.get("tool_name", "unknown")
                    for tc in (
                        msg.tool_calls
                        if isinstance(msg.tool_calls, list)
                        else []
                    )
                ]
                if tool_names:
                    tool_info = f" [\u8c03\u7528\u4e86\u5de5\u5177: {', '.join(tool_names)}]"
            lines.append(f"**{role_label}**{tool_info}: {content}")
        return "\n\n".join(lines)

    # ── Private rehydration helpers ──────────────────────────────────

    async def _fetch_user_profile(self, user_id: UUID) -> Dict[str, Any]:
        try:
            from ..member.models import User

            async with self._session_factory() as session:
                result = await session.execute(
                    select(User).where(User.id == user_id)
                )
                user = result.scalar_one_or_none()
                if user:
                    return {
                        "id": str(user.id),
                        "email": getattr(user, "email", None),
                        "name": getattr(user, "name", None),
                        "timezone": getattr(
                            user, "timezone", DEFAULT_TIMEZONE_NAME
                        ),
                    }
            return {}
        except Exception as e:
            logger.warning("Failed to fetch user profile: %s", e)
            return {}

    async def _fetch_family_members(
        self, family_id: UUID
    ) -> List[Dict[str, Any]]:
        try:
            from ..member.context_service import (
                MemberContextService,
            )

            async with self._session_factory() as session:
                service = MemberContextService(session)
                members = await service.get_all_members_for_context(
                    family_id
                )
                return members if members else []
        except Exception as e:
            logger.warning("Failed to fetch family members: %s", e)
            return []

    async def _fetch_recent_messages(
        self,
        user_id: UUID,
        session_id: Optional[str],
        limit: int,
    ) -> List[Dict[str, Any]]:
        try:
            async with self._session_factory() as session:
                session_uuid: Optional[UUID] = None
                if session_id:
                    try:
                        session_uuid = UUID(str(session_id))
                    except Exception:
                        session_uuid = None

                compressed_up_to = 0
                if session_uuid is not None:
                    summary_q = await session.execute(
                        select(SessionSummary.compressed_up_to).where(
                            SessionSummary.session_id == session_uuid
                        )
                    )
                    compressed_up_to = int(summary_q.scalar() or 0)

                query = (
                    select(ConversationMessage)
                    .join(
                        AssistantChatSession,
                        ConversationMessage.session_id
                        == AssistantChatSession.id,
                    )
                    .where(AssistantChatSession.user_id == user_id)
                )
                if session_uuid is not None:
                    query = query.where(
                        AssistantChatSession.id == session_uuid
                    )
                    if compressed_up_to > 0:
                        query = query.where(
                            ConversationMessage.sequence_number > compressed_up_to
                        )

                query = query.order_by(desc(ConversationMessage.created_at))
                if limit > 0:
                    query = query.limit(limit)

                result = await session.execute(query)
                messages = result.scalars().all()
                return [
                    {
                        "role": msg.role,
                        "content": msg.content,
                        "created_at": (
                            msg.created_at.isoformat()
                            if msg.created_at
                            else None
                        ),
                    }
                    for msg in reversed(messages)
                ]
        except Exception as e:
            logger.warning("Failed to fetch recent messages: %s", e)
            return []

    async def _fetch_data_summary(
        self, family_id: UUID, user_id: UUID
    ) -> Dict[str, int]:
        try:
            trip_count, pending_count = await asyncio.gather(
                self._count_active_trips(family_id),
                self._count_pending_actions(user_id),
            )
            return {"trips": trip_count, "pending_actions": pending_count}
        except Exception:
            return {}

    async def _count_active_trips(self, family_id: UUID) -> int:
        try:
            from ..trip.models.trip_plan import TripPlan

            async with self._session_factory() as session:
                result = await session.execute(
                    select(func.count())
                    .select_from(TripPlan)
                    .where(
                        TripPlan.family_id == family_id,
                        TripPlan.status.in_(
                            ["planning", "confirmed", "in_progress"]
                        ),
                    )
                )
                return result.scalar() or 0
        except Exception:
            return 0

    async def _count_pending_actions(self, user_id: UUID) -> int:
        try:
            from sqlalchemy import text as sa_text

            async with self._session_factory() as session:
                result = await session.execute(
                    sa_text(
                        """
                        SELECT COUNT(*)
                        FROM pending_actions
                        WHERE user_id = :user_id
                        AND status = 'pending'
                        AND expires_at > NOW()
                    """
                    ),
                    {"user_id": str(user_id)},
                )
                return result.scalar() or 0
        except Exception:
            return 0

    async def _fetch_user_preferences(
        self, user_id: UUID
    ) -> Dict[str, Any]:
        try:
            from ..member.models import PersonProfile

            async with self._session_factory() as session:
                result = await session.execute(
                    select(PersonProfile).where(
                        PersonProfile.user_id == user_id,
                        PersonProfile.relationship == "self",
                    )
                )
                profile = result.scalars().first()
                if profile:
                    return {
                        "preferences": getattr(
                            profile, "preferences", {}
                        ),
                        "traits": getattr(profile, "traits", {}),
                        "communication_style": getattr(
                            profile, "communication_style", None
                        ),
                    }
            return {}
        except Exception as e:
            logger.warning("Failed to fetch user preferences: %s", e)
            return {}

    async def _fetch_compressed_summary(
        self, session_id: Optional[str]
    ) -> Optional[str]:
        if not session_id:
            return None
        try:
            try:
                session_uuid = UUID(str(session_id))
            except Exception:
                return None
            async with self._session_factory() as session:
                result = await session.execute(
                    select(SessionSummary.content).where(
                        SessionSummary.session_id == session_uuid
                    )
                )
                return result.scalar_one_or_none()
        except Exception as e:
            logger.warning("Failed to fetch compressed summary: %s", e)
            return None

    @staticmethod
    async def _get_redis_client() -> Optional[Any]:
        try:
            from ...core.cache import redis_client
            return redis_client
        except Exception:
            return None

    async def _fetch_cross_session_memories(
        self, user_id: UUID, family_id: UUID
    ) -> str:
        cache_key = f"svc:ctx:memories:{user_id}:{family_id}"
        try:
            rc = await self._get_redis_client()
            if rc is not None:
                cached = await rc.get(cache_key)
                if cached is not None:
                    return cached if isinstance(cached, str) else cached.decode()
        except Exception:
            pass

        try:
            from ..memory.models import ConversationMemory

            async with self._session_factory() as session:
                result = await session.execute(
                    select(ConversationMemory)
                    .where(
                        ConversationMemory.user_id == user_id,
                        ConversationMemory.family_id == family_id,
                    )
                    .order_by(desc(ConversationMemory.created_at))
                    .limit(20)
                )
                memories = result.scalars().all()
                if not memories:
                    value = ""
                else:
                    lines = []
                    for mem in memories:
                        category = getattr(mem, "category", "general")
                        content = getattr(mem, "content", "")
                        if content:
                            lines.append(f"- [{category}] {content}")
                    value = "\n".join(lines)

                try:
                    rc = await self._get_redis_client()
                    if rc is not None:
                        await rc.set(cache_key, value, ttl=30)
                except Exception:
                    pass

                return value
        except Exception as e:
            logger.warning(
                "Failed to fetch cross-session memories: %s", e
            )
            return ""

    async def _fetch_person_profiles(
        self, user_id: UUID, family_id: UUID
    ) -> str:
        cache_key = f"svc:ctx:profiles:{user_id}:{family_id}"
        try:
            rc = await self._get_redis_client()
            if rc is not None:
                cached = await rc.get(cache_key)
                if cached is not None:
                    return cached if isinstance(cached, str) else cached.decode()
        except Exception:
            pass

        try:
            from ..member.models import PersonProfile

            async with self._session_factory() as session:
                result = await session.execute(
                    select(PersonProfile)
                    .where(
                        PersonProfile.user_id == user_id,
                        PersonProfile.family_id == family_id,
                    )
                    .limit(20)
                )
                profiles = result.scalars().all()
                if not profiles:
                    value = ""
                else:
                    lines = []
                    for p in profiles:
                        name = getattr(p, "name", "\u672a\u77e5")
                        relationship = getattr(p, "relationship", "")
                        traits = getattr(p, "traits", {})
                        preferences = getattr(p, "preferences", {})
                        parts = [f"**{name}**"]
                        if relationship:
                            parts[0] += f" ({relationship})"
                        if traits:
                            trait_items = [
                                f"{k}: {v}"
                                for k, v in traits.items()
                                if v
                            ]
                            if trait_items:
                                parts.append(
                                    f"  \u7279\u5f81: {', '.join(trait_items[:5])}"
                                )
                        if preferences:
                            pref_items = [
                                f"{k}: {v}"
                                for k, v in preferences.items()
                                if v
                            ]
                            if pref_items:
                                parts.append(
                                    f"  \u504f\u597d: {', '.join(pref_items[:5])}"
                                )
                        lines.append("\n".join(parts))
                    value = "\n".join(lines)

                try:
                    rc = await self._get_redis_client()
                    if rc is not None:
                        await rc.set(cache_key, value, ttl=30)
                except Exception:
                    pass

                return value
        except Exception as e:
            logger.warning("Failed to fetch person profiles: %s", e)
            return ""
