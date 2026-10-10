"""InsightLLMClient — LLM call + response parsing for insight generation.

Extracted from InsightPipeline to keep each module focused.
Handles the Haiku API call, retry logic, JSON parsing, and
InsightCandidate construction from raw LLM output.
"""

from __future__ import annotations

import json
from typing import List, Optional

from ...config.logging import get_logger
from ...config.settings import settings
from .models import EntitySpec, InsightCandidate, InsightType

logger = get_logger(__name__)


# Valid insight types for validation
_VALID_INSIGHT_TYPES = frozenset(t.value for t in InsightType)


async def call_llm_raw(
    system_prompt: str,
    user_prompt: str,
    model: str = "haiku",
    max_tokens: int = 300,
) -> str:
    """Call LLM and return raw text response (no JSON parsing).

    Used by enrichment steps that need lightweight LLM responses
    and handle their own parsing. Raises on failure (no retry).
    """
    from ...core.llm.haiku_client import get_haiku_client

    client = get_haiku_client()
    model_name = settings.fast_worker_model if model == "haiku" else model

    import asyncio

    response = await asyncio.wait_for(
        client.messages.create(
            model=model_name,
            max_tokens=max_tokens,
            temperature=0.3,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        ),
        timeout=15.0,
    )

    raw = _extract_text(response)
    if raw is None:
        raise ValueError("Empty text blocks from LLM")
    return raw


async def call_llm_and_parse(
    system_prompt: str,
    user_prompt: str,
    max_attempts: int = 2,
) -> List[InsightCandidate]:
    """Call Haiku and parse JSON array response. Retry once on failure."""
    from ...core.llm.haiku_client import get_haiku_client

    client = get_haiku_client()
    last_error: Optional[Exception] = None

    for attempt in range(max_attempts):
        try:
            response = await client.messages.create(
                model=settings.fast_worker_model,
                max_tokens=8000,
                temperature=0.3,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )

            # Detect output truncation before parsing
            stop = getattr(response, "stop_reason", None)
            if stop == "max_tokens":
                logger.warning(
                    "LLM output truncated (attempt %d/%d, max_tokens hit)",
                    attempt + 1, max_attempts,
                )
                last_error = ValueError("LLM output truncated at max_tokens")
                continue

            raw_text = _extract_text(response)
            if raw_text is None:
                last_error = ValueError("empty text blocks from LLM")
                continue

            parsed = json.loads(raw_text)
            if not isinstance(parsed, list):
                parsed = [parsed]

            return [
                candidate
                for item in parsed
                if (candidate := _parse_candidate_item(item)) is not None
            ]

        except json.JSONDecodeError as exc:
            logger.warning(
                "LLM returned non-JSON (attempt %d/%d): %s",
                attempt + 1, max_attempts, exc,
            )
            last_error = exc
        except Exception as exc:
            logger.warning(
                "LLM insight generation failed (attempt %d/%d): %s",
                attempt + 1, max_attempts, exc,
            )
            last_error = exc

    logger.error("All %d LLM attempts failed: %s", max_attempts, last_error)
    return []


def _extract_text(response) -> Optional[str]:
    """Extract text from LLM response, stripping markdown fences."""
    text_parts = [
        block.text for block in response.content
        if hasattr(block, "text")
    ]
    if not text_parts:
        return None

    raw = text_parts[0].strip()
    if raw.startswith("```"):
        raw = raw.split("\n", 1)[-1].rsplit("```", 1)[0].strip()
    return raw


def _parse_candidate_item(item: dict) -> Optional[InsightCandidate]:
    """Parse a single LLM output item into an InsightCandidate.

    Returns None if the item is malformed.
    """
    try:
        # Entity synthesis is handled by synthesize_entities() in enrichment step.
        # LLM entity output is unreliable (UUID hallucination) — skip parsing.
        entity_specs: List[EntitySpec] = []

        # Build source_context from signal IDs
        sc = dict(item.get("source_context", {}))
        signal_ids = item.get("source_signal_ids", [])
        if signal_ids:
            sc["signal_ids"] = signal_ids

        importance = _parse_importance(item)
        insight_type = _validate_insight_type(item.get("insight_type"))

        # Parse disposition (LLM-aware dedup): NEW / KEEP / UPDATE / DELETE
        raw_disposition = item.get("disposition", "NEW")
        disposition = str(raw_disposition).strip().upper() if raw_disposition else "NEW"
        if disposition not in ("NEW", "KEEP", "UPDATE", "DELETE"):
            disposition = "NEW"

        existing_id = item.get("existing_id")

        return InsightCandidate(
            insight_type=insight_type,
            title=item.get("title", ""),
            content=item.get("content", ""),
            importance=_clamp(importance),
            urgency=_clamp(int(item.get("urgency", 50))),
            entities=entity_specs,
            source_context=sc,
            suggested_action=item.get("suggested_action"),
            action_options=item.get("action_options"),
            disposition=disposition,
            existing_id=existing_id,
        )
    except (TypeError, ValueError) as err:
        logger.warning("Skipping malformed insight candidate: %s", err)
        return None


def _parse_importance(item: dict) -> int:
    """Parse importance from LLM output, supporting legacy priority field."""
    importance = item.get("importance")
    if importance is not None:
        return int(importance)
    # Legacy: convert 1-10 priority to 0-100 importance
    return int(item.get("priority", 5)) * 10


def _validate_insight_type(raw_type: Optional[str]) -> str:
    """Validate insight_type against enum; fallback to EFFICIENCY."""
    if raw_type is None:
        return InsightType.EFFICIENCY.value
    if raw_type in _VALID_INSIGHT_TYPES:
        return raw_type
    logger.warning(
        "LLM returned invalid insight_type '%s', falling back to '%s'",
        raw_type, InsightType.EFFICIENCY.value,
    )
    return InsightType.EFFICIENCY.value


def _clamp(value: int, lo: int = 0, hi: int = 100) -> int:
    """Clamp an integer to [lo, hi]."""
    return max(lo, min(hi, value))
