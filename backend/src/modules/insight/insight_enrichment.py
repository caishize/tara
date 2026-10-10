"""InsightEnrichment — Post-LLM entity injection and action_options defaults.

Pure functions (no DB access) that enrich InsightCandidate lists with
missing entity references and default action options. Extracted from
InsightPipeline for cohesion and to reduce pipeline file size.
"""

from __future__ import annotations

import json
from dataclasses import replace
from typing import Any, Dict, List

from ...config.logging import get_logger
from .insight_signal_collector import AllSignals
from .models import EntitySpec, InsightCandidate, InsightType

logger = get_logger(__name__)


def synthesize_entities(
    candidates: List[InsightCandidate],
    signals: AllSignals,
) -> List[InsightCandidate]:
    """Deterministic entity synthesis from signal fields.

    For each candidate, looks up source_context["signal_ids"] against all signal
    categories in AllSignals to find matching entity ID fields. Creates EntitySpec
    entries from matched signal data. This replaces the unreliable LLM entity
    extraction with structured, deterministic linking.

    Returns new list with enriched candidates (immutable pattern).
    """
    # Build lookup: signal entity ID field value -> list of EntitySpec to create
    signal_id_to_entities: Dict[str, List[EntitySpec]] = {}

    for sig in signals.events:
        eid = sig.get("event_id")
        if eid:
            specs = [EntitySpec(entity_type="event", entity_id=eid, role="related")]
            tid = sig.get("trip_id")
            if tid:
                specs.append(EntitySpec(entity_type="trip", entity_id=tid, role="related"))
            signal_id_to_entities[eid] = specs

    for sig in signals.protected:
        fid = sig.get("favor_record_id")
        if fid:
            specs: List[EntitySpec] = []
            cid = sig.get("contact_id")
            if cid:
                specs.append(EntitySpec(entity_type="person", entity_id=cid, role="related"))
            if specs:
                signal_id_to_entities[fid] = specs

        cmt_id = sig.get("commitment_id")
        if cmt_id:
            signal_id_to_entities[cmt_id] = [
                EntitySpec(entity_type="commitment", entity_id=cmt_id, role="related"),
            ]

    for sig in signals.relationships:
        pid = sig.get("person_id")
        if pid:
            signal_id_to_entities[pid] = [
                EntitySpec(entity_type="person", entity_id=pid, role="related"),
            ]

    enriched: List[InsightCandidate] = []
    for candidate in candidates:
        # Skip candidates that already have entities (e.g. from run_reactive or L1 rules)
        if candidate.entities:
            enriched.append(candidate)
            continue

        signal_ids = candidate.source_context.get("signal_ids", [])
        if not signal_ids:
            logger.warning(
                "synthesize_entities: candidate '%s' has empty source_signal_ids",
                candidate.title,
                extra={"metric": "synthesis_no_signal_ids_count"},
            )
            enriched.append(candidate)
            continue

        new_entities: List[EntitySpec] = []
        seen: set = set()

        for sid in signal_ids:
            for spec in signal_id_to_entities.get(sid, []):
                key = (spec.entity_type, spec.entity_id)
                if key not in seen:
                    seen.add(key)
                    new_entities.append(spec)

        if new_entities:
            enriched.append(replace(candidate, entities=new_entities))
        else:
            enriched.append(candidate)

    return enriched


def inject_trip_entities(
    candidates: List[InsightCandidate],
    signals: AllSignals,
) -> List[InsightCandidate]:
    """Ensure candidates referencing events with trip_id also have trip entities.

    Cross-references candidate source_signal_ids and event entities against
    the collected event signals to find matching trip_ids. Returns new list
    with enriched candidates (immutable pattern).
    """
    event_to_trip: Dict[str, str] = {}
    for sig in signals.events:
        eid = sig.get("event_id")
        tid = sig.get("trip_id")
        if eid and tid:
            event_to_trip[eid] = tid

    enriched: List[InsightCandidate] = []
    for candidate in candidates:
        trip_ids_to_add: List[str] = []
        existing_trip_ids = {
            e.entity_id for e in candidate.entities if e.entity_type == "trip"
        }

        for entity in candidate.entities:
            if entity.entity_type == "event" and entity.entity_id in event_to_trip:
                tid = event_to_trip[entity.entity_id]
                if tid not in existing_trip_ids:
                    trip_ids_to_add.append(tid)
                    existing_trip_ids.add(tid)

        signal_ids = candidate.source_context.get("signal_ids", [])
        for sid in signal_ids:
            if sid in event_to_trip:
                tid = event_to_trip[sid]
                if tid not in existing_trip_ids:
                    trip_ids_to_add.append(tid)
                    existing_trip_ids.add(tid)

        if trip_ids_to_add:
            new_entities = list(candidate.entities) + [
                EntitySpec(entity_type="trip", entity_id=tid, role="related")
                for tid in trip_ids_to_add
            ]
            enriched.append(replace(candidate, entities=new_entities))
        else:
            enriched.append(candidate)

    return enriched


def inject_person_entities(
    candidates: List[InsightCandidate],
    signals: AllSignals,
) -> List[InsightCandidate]:
    """Ensure candidates referencing relationship signals have person entities.

    Cross-references candidate source_signal_ids against relationship signals
    to find matching person_ids. Returns new list with enriched candidates.
    """
    signal_person_ids: Dict[str, str] = {}
    for sig in signals.relationships:
        pid = sig.get("person_id")
        if pid:
            signal_person_ids[pid] = pid

    for sig in signals.protected:
        cid = sig.get("contact_id")
        if cid:
            signal_person_ids[cid] = cid

    if not signal_person_ids:
        return candidates

    enriched: List[InsightCandidate] = []
    for candidate in candidates:
        existing_person_ids = {
            e.entity_id for e in candidate.entities if e.entity_type == "person"
        }

        person_ids_to_add: List[str] = []

        signal_ids = candidate.source_context.get("signal_ids", [])
        for sid in signal_ids:
            if sid in signal_person_ids and sid not in existing_person_ids:
                person_ids_to_add.append(sid)
                existing_person_ids.add(sid)

        # For relationship-type insights, check if any relationship signal person
        # is referenced but missing from entities
        if candidate.insight_type == InsightType.RELATIONSHIP.value:
            for sig in signals.relationships:
                pid = sig.get("person_id")
                pname = sig.get("person_name", "")
                if pid and pid not in existing_person_ids:
                    # Require name length >= 2 to avoid false positives
                    if pname and len(pname) >= 2 and pname in candidate.content:
                        person_ids_to_add.append(pid)
                        existing_person_ids.add(pid)

        if person_ids_to_add:
            new_entities = list(candidate.entities) + [
                EntitySpec(entity_type="person", entity_id=pid, role="related")
                for pid in person_ids_to_add
            ]
            enriched.append(replace(candidate, entities=new_entities))
        else:
            enriched.append(candidate)

    return enriched


def _generate_contextual_actions(
    candidate: InsightCandidate,
) -> List[Dict[str, Any]]:
    """Generate type-specific contextual action_options (pure rules, no LLM).

    Dispatches on insight_type to return a curated action list.
    Falls back to entity-based rules for unrecognised types.
    """
    insight_type = candidate.insight_type or ""
    person_entities = [e for e in candidate.entities if e.entity_type == "person"]
    trip_entities = [e for e in candidate.entities if e.entity_type == "trip"]

    # --- SOCIAL_OBLIGATION / FAVOR ----------------------------------------
    if insight_type in (InsightType.SOCIAL_OBLIGATION.value, InsightType.FAVOR.value):
        if person_entities:
            return [
                {
                    "label": "查看记录",
                    "action_type": "open_detail",
                    "action_payload": {"person_id": person_entities[0].entity_id},
                },
                {"label": "生成祝福语", "action_type": "generate_greeting"},
                {"label": "设置提醒", "action_type": "set_reminder"},
                {"label": "稍后再提醒", "action_type": "snooze"},
            ]
        return [
            {"label": "查看记录", "action_type": "open_detail"},
            {"label": "生成祝福语", "action_type": "generate_greeting"},
            {"label": "设置提醒", "action_type": "set_reminder"},
            {"label": "稍后再提醒", "action_type": "snooze"},
        ]

    # --- RELATIONSHIP -------------------------------------------------------
    if insight_type == InsightType.RELATIONSHIP.value:
        if person_entities:
            pid = person_entities[0].entity_id
            return [
                {
                    "label": "现在联系",
                    "action_type": "open_chat",
                    "action_payload": {"person_id": pid},
                },
                {
                    "label": "发关心消息",
                    "action_type": "send_care_message",
                    "action_payload": {"person_id": pid},
                },
                {
                    "label": "计划探望",
                    "action_type": "create_pending_action",
                    "action_payload": {"person_id": pid, "action_subtype": "plan_visit"},
                },
            ]
        return [
            {"label": "现在联系", "action_type": "open_chat"},
            {"label": "发关心消息", "action_type": "send_care_message"},
            {"label": "计划探望", "action_type": "create_pending_action"},
        ]

    # --- TREND_ALERT --------------------------------------------------------
    if insight_type == InsightType.TREND_ALERT.value:
        if trip_entities:
            return [
                {"label": "查看详情", "action_type": "open_detail"},
                {
                    "label": "制定应对计划",
                    "action_type": "create_pending_action",
                    "action_payload": {"related_trip_id": trip_entities[0].entity_id},
                },
                {"label": "标记已知晓", "action_type": "acknowledge"},
            ]
        return [
            {"label": "查看详情", "action_type": "open_detail"},
            {"label": "制定应对计划", "action_type": "create_pending_action"},
            {"label": "标记已知晓", "action_type": "acknowledge"},
        ]

    # --- POSITIVE_AFFIRMATION -----------------------------------------------
    if insight_type == InsightType.POSITIVE_AFFIRMATION.value:
        return [
            {"label": "分享", "action_type": "share"},
            {"label": "记录这一刻", "action_type": "create_memory"},
            {"label": "继续保持", "action_type": "acknowledge"},
        ]

    # --- Fallback: entity-based rules (original logic) ----------------------
    if trip_entities:
        return [
            {
                "label": "采纳到行程",
                "action_type": "create_pending_action",
                "action_payload": {"related_trip_id": trip_entities[0].entity_id},
            },
            {"label": "了解", "action_type": "open_detail"},
        ]
    if person_entities:
        return [
            {
                "label": "发消息",
                "action_type": "open_chat",
                "action_payload": {"person_id": person_entities[0].entity_id},
            },
            {"label": "了解", "action_type": "open_detail"},
        ]
    return [{"label": "了解", "action_type": "open_detail"}]


def ensure_action_options(candidate: InsightCandidate) -> InsightCandidate:
    """Guarantee non-empty action_options on a candidate (immutable).

    Rules:
    - If candidate already has non-empty action_options, return as-is
    - Dispatch to _generate_contextual_actions() for type-specific options
    """
    if candidate.action_options:
        return candidate

    action_options = _generate_contextual_actions(candidate)
    return replace(candidate, action_options=action_options)


# ---------------------------------------------------------------------------
# LLM-powered dynamic action generation
# ---------------------------------------------------------------------------

# Types that benefit from LLM-generated contextual actions
_LLM_ACTION_TYPES = frozenset({
    InsightType.SOCIAL_OBLIGATION.value,
    InsightType.FAVOR.value,
    InsightType.RELATIONSHIP.value,
    InsightType.TREND_ALERT.value,
    InsightType.PREP_CHAIN.value,
    InsightType.WEATHER_CARE.value,
})

# Valid action_type values that LLM can generate
_VALID_ACTION_TYPES = frozenset({
    "open_detail", "open_chat", "create_pending_action",
    "set_reminder", "generate_greeting", "send_care_message",
    "acknowledge", "snooze", "share", "create_memory",
})


async def generate_dynamic_action_options(
    candidates: List[InsightCandidate],
) -> List[InsightCandidate]:
    """Enrich candidates with LLM-generated contextual action_options.

    For insight types in _LLM_ACTION_TYPES, calls Haiku to generate
    context-aware actions based on the insight's title, content, and
    context_hint. Falls back to rule-based generation on failure.

    Candidates that already have action_options are skipped.
    Candidates with types NOT in _LLM_ACTION_TYPES use rule-based fallback.
    """
    needs_llm: List[tuple[int, InsightCandidate]] = []
    result = list(candidates)

    for i, c in enumerate(candidates):
        if c.action_options:
            continue
        if c.insight_type not in _LLM_ACTION_TYPES:
            result[i] = ensure_action_options(c)
            continue
        needs_llm.append((i, c))

    if not needs_llm:
        return result

    # Batch all LLM-eligible candidates into a single call
    prompt_items = []
    for _, c in needs_llm:
        prompt_items.append(
            f"- 类型: {c.insight_type}\n"
            f"  标题: {c.title}\n"
            f"  内容: {c.content}\n"
            f"  背景: {c.context_hint or '无'}"
        )

    system_prompt = (
        "你是智能家庭秘书的action按钮生成器。根据每条洞察的内容，"
        "为其生成2-4个情境化操作按钮。\n\n"
        "每个按钮格式: {\"label\": \"按钮文字(≤6字)\", \"action_type\": \"类型\"}\n"
        f"可用action_type: {sorted(_VALID_ACTION_TYPES)}\n\n"
        "要求:\n"
        "- label要具体、情境化，不要泛泛的'了解'\n"
        "- 第一个按钮是最可能的行动\n"
        "- 最后一个按钮是'稍后再说'类的延迟选项\n"
        "- 严格返回JSON数组的数组，外层对应每条洞察"
    )
    user_prompt = "为以下洞察生成操作按钮:\n\n" + "\n\n".join(prompt_items)

    try:
        from .insight_llm_client import call_llm_raw

        raw = await call_llm_raw(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            model="haiku",
            max_tokens=max(300, len(needs_llm) * 80),
        )

        # Parse JSON array of arrays
        parsed = json.loads(raw.strip())
        if not isinstance(parsed, list) or len(parsed) != len(needs_llm):
            raise ValueError(
                f"Expected {len(needs_llm)} action lists, "
                f"got {len(parsed) if isinstance(parsed, list) else 'non-list'}"
            )

        for (idx, candidate), actions in zip(needs_llm, parsed):
            if not isinstance(actions, list) or not actions:
                result[idx] = ensure_action_options(candidate)
                continue
            # Validate and sanitize each action
            valid_actions: List[Dict[str, Any]] = []
            for act in actions:
                if (
                    isinstance(act, dict)
                    and "label" in act
                    and act.get("action_type") in _VALID_ACTION_TYPES
                ):
                    valid_actions.append({
                        "label": str(act["label"])[:20],
                        "action_type": act["action_type"],
                    })
            if valid_actions:
                result[idx] = replace(candidate, action_options=valid_actions)
            else:
                result[idx] = ensure_action_options(candidate)

    except Exception as e:
        logger.warning(
            "LLM action_options generation failed, falling back to rules: %s", e,
        )
        for idx, candidate in needs_llm:
            result[idx] = ensure_action_options(candidate)

    return result
