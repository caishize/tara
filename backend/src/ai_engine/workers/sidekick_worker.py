"""
SidekickWorker - Evaluates and injects proactive insights into active sessions.

Architecture:
    InsightOrchestrator -> SidekickWorker -> session:signal:{session_id}

The SidekickWorker acts as a bridge between the insight systems (A/B/C) and the
ReactiveSessionActor. When an insight is generated, the worker checks whether it
is contextually relevant to an active session, respects injection rate limits,
and if so publishes an InterventionSignal so the Actor can weave the insight
into the ongoing conversation naturally.

Anti-derailment:
    - Expired insights are discarded before evaluation.
    - Entity intersection is required before injection.
    - Rate limits prevent flooding (max 3 per session, 60s cooldown).
    - High-urgency insights bypass rate limits.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from ...core.cache import redis_client
from ...core.utils.timezone import utc_now
from ..intervention.types import (
    InterventionSignal,
    InterventionType,
    SessionStatus,
    session_signal_channel,
    session_status_key,
)

logger = logging.getLogger(__name__)

# Redis key templates for rate limiting
_SIDEKICK_COUNT_KEY = "sidekick:count:{session_id}"
_SIDEKICK_LAST_KEY = "sidekick:last:{session_id}"

# Rate limit constants
_MAX_INJECTIONS_PER_SESSION = 3
_MIN_INJECTION_INTERVAL_SECONDS = 60
_COUNT_KEY_TTL_SECONDS = 3600


# Injection prompt template for the Actor to incorporate into the conversation
INJECTION_PROMPT_TEMPLATE = (
    "[SYSTEM_INSIGHT]\n"
    "\u4ee5\u4e0b\u4fe1\u606f\u53ef\u80fd\u4e0e\u5f53\u524d\u5bf9\u8bdd"
    "\u76f8\u5173\uff08\u4ec5\u4f9b\u53c2\u8003\uff0c\u8bf7\u5728\u56de"
    "\u590d\u4e2d\u81ea\u7136\u878d\u5165\uff0c\u5982\u679c\u4e0e\u5f53"
    "\u524d\u8bdd\u9898\u65e0\u5173\u5219\u5ffd\u7565\uff09:\n"
    "{insight_text}\n"
    "[/SYSTEM_INSIGHT]"
)


class SidekickWorker:
    """Evaluates proactive insights and injects relevant ones into active sessions.

    This is an async service class (NOT a Celery task). It is instantiated and
    called from insight generation pipelines when new insights are produced.

    Usage:
        worker = SidekickWorker()
        await worker.evaluate_and_inject(user_id, insight)
    """

    def __init__(self) -> None:
        pass

    async def evaluate_and_inject(
        self,
        user_id: str,
        insight: Dict[str, Any],
    ) -> bool:
        """Evaluate an insight and inject it into the user's active session if relevant.

        Args:
            user_id: The target user ID.
            insight: Insight payload with keys:
                - insight_type: str (e.g. "trip_correlation", "favor_reciprocation")
                - insight_text: str
                - urgency: str ("high" | "medium" | "low")
                - source_system: str ("A" | "B" | "C")
                - context_entities: List[str]
                - expires_at: Optional[str] (ISO 8601)

        Returns:
            True if the insight was injected, False otherwise.
        """
        # 1. Check expiry
        if self._is_expired(insight):
            logger.debug(
                "Sidekick: discarding expired insight type=%s for user=%s",
                insight.get("insight_type"),
                user_id,
            )
            return False

        # 2. Find active session
        session_status = await self._find_active_session(user_id)
        if session_status is None:
            logger.debug(
                "Sidekick: no active session for user=%s, skipping insight",
                user_id,
            )
            return False

        session_id = session_status.get("session_id", "")
        job_id = session_status.get("job_id", "")
        task_summary = session_status.get("task_summary", "")

        # 3. Check contextual relevance (F2: multi-level matching)
        session_context = {
            "task_summary": task_summary,
            "mentioned_person_ids": session_status.get("mentioned_person_ids") or [],
            "mentioned_locations": session_status.get("mentioned_locations") or [],
            "action_category": session_status.get("action_category", ""),
        }
        if not self._is_contextually_relevant(insight, session_context):
            logger.debug(
                "Sidekick: insight not relevant to current task for user=%s "
                "(insight_type=%s, task=%s)",
                user_id,
                insight.get("insight_type"),
                task_summary[:80],
            )
            return False

        # 3b. Delivery dedup is now handled by InsightQueryService
        # (delivered_via_sidekick = false filter in get_for_sidekick)
        urgency = insight.get("urgency", "low")

        # 4. Check rate limits (high urgency bypasses)
        if urgency != "high":
            allowed = await self._check_injection_limits(session_id)
            if not allowed:
                logger.debug(
                    "Sidekick: rate limit exceeded for session=%s, "
                    "skipping insight type=%s",
                    session_id,
                    insight.get("insight_type"),
                )
                return False

        # 5. Build and publish InterventionSignal
        signal = self._build_signal(
            session_id=session_id,
            job_id=job_id,
            user_id=user_id,
            insight=insight,
        )

        await self._publish_signal(session_id, signal)

        # 6. Record injection for rate limiting
        await self._record_injection(session_id)

        logger.info(
            "Sidekick: injected insight type=%s urgency=%s into session=%s "
            "(signal_id=%s)",
            insight.get("insight_type"),
            urgency,
            session_id,
            signal.signal_id,
        )
        return True

    def _is_expired(self, insight: Dict[str, Any]) -> bool:
        """Check whether the insight has passed its expiry time."""
        expires_at_raw = insight.get("expires_at")
        if not expires_at_raw:
            return False
        try:
            if isinstance(expires_at_raw, str):
                expires_at = datetime.fromisoformat(
                    expires_at_raw.replace("Z", "+00:00")
                )
            else:
                expires_at = expires_at_raw
            now = utc_now()
            # Make comparison timezone-aware if needed
            if expires_at.tzinfo is None:
                return False
            return now > expires_at
        except (ValueError, TypeError):
            return False

    async def _find_active_session(
        self, user_id: str
    ) -> Optional[Dict[str, Any]]:
        """Look up the user's active session status from Redis.

        Uses the ``user:active_session:{user_id}`` reverse index maintained
        by ReactiveSessionActor for O(1) lookup, with a SCAN fallback for
        backward compatibility during deployment.
        """
        rc = redis_client.client
        if rc is None:
            return None

        # --- O(1) path: reverse index ---
        try:
            session_id = await rc.get(f"user:active_session:{user_id}")
            if session_id:
                raw = await rc.get(f"session:status:{session_id}")
                if raw:
                    try:
                        status_data = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        pass
                    else:
                        status = SessionStatus.from_dict(status_data)
                        if status.is_active():
                            result = status.to_dict()
                            result["session_id"] = session_id
                            return result
        except Exception as e:
            logger.warning(
                "Sidekick: reverse index lookup failed, falling back to SCAN: %s", e
            )

        # --- Fallback: SCAN (backward compat during rolling deploy) ---
        try:
            cursor = "0"
            while True:
                cursor, keys = await rc.scan(
                    cursor=cursor,
                    match="session:status:*",
                    count=50,
                )
                for key in keys:
                    raw = await rc.get(key)
                    if not raw:
                        continue
                    try:
                        status_data = json.loads(raw)
                    except (json.JSONDecodeError, TypeError):
                        continue
                    status = SessionStatus.from_dict(status_data)
                    if status.user_id and status.user_id != user_id:
                        continue
                    if not status.is_active():
                        continue
                    parts = key.split(":", 2)
                    if len(parts) < 3:
                        continue
                    sid = parts[2]
                    result = status.to_dict()
                    result["session_id"] = sid
                    return result
                if cursor == 0 or cursor == "0":
                    break
        except Exception as e:
            logger.error("Sidekick: failed to scan session status: %s", e)
        return None

    def _is_contextually_relevant(
        self,
        insight: Dict[str, Any],
        session_context: Dict[str, Any],
    ) -> bool:
        """Multi-level contextual relevance check (F2: replaces text-containment).

        Three matching levels, returning True on first hit:
          1. Entity ID precise matching (related_member_ids vs mentioned_person_ids)
          2. Event type affinity (insight_type x action_category lookup)
          3. Location overlap (insight location vs session mentioned_locations)

        Falls back to legacy text containment if no structured IDs are available.
        """
        # Level 1: Entity ID precise matching
        insight_person_ids: set = set()
        if hasattr(insight, "related_member_ids") and insight.related_member_ids:
            insight_person_ids = {str(pid) for pid in insight.related_member_ids}
        elif isinstance(insight, dict):
            for key in ("related_member_ids", "related_person_ids"):
                ids = insight.get(key) or []
                insight_person_ids.update(str(pid) for pid in ids)

        context_person_ids = set(
            str(pid) for pid in (session_context.get("mentioned_person_ids") or [])
        )
        if insight_person_ids and context_person_ids and (insight_person_ids & context_person_ids):
            return True

        # Level 2: Event type affinity
        _affinity_map = {
            ("trip_correlation", "trip"): True,
            ("trip_correlation", "travel"): True,
            ("favor_reciprocation", "gift"): True,
            ("relationship_maintenance", "social"): True,
            ("relationship_maintenance", "greeting"): True,
            ("event_preparation", "trip"): True,
            ("event_preparation", "meeting"): True,
        }
        insight_type = (
            getattr(insight, "insight_type", None)
            or (insight.get("insight_type") if isinstance(insight, dict) else None)
        )
        action_category = session_context.get("action_category", "")
        if insight_type and action_category and _affinity_map.get((insight_type, action_category)):
            return True

        # Level 3: Location overlap
        insight_location = (
            getattr(insight, "location", None)
            or (insight.get("location") if isinstance(insight, dict) else None)
        )
        if not insight_location:
            extra = (
                getattr(insight, "extra_data", None)
                or (insight.get("extra_data") if isinstance(insight, dict) else {})
            )
            if isinstance(extra, dict):
                insight_location = extra.get("location")

        mentioned_locations = session_context.get("mentioned_locations") or []
        if insight_location and insight_location in mentioned_locations:
            return True

        # Fallback: legacy text containment for backward compatibility
        context_entities = (
            insight.get("context_entities", []) if isinstance(insight, dict) else []
        )
        task_summary = session_context.get("task_summary", "")
        if context_entities and task_summary:
            task_lower = task_summary.lower()
            for entity in context_entities:
                if entity and entity.lower() in task_lower:
                    return True

        return False

    async def _check_injection_limits(self, session_id: str) -> bool:
        """Check whether injection rate limits allow another injection.

        Limits:
            - Max 3 injections per session (Redis counter, TTL 3600s)
            - Min 60s between injections (Redis timestamp, TTL 60s)

        Returns True if injection is allowed.
        """
        rc = redis_client.client
        if rc is None:
            return True

        # Check per-session count
        count_key = _SIDEKICK_COUNT_KEY.format(session_id=session_id)
        try:
            count_raw = await rc.get(count_key)
            if count_raw is not None:
                count = int(count_raw)
                if count >= _MAX_INJECTIONS_PER_SESSION:
                    return False
        except (ValueError, TypeError):
            pass

        # Check minimum interval
        last_key = _SIDEKICK_LAST_KEY.format(session_id=session_id)
        try:
            last_raw = await rc.get(last_key)
            if last_raw is not None:
                # Key exists and hasn't expired -> too soon
                return False
        except Exception:
            pass

        return True

    async def _record_injection(self, session_id: str) -> None:
        """Record an injection event for rate limiting."""
        rc = redis_client.client
        if rc is None:
            return

        count_key = _SIDEKICK_COUNT_KEY.format(session_id=session_id)
        last_key = _SIDEKICK_LAST_KEY.format(session_id=session_id)

        try:
            pipe = rc.pipeline()
            pipe.incr(count_key)
            pipe.expire(count_key, _COUNT_KEY_TTL_SECONDS)
            pipe.setex(last_key, _MIN_INJECTION_INTERVAL_SECONDS, "1")
            await pipe.execute()
        except Exception as e:
            logger.warning(
                "Sidekick: failed to record injection for session=%s: %s",
                session_id,
                e,
            )

    def _build_signal(
        self,
        session_id: str,
        job_id: str,
        user_id: str,
        insight: Dict[str, Any],
    ) -> InterventionSignal:
        """Build an InterventionSignal from an insight payload."""
        insight_text = insight.get("insight_text", "")
        injection_prompt = INJECTION_PROMPT_TEMPLATE.format(
            insight_text=insight_text
        )

        # PLAN-013: include action_options (List[ActionSpec dict]) in the
        # signal payload so the ReactiveSessionActor / mobile clients that
        # receive SIDEKICK_INSIGHT signals can render action chips.
        # InterventionSignal.payload is Dict[str,Any] — no structural change
        # required; we simply forward the field (confirmed by audit).
        payload = {
            "insight_type": insight.get("insight_type", "unknown"),
            "insight_text": insight_text,
            "injection_prompt": injection_prompt,
            "urgency": insight.get("urgency", "low"),
            "source_system": insight.get("source_system", ""),
            "context_entities": insight.get("context_entities", []),
            "expires_at": insight.get("expires_at"),
            "action_options": insight.get("action_options") or [],
        }

        return InterventionSignal.create(
            signal_type=InterventionType.SIDEKICK_INSIGHT.value,
            session_id=session_id,
            job_id=job_id,
            user_id=user_id,
            payload=payload,
        )

    async def generate_and_inject(
        self,
        user_id: str,
        family_id: str,
        session_id: str,
        db_session,
    ) -> None:
        """Query recent high-importance insights and inject relevant ones.

        Uses InsightQueryService.get_for_sidekick() to find candidates from
        the unified ``insights`` table (importance >= 70, created within 6h,
        not yet delivered via sidekick), then evaluates each for injection.
        """
        from ...modules.insight.insight_query_service import InsightQueryService
        from uuid import UUID

        query_svc = InsightQueryService(db_session)
        candidates = await query_svc.get_for_sidekick(
            user_id=UUID(user_id),
            limit=3,
        )
        for card in candidates:
            # Extract context entities from insight card fields.
            entities: List[str] = []
            if card.title:
                entities.append(card.title)
            if card.insight_type:
                entities.append(card.insight_type)

            # Build related_member_ids for Gate 3 entity-ID matching
            related_member_ids: List[str] = [
                str(e.entity_id) for e in (card.entities or [])
                if e.entity_type == "person"
            ]

            # Map numeric urgency to string
            if card.urgency >= 90:
                urgency_str = "high"
            elif card.urgency >= 60:
                urgency_str = "medium"
            else:
                urgency_str = "low"

            action_opts = card.action_options or []
            injected = await self.evaluate_and_inject(user_id, {
                "insight_id": str(card.id),
                "insight_text": card.content,
                "insight_type": card.insight_type or "general",
                "urgency": urgency_str,
                "source_system": "unified",
                "context_entities": entities,
                "related_member_ids": related_member_ids,
                "expires_at": (
                    card.expires_at.isoformat() if card.expires_at else None
                ),
                "action_options": action_opts,
            })

            # Mark delivered_via_sidekick in unified insights table
            if injected:
                try:
                    await query_svc.mark_delivered(card.id, "sidekick")
                except Exception as exc:
                    logger.debug(
                        "Sidekick: failed to mark delivered for insight=%s: %s",
                        card.id, exc,
                    )

    async def _publish_signal(
        self, session_id: str, signal: InterventionSignal
    ) -> None:
        """Publish the intervention signal to the session's signal channel."""
        rc = redis_client.client
        if rc is None:
            logger.warning(
                "Sidekick: Redis not available, cannot publish signal "
                "for session=%s",
                session_id,
            )
            return

        channel = session_signal_channel(session_id)
        try:
            await rc.publish(channel, signal.to_json())
            logger.info(
                "AQ sidekick_published: session=%s signal_id=%s job_id=%s "
                "insight_type=%s urgency=%s channel=%s",
                session_id,
                signal.signal_id,
                signal.job_id,
                signal.payload.get("insight_type", "unknown"),
                signal.payload.get("urgency", "low"),
                channel,
            )
        except Exception as e:
            logger.error(
                "Sidekick: failed to publish signal to channel=%s: %s",
                channel,
                e,
            )
