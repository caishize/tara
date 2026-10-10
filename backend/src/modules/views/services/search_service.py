"""Event search service.

Extracted from secretary/services/event_context_service.py (search_events).
"""
from typing import List, Optional
from uuid import UUID

from sqlalchemy import select, and_, or_, func
from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ...curation.models import CuratedEvent
from ...curation.services.query_utils import escape_like
from ..kanban_schemas import EventSearchResult, EventSearchResponse

logger = get_logger(__name__)


class SearchService:
    """Full-text search across curated event titles, locations, and notes."""

    def __init__(self, session: AsyncSession):
        self.session = session

    async def search_events(
        self,
        family_id: UUID,
        query: str,
        event_types: Optional[List[str]] = None,
        limit: int = 20,
    ) -> EventSearchResponse:
        """Full-text search across curated event titles, locations, and notes."""
        if not query or not query.strip():
            return EventSearchResponse(query=query)

        query = query.strip()[:200]

        like_pattern = f"%{escape_like(query)}%"

        conditions = [
            CuratedEvent.family_id == family_id,
            CuratedEvent.is_active.is_(True),
        ]

        if event_types:
            conditions.append(CuratedEvent.event_type.in_(event_types))

        text_match = or_(
            CuratedEvent.title.ilike(like_pattern, escape="\\"),
            CuratedEvent.location.ilike(like_pattern, escape="\\"),
            CuratedEvent.notes.ilike(like_pattern, escape="\\"),
        )
        conditions.append(text_match)

        count_stmt = (
            select(func.count())
            .select_from(CuratedEvent)
            .where(and_(*conditions))
        )
        count_result = await self.session.execute(count_stmt)
        total = count_result.scalar() or 0

        stmt = (
            select(CuratedEvent)
            .where(and_(*conditions))
            .order_by(CuratedEvent.normalized_start.desc())
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        events = result.scalars().all()

        results = [
            EventSearchResult(
                id=str(ev.id),
                title=ev.title,
                event_type=ev.event_type,
                start_time=ev.normalized_start,
                location=ev.location,
                status=ev.status,
                trip_name=ev.trip_name,
            )
            for ev in events
        ]

        return EventSearchResponse(
            results=results,
            total=total,
            query=query,
        )
