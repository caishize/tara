"""InsightHygiene — Maintenance: expiry, orphan cleanup, obligation audit, archive.

Scheduled via Celery Beat at 04:00 UTC + every 6h.
All operations use batch queries with bounded result sets to avoid
excessive memory usage.
"""

from datetime import timedelta
from typing import Dict, List, Optional
from uuid import UUID

from sqlalchemy import and_, delete, exists, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...core.utils.timezone import utc_now
from .insight_enrichment import synthesize_entities
from .insight_signal_collector import AllSignals
from .models import (
    EntitySpec,
    Insight,
    InsightEntity,
    InsightStatus,
    InsightSource,
    SourceContext,
    SUPPRESSION_THRESHOLDS,
)

logger = get_logger(__name__)

# Archive threshold: dismissed/expired insights older than this are deleted
_ARCHIVE_DAYS = 90

# Acknowledged insights without snooze that exceed this age revert to active
_ACKNOWLEDGED_EXPIRY_DAYS = 90

# Past-date grace window for social obligations (demote but keep)
_PAST_DATE_GRACE_DAYS = 7

# Maximum orphan obligations to inject per cleanup run
_MAX_ORPHAN_SIGNALS = 20

# Commitment coverage threshold (cumulative dismiss count)
_COMMITMENT_DISMISS_THRESHOLD = 3

# Entity type -> ORM model class mapping (lazy-loaded to avoid circular imports)
_ENTITY_TABLE_MAP = {
    "person": ("member.models", "PersonProfile"),
    "trip": ("trip.models.trip_plan", "TripPlan"),
    "event": ("curation.models", "CuratedEvent"),
    "important_date": ("date_manager.date_models", "ImportantDate"),
    "event_association": ("curation.models", "EventAssociation"),
    "favor": ("relationship.models", "FavorRecord"),
    "commitment": ("memory.commitment_models", "CommitmentItemRecord"),
}


def _resolve_model(entity_type: str):
    """Lazily resolve an entity type to its ORM model class."""
    spec = _ENTITY_TABLE_MAP.get(entity_type)
    if spec is None:
        return None
    module_path, class_name = spec
    import importlib
    full_path = f"..{module_path}"
    try:
        mod = importlib.import_module(full_path, package=__name__)
        return getattr(mod, class_name, None)
    except (ImportError, AttributeError):
        return None


def _get_pk_column(model_cls):
    """Return the primary key column of an ORM model."""
    mapper = model_cls.__mapper__
    pk_cols = mapper.primary_key
    if pk_cols:
        return pk_cols[0]
    return None


class InsightHygiene:
    """Maintenance service for the unified insight system."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def _resolve_user_id_for_family(self, family_id: UUID) -> Optional[str]:
        """Resolve the primary (first active) user_id for a given family_id."""
        from ..member.models.user import User

        result = await self.db.execute(
            select(User.id)
            .where(
                User.family_id == family_id,
                User.is_active.is_(True),
            )
            .limit(1)
        )
        row = result.scalar_one_or_none()
        return str(row) if row else None

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    async def run_cleanup(self) -> dict:
        """Run all cleanup steps. Returns a summary dict.

        Steps (in order):
        1. expire_stale
        2. dismiss_orphaned_entities
        3. dismiss_past_event_insights
        4. handle_past_dates
        5. obligation_coverage_audit
        6. recheck_expired_cascade_actions
        7. archive_old
        8. check_acknowledged_expiry
        9. check_trip_completed_adopted
        """
        summary = {}

        summary["expired"] = await self.expire_stale()
        summary["orphaned"] = await self.dismiss_orphaned_entities()
        summary["past_events"] = await self.dismiss_past_event_insights()
        summary["past_dates"] = await self.handle_past_dates()
        summary["orphan_obligations"] = await self.obligation_coverage_audit()
        summary["rechecked_pas"] = await self.recheck_expired_cascade_actions()
        summary["archived"] = await self.archive_old()
        summary["ack_reverted"] = await self.check_acknowledged_expiry()
        summary["unadopted"] = await self.check_trip_completed_adopted()

        await self.db.flush()

        logger.info("Insight hygiene run complete: %s", summary)
        return summary

    # ------------------------------------------------------------------
    # Step 1: Expire stale insights
    # ------------------------------------------------------------------

    async def expire_stale(self) -> int:
        """Expire insights past their expires_at timestamp."""
        now = utc_now()
        result = await self.db.execute(
            update(Insight)
            .where(
                Insight.expires_at < now,
                Insight.status.in_([
                    InsightStatus.PENDING.value,
                    InsightStatus.ACTIVE.value,
                ]),
            )
            .values(status=InsightStatus.EXPIRED.value)
        )
        count = result.rowcount
        if count > 0:
            logger.info("Expired %d stale insights", count)
        return count

    # ------------------------------------------------------------------
    # Step 2: Dismiss orphaned entity insights
    # ------------------------------------------------------------------

    async def dismiss_orphaned_entities(self) -> int:
        """Dismiss insights whose primary source entities no longer exist.

        Uses NOT EXISTS sub-queries for each entity_type in the map.
        """
        now = utc_now()
        total = 0

        for entity_type, spec in _ENTITY_TABLE_MAP.items():
            model_cls = _resolve_model(entity_type)
            if model_cls is None:
                continue

            pk_col = _get_pk_column(model_cls)
            if pk_col is None:
                continue

            # Find insights with source entities of this type where
            # the referenced entity no longer exists
            orphan_subq = (
                select(InsightEntity.insight_id)
                .where(
                    InsightEntity.entity_type == entity_type,
                    InsightEntity.role == "primary",
                    ~exists(
                        select(pk_col).where(
                            pk_col == InsightEntity.entity_id
                        )
                    ),
                )
            )

            result = await self.db.execute(
                update(Insight)
                .where(
                    Insight.id.in_(orphan_subq),
                    Insight.status.in_([
                        InsightStatus.PENDING.value,
                        InsightStatus.ACTIVE.value,
                        InsightStatus.ACKNOWLEDGED.value,
                    ]),
                )
                .values(
                    status=InsightStatus.DISMISSED.value,
                    dismissed_at=now,
                )
            )
            count = result.rowcount
            if count > 0:
                logger.info(
                    "Dismissed %d orphaned insights (entity_type=%s)",
                    count,
                    entity_type,
                )
                total += count

        return total

    # ------------------------------------------------------------------
    # Step 3: Dismiss past event insights
    # ------------------------------------------------------------------

    async def dismiss_past_event_insights(self) -> int:
        """Dismiss insights linked to past CuratedEvents (exclude adopted)."""
        from ..curation.models import CuratedEvent

        now = utc_now()

        # Sub-query: insight IDs linked to past events via entity
        past_event_subq = (
            select(InsightEntity.insight_id)
            .join(
                CuratedEvent,
                and_(
                    InsightEntity.entity_type == "event",
                    InsightEntity.entity_id == CuratedEvent.id,
                ),
            )
            .where(CuratedEvent.normalized_start < now)
        )

        # Exclude adopted insights
        adopted_ids_subq = (
            select(InsightEntity.insight_id)
            .where(InsightEntity.adopted_at.isnot(None))
        )

        result = await self.db.execute(
            update(Insight)
            .where(
                Insight.id.in_(past_event_subq),
                ~Insight.id.in_(adopted_ids_subq),
                Insight.status.in_([
                    InsightStatus.PENDING.value,
                    InsightStatus.ACTIVE.value,
                ]),
            )
            .values(
                status=InsightStatus.DISMISSED.value,
                dismissed_at=now,
            )
        )
        count = result.rowcount
        if count > 0:
            logger.info("Dismissed %d past-event insights", count)
        return count

    # ------------------------------------------------------------------
    # Step 4: Handle past important dates
    # ------------------------------------------------------------------

    async def handle_past_dates(self) -> int:
        """Handle insights linked to past important dates.

        - <= 7 days past + social obligation: demote (add prefix, urgency -20)
        - > 7 days or non-social: dismiss with feedback_source='hygiene_date_past'
        """
        from ..date_manager.date_models import ImportantDate

        now = utc_now()
        today = now.date()
        grace_cutoff = today - timedelta(days=_PAST_DATE_GRACE_DAYS)
        total = 0

        # Load insights linked to past important dates
        stmt = (
            select(Insight, ImportantDate.solar_date)
            .join(
                InsightEntity,
                InsightEntity.insight_id == Insight.id,
            )
            .join(
                ImportantDate,
                and_(
                    InsightEntity.entity_type == "important_date",
                    InsightEntity.entity_id == ImportantDate.id,
                ),
            )
            .where(
                ImportantDate.solar_date < today,
                Insight.status.in_([
                    InsightStatus.PENDING.value,
                    InsightStatus.ACTIVE.value,
                    InsightStatus.ACKNOWLEDGED.value,
                ]),
            )
        )
        result = await self.db.execute(stmt)
        rows = list(result.all())

        social_types = frozenset({"relationship", "favor", "memory"})

        for insight, solar_date in rows:
            is_social = insight.insight_type in social_types
            is_within_grace = solar_date >= grace_cutoff
            days_past = (today - solar_date).days

            if is_social and is_within_grace:
                # Demote but keep (idempotent: skip if already prefixed)
                if not insight.title.startswith("[已过期]"):
                    insight.title = f"[已过期] {insight.title}"
                    insight.content = f"原定日期已过{days_past}天，但仍可补上。{insight.content}"
                    insight.urgency = max(insight.urgency - 20, 30)
            else:
                # Dismiss
                insight.status = InsightStatus.DISMISSED.value
                insight.dismissed_at = now
                insight.feedback_source = "hygiene_date_past"

            total += 1

        if total > 0:
            logger.info("Handled %d past-date insights", total)
        return total

    # ------------------------------------------------------------------
    # Step 5: Obligation coverage audit
    # ------------------------------------------------------------------

    async def obligation_coverage_audit(self) -> int:
        """Find unresolved obligations without coverage and inject signals.

        Core invariant: every unresolved obligation must have one of:
        (a) active/acknowledged insight
        (b) pending PendingAction
        (c) permanent suppression rule
        (d) dismissed insight with regen_suppressed_until > now()
        (e) cumulative dismiss count >= type threshold

        If none: orphan obligation -> inject priority signal (up to 20).
        """
        uncovered: List[dict] = []

        uncovered.extend(await self._find_uncovered_favors())
        uncovered.extend(await self._find_uncovered_cold_relationships())
        uncovered.extend(await self._find_uncovered_commitments())

        # Cap at max signals per run
        to_inject = uncovered[:_MAX_ORPHAN_SIGNALS]

        for signal in to_inject:
            await self._inject_priority_signal(signal)

        if to_inject:
            logger.info(
                "Injected %d priority signals for uncovered obligations",
                len(to_inject),
            )
        return len(to_inject)

    async def _find_uncovered_favors(self) -> List[dict]:
        """Find pending FavorRecords with no insight/PA/suppression coverage.

        Uses all 5 NOT EXISTS conditions from the design:
        (a) No active/acknowledged insight (via insight_entities role='source')
        (b) No pending PA (via pending_actions.source_entity_id)
        (c) No permanent suppression rule (via user_preference_rules)
        (d) No dismissed insight with regen_suppressed_until > now()
        (e) No cumulative dismiss count >= 5
        """
        # Retrieve all family IDs that have pending favors
        from ..relationship.models import FavorRecord as FRModel

        family_stmt = (
            select(FRModel.family_id)
            .where(FRModel.status == "pending")
            .distinct()
        )
        family_result = await self.db.execute(family_stmt)
        family_ids = [row[0] for row in family_result.all()]

        results: List[dict] = []
        for family_id in family_ids:
            user_id = await self._resolve_user_id_for_family(family_id)
            if not user_id:
                continue

            raw = text("""
                SELECT fr.id, fr.contact_name FROM favor_records fr
                WHERE fr.status = 'pending' AND fr.family_id = :family_id
                  AND NOT EXISTS (SELECT 1 FROM insight_entities ie JOIN insights i ON ie.insight_id = i.id
                                  WHERE ie.entity_type = 'favor' AND ie.entity_id = fr.id AND ie.role = 'source'
                                    AND i.status IN ('pending', 'active', 'acknowledged'))
                  AND NOT EXISTS (SELECT 1 FROM pending_actions pa
                                  WHERE pa.source_entity_id = fr.id AND pa.status = 'pending')
                  AND NOT EXISTS (SELECT 1 FROM user_preference_rules upr
                                  WHERE upr.entity_type = 'favor' AND upr.entity_id = fr.id
                                    AND upr.rule_type = 'suppress_forever')
                  AND NOT EXISTS (SELECT 1 FROM insight_entities ie2 JOIN insights i2 ON ie2.insight_id = i2.id
                                  WHERE ie2.entity_type = 'favor' AND ie2.entity_id = fr.id AND ie2.role = 'source'
                                    AND i2.status = 'dismissed' AND i2.regen_suppressed_until > NOW())
                  AND NOT EXISTS (SELECT 1 FROM insight_entities ie3 JOIN insights i3 ON ie3.insight_id = i3.id
                                  WHERE ie3.entity_type = 'favor' AND ie3.entity_id = fr.id AND ie3.role = 'source'
                                    AND i3.feedback_source = 'user' AND i3.status = 'dismissed'
                                  GROUP BY ie3.entity_id HAVING COUNT(*) >= 5)
                LIMIT 20
            """)
            result = await self.db.execute(raw, {"family_id": str(family_id)})
            rows = list(result.all())
            results.extend(
                {
                    "entity_type": "favor",
                    "entity_id": row[0],
                    "family_id": family_id,
                    "user_id": user_id,
                    "context": f"Pending favor for contact {row[1]}",
                }
                for row in rows
            )
            if len(results) >= _MAX_ORPHAN_SIGNALS:
                break

        return results[:_MAX_ORPHAN_SIGNALS]

    async def _find_uncovered_cold_relationships(self) -> List[dict]:
        """Find cold relationships with no active insight coverage.

        Queries PersonProfile for persons whose composite temperature
        indicates 'cold', then excludes those already covered by an
        active/acknowledged insight with entity_type='person' and
        role='primary'.
        """
        from ..member.models.person_profile import PersonProfile

        has_active_insight = exists(
            select(InsightEntity.insight_id)
            .join(Insight, Insight.id == InsightEntity.insight_id)
            .where(
                InsightEntity.entity_type == "person",
                InsightEntity.entity_id == PersonProfile.id,
                InsightEntity.role == "primary",
                Insight.status.in_([
                    InsightStatus.ACTIVE.value,
                    InsightStatus.ACKNOWLEDGED.value,
                ]),
            )
        )

        stmt = (
            select(
                PersonProfile.id,
                PersonProfile.family_id,
                PersonProfile.name,
            )
            .where(
                PersonProfile.composite_temperature == "cold",
                ~has_active_insight,
            )
            .limit(_MAX_ORPHAN_SIGNALS)
        )

        try:
            result = await self.db.execute(stmt)
            rows = list(result.all())
        except Exception:
            # composite_temperature column may not exist yet; skip gracefully
            logger.debug(
                "Cold relationship query failed (column may not exist)",
                exc_info=True,
            )
            return []

        # Build results with user_id resolved per family
        results: List[dict] = []
        family_user_cache: Dict[UUID, Optional[str]] = {}
        for row in rows:
            fid = row[1]
            if fid not in family_user_cache:
                family_user_cache[fid] = await self._resolve_user_id_for_family(fid)
            uid = family_user_cache[fid]
            if not uid:
                continue
            results.append({
                "entity_type": "person",
                "entity_id": row[0],
                "family_id": fid,
                "user_id": uid,
                "context": f"Cold relationship: {row[2] or 'unknown'}",
            })
        return results

    async def _find_uncovered_commitments(self) -> List[dict]:
        """Find unfulfilled commitments with no insight coverage.

        Uses all 5 NOT EXISTS conditions (same as favors, threshold=3).
        """
        from ..memory.commitment_models import CommitmentItemRecord

        family_stmt = (
            select(CommitmentItemRecord.family_id)
            .where(
                CommitmentItemRecord.status.notin_(["fulfilled", "expired", "dropped"]),
            )
            .distinct()
        )
        family_result = await self.db.execute(family_stmt)
        family_ids = [row[0] for row in family_result.all()]

        results: List[dict] = []
        for family_id in family_ids:
            user_id = await self._resolve_user_id_for_family(family_id)
            if not user_id:
                continue

            raw = text("""
                SELECT cr.id, cr.what FROM commitment_items cr
                WHERE cr.status NOT IN ('fulfilled', 'expired', 'dropped')
                  AND cr.family_id = :family_id
                  AND NOT EXISTS (SELECT 1 FROM insight_entities ie JOIN insights i ON ie.insight_id = i.id
                                  WHERE ie.entity_type = 'commitment' AND ie.entity_id = cr.id AND ie.role = 'source'
                                    AND i.status IN ('pending', 'active', 'acknowledged'))
                  AND NOT EXISTS (SELECT 1 FROM pending_actions pa
                                  WHERE pa.source_entity_id = cr.id AND pa.status = 'pending')
                  AND NOT EXISTS (SELECT 1 FROM user_preference_rules upr
                                  WHERE upr.entity_type = 'commitment' AND upr.entity_id = cr.id
                                    AND upr.rule_type = 'suppress_forever')
                  AND NOT EXISTS (SELECT 1 FROM insight_entities ie2 JOIN insights i2 ON ie2.insight_id = i2.id
                                  WHERE ie2.entity_type = 'commitment' AND ie2.entity_id = cr.id AND ie2.role = 'source'
                                    AND i2.status = 'dismissed' AND i2.regen_suppressed_until > NOW())
                  AND NOT EXISTS (SELECT 1 FROM insight_entities ie3 JOIN insights i3 ON ie3.insight_id = i3.id
                                  WHERE ie3.entity_type = 'commitment' AND ie3.entity_id = cr.id AND ie3.role = 'source'
                                    AND i3.feedback_source = 'user' AND i3.status = 'dismissed'
                                  GROUP BY ie3.entity_id HAVING COUNT(*) >= :threshold)
                LIMIT 20
            """)
            result = await self.db.execute(
                raw,
                {"family_id": str(family_id), "threshold": _COMMITMENT_DISMISS_THRESHOLD},
            )
            rows = list(result.all())
            results.extend(
                {
                    "entity_type": "commitment",
                    "entity_id": row[0],
                    "family_id": family_id,
                    "user_id": user_id,
                    "context": f"Unfulfilled commitment: {(row[1] or '')[:80]}",
                }
                for row in rows
            )
            if len(results) >= _MAX_ORPHAN_SIGNALS:
                break

        return results[:_MAX_ORPHAN_SIGNALS]

    async def _inject_priority_signal(self, signal: dict) -> None:
        """Inject a priority signal for an uncovered obligation.

        Creates a PreferenceSignal record that the insight generation
        pipeline can pick up on its next scheduled run.
        """
        try:
            from ..curation.models import PreferenceSignal

            user_id = signal.get("user_id")
            family_id = signal.get("family_id")
            if not user_id or not family_id:
                logger.warning(
                    "Skipping priority signal: missing user_id or family_id for %s:%s",
                    signal.get("entity_type"),
                    signal.get("entity_id"),
                )
                return

            ps = PreferenceSignal(
                user_id=user_id,
                family_id=family_id,
                signal_type="orphan_obligation",
                source_type="hygiene",
                source_id=signal["entity_id"],
                source_context={
                    "entity_type": signal["entity_type"],
                    "context": signal.get("context", ""),
                },
                category_key=f"orphan:{signal['entity_type']}:{signal['entity_id']}",
            )
            self.db.add(ps)
        except Exception:
            logger.warning(
                "Failed to inject priority signal for %s:%s",
                signal.get("entity_type"),
                signal.get("entity_id"),
                exc_info=True,
            )

    # ------------------------------------------------------------------
    # Step 6: Recheck expired cascade actions
    # ------------------------------------------------------------------

    async def recheck_expired_cascade_actions(self) -> int:
        """Check expired PAs: if obligation still pending, clear regen suppression.

        When a PA created by InsightCascadeService expires without user action
        and the underlying obligation is still pending, we clear the
        regen_suppressed_until on the dismissed insight so the next generation
        cycle can re-create it.
        """
        from ..conversation.pending_action import PendingAction

        now = utc_now()

        # Find expired PAs from cascade (any cascade PA, not just trip-cancellation)
        stmt = (
            select(PendingAction)
            .where(
                PendingAction.status == "expired",
                PendingAction.payload["insight_id"].isnot(None),
            )
            .limit(100)
        )
        result = await self.db.execute(stmt)
        expired_pas = list(result.scalars())

        cleared = 0
        for pa in expired_pas:
            insight_id_str = pa.payload.get("insight_id")
            if insight_id_str is None:
                continue

            try:
                from uuid import UUID as _UUID
                insight_id = _UUID(insight_id_str)
            except (ValueError, TypeError):
                continue

            # Check if the original insight is dismissed with suppression
            insight_result = await self.db.execute(
                select(Insight).where(
                    Insight.id == insight_id,
                    Insight.status == InsightStatus.DISMISSED.value,
                )
            )
            insight = insight_result.scalar_one_or_none()
            if insight is None:
                continue

            # Clear regen suppression (column exists in DB from migration 120)
            # Use text-based update since ORM model may not have the column yet
            await self.db.execute(
                update(Insight)
                .where(Insight.id == insight_id)
                .values(regen_suppressed_until=None)
            )
            cleared += 1

        if cleared > 0:
            logger.info(
                "Cleared regen suppression on %d insights (expired cascade PAs)",
                cleared,
            )
        return cleared

    # ------------------------------------------------------------------
    # Step 7: Archive old dismissed/expired
    # ------------------------------------------------------------------

    async def archive_old(self) -> int:
        """Delete dismissed/expired insights older than 90 days."""
        cutoff = utc_now() - timedelta(days=_ARCHIVE_DAYS)

        result = await self.db.execute(
            delete(Insight).where(
                Insight.status.in_([
                    InsightStatus.DISMISSED.value,
                    InsightStatus.EXPIRED.value,
                ]),
                Insight.created_at < cutoff,
            )
        )
        count = result.rowcount
        if count > 0:
            logger.info("Archived (deleted) %d old insights", count)
        return count

    # ------------------------------------------------------------------
    # Step 8: Acknowledged expiry
    # ------------------------------------------------------------------

    async def check_acknowledged_expiry(self) -> int:
        """Revert acknowledged insights with expired snooze back to active.

        Acknowledged insights with snoozed_until <= now() are set back to
        active status so they reappear in the user's feed.
        """
        now = utc_now()

        # Use text-based column reference for snoozed_until
        # (exists in DB from migration 120)
        result = await self.db.execute(
            update(Insight)
            .where(
                Insight.status == InsightStatus.ACKNOWLEDGED.value,
                Insight.__table__.c.snoozed_until <= now,
            )
            .values(
                status=InsightStatus.ACTIVE.value,
                activated_at=now,
                snoozed_until=None,
            )
        )
        count = result.rowcount
        if count > 0:
            logger.info(
                "Reverted %d acknowledged insights to active (snooze expired)",
                count,
            )
        return count

    # ------------------------------------------------------------------
    # Step 9: Trip completed + adopted not done -> unadopt
    # ------------------------------------------------------------------

    async def check_trip_completed_adopted(self) -> int:
        """Unadopt insights for completed trips where the task was not done.

        When a trip is completed but an adopted insight entity was never
        marked done, clear the adopted_at so the obligation audit can
        take over.
        """
        from ..trip.models.trip_plan import TripPlan

        # Find trip entities with adopted_at set, linked to completed trips
        stmt = (
            select(InsightEntity)
            .join(
                TripPlan,
                and_(
                    InsightEntity.entity_type == "trip",
                    InsightEntity.entity_id == TripPlan.trip_id,
                ),
            )
            .where(
                TripPlan.status == "completed",
                InsightEntity.__table__.c.adopted_at.isnot(None),
                InsightEntity.__table__.c.done_at.is_(None),
            )
        )
        result = await self.db.execute(stmt)
        entities = list(result.scalars())

        for entity in entities:
            # Clear adopted_at via table-level update (column in DB, not ORM)
            await self.db.execute(
                update(InsightEntity.__table__)
                .where(
                    InsightEntity.__table__.c.insight_id == entity.insight_id,
                    InsightEntity.__table__.c.entity_type == entity.entity_type,
                    InsightEntity.__table__.c.entity_id == entity.entity_id,
                )
                .values(adopted_at=None)
            )

        count = len(entities)
        if count > 0:
            logger.info(
                "Unadopted %d insight entities (trip completed, task not done)",
                count,
            )
        return count

    # ------------------------------------------------------------------
    # Backfill: repair entity links for insights with zero InsightEntity rows
    # ------------------------------------------------------------------

    async def repair_entity_links(self, batch_size: int = 50) -> dict:
        """Repair insights that have zero InsightEntity rows by synthesizing
        entities from their source_context signal_ids.

        Additive only: creates InsightEntity rows, never changes insight
        status or content. Idempotent — re-running on repaired insights
        produces no changes (they already have InsightEntity rows).
        """
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        from .models import InsightCandidate

        # Find insights with zero entity rows
        stmt = (
            select(Insight.id, Insight.source_context, Insight.insight_type,
                   Insight.title, Insight.content)
            .outerjoin(InsightEntity, InsightEntity.insight_id == Insight.id)
            .where(
                and_(
                    InsightEntity.insight_id.is_(None),
                    Insight.status.in_([
                        InsightStatus.ACTIVE.value,
                        InsightStatus.PENDING.value,
                    ]),
                )
            )
            .limit(batch_size)
        )

        result = await self.db.execute(stmt)
        rows = result.all()

        if not rows:
            logger.info("repair_entity_links: no insights need repair")
            return {"repaired": 0, "skipped": 0}

        repaired = 0
        skipped = 0

        for row in rows:
            insight_id, source_ctx, insight_type, title, content = row
            source_ctx = source_ctx or {}
            signal_ids = source_ctx.get("signal_ids", [])

            if not signal_ids:
                skipped += 1
                continue

            # Build synthetic AllSignals by looking up domain records
            synthetic_signals = await self._lookup_signals_for_repair(signal_ids)

            candidate = InsightCandidate(
                insight_type=insight_type or "",
                title=title or "",
                content=content or "",
                source_context=source_ctx,
            )

            enriched = synthesize_entities([candidate], synthetic_signals)
            entities = enriched[0].entities

            if not entities:
                skipped += 1
                continue

            # Persist new InsightEntity rows
            entity_rows = []
            seen_keys: set = set()
            for spec in entities:
                if not spec.entity_id:
                    continue
                from uuid import UUID as UUID_type
                try:
                    eid = (
                        UUID_type(spec.entity_id)
                        if not isinstance(spec.entity_id, UUID_type)
                        else spec.entity_id
                    )
                except (ValueError, AttributeError):
                    continue
                key = (spec.entity_type, eid)
                if key not in seen_keys:
                    seen_keys.add(key)
                    entity_rows.append({
                        "insight_id": insight_id,
                        "entity_type": spec.entity_type,
                        "entity_id": eid,
                        "role": spec.role,
                    })

            if entity_rows:
                await self.db.execute(
                    pg_insert(InsightEntity)
                    .values(entity_rows)
                    .on_conflict_do_nothing()
                )
                repaired += 1
            else:
                skipped += 1

        logger.info(
            "repair_entity_links: repaired=%d skipped=%d (batch_size=%d)",
            repaired, skipped, batch_size,
        )
        return {"repaired": repaired, "skipped": skipped}

    async def _lookup_signals_for_repair(
        self, signal_ids: list
    ) -> AllSignals:
        """Look up domain records by signal IDs to build synthetic AllSignals.

        Handles deleted/archived records gracefully by skipping them.
        """
        synthetic = AllSignals()

        for sid in signal_ids:
            # Try event lookup
            try:
                from ..curation.models import CuratedEvent
                result = await self.db.execute(
                    select(
                        CuratedEvent.id,
                        CuratedEvent.trip_id,
                    ).where(CuratedEvent.id == sid)
                )
                row = result.one_or_none()
                if row:
                    synthetic.events.append({
                        "event_id": str(row[0]),
                        "trip_id": str(row[1]) if row[1] else None,
                    })
                    continue
            except Exception:
                pass

            # Try favor lookup
            try:
                from ..relationship.models import FavorRecord
                result = await self.db.execute(
                    select(
                        FavorRecord.id,
                        FavorRecord.contact_id,
                    ).where(FavorRecord.id == sid)
                )
                row = result.one_or_none()
                if row:
                    synthetic.protected.append({
                        "favor_record_id": str(row[0]),
                        "contact_id": str(row[1]) if row[1] else None,
                    })
                    continue
            except Exception:
                pass

            # Try commitment lookup
            try:
                from ..memory.commitment_models import CommitmentItemRecord
                result = await self.db.execute(
                    select(CommitmentItemRecord.id).where(
                        CommitmentItemRecord.id == sid
                    )
                )
                row = result.one_or_none()
                if row:
                    synthetic.protected.append({
                        "commitment_id": str(row[0]),
                    })
                    continue
            except Exception:
                pass

            # Try relationship/person lookup
            try:
                from ..member.models.person_profile import PersonProfile
                result = await self.db.execute(
                    select(PersonProfile.id).where(PersonProfile.id == sid)
                )
                row = result.one_or_none()
                if row:
                    synthetic.relationships.append({
                        "person_id": str(row[0]),
                    })
                    continue
            except Exception:
                pass

            logger.debug(
                "repair_entity_links: signal_id %s not found in any domain table "
                "(deleted or archived)",
                sid,
            )

        return synthetic
