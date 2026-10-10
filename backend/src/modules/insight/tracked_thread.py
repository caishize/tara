"""TrackedThreadService -- manages long-running information tracking threads.

Threads track commitments, relationship reciprocity, event preparation, and
other multi-step concerns that span days or weeks.  Each thread carries ordered
checkpoints (with due dates) and a chronological context log.

Auto-creation from domain events, checkpoint-driven insight generation, and
immutable append for context updates.
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from sqlalchemy import and_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .models import (
    EntitySpec,
    GenerationLevel,
    InformationTier,
    InsightCandidate,
    ThreadStatus,
    TrackedThread,
)

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Thread-type → default checkpoint templates
# ---------------------------------------------------------------------------

_COMMITMENT_CHECKPOINTS = (
    {"title": "进展确认", "offset_days": -3, "insight_type": "efficiency"},
    {"title": "完成提醒", "offset_days": -1, "insight_type": "time"},
    {"title": "到期提醒", "offset_days": 0, "insight_type": "time"},
)

_FAVOR_CHECKPOINTS = (
    {"title": "回礼考虑", "offset_days": 7, "insight_type": "favor"},
    {"title": "回礼提醒", "offset_days": 30, "insight_type": "social_obligation"},
)

_IMPORTANT_DATE_CHECKPOINTS = (
    {"title": "礼物建议", "offset_days": -14, "insight_type": "favor"},
    {"title": "购买提醒", "offset_days": -7, "insight_type": "life_admin"},
    {"title": "安排提醒", "offset_days": -3, "insight_type": "time"},
    {"title": "发送祝福", "offset_days": 0, "insight_type": "social_obligation"},
)


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------


class TrackedThreadService:
    """Manages long-running information tracking threads."""

    def __init__(self, db: AsyncSession):
        self._db = db

    # ------------------------------------------------------------------
    # Auto-create from domain events
    # ------------------------------------------------------------------

    async def auto_create_from_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        user_id: UUID,
        family_id: UUID,
    ) -> Optional[TrackedThread]:
        """Auto-create thread when a new commitment / favor / important event is detected.

        Returns the created TrackedThread, or None if the event_type is not tracked.
        """
        builder = _THREAD_BUILDERS.get(event_type)
        if builder is None:
            return None

        title, thread_type, entity_refs, checkpoints = builder(event_data)

        thread = TrackedThread(
            id=uuid4(),
            user_id=user_id,
            family_id=family_id,
            title=title[:200],
            thread_type=thread_type,
            status=ThreadStatus.MONITORING.value,
            entity_refs=[
                {"entity_type": e.entity_type, "entity_id": e.entity_id, "role": e.role}
                for e in entity_refs
            ],
            checkpoints=checkpoints,
            context_log=[
                {
                    "ts": utc_now().isoformat(),
                    "action": "created",
                    "detail": f"Auto-created from {event_type}",
                }
            ],
            created_at=utc_now(),
            updated_at=utc_now(),
        )
        self._db.add(thread)
        await self._db.flush()
        logger.info("Created tracked thread %s for %s", thread.id, event_type)
        return thread

    # ------------------------------------------------------------------
    # Checkpoint scanning
    # ------------------------------------------------------------------

    async def check_all_active(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: datetime,
    ) -> List[InsightCandidate]:
        """Check active threads for due checkpoints, return insight candidates."""
        stmt = (
            select(TrackedThread)
            .where(
                and_(
                    TrackedThread.user_id == user_id,
                    TrackedThread.family_id == family_id,
                    TrackedThread.status.in_([
                        ThreadStatus.MONITORING.value,
                        ThreadStatus.APPROACHING.value,
                        ThreadStatus.ACTIVE.value,
                    ]),
                )
            )
        )
        result = await self._db.execute(stmt)
        threads = list(result.scalars().all())

        candidates: List[InsightCandidate] = []
        for thread in threads:
            due = self._find_due_checkpoints(thread, target_date)
            for cp in due:
                candidates.append(self._checkpoint_to_candidate(thread, cp))
        return candidates

    # ------------------------------------------------------------------
    # Context append (immutable)
    # ------------------------------------------------------------------

    async def append_context(
        self,
        thread_id: UUID,
        new_context: Dict[str, Any],
    ) -> TrackedThread:
        """Append new information to thread's context_log (immutable pattern)."""
        thread = await self._get_thread(thread_id)
        existing_log: list = list(thread.context_log or [])
        entry = {
            **new_context,
            "ts": utc_now().isoformat(),
        }
        updated_log = [*existing_log, entry]

        await self._db.execute(
            update(TrackedThread)
            .where(TrackedThread.id == thread_id)
            .values(context_log=updated_log, updated_at=utc_now())
        )
        await self._db.flush()

        # Return refreshed instance
        return await self._get_thread(thread_id)

    # ------------------------------------------------------------------
    # Status management
    # ------------------------------------------------------------------

    async def advance_status(self, thread_id: UUID) -> TrackedThread:
        """Check if thread should advance status based on checkpoints."""
        thread = await self._get_thread(thread_id)
        checkpoints: list = thread.checkpoints or []
        if not checkpoints:
            return thread

        now = utc_now()
        completed = sum(1 for cp in checkpoints if cp.get("completed"))
        total = len(checkpoints)

        # Determine new status
        new_status = thread.status
        if completed == total:
            new_status = ThreadStatus.RESOLVED.value
        else:
            # Find earliest incomplete checkpoint
            earliest_due = self._earliest_incomplete_due(checkpoints)
            if earliest_due is not None:
                days_until = (earliest_due.date() - now.date()).days
                if days_until <= 0:
                    new_status = ThreadStatus.ACTIVE.value
                elif days_until <= 3:
                    new_status = ThreadStatus.APPROACHING.value

        if new_status == thread.status:
            return thread

        values: Dict[str, Any] = {
            "status": new_status,
            "updated_at": utc_now(),
        }
        if new_status == ThreadStatus.RESOLVED.value:
            values["resolved_at"] = utc_now()

        await self._db.execute(
            update(TrackedThread)
            .where(TrackedThread.id == thread_id)
            .values(**values)
        )
        await self._db.flush()
        return await self._get_thread(thread_id)

    async def resolve(
        self,
        thread_id: UUID,
        resolution: str,
    ) -> TrackedThread:
        """Mark thread as resolved."""
        thread = await self._get_thread(thread_id)
        existing_log: list = list(thread.context_log or [])
        entry = {
            "ts": utc_now().isoformat(),
            "action": "resolved",
            "detail": resolution,
        }
        updated_log = [*existing_log, entry]

        await self._db.execute(
            update(TrackedThread)
            .where(TrackedThread.id == thread_id)
            .values(
                status=ThreadStatus.RESOLVED.value,
                resolved_at=utc_now(),
                updated_at=utc_now(),
                context_log=updated_log,
            )
        )
        await self._db.flush()
        return await self._get_thread(thread_id)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    async def _get_thread(self, thread_id: UUID) -> TrackedThread:
        """Fetch a thread by ID or raise."""
        stmt = select(TrackedThread).where(TrackedThread.id == thread_id)
        result = await self._db.execute(stmt)
        thread = result.scalar_one_or_none()
        if thread is None:
            raise ValueError(f"TrackedThread {thread_id} not found")
        return thread

    @staticmethod
    def _find_due_checkpoints(
        thread: TrackedThread,
        target_date: datetime,
    ) -> List[Dict[str, Any]]:
        """Return checkpoints where due_date <= target_date and not completed."""
        due: List[Dict[str, Any]] = []
        for cp in (thread.checkpoints or []):
            if cp.get("completed"):
                continue
            due_str = cp.get("due_date")
            if not due_str:
                continue
            try:
                due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if due_dt.date() <= target_date.date():
                due.append(cp)
        return due

    @staticmethod
    def _checkpoint_to_candidate(
        thread: TrackedThread,
        checkpoint: Dict[str, Any],
    ) -> InsightCandidate:
        """Convert a due checkpoint into an InsightCandidate."""
        cp_title = checkpoint.get("title", "检查点")
        insight_type = checkpoint.get("insight_type", "time")

        entities: List[EntitySpec] = []
        for ref in (thread.entity_refs or []):
            entities.append(EntitySpec(
                entity_type=ref.get("entity_type", "unknown"),
                entity_id=ref.get("entity_id", ""),
                role=ref.get("role", "related"),
            ))

        return InsightCandidate(
            insight_type=insight_type,
            title=f"{thread.title}: {cp_title}"[:200],
            content=f"跟踪事项「{thread.title}」的检查点「{cp_title}」已到期",
            importance=70,
            urgency=75,
            entities=entities,
            source_context={
                "thread_id": str(thread.id),
                "thread_type": thread.thread_type,
                "checkpoint_title": cp_title,
            },
            context_hint=f"这是跟踪事项「{thread.title}」的一部分",
            best_action_window="今天",
            generation_level=GenerationLevel.L1_RULE.value,
            information_tier=InformationTier.L2_FORMAL.value,
            action_options=[
                {"type": "open_detail", "label": "查看详情"},
                {"type": "acknowledge", "label": "已处理"},
                {"type": "defer", "label": "稍后提醒"},
            ],
            dedup_key=f"thread:{thread.id}:{cp_title}",
        )

    @staticmethod
    def _earliest_incomplete_due(
        checkpoints: List[Dict[str, Any]],
    ) -> Optional[datetime]:
        """Find earliest due_date among incomplete checkpoints."""
        earliest: Optional[datetime] = None
        for cp in checkpoints:
            if cp.get("completed"):
                continue
            due_str = cp.get("due_date")
            if not due_str:
                continue
            try:
                due_dt = datetime.fromisoformat(due_str.replace("Z", "+00:00"))
            except (ValueError, TypeError):
                continue
            if earliest is None or due_dt < earliest:
                earliest = due_dt
        return earliest


# ---------------------------------------------------------------------------
# Thread builders (event_type -> builder function)
# ---------------------------------------------------------------------------


def _build_commitment_thread(
    data: Dict[str, Any],
) -> tuple[str, str, List[EntitySpec], List[Dict[str, Any]]]:
    """Build thread data for a commitment."""
    who = data.get("who", "")
    what = data.get("what", "")
    title = f"{who}: {what}" if who else what
    deadline_str = data.get("deadline")
    deadline = _parse_dt(deadline_str) if deadline_str else utc_now() + timedelta(days=7)

    entities: List[EntitySpec] = []
    if data.get("commitment_id"):
        entities.append(EntitySpec(
            entity_type="commitment",
            entity_id=str(data["commitment_id"]),
            role="primary",
        ))

    checkpoints = [
        {
            "title": tmpl["title"],
            "due_date": (deadline + timedelta(days=tmpl["offset_days"])).isoformat(),
            "completed": False,
            "insight_type": tmpl["insight_type"],
        }
        for tmpl in _COMMITMENT_CHECKPOINTS
    ]
    return title[:200], "commitment", entities, checkpoints


def _build_favor_thread(
    data: Dict[str, Any],
) -> tuple[str, str, List[EntitySpec], List[Dict[str, Any]]]:
    """Build thread data for a received favor."""
    contact = data.get("contact_name", "")
    event_type = data.get("event_type", "人情")
    title = f"{contact}的{event_type} - 回礼跟踪"
    recorded_at_str = data.get("recorded_at")
    base_date = _parse_dt(recorded_at_str) if recorded_at_str else utc_now()

    entities: List[EntitySpec] = []
    if data.get("favor_record_id"):
        entities.append(EntitySpec(
            entity_type="favor",
            entity_id=str(data["favor_record_id"]),
            role="primary",
        ))
    if data.get("contact_id"):
        entities.append(EntitySpec(
            entity_type="person",
            entity_id=str(data["contact_id"]),
            role="related",
        ))

    checkpoints = [
        {
            "title": tmpl["title"],
            "due_date": (base_date + timedelta(days=tmpl["offset_days"])).isoformat(),
            "completed": False,
            "insight_type": tmpl["insight_type"],
        }
        for tmpl in _FAVOR_CHECKPOINTS
    ]
    return title[:200], "relationship", entities, checkpoints


def _build_important_date_thread(
    data: Dict[str, Any],
) -> tuple[str, str, List[EntitySpec], List[Dict[str, Any]]]:
    """Build thread data for an important date."""
    title = data.get("title", "重要日期准备")
    event_date_str = data.get("normalized_start") or data.get("start") or data.get("date")
    event_date = _parse_dt(event_date_str) if event_date_str else utc_now() + timedelta(days=14)

    entities: List[EntitySpec] = []
    if data.get("important_date_id"):
        entities.append(EntitySpec(
            entity_type="important_date",
            entity_id=str(data["important_date_id"]),
            role="primary",
        ))
    if data.get("event_id") or data.get("id"):
        eid = str(data.get("event_id") or data["id"])
        entities.append(EntitySpec(
            entity_type="event",
            entity_id=eid,
            role="related",
        ))

    checkpoints = [
        {
            "title": tmpl["title"],
            "due_date": (event_date + timedelta(days=tmpl["offset_days"])).isoformat(),
            "completed": False,
            "insight_type": tmpl["insight_type"],
        }
        for tmpl in _IMPORTANT_DATE_CHECKPOINTS
    ]
    return title[:200], "preparation", entities, checkpoints


def _parse_dt(val: Any) -> datetime:
    """Parse a datetime from string or return as-is."""
    if isinstance(val, datetime):
        return val
    if isinstance(val, str):
        try:
            return datetime.fromisoformat(val.replace("Z", "+00:00"))
        except (ValueError, TypeError):
            pass
    return utc_now()


_THREAD_BUILDERS = {
    "commitment": _build_commitment_thread,
    "favor": _build_favor_thread,
    "important_date": _build_important_date_thread,
}
