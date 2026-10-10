"""Insight Pipeline - Unified scheduled and reactive insight generation.

Replaces scattered generation paths with a single pipeline that:
1. Collects signals from all sources (events, relationships, favors, memories, commitments)
2. Compresses signals within a token budget
3. Generates insights via a single Haiku LLM call
4. Deduplicates, applies user preferences, and persists

Entry points:
- run_scheduled(): Celery Beat daily at 06:00 UTC
- run_reactive(): Event-driven per CuratedEvent
- run_reactive_commitment(): Urgent commitment trigger (deadline <= 2 days)
"""

from __future__ import annotations

import dataclasses
import json
import hashlib
from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any, Dict, List, Optional, Set, TYPE_CHECKING
from uuid import UUID, uuid4

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from ...config.logging import get_logger
from ...config.settings import settings
from ...core.utils.timezone import utc_now, local_today
from .constants import SECRETARY_PERSONA_PROMPT
from .expiry_policy import compute_expires_at
from .insight_enrichment import (
    synthesize_entities,
    inject_trip_entities,
    inject_person_entities,
    ensure_action_options,
    generate_dynamic_action_options,
)
from .insight_dedup_aware import (
    apply_updates,
    build_dedup_aware_prompt_section,
    expire_unreferenced_insights,
    fetch_active_insights,
    process_dispositions,
)
from .insight_llm_client import call_llm_and_parse
from .insight_signal_collector import AllSignals, InsightSignalCollector
from .information_triage import InformationTriage
from .life_stage_detector import LifeStage, LifeStageContext, detect_life_stage
from .rule_engine_insights import RuleEngineInsights
from .insight_trend_detector import InsightTrendDetector
from .prep_chain_engine import PrepChainEngine
from .models import (
    EntitySpec,
    InformationTier,
    Insight,
    InsightCandidate,
    InsightEntity,
    InsightStatus,
    InsightType,
    SUPPRESSION_THRESHOLDS,
    TYPE_TTL_OVERRIDES,
)

if TYPE_CHECKING:
    from ..curation.models import (
        CuratedEvent,
        EventAssociation,
        FamilyPreference,
        UserPreferenceRule,
    )

logger = get_logger(__name__)


# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

_BATCH_SYSTEM_PROMPT = SECRETARY_PERSONA_PROMPT + """你的任务是根据以下信号为用户生成洞察提醒。

## 规则
1. 每条洞察必须基于至少一条信号，不要编造
2. 优先处理 protected 信号（社交义务、承诺），这些不可忽略
3. 语气温暖自然，像家人叮嘱
4. 用"记得"、"别忘了"、"注意"而非"建议"、"请注意"
5. 每条洞察简洁，标题10字以内，内容50字以内
6. 合理设置 importance (0-100): >=80 重要, 50-79 一般, <50 低优先
7. 合理设置 urgency (0-100): >=80 紧急, 50-79 一般, <50 低优先
8. suggested_action: 具体可操作的建议步骤
9. action_options: 可选操作按钮列表（如适用）
10. 合并同类义务：如果多笔人情/义务涉及同一个人，合并为一条洞察（例如不要既生成"A大额人情"又生成"A和B人情待还"，应该只保留合并版本）
11. 正向信号（联系频繁、承诺履行、家庭时间充足等）应生成 positive_affirmation 类型洞察，目标占比 20-30%
12. source_signal_ids 必须包含至少一个对应信号的ID字段值（如 event_id、favor_record_id、commitment_id 等）

## 洞察类型说明
- time: 时间和行程提醒
- relationship: 关系维护提醒
- favor: 人情往来义务
- social_obligation: 节日/社交义务问候。当 holidays 信号中包含即将到来的节日时，为每个节日生成一条合并的问候洞察，包含所有需要问候的人。**每个节日只生成一条洞察，不要为每个人分开生成。**
- efficiency: 效率和习惯
- health: 健康相关
- finance: 财务相关
- memory: 重要记忆
- positive_affirmation: 正向确认和鼓励，当信号显示用户在某方面做得很好时（如：联系频繁、承诺履行、家庭时间充足），importance <=50，urgency <=25。示例：{"insight_type": "positive_affirmation", "title": "和妈妈关系很温暖", "content": "你最近一周每天都和妈妈通话，关系非常温暖。继续保持！", "importance": 40, "urgency": 20}

## 输出格式（严格JSON数组，不含 markdown 代码块）
[
  {
    "insight_type": "time|relationship|favor|social_obligation|efficiency|health|finance|memory|positive_affirmation",
    "title": "<=10字简短标题",
    "content": "<=50字具体可执行的建议",
    "importance": 50,
    "urgency": 50,
    "suggested_action": "具体操作建议",
    "action_options": [{"label": "按钮文本", "action_type": "open_chat|create_pending_action|open_detail", "action_payload": {}}],
    "source_signal_ids": ["信号来源ID"]
  }
]

注意: dedup_key 由系统自动计算，不需要在输出中包含。

## 去重处理协议 (Disposition)
如果用户消息中包含"现有活跃洞察"列表，你必须对每条现有洞察做出明确处置，并标注 disposition 字段:
- "KEEP": 该洞察仍然有效，无需变更（需提供 existing_id，title/content 可为空）
- "UPDATE": 该洞察需要更新（需提供 existing_id 和新的 content/importance/urgency）
- "DELETE": 该洞察已过时、重复或不再需要（需提供 existing_id，title/content 可为空）
- "NEW": 全新洞察（默认，无需 existing_id）

重要：同一主题的多条重复洞察，只保留一条（UPDATE），其余全部 DELETE。
如果没有提供现有洞察列表，所有输出默认为 "NEW"。"""

_REACTIVE_SYSTEM_PROMPT = SECRETARY_PERSONA_PROMPT + """根据以下事件信息，判断是否需要生成洞察提醒。
如果需要，输出严格JSON数组；如果不需要，输出空数组 []。

## 规则
1. 只有有价值的洞察才输出（提前准备、关联人物、潜在冲突等）
2. 标题10字以内，内容50字以内
3. importance (0-100), urgency (0-100)
4. suggested_action: 具体可操作的建议步骤

## 输出格式（严格JSON数组，不含 markdown 代码块）
[{"insight_type":"...","title":"...","content":"...","importance":50,"urgency":50,"suggested_action":"...","action_options":[{"label":"按钮文本","action_type":"open_chat|create_pending_action|open_detail","action_payload":{}}],"source_signal_ids":[]}]

## 去重处理协议 (Disposition)
如果用户消息中包含"现有活跃洞察"列表，你必须对每条现有洞察做出明确处置，并标注 disposition 字段:
- "KEEP": 该洞察仍然有效，无需变更（需提供 existing_id，title/content 可为空）
- "UPDATE": 该洞察需要更新（需提供 existing_id 和新的 content/importance/urgency）
- "DELETE": 该洞察已过时、重复或不再需要（需提供 existing_id，title/content 可为空）
- "NEW": 全新洞察（默认，无需 existing_id）

重要：同一主题的多条重复洞察，只保留一条（UPDATE），其余全部 DELETE。
如果没有提供现有洞察列表，所有输出默认为 "NEW"。"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _urgency_label(urgency: int) -> str:
    """Convert numeric urgency to a human-readable label."""
    if urgency >= 70:
        return "high"
    if urgency >= 40:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

class InsightPipeline:
    """Unified insight generation pipeline.

    Handles both scheduled batch generation and reactive per-event generation.
    """

    SIGNAL_TOKEN_BUDGET = 8000

    def __init__(self, db: AsyncSession):
        self.db = db

    # ==================== Public entry points ====================

    async def run_scheduled(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: date,
    ) -> List[UUID]:
        """Main scheduled batch generation (Celery Beat 06:00 UTC).

        Steps:
        1. Load preferences
        2. Build budget from preferences
        3. Refresh stale insights
        4. Collect all signal sources
        5. Compress signals
        6. Single LLM call
        7. Contextual reactivation
        8. Compute dedup_key per candidate
        9. Dedup
        10. Apply preferences
        11. Person budget filter
        12. Persist
        13. Trigger sidekick evaluation
        """
        try:
            prefs = await self._load_preferences(user_id, family_id)
            budget = self._build_budget(prefs)

            await self._refresh_stale_insights(user_id)

            # ── Life stage detection (zero-LLM cost) ──────────────────────
            try:
                life_stage_ctx = await detect_life_stage(self.db, family_id)
                logger.debug(
                    "Life stage for family %s: %s",
                    family_id, life_stage_ctx.stage.value,
                )
            except Exception as ls_exc:
                logger.warning(
                    "Life stage detection failed for family %s: %s",
                    family_id, ls_exc,
                )
                life_stage_ctx = LifeStageContext(
                    stage=LifeStage.UNKNOWN,
                    youngest_child_age=None,
                    child_count=0,
                    strategy_adjustments={
                        "focus_areas": [],
                        "suppress_types": [],
                        "boost_types": [],
                        "description": "数据不足，无法判断家庭阶段",
                    },
                )

            signals = await self._collect_all_signals(
                user_id, family_id, target_date,
            )

            if signals.total_count() == 0:
                logger.info("No signals collected for user %s, skipping generation", user_id)
                return []

            compressed = self._compress_signals(signals, budget)

            # ── L1 Rule engine (zero-LLM cost) ───────────────────────────────
            try:
                rule_engine = RuleEngineInsights()
                rule_candidates = await rule_engine.generate(
                    user_id=user_id,
                    family_id=family_id,
                    target_date=target_date,
                    signals=compressed,
                    db=self.db,
                )
                logger.debug(
                    "RuleEngineInsights produced %d candidates for user %s",
                    len(rule_candidates), user_id,
                )
            except Exception as rule_exc:
                logger.warning(
                    "RuleEngineInsights failed for user %s: %s", user_id, rule_exc
                )
                rule_candidates = []

            # ── Trend detection (zero-LLM cost) ──────────────────────────
            try:
                trend_detector = InsightTrendDetector(self.db)
                trend_candidates = await trend_detector.detect(
                    user_id=user_id,
                    family_id=family_id,
                )
                logger.debug(
                    "InsightTrendDetector produced %d candidates for user %s",
                    len(trend_candidates), user_id,
                )
            except Exception as trend_exc:
                logger.warning(
                    "InsightTrendDetector failed for user %s: %s", user_id, trend_exc
                )
                trend_candidates = []

            # ── Prep chain (zero-LLM cost) ────────────────────────────────
            try:
                prep_engine = PrepChainEngine()
                prep_candidates = prep_engine.generate_for_date(
                    target_date=target_date,
                    events=compressed.events,
                )
                logger.debug(
                    "PrepChainEngine produced %d candidates for user %s",
                    len(prep_candidates), user_id,
                )
            except Exception as prep_exc:
                logger.warning(
                    "PrepChainEngine failed for user %s: %s", user_id, prep_exc
                )
                prep_candidates = []

            candidates = await self._generate_batch(
                compressed, budget, life_stage_ctx=life_stage_ctx,
                user_id=user_id,
            )

            # LLM-aware dedup: process dispositions from LLM output
            try:
                disp_result = process_dispositions(candidates)
                if disp_result.update_specs:
                    await apply_updates(self.db, user_id, disp_result.update_specs)

                # Expire: LLM-marked DELETE + unreferenced active insights.
                # "referenced" = KEEP + UPDATE (still wanted by LLM).
                # Everything else (DELETE + not mentioned) gets expired.
                kept_ids = set(
                    disp_result.keep_ids
                    + [s["existing_id"] for s in disp_result.update_specs]
                )
                try:
                    active_rows = await fetch_active_insights(self.db, user_id)
                    active_ids = [row.id for row in active_rows]
                    await expire_unreferenced_insights(
                        self.db, user_id, active_ids, list(kept_ids),
                    )
                except Exception as gc_exc:
                    logger.warning(
                        "Disposition GC failed: %s", gc_exc,
                    )

                candidates = disp_result.new_candidates
            except Exception as disp_exc:
                logger.warning(
                    "Disposition processing failed, treating all as NEW: %s",
                    disp_exc,
                )

            # Merge L1 rule candidates (already tagged generation_level=L1_RULE)
            candidates.extend(rule_candidates)
            candidates.extend(trend_candidates)
            candidates.extend(prep_candidates)

            # Post-LLM entity injection: deterministic synthesis + cross-ref amplifiers
            candidates = synthesize_entities(candidates, compressed)
            candidates = inject_trip_entities(candidates, compressed)
            candidates = inject_person_entities(candidates, compressed)

            reactivated = await self._contextual_reactivation(user_id, compressed)
            candidates.extend(reactivated)

            affirmations = self._generate_positive_affirmations(signals, target_date)
            candidates.extend(affirmations)

            # ── Dynamic action_options (LLM-enhanced with rule fallback) ────
            # generate_dynamic_action_options has internal try/except — never raises
            candidates = await generate_dynamic_action_options(candidates)

            # ── Information triage: stamp information_tier on every candidate ─
            triage = InformationTriage()
            candidates = triage.classify_batch(candidates)

            # ── G1: Materialize L0_AUTO as PendingActions (no user insight) ──
            l0_auto = [
                c for c in candidates
                if c.information_tier == InformationTier.L0_AUTO.value
            ]
            candidates = [
                c for c in candidates
                if c.information_tier != InformationTier.L0_AUTO.value
            ]
            if l0_auto:
                await self._materialize_l0_auto(l0_auto, user_id, family_id)

            # ── G5: Enforce positive affirmation ratio (20-30%) ──────────────
            candidates = self._enforce_positive_ratio(candidates)

            # ── Life stage filtering (suppress/boost by stage) ────────────
            candidates = self._apply_life_stage_adjustments(
                candidates, life_stage_ctx,
            )

            candidates = self._cross_candidate_dedup(candidates)

            candidates = [
                dataclasses.replace(
                    c,
                    user_id=user_id if c.user_id is None else c.user_id,
                    family_id=family_id if c.family_id is None else c.family_id,
                    dedup_key=self._compute_dedup_key(c),
                )
                for c in candidates
            ]

            candidates = await self._dedup(candidates, user_id)
            candidates = self._apply_preferences(candidates, prefs)
            candidates = self._person_budget_filter(candidates)

            # ── M4 Self-model weight adjustment (zero-LLM cost) ───────────
            candidates = await self._apply_self_model_weights(
                candidates, family_id,
            )

            inserted_ids = await self._persist(candidates)

            if inserted_ids:
                await self._trigger_sidekick_evaluation(user_id, inserted_ids)

            # ── TrackedThread integration (post-persist) ──────────────────
            # 1. Auto-create threads for newly-generated commitment/favor/event candidates.
            # 2. Check active threads for due checkpoints and persist resulting candidates.
            # Both steps are isolated with try/except so any failure cannot abort the pipeline.
            await self._integrate_tracked_threads(
                candidates=candidates,
                user_id=user_id,
                family_id=family_id,
                target_date=target_date,
            )

            # ── Queue L3 deep reasoning (async, doesn't block the pipeline) ──
            try:
                from .tasks import generate_deep_insights_task

                generate_deep_insights_task.delay(
                    str(user_id),
                    str(family_id),
                    target_date.isoformat(),
                )
                logger.debug(
                    "Queued L3 deep reasoning task for user %s", user_id,
                )
            except Exception as deep_exc:
                logger.warning(
                    "Failed to queue L3 deep reasoning for user %s: %s",
                    user_id, deep_exc,
                )

            logger.info(
                "InsightPipeline.run_scheduled: user=%s signals=%d candidates=%d persisted=%d",
                user_id, signals.total_count(), len(candidates), len(inserted_ids),
            )
            return inserted_ids

        except Exception as exc:
            logger.error("InsightPipeline.run_scheduled failed for user %s: %s", user_id, exc)
            try:
                await self.db.rollback()
            except Exception:
                pass
            return []

    async def run_reactive(
        self,
        event: "CuratedEvent",
        family_id: UUID,
    ) -> List[UUID]:
        """Event-driven reactive generation. Single Haiku call per event."""
        try:
            user_id = event.user_id
            if user_id is None:
                logger.warning("CuratedEvent %s has no user_id, skipping reactive", event.id)
                return []

            context = self._build_event_context(event)
            candidates = await self._generate_single(context, user_id=user_id)

            for c in candidates:
                c.user_id = user_id
                c.family_id = family_id
                c.source_context["_source"] = "trip_event"
                # Ensure the triggering event is in entities
                event_entity = EntitySpec(entity_type="event", entity_id=str(event.id), role="related")
                if not any(e.entity_type == "event" and e.entity_id == str(event.id) for e in c.entities):
                    c.entities.append(event_entity)
                # Ensure trip entity if the event belongs to a trip
                if event.trip_id is not None:
                    trip_id_str = str(event.trip_id)
                    if not any(e.entity_type == "trip" and e.entity_id == trip_id_str for e in c.entities):
                        c.entities.append(
                            EntitySpec(entity_type="trip", entity_id=trip_id_str, role="related")
                        )
                c.dedup_key = self._compute_dedup_key(c)

            candidates = await self._dedup(candidates, user_id)

            prefs = await self._load_preferences(user_id, family_id)
            candidates = self._apply_preferences(candidates, prefs)

            return await self._persist(candidates)

        except Exception as exc:
            logger.error("InsightPipeline.run_reactive failed for event %s: %s", event.id, exc)
            return []

    async def run_reactive_commitment(
        self,
        commitment: Any,
        user_id: UUID,
        family_id: UUID,
    ) -> List[UUID]:
        """Urgent commitment trigger: firm commitment with deadline <= 2 days."""
        try:
            context = {
                "trigger": "urgent_commitment",
                "commitment_id": str(commitment.id),
                "who": commitment.who,
                "what": commitment.what,
                "to_whom": commitment.to_whom,
                "deadline": commitment.deadline.isoformat() if commitment.deadline else None,
                "commitment_type": commitment.commitment_type,
            }

            candidates = await self._generate_single(context, user_id=user_id)

            for c in candidates:
                c.user_id = user_id
                c.family_id = family_id
                c.source_context["commitment_id"] = str(commitment.id)
                c.source_context["_source"] = "reactive_commitment"
                # Add commitment as source entity
                commitment_entity = EntitySpec(
                    entity_type="commitment", entity_id=str(commitment.id), role="source",
                )
                if not any(e.entity_type == "commitment" for e in c.entities):
                    c.entities.append(commitment_entity)
                c.dedup_key = self._compute_dedup_key(c)

            candidates = await self._dedup(candidates, user_id)

            prefs = await self._load_preferences(user_id, family_id)
            candidates = self._apply_preferences(candidates, prefs)

            return await self._persist(candidates)

        except Exception as exc:
            logger.error(
                "InsightPipeline.run_reactive_commitment failed for commitment %s: %s",
                getattr(commitment, "id", "?"), exc,
            )
            return []

    # ==================== Dedup key computation ====================

    def _compute_dedup_key(self, candidate: InsightCandidate) -> str:
        """Pipeline-side dedup_key computation based on obligation identity.

        Uses EntitySpec list with roles for proper obligation identification:
        - favor → favor:{favor_record_id} (via source entity)
        - relationship → relationship:{person_id} (via primary person)
        - commitment → commitment:{commitment_id} (via source entity)
        - trip → trip:{trip_id}:{insight_type} (one active insight per trip per type)
        - time → time:{important_date_id}:{event_id}
        - fallback → {type}:{sorted entity IDs}
        """
        source_entities = [e for e in candidate.entities if e.role == "source"]

        # Favor: use source favor entity
        if candidate.insight_type == InsightType.FAVOR.value and source_entities:
            favor_src = next((e for e in source_entities if e.entity_type == "favor"), None)
            if favor_src:
                return f"favor:{favor_src.entity_id}"

        # Also check source_context for backward compat
        sc = candidate.source_context
        favor_id = sc.get("favor_record_id")
        if favor_id:
            return f"favor:{favor_id}"

        # Relationship: use primary person
        if candidate.insight_type == InsightType.RELATIONSHIP.value:
            primary_person = next(
                (e for e in candidate.entities if e.entity_type == "person" and e.role == "primary"),
                None,
            )
            if primary_person:
                return f"relationship:{primary_person.entity_id}"
            person_ids = candidate.person_ids
            if person_ids:
                return f"relationship:{sorted(person_ids)[0]}"

        # Commitment: use source entity or source_context
        commitment_src = next(
            (e for e in source_entities if e.entity_type == "commitment"), None,
        )
        if commitment_src:
            return f"commitment:{commitment_src.entity_id}"
        commitment_id = sc.get("commitment_id")
        if commitment_id:
            return f"commitment:{commitment_id}"

        # Trip: one insight per trip per type (prevents near-duplicate
        # insights when multiple events of the same trip trigger generation)
        trip_entities = [e for e in candidate.entities if e.entity_type == "trip"]
        if len(trip_entities) == 1:
            return f"trip:{trip_entities[0].entity_id}:{candidate.insight_type}"

        # Time: important_date + event
        if candidate.insight_type == InsightType.TIME.value:
            idate_entity = next(
                (e for e in candidate.entities if e.entity_type == "important_date"), None,
            )
            idate_id = idate_entity.entity_id if idate_entity else sc.get("important_date_id")
            event_id = candidate.event_ids[0] if candidate.event_ids else ""
            if idate_id:
                return f"time:{idate_id}:{event_id}"

        # Generic source entity
        if source_entities:
            return f"{source_entities[0].entity_type}:{source_entities[0].entity_id}"

        # Fallback: type + sorted entity IDs (hashed if too many)
        all_ids = sorted(set(e.entity_id for e in candidate.entities if e.role in ("primary", "related")))
        if all_ids:
            joined = ",".join(all_ids)
            # Hash if the raw ID list would push dedup_key past VARCHAR(255)
            if len(candidate.insight_type) + 1 + len(joined) > 255:
                id_part = hashlib.sha256(joined.encode()).hexdigest()[:16]
            else:
                id_part = joined
        else:
            # Hash title only (not content) so that same-topic insights with
            # different LLM-generated content still dedup correctly.
            id_part = hashlib.md5(candidate.title.encode()).hexdigest()[:12]
        return f"{candidate.insight_type}:{id_part}"

    # ==================== Cross-candidate overlap dedup ====================

    @staticmethod
    def _apply_life_stage_adjustments(
        candidates: List[InsightCandidate],
        life_stage_ctx: LifeStageContext,
    ) -> List[InsightCandidate]:
        """Apply life-stage-based filtering and boosting to candidates.

        - Suppresses insight types listed in strategy_adjustments.suppress_types
          by reducing their importance below the persist threshold.
        - Boosts insight types listed in strategy_adjustments.boost_types
          by increasing their importance.
        """
        if life_stage_ctx.stage == LifeStage.UNKNOWN:
            return candidates

        suppress_types = set(
            life_stage_ctx.strategy_adjustments.get("suppress_types", [])
        )
        boost_types = set(
            life_stage_ctx.strategy_adjustments.get("boost_types", [])
        )

        _SUPPRESS_IMPORTANCE_REDUCTION = 20
        _BOOST_IMPORTANCE_INCREASE = 15

        adjusted: List[InsightCandidate] = []
        for candidate in candidates:
            if candidate.insight_type in suppress_types:
                # Only suppress non-protected (low importance) candidates
                if candidate.importance < 70:
                    adjusted.append(dataclasses.replace(
                        candidate,
                        importance=max(0, candidate.importance - _SUPPRESS_IMPORTANCE_REDUCTION),
                        context_hint=(
                            candidate.context_hint or ""
                        ) + f" [life_stage:{life_stage_ctx.stage.value}:suppressed]",
                    ))
                else:
                    adjusted.append(candidate)
            elif candidate.insight_type in boost_types:
                adjusted.append(dataclasses.replace(
                    candidate,
                    importance=min(100, candidate.importance + _BOOST_IMPORTANCE_INCREASE),
                    context_hint=(
                        candidate.context_hint or ""
                    ) + f" [life_stage:{life_stage_ctx.stage.value}:boosted]",
                ))
            else:
                adjusted.append(candidate)

        return adjusted

    @staticmethod
    def _cross_candidate_dedup(
        candidates: List[InsightCandidate],
    ) -> List[InsightCandidate]:
        """Remove candidates whose person entities are a strict subset of another.

        When the LLM generates both an individual insight (e.g. "Elena大额人情")
        and a combined insight (e.g. "Elena和外婆人情待还"), the individual one
        is redundant. Keep only the superset.

        Only applies to favor/relationship insights that share person entities.
        """
        if len(candidates) <= 1:
            return candidates

        favor_types = {InsightType.FAVOR.value, InsightType.RELATIONSHIP.value, InsightType.SOCIAL_OBLIGATION.value}

        # Separate favor-related candidates from others
        favor_candidates: List[InsightCandidate] = []
        other_candidates: List[InsightCandidate] = []
        for c in candidates:
            if c.insight_type in favor_types and c.person_ids:
                favor_candidates.append(c)
            else:
                other_candidates.append(c)

        if len(favor_candidates) <= 1:
            return candidates

        # Build person_id sets for each favor candidate
        person_sets = [set(c.person_ids) for c in favor_candidates]

        # Mark candidates whose person set is a strict subset of another
        drop_indices: Set[int] = set()
        for i, set_i in enumerate(person_sets):
            if i in drop_indices:
                continue
            for j, set_j in enumerate(person_sets):
                if i == j or j in drop_indices:
                    continue
                # i is a strict subset of j → drop i (keep the broader one)
                if set_i < set_j:
                    drop_indices.add(i)
                    break
                # j is a strict subset of i → drop j
                if set_j < set_i:
                    drop_indices.add(j)

        kept_favor = [
            c for idx, c in enumerate(favor_candidates) if idx not in drop_indices
        ]

        if drop_indices:
            logger.info(
                "Cross-candidate dedup: dropped %d subset insights from %d favor candidates",
                len(drop_indices), len(favor_candidates),
            )

        return other_candidates + kept_favor

    # ==================== Signal compression ====================

    def _compress_signals(self, signals: AllSignals, budget: int) -> AllSignals:
        """Priority: protected > holidays > events > relationships > memories > associations.

        Whole-item discard. Token estimation: len(text) / 3.5 + 20% buffer.
        Protected signals are never truncated. Holidays are high priority
        since they drive social obligation insights.
        """
        remaining = budget

        def _estimate_tokens(items: List[Dict[str, Any]]) -> int:
            text = json.dumps(items, ensure_ascii=False)
            return int(len(text) / 3.5 * 1.2)

        def _fit(items: List[Dict[str, Any]], budget_left: int) -> tuple:
            """Return (kept_items, tokens_used)."""
            if not items:
                return [], 0
            tokens = _estimate_tokens(items)
            if tokens <= budget_left:
                return list(items), tokens
            # Whole-item discard from the end
            kept = []
            used = 0
            for item in items:
                item_tokens = _estimate_tokens([item])
                if used + item_tokens > budget_left:
                    break
                kept.append(item)
                used += item_tokens
            return kept, used

        result = AllSignals()

        # Protected signals are never truncated
        result.protected = list(signals.protected)
        remaining -= _estimate_tokens(result.protected)

        # Remaining categories in priority order
        for cat in ("holidays", "events", "relationships", "memories", "associations"):
            source = getattr(signals, cat, [])
            kept, used = _fit(source, remaining)
            setattr(result, cat, kept)
            remaining -= used

        return result

    # ==================== LLM generation ====================

    async def _generate_batch(
        self,
        signals: AllSignals,
        budget: int,
        life_stage_ctx: Optional[LifeStageContext] = None,
        user_id: Optional[UUID] = None,
    ) -> List[InsightCandidate]:
        """Single Haiku 4.5 call for batch generation."""
        signal_payload = json.dumps(
            {
                "protected": signals.protected,
                "events": signals.events,
                "holidays": signals.holidays,
                "relationships": signals.relationships,
                "memories": signals.memories,
                "associations": signals.associations,
            },
            ensure_ascii=False,
        )

        today_str = local_today().isoformat()

        # Build life stage context hint for LLM
        life_stage_hint = ""
        if (
            life_stage_ctx is not None
            and life_stage_ctx.stage != LifeStage.UNKNOWN
        ):
            adjustments = life_stage_ctx.strategy_adjustments
            description = adjustments.get("description", "")
            focus = ", ".join(adjustments.get("focus_areas", []))
            life_stage_hint = (
                f"\n\n## 家庭阶段上下文\n"
                f"当前阶段: {description}\n"
                f"重点关注: {focus}\n"
                f"子女数量: {life_stage_ctx.child_count}"
            )
            if life_stage_ctx.youngest_child_age is not None:
                life_stage_hint += (
                    f", 最小孩子年龄: {life_stage_ctx.youngest_child_age}岁"
                )
            life_stage_hint += (
                "\n请根据家庭阶段调整洞察的侧重点和语气。"
            )

        # LLM-aware dedup: inject active insights into user prompt
        dedup_section = ""
        if user_id is not None:
            try:
                active_rows = await fetch_active_insights(self.db, user_id)
                dedup_section = build_dedup_aware_prompt_section(active_rows)
            except Exception as exc:
                logger.warning(
                    "Failed to fetch active insights for dedup-aware prompt: %s",
                    exc,
                )

        user_prompt = (
            f"今天是 {today_str}。{life_stage_hint}"
            f"\n\n以下是收集到的信号：\n{signal_payload}"
            f"{dedup_section}"
        )

        return await call_llm_and_parse(
            system_prompt=_BATCH_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_attempts=2,
        )

    async def _generate_single(
        self,
        context: dict,
        user_id: Optional[UUID] = None,
    ) -> List[InsightCandidate]:
        """Single reactive generation for one event/commitment context."""
        today_str = local_today().isoformat()

        # LLM-aware dedup: inject active insights into user prompt
        dedup_section = ""
        if user_id is not None:
            try:
                active_rows = await fetch_active_insights(self.db, user_id)
                dedup_section = build_dedup_aware_prompt_section(active_rows)
            except Exception as exc:
                logger.warning(
                    "Failed to fetch active insights for reactive dedup: %s",
                    exc,
                )

        user_prompt = (
            f"今天是 {today_str}。\n\n事件信息：\n"
            f"{json.dumps(context, ensure_ascii=False)}"
            f"{dedup_section}"
        )

        return await call_llm_and_parse(
            system_prompt=_REACTIVE_SYSTEM_PROMPT,
            user_prompt=user_prompt,
            max_attempts=2,
        )

    # ==================== Dedup ====================

    async def _dedup(
        self, candidates: List[InsightCandidate], user_id: UUID,
    ) -> List[InsightCandidate]:
        """Dedup against existing active insights by dedup_key.

        Also checks cumulative dismiss count for auto-upgrade to Level 3 (suppress).
        """
        if not candidates:
            return []

        dedup_keys = [c.dedup_key for c in candidates if c.dedup_key]
        if not dedup_keys:
            return candidates

        # Query existing active insights with matching dedup keys
        existing_stmt = (
            select(Insight.dedup_key, Insight.status)
            .where(
                and_(
                    Insight.user_id == user_id,
                    Insight.dedup_key.in_(dedup_keys),
                    Insight.status.in_([
                        InsightStatus.PENDING.value,
                        InsightStatus.ACTIVE.value,
                        InsightStatus.ACKNOWLEDGED.value,
                    ]),
                )
            )
        )
        result = await self.db.execute(existing_stmt)
        existing_keys = {row[0] for row in result.all()}

        # Check cumulative dismiss count for auto-upgrade
        dismiss_stmt = (
            select(
                Insight.dedup_key,
                func.count(Insight.id),
            )
            .where(
                and_(
                    Insight.user_id == user_id,
                    Insight.dedup_key.in_(dedup_keys),
                    Insight.status == InsightStatus.DISMISSED.value,
                    Insight.feedback_source == "user",
                )
            )
            .group_by(Insight.dedup_key)
        )
        dismiss_result = await self.db.execute(dismiss_stmt)
        dismiss_counts = {row[0]: row[1] for row in dismiss_result.all()}

        kept: List[InsightCandidate] = []
        for c in candidates:
            if c.dedup_key in existing_keys:
                logger.debug("Dedup: skipping duplicate key=%s", c.dedup_key)
                continue

            # Auto-upgrade: if dismissed >= type threshold, suppress unless unsuppressable
            type_threshold = SUPPRESSION_THRESHOLDS.get(c.insight_type, 3)
            if dismiss_counts.get(c.dedup_key, 0) >= type_threshold:
                if not self._should_pierce_suppression(c):
                    logger.info(
                        "Dedup: auto-suppressing key=%s (dismissed %d times, threshold=%d)",
                        c.dedup_key, dismiss_counts[c.dedup_key], type_threshold,
                    )
                    continue

            kept.append(c)

        return kept

    # ==================== Preference application ====================

    def _apply_preferences(
        self, candidates: List[InsightCandidate], prefs: Dict[str, Any],
    ) -> List[InsightCandidate]:
        """Apply user preference rules.

        Unsuppressable whitelist:
        - urgency >= 80
        - insight_type == 'health'
        - source_context.health_event == True
        """
        suppressed_types: List[str] = prefs.get("suppressed_types", [])
        preference_rules: List[Dict[str, Any]] = prefs.get("preference_rules", [])

        if not suppressed_types and not preference_rules:
            return candidates

        kept: List[InsightCandidate] = []
        for c in candidates:
            if self._should_pierce_suppression(c):
                kept.append(c)
                continue

            if c.insight_type in suppressed_types:
                logger.debug("Preference: suppressing type=%s", c.insight_type)
                continue

            suppressed = False
            for rule in preference_rules:
                if self._rule_matches(rule, c):
                    if rule.get("action") == "suppress":
                        suppressed = True
                        break

            if not suppressed:
                kept.append(c)

        return kept

    def _should_pierce_suppression(self, candidate: InsightCandidate) -> bool:
        """OR logic: urgency >= 80 OR type == 'health' OR health_event."""
        if candidate.urgency >= 80:
            return True
        if candidate.insight_type == InsightType.HEALTH.value:
            return True
        if candidate.source_context.get("health_event") is True:
            return True
        return False

    @staticmethod
    def _rule_matches(rule: Dict[str, Any], candidate: InsightCandidate) -> bool:
        """Check if a UserPreferenceRule condition matches a candidate."""
        cond_type = rule.get("condition_suggestion_type")
        if cond_type and cond_type != candidate.insight_type:
            return False

        cond_person = rule.get("condition_person_id")
        if cond_person and str(cond_person) not in candidate.person_ids:
            return False

        cond_event_type = rule.get("condition_event_type")
        if cond_event_type:
            # Match against event entity types in the candidate
            event_types = {e.entity_type for e in candidate.entities if e.entity_type == "event"}
            sc_event_type = candidate.source_context.get("event_type")
            if cond_event_type != sc_event_type and cond_event_type not in event_types:
                return False

        # All conditions matched (or no conditions present)
        return True

    # ==================== Person budget filter ====================

    def _person_budget_filter(
        self, candidates: List[InsightCandidate],
    ) -> List[InsightCandidate]:
        """Max 2 insights per person."""
        person_counts: Dict[str, int] = defaultdict(int)
        kept: List[InsightCandidate] = []

        for c in candidates:
            if not c.person_ids:
                kept.append(c)
                continue

            primary_person = c.person_ids[0]
            if person_counts[primary_person] < 2:
                person_counts[primary_person] += 1
                kept.append(c)
            else:
                logger.debug(
                    "Person budget: dropping insight for person=%s (already %d)",
                    primary_person, person_counts[primary_person],
                )

        return kept

    # ==================== Self-Model Weight Adjustment ====================

    async def _apply_self_model_weights(
        self,
        candidates: List[InsightCandidate],
        family_id: UUID,
    ) -> List[InsightCandidate]:
        """Apply M4 self-model weight adjustments to candidate importance scores.

        Queries the secretary's own insight performance trends and adjusts
        importance scores: declining types get reduced weight, improving
        types get a boost. Zero LLM cost.
        """
        try:
            from .insight_self_model import get_type_weight_adjustments

            weights = await get_type_weight_adjustments(self.db, family_id)
        except Exception as exc:
            logger.warning(
                "Self-model weight adjustment failed, skipping: %s", exc,
            )
            return candidates

        if not weights:
            return candidates

        adjusted: List[InsightCandidate] = []
        for c in candidates:
            weight = weights.get(c.insight_type, 1.0)
            if weight != 1.0:
                new_importance = max(0, min(100, int(c.importance * weight)))
                adjusted.append(
                    dataclasses.replace(c, importance=new_importance)
                )
            else:
                adjusted.append(c)

        non_neutral = {k: v for k, v in weights.items() if v != 1.0}
        if non_neutral:
            logger.info(
                "Self-model weights applied: adjustments=%s candidates=%d",
                non_neutral, len(candidates),
            )

        return adjusted

    # ==================== Persistence ====================

    async def _persist(self, candidates: List[InsightCandidate]) -> List[UUID]:
        """INSERT ON CONFLICT DO NOTHING on (user_id, dedup_key) unique index.

        Creates Insight rows and associated InsightEntity rows.
        Returns list of actually inserted insight IDs.
        """
        if not candidates:
            return []

        inserted_ids: List[UUID] = []
        now = utc_now()

        # Ensure action_options are populated for all candidates
        candidates = [ensure_action_options(c) for c in candidates]

        for c in candidates:
            insight_id = uuid4()

            # Compute expires_at from TYPE_TTL_OVERRIDES, falling back to expiry_policy
            ttl_override = TYPE_TTL_OVERRIDES.get(c.insight_type)
            if ttl_override is not None:
                expires = now + ttl_override
            elif c.expires_at is not None:
                expires = c.expires_at
            else:
                expires = compute_expires_at(
                    c.insight_type,
                    action_data=c.source_context,
                )

            # Determine source without mutating the original dict
            source = c.source_context.get("_source", "scheduled")
            persisted_context = {k: v for k, v in c.source_context.items() if k != "_source"}

            stmt = pg_insert(Insight).values(
                id=insight_id,
                user_id=c.user_id,
                family_id=c.family_id,
                insight_type=c.insight_type,
                title=c.title,
                content=c.content,
                importance=c.importance,
                urgency=c.urgency,
                status=InsightStatus.PENDING.value,
                source=source,
                suggested_action=c.suggested_action,
                action_options=c.action_options,
                source_context=persisted_context or None,
                feedback_source="system",
                dedup_key=c.dedup_key or None,
                expires_at=expires,
                created_at=now,
            ).on_conflict_do_nothing(
                index_elements=["user_id", "dedup_key"],
                index_where=text("dedup_key IS NOT NULL AND status NOT IN ('dismissed', 'acted', 'expired')"),
            )

            result = await self.db.execute(stmt)
            if result.rowcount > 0:
                inserted_ids.append(insight_id)

                # Create InsightEntity rows from typed EntitySpec list
                # Roles must be: primary, related, mentioned, source (CHECK constraint)
                all_entities: List[Dict[str, Any]] = []
                seen_keys: Set[tuple] = set()
                for spec in c.entities:
                    if not spec.entity_id:
                        continue
                    try:
                        eid = UUID(spec.entity_id) if not isinstance(spec.entity_id, UUID) else spec.entity_id
                    except (ValueError, AttributeError):
                        continue
                    # Validate role against CHECK constraint
                    role = spec.role if spec.role in ("primary", "related", "mentioned", "source") else "related"
                    key = (spec.entity_type, eid)
                    if key not in seen_keys:
                        seen_keys.add(key)
                        all_entities.append({
                            "insight_id": insight_id,
                            "entity_type": spec.entity_type,
                            "entity_id": eid,
                            "role": role,
                        })

                if all_entities:
                    await self.db.execute(
                        pg_insert(InsightEntity).values(all_entities)
                        .on_conflict_do_nothing()
                    )

        if inserted_ids:
            await self.db.flush()

        return inserted_ids

    # ==================== Contextual reactivation ====================

    async def _contextual_reactivation(
        self, user_id: UUID, signals: AllSignals,
    ) -> List[InsightCandidate]:
        """Check dismissed obligations for reactivation. Pure rule-based, no LLM.

        Jaccard coefficient > 0.6 for context relevance.
        Batch preload source entities and temperatures.
        """
        # Find recently dismissed insights eligible for reactivation
        reactivatable_types = [
            InsightType.FAVOR.value,
            InsightType.RELATIONSHIP.value,
            InsightType.MEMORY.value,
        ]
        now = utc_now()
        dismissed_stmt = (
            select(Insight)
            .outerjoin(InsightEntity, InsightEntity.insight_id == Insight.id)
            .where(
                and_(
                    Insight.user_id == user_id,
                    Insight.status == InsightStatus.DISMISSED.value,
                    Insight.insight_type.in_(reactivatable_types),
                    Insight.dedup_key.isnot(None),
                    or_(
                        Insight.regen_suppressed_until.is_(None),
                        Insight.regen_suppressed_until <= now,
                    ),
                    Insight.created_at >= now - timedelta(days=30),
                )
            )
            .order_by(Insight.created_at.desc())
            .limit(20)
        )
        result = await self.db.execute(dismissed_stmt)
        dismissed = list(result.unique().scalars().all())

        if not dismissed:
            return []

        # Build current signal entity set for Jaccard comparison
        current_entity_ids = signals.get_all_entity_ids()
        current_id_strs = {str(eid) for eid in current_entity_ids}

        # Batch preload entity IDs from InsightEntity via the eagerly loaded relationship
        reactivated: List[InsightCandidate] = []
        for insight in dismissed:
            src_ctx = insight.source_context if isinstance(insight.source_context, dict) else {}

            # Collect entity IDs from InsightEntity rows
            dismissed_ids: Set[str] = set()
            for entity in (insight.entities or []):
                dismissed_ids.add(str(entity.entity_id))

            if not dismissed_ids:
                continue

            # Jaccard coefficient
            intersection = dismissed_ids & current_id_strs
            union = dismissed_ids | current_id_strs
            jaccard = len(intersection) / len(union) if union else 0.0

            if jaccard > 0.6:
                reactivation_context = {
                    **src_ctx,
                    "reactivated_from": str(insight.id),
                    "reactivation_depth": src_ctx.get("reactivation_depth", 0) + 1,
                    "reactivation_jaccard": round(jaccard, 2),
                }
                candidate = InsightCandidate(
                    insight_type=insight.insight_type,
                    title=insight.title,
                    content=insight.content,
                    importance=insight.importance or 50,
                    urgency=min((insight.urgency or 50) + 10, 100),
                    entities=[],
                    source_context=reactivation_context,
                )
                # Synthesize entities from source_context signals
                # instead of copying potentially empty entity lists
                repaired = synthesize_entities([candidate], signals)
                reactivated.append(repaired[0])

        logger.info(
            "Contextual reactivation: checked %d dismissed, reactivated %d",
            len(dismissed), len(reactivated),
        )
        return reactivated

    # ==================== Signal collection ====================

    async def _collect_all_signals(
        self,
        user_id: UUID,
        family_id: UUID,
        target_date: date,
    ) -> AllSignals:
        """Delegate to InsightSignalCollector for parallel signal collection."""
        collector = InsightSignalCollector(self.db)
        return await collector.collect_all(user_id, family_id, target_date)

    # ==================== Helpers ====================

    def _generate_positive_affirmations(
        self,
        signals: AllSignals,
        target_date: date,
    ) -> List[InsightCandidate]:
        """Extract positive-signal data from collected signals and generate affirmations.

        Derives three data slices from raw signals:
        - recent_contacts: relationship signals with mention_count proxy
        - completed_commitments: protected commitment signals with status 'completed'
        - family_events: event signals with family-typed event_type
        """
        # Slice 1: relationship signals — use days_since_contact as a proxy for
        # recent frequency.  A very low days_since (<=7) combined with an
        # existing mention means recent interaction; we report mention_count=3
        # as a conservative floor so the threshold in _positive_affirmations
        # is satisfied whenever someone was mentioned very recently.
        recent_contacts: List[Dict[str, Any]] = []
        for rel in signals.relationships:
            days_since = rel.get("days_since_contact")
            if days_since is not None and days_since <= 7:
                recent_contacts.append({
                    "person_id": rel.get("person_id", ""),
                    "person_name": rel.get("person_name", ""),
                    # Treat "contacted within 7 days" as 3+ interactions
                    "recent_mention_count": 3,
                })

        # Slice 2: completed commitments from protected signals
        completed_commitments: List[Dict[str, Any]] = []
        for sig in signals.protected:
            if sig.get("signal_type") != "commitment":
                continue
            if sig.get("status") == "completed":
                completed_commitments.append({
                    "commitment_id": sig.get("commitment_id", ""),
                    "what": sig.get("what", ""),
                })

        # Slice 3: all event signals (family filter applied inside _positive_affirmations)
        family_events = list(signals.events)

        rule_engine = RuleEngineInsights()
        return rule_engine._positive_affirmations(
            recent_contacts=recent_contacts,
            completed_commitments=completed_commitments,
            family_events=family_events,
            today=target_date,
        )

    # ==================== G1: L0 Auto-Handling Materialization ====================

    # Mapping from insight_type to PendingAction action_type for L0_AUTO candidates.
    _L0_ACTION_TYPE_MAP: Dict[str, str] = {
        InsightType.POSITIVE_AFFIRMATION.value: "suggest_greeting",
        InsightType.SOCIAL_OBLIGATION.value: "suggest_greeting",
        InsightType.TIME.value: "create_event",
        InsightType.LIFE_ADMIN.value: "create_event",
    }

    _L0_DEFAULT_ACTION_TYPE = "suggest_defer"

    async def _materialize_l0_auto(
        self,
        candidates: List[InsightCandidate],
        user_id: UUID,
        family_id: UUID,
    ) -> None:
        """Convert L0_AUTO insight candidates into PendingActions.

        These candidates are handled autonomously by the secretary — they
        should not appear in the user's insight feed. Instead, a PendingAction
        is created so the action can be executed via the normal confirmation
        flow (or auto-confirmed for truly autonomous items).

        Creates PendingAction rows directly (not via PendingActionService) to
        stay within the pipeline's transaction boundary (flush, not commit).

        Isolated: any individual failure is logged and swallowed.
        """
        if not candidates:
            return

        # Lazy import to avoid circular dependency (conversation ↔ insight)
        from ..conversation.pending_action import PendingAction, ActionStatus

        now = utc_now()
        ttl = timedelta(hours=24)
        created_count = 0

        for candidate in candidates:
            try:
                action_type = self._L0_ACTION_TYPE_MAP.get(
                    candidate.insight_type,
                    self._L0_DEFAULT_ACTION_TYPE,
                )

                payload = {
                    "insight_type": candidate.insight_type,
                    "title": candidate.title,
                    "content": candidate.content,
                    "importance": candidate.importance,
                    "urgency": candidate.urgency,
                    "source_context": candidate.source_context,
                    "entities": [
                        {
                            "entity_type": e.entity_type,
                            "entity_id": e.entity_id,
                            "role": e.role,
                        }
                        for e in candidate.entities
                    ],
                }

                display_data = {
                    "title": candidate.title,
                    "description": candidate.content,
                    "context_hint": candidate.context_hint,
                    "best_action_window": candidate.best_action_window,
                }

                action = PendingAction(
                    user_id=user_id,
                    family_id=family_id,
                    action_type=action_type,
                    payload=payload,
                    display_data=display_data,
                    status=ActionStatus.PENDING.value,
                    expires_at=now + ttl,
                )
                self.db.add(action)
                created_count += 1
            except Exception as exc:
                logger.warning(
                    "Failed to materialize L0_AUTO candidate '%s' for user %s: %s",
                    candidate.title, user_id, exc,
                )

        if created_count:
            await self.db.flush()
            logger.info(
                "Materialized %d/%d L0_AUTO candidates as PendingActions for user %s",
                created_count, len(candidates), user_id,
            )

    # ==================== G5: Positive Insight Ratio Control ====================

    # Target ratio bounds for POSITIVE_AFFIRMATION insights
    _POSITIVE_RATIO_MIN = 0.20
    _POSITIVE_RATIO_MAX = 0.30
    _POSITIVE_IMPORTANCE_BOOST = 15

    @staticmethod
    def _enforce_positive_ratio(
        candidates: List[InsightCandidate],
    ) -> List[InsightCandidate]:
        """Ensure POSITIVE_AFFIRMATION insights comprise 20-30% of total.

        - If ratio < 20%: boost positive candidates' importance by +15
          (makes them more visible but doesn't fabricate new ones).
        - If ratio > 30%: drop lowest-importance positive candidates
          until ratio is within range.

        Returns a new list (immutable).
        """
        if not candidates:
            return candidates

        positive_type = InsightType.POSITIVE_AFFIRMATION.value
        total = len(candidates)

        positive_indices = [
            i for i, c in enumerate(candidates)
            if c.insight_type == positive_type
        ]
        positive_count = len(positive_indices)

        # Nothing to do if there are zero positive insights
        # (generating new ones is the rule engine's job, not ours)
        if positive_count == 0:
            return candidates

        ratio = positive_count / total

        # Under-represented: boost importance to increase visibility
        if ratio < InsightPipeline._POSITIVE_RATIO_MIN:
            boosted_indices = set(positive_indices)
            return [
                dataclasses.replace(
                    c,
                    importance=min(c.importance + InsightPipeline._POSITIVE_IMPORTANCE_BOOST, 100),
                )
                if i in boosted_indices
                else c
                for i, c in enumerate(candidates)
            ]

        # Over-represented: trim lowest-importance positives
        if ratio > InsightPipeline._POSITIVE_RATIO_MAX:
            non_positive_count = total - positive_count
            # Target: positive_target / (non_positive + positive_target) <= 0.30
            # => positive_target <= 0.30 * non_positive / 0.70
            if non_positive_count == 0:
                return candidates
            target_positive = max(
                1,
                int(non_positive_count * InsightPipeline._POSITIVE_RATIO_MAX
                    / (1.0 - InsightPipeline._POSITIVE_RATIO_MAX)),
            )
            excess = positive_count - target_positive
            if excess <= 0:
                return candidates

            # Sort positive candidates by importance ascending — drop the weakest
            sorted_positive = sorted(
                positive_indices, key=lambda i: candidates[i].importance,
            )
            drop_indices = set(sorted_positive[:excess])

            kept = [c for i, c in enumerate(candidates) if i not in drop_indices]

            logger.info(
                "Positive ratio control: dropped %d low-importance positives "
                "(was %d/%d = %.0f%%, target <= %.0f%%)",
                excess, positive_count, total,
                ratio * 100,
                InsightPipeline._POSITIVE_RATIO_MAX * 100,
            )
            return kept

        return candidates

    async def _load_preferences(
        self, user_id: UUID, family_id: UUID,
    ) -> Dict[str, Any]:
        """Load user and family preference settings."""
        from ..curation.models import FamilyPreference, UserPreferenceRule

        prefs: Dict[str, Any] = {
            "suppressed_types": [],
            "preference_rules": [],
        }

        # FamilyPreference suppressed types
        fp_stmt = select(FamilyPreference).where(FamilyPreference.family_id == family_id)
        fp_result = await self.db.execute(fp_stmt)
        fp = fp_result.scalar_one_or_none()
        if fp and fp.suppressed_types:
            suppressed = fp.suppressed_types
            if isinstance(suppressed, list):
                prefs["suppressed_types"] = suppressed

        # UserPreferenceRules
        rule_stmt = (
            select(UserPreferenceRule)
            .where(
                and_(
                    UserPreferenceRule.user_id == user_id,
                    UserPreferenceRule.family_id == family_id,
                    UserPreferenceRule.is_active.is_(True),
                )
            )
        )
        rule_result = await self.db.execute(rule_stmt)
        for rule in rule_result.scalars().all():
            prefs["preference_rules"].append({
                "action": rule.action,
                "condition_suggestion_type": rule.condition_suggestion_type,
                "condition_person_id": str(rule.condition_person_id) if rule.condition_person_id else None,
                "condition_event_type": rule.condition_event_type,
            })

        return prefs

    def _build_budget(self, prefs: Dict[str, Any]) -> int:
        """Determine token budget based on preferences. Default = SIGNAL_TOKEN_BUDGET."""
        # Future: adjust budget based on user tier or preference
        return self.SIGNAL_TOKEN_BUDGET

    async def _refresh_stale_insights(self, user_id: UUID) -> None:
        """Mark expired insights before generating new ones."""
        now = utc_now()
        stmt = (
            Insight.__table__.update()
            .where(
                and_(
                    Insight.user_id == user_id,
                    Insight.status.in_([
                        InsightStatus.PENDING.value,
                        InsightStatus.ACTIVE.value,
                    ]),
                    Insight.expires_at.isnot(None),
                    Insight.expires_at <= now,
                )
            )
            .values(status=InsightStatus.EXPIRED.value)
        )
        result = await self.db.execute(stmt)
        if result.rowcount > 0:
            await self.db.flush()
            logger.info("Expired %d stale insights for user %s", result.rowcount, user_id)

    def _build_event_context(self, event: "CuratedEvent") -> Dict[str, Any]:
        """Build context dict from a CuratedEvent for reactive generation."""
        return {
            "event_id": str(event.id),
            "trip_id": str(event.trip_id) if event.trip_id else None,
            "title": event.title,
            "event_type": event.event_type,
            "start": event.normalized_start.isoformat() if event.normalized_start else None,
            "end": event.normalized_end.isoformat() if event.normalized_end else None,
            "location": event.location,
            "priority": event.priority,
            "life_context_hint": event.life_context_hint,
            "secretary_note": event.secretary_note,
        }

    # Tracked entity types that should trigger a new TrackedThread
    _TRACKED_ENTITY_TYPES = frozenset({"commitment", "favor", "important_date"})

    async def _integrate_tracked_threads(
        self,
        candidates: List["InsightCandidate"],
        user_id: UUID,
        family_id: UUID,
        target_date: "date",
    ) -> None:
        """Integrate TrackedThreadService into the pipeline after persistence.

        Step 1 — Auto-create tracked threads for newly generated candidates
        whose entities reference a commitment, favor, or important_date.

        Step 2 — Check all active threads for due checkpoints and persist
        the resulting InsightCandidate list so they appear in the user's feed.

        Both steps are isolated: any individual failure is logged and swallowed
        so that tracked-thread errors can never abort the main pipeline.
        """
        from .tracked_thread import TrackedThreadService

        tracked_svc = TrackedThreadService(self.db)

        # ── Step 1: auto-create threads from new candidates ──────────────
        for candidate in candidates:
            for entity in candidate.entities:
                if entity.entity_type not in self._TRACKED_ENTITY_TYPES:
                    continue
                try:
                    event_data = {
                        **candidate.source_context,
                        f"{entity.entity_type}_id": entity.entity_id,
                    }
                    await tracked_svc.auto_create_from_event(
                        event_type=entity.entity_type,
                        event_data=event_data,
                        user_id=user_id,
                        family_id=family_id,
                    )
                except Exception as exc:
                    logger.warning(
                        "TrackedThread auto_create_from_event failed for "
                        "entity_type=%s entity_id=%s user=%s: %s",
                        entity.entity_type, entity.entity_id, user_id, exc,
                    )

        # ── Step 2: persist due checkpoint insights ───────────────────────
        try:
            target_dt = datetime(
                target_date.year, target_date.month, target_date.day,
                tzinfo=utc_now().tzinfo,
            )
            checkpoint_candidates = await tracked_svc.check_all_active(
                user_id=user_id,
                family_id=family_id,
                target_date=target_dt,
            )
            if checkpoint_candidates:
                for cp in checkpoint_candidates:
                    cp.user_id = user_id
                    cp.family_id = family_id
                    cp.dedup_key = self._compute_dedup_key(cp)

                checkpoint_candidates = await self._dedup(checkpoint_candidates, user_id)
                if checkpoint_candidates:
                    checkpoint_ids = await self._persist(checkpoint_candidates)
                    logger.info(
                        "TrackedThread checkpoints persisted: user=%s count=%d",
                        user_id, len(checkpoint_ids),
                    )
        except Exception as exc:
            logger.warning(
                "TrackedThread check_all_active failed for user=%s: %s",
                user_id, exc,
            )

    async def _trigger_sidekick_evaluation(
        self, user_id: UUID, insight_ids: List[UUID],
    ) -> None:
        """Trigger sidekick evaluation for newly generated insights.

        Loads high-importance insights and passes them to SidekickWorker
        for contextual injection into active sessions.
        """
        if not insight_ids:
            return

        try:
            from ...ai_engine.workers.sidekick_worker import SidekickWorker

            # Load newly persisted insights with high importance for sidekick
            rows = await self.db.execute(
                select(Insight).where(
                    Insight.id.in_(insight_ids),
                    Insight.importance >= 70,
                    Insight.delivered_via_sidekick.is_(False),
                )
            )
            high_value = rows.scalars().all()
            if not high_value:
                return

            worker = SidekickWorker()
            delivered_ids: List[UUID] = []
            for ins in high_value:
                payload = {
                    "insight_type": ins.insight_type,
                    "insight_text": f"{ins.title}: {ins.content}",
                    "urgency": _urgency_label(ins.urgency),
                    "source_system": ins.source,
                    "context_entities": [
                        str(e.entity_id) for e in (ins.entities or [])
                    ],
                    "expires_at": ins.expires_at.isoformat() if ins.expires_at else None,
                }
                injected = await worker.evaluate_and_inject(str(user_id), payload)
                if injected:
                    delivered_ids.append(ins.id)

            # Batch update instead of per-row mutation
            if delivered_ids:
                from sqlalchemy import update
                await self.db.execute(
                    update(Insight)
                    .where(Insight.id.in_(delivered_ids))
                    .values(delivered_via_sidekick=True)
                )
                await self.db.flush()
        except Exception:
            logger.warning(
                "Sidekick evaluation failed for user=%s, skipping (non-fatal)",
                user_id, exc_info=True,
            )
