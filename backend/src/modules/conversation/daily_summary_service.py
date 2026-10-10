"""Daily Summary Service - Generates and caches per-date conversation summaries.

Summaries are stored in AssistantChatSession.context["daily_summaries"] as a list of
{"date": "YYYY-MM-DD", "summary": "..."} dicts.
"""

from collections import defaultdict
from typing import Any, Dict, List
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from .models import AssistantChatSession, ConversationMessage

logger = get_logger(__name__)

SUMMARIES_CACHE_KEY = "daily_summaries"
MIN_MESSAGES_PER_DATE = 5
MAX_MESSAGES_PER_DATE = 20
MAX_CONTENT_CHARS = 200
MAX_SUMMARY_TOKENS = 150


class DailySummaryService:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def get_summaries(self, session_id: UUID) -> List[Dict[str, str]]:
        """Return cached daily summaries. Returns [] if none cached yet."""
        result = await self._db.execute(
            select(AssistantChatSession.context).where(
                AssistantChatSession.id == session_id
            )
        )
        context = result.scalar_one_or_none()
        if not context:
            return []
        return context.get(SUMMARIES_CACHE_KEY, [])

    async def generate_and_cache(self, session_id: UUID) -> int:
        """Generate summaries for all qualifying dates and cache them.

        Returns the number of summaries generated and stored.
        """
        result = await self._db.execute(
            select(AssistantChatSession).where(AssistantChatSession.id == session_id)
        )
        session = result.scalar_one_or_none()
        if not session:
            return 0

        if (session.message_count or 0) < MIN_MESSAGES_PER_DATE:
            return 0

        msgs_result = await self._db.execute(
            select(ConversationMessage)
            .where(ConversationMessage.session_id == session_id)
            .order_by(ConversationMessage.created_at.asc())
        )
        messages = list(msgs_result.scalars().all())

        if len(messages) < MIN_MESSAGES_PER_DATE:
            return 0

        by_date: Dict[str, list] = defaultdict(list)
        for msg in messages:
            if msg.created_at:
                date_key = msg.created_at.date().isoformat()
                by_date[date_key].append(msg)

        summaries = []
        for date_key, date_msgs in sorted(by_date.items()):
            if len(date_msgs) < MIN_MESSAGES_PER_DATE:
                continue

            selected = date_msgs[-MAX_MESSAGES_PER_DATE:]
            conversation_text = "\n".join(
                f"[{m.role}]: {(m.content or '')[:MAX_CONTENT_CHARS]}"
                for m in selected
            )

            try:
                summary = await self._summarize(date_key, conversation_text)
                summaries.append({"date": date_key, "summary": summary})
            except Exception as e:
                logger.warning(
                    "Failed to generate summary for session=%s date=%s: %s",
                    session_id,
                    date_key,
                    e,
                )

        if not summaries:
            return 0

        context = dict(session.context or {})
        context[SUMMARIES_CACHE_KEY] = summaries
        await self._db.execute(
            update(AssistantChatSession)
            .where(AssistantChatSession.id == session_id)
            .values(context=context)
        )
        await self._db.flush()

        return len(summaries)

    async def _summarize(self, date_str: str, conversation_text: str) -> str:
        """Use Haiku to produce a one-sentence summary of the conversation."""
        from ...core.llm.haiku_client import get_haiku_client

        client = get_haiku_client()
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=MAX_SUMMARY_TOKENS,
            messages=[
                {
                    "role": "user",
                    "content": (
                        f"请用一句话总结 {date_str} 的对话主要内容（不超过50字）：\n\n"
                        f"{conversation_text}"
                    ),
                }
            ],
        )
        return response.content[0].text.strip()
