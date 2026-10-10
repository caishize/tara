"""CurationEnricher — pre-generates warm content for curated events via Haiku.

Called once per curation run (PLAN-002). Generates three pre-warmed fields
on each CuratedEvent so the read path (timeline) can display them without any
LLM call at query time:

    life_context_hint  — short warm context tag  (≤200 chars)
    secretary_note     — longer secretary annotation
    prep_hint          — actionable preparation reminder (≤200 chars)

The enricher caches the InsightContextAssembler result for the whole run so
that multiple events in the same family batch share one set of DB reads.
"""

import json
from datetime import timedelta
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from ....config.logging import get_logger
from ....config.settings import settings
from ....core.utils.timezone import utc_now
from ....core.utils.xml_escape import escape_xml
from ..models import CuratedEvent

logger = get_logger(__name__)

# System prompt tuned for event-level enrichment (not person-insight).
_ENRICHMENT_SYSTEM_PROMPT = """你是贴心的家庭管家，负责为家庭日历上的每个事项生成三条简短的温馨提示。

## 要求
1. 语气像家人叮嘱，不要用"建议您"、"请确认"等公文词
2. 每条内容具体、温暖、可执行
3. life_context_hint 和 prep_hint 各不超过30字，secretary_note 不超过60字
4. 如果事项信息简单，可省略 prep_hint（返回 null）

## 输出格式（严格JSON）
{
  "life_context_hint": "生活背景提示（≤30字）",
  "secretary_note": "管家备注，更详细的说明（≤60字）",
  "prep_hint": "准备事项提示（≤30字，可为null）"
}"""

# Only re-generate if enrichment is older than this threshold.
_ENRICHMENT_TTL = timedelta(hours=24)


def _build_event_xml(event: CuratedEvent) -> str:
    """Serialize the event's key fields into XML for the LLM prompt."""
    parts = ["<event>"]
    if event.title:
        parts.append(f"  <title>{escape_xml(event.title)}</title>")
    if event.event_type:
        parts.append(f"  <event_type>{escape_xml(event.event_type)}</event_type>")
    if event.location:
        parts.append(f"  <location>{escape_xml(event.location)}</location>")
    if event.notes:
        # Truncate notes to avoid blowing past the token budget.
        notes_snippet = event.notes[:300]
        parts.append(f"  <notes>{escape_xml(notes_snippet)}</notes>")
    if event.priority:
        parts.append(f"  <priority>{escape_xml(event.priority)}</priority>")
    parts.append("</event>")
    return "\n".join(parts)


async def _call_haiku_enrichment(context_xml: str) -> Optional[dict]:
    """Call Haiku with the enrichment prompt and parse the three-field JSON.

    Returns a dict with keys life_context_hint, secretary_note, prep_hint
    on success, or None on any failure so the caller can skip gracefully.
    """
    try:
        from ....core.llm.haiku_client import get_haiku_client

        client = get_haiku_client()
        response = await client.messages.create(
            model=settings.fast_worker_model,
            max_tokens=250,
            temperature=0.4,
            system=_ENRICHMENT_SYSTEM_PROMPT,
            messages=[{"role": "user", "content": context_xml}],
        )

        text_parts = [
            block.text for block in response.content
            if hasattr(block, "text")
        ]
        if not text_parts:
            return None

        parsed = json.loads(text_parts[0].strip())
        return parsed

    except json.JSONDecodeError:
        logger.warning("Enrichment LLM returned non-JSON — skipping")
        return None
    except Exception as exc:
        logger.warning("Enrichment LLM call failed: %s", exc)
        return None


class CurationEnricher:
    """Pre-generates warm content for curated events using Haiku.

    Instantiate once per curation run to share the cached static context
    across all events in the batch.

    Usage::

        enricher = CurationEnricher(db=session, user_id=user_id, family_id=family_id)
        for event in stored_events:
            try:
                await enricher.enrich(event)
            except Exception as exc:
                logger.warning("Enrichment failed for event %s: %s", event.id, exc)
    """

    def __init__(self, db: AsyncSession, user_id: UUID, family_id: UUID) -> None:
        self.db = db
        self.user_id = user_id
        self.family_id = family_id
        # Lazy-populated once on first enrich() call.
        self._static_context_xml: Optional[str] = None
        self._context_loaded: bool = False

    async def _get_static_context_xml(self) -> str:
        """Assemble and cache the person/memory context XML for this run.

        Fetches InsightContextAssembler data once and caches it for all
        subsequent events in the same batch.
        """
        if self._context_loaded:
            return self._static_context_xml or ""

        self._context_loaded = True
        try:
            from ....modules.insight.insight_context_assembler import InsightContextAssembler
            assembler = InsightContextAssembler(db=self.db)
            context = await assembler.assemble(
                user_id=self.user_id,
                family_id=self.family_id,
            )
            self._static_context_xml = context.to_prompt_xml()
        except Exception as exc:
            logger.warning(
                "InsightContextAssembler failed for user %s, proceeding without context: %s",
                self.user_id,
                exc,
            )
            self._static_context_xml = ""

        return self._static_context_xml or ""

    async def enrich(self, event: CuratedEvent) -> None:
        """Generate and write warm content fields to the event.

        Skips if enrichment was generated within the last 24 hours.
        On LLM failure logs a warning and leaves existing fields untouched.

        The session is NOT flushed or committed here — callers own
        the transaction lifecycle.
        """
        # --- TTL guard ---
        if event.enrichment_generated_at is not None:
            age = utc_now() - event.enrichment_generated_at
            if age < _ENRICHMENT_TTL:
                return

        # --- Build prompt input ---
        event_xml = _build_event_xml(event)
        static_context = await self._get_static_context_xml()
        context_xml = f"{event_xml}\n{static_context}" if static_context else event_xml

        # --- LLM call (graceful fallback) ---
        parsed = await _call_haiku_enrichment(context_xml)
        if parsed is None:
            return

        life_hint_raw = parsed.get("life_context_hint") or ""
        secretary_note_raw = parsed.get("secretary_note") or ""
        prep_hint_raw = parsed.get("prep_hint") or ""

        event.life_context_hint = life_hint_raw.strip()[:200] or None
        event.secretary_note = secretary_note_raw.strip()[:500] or None
        event.prep_hint = prep_hint_raw.strip()[:200] or None
        event.enrichment_generated_at = utc_now()

        logger.debug(
            "Enriched event %s (%s): hint=%r",
            event.id,
            event.event_type,
            event.life_context_hint,
        )
