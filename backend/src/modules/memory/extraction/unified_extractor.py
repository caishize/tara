"""
Unified Agentic Extractor - Single LLM call for all extraction tasks.

Uses LLM-driven semantic understanding to extract:
- Intent classification
- Entity extraction (persons, locations, dates, amounts, items)
- Slot filling (based on intent requirements)
- Relationship inference

Design Goals:
- Semantic understanding via LLM
- Reduce latency through caching
- Graceful fallback to basic extraction when LLM unavailable
- Support both Haiku (fast/cheap) and Sonnet (accurate) models
"""

import asyncio
import hashlib
import json
import re
import os
import threading
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Union
from uuid import UUID

from ....config.logging import get_logger
from ....core.llm import openai_adapter
from ..utils import extract_json_from_response

from .prompts import build_extraction_prompt, build_slot_filling_prompt, INTENT_REQUIRED_SLOTS
from .cache import get_extraction_cache, ExtractionCache

logger = get_logger(__name__)

# Constants
MAX_INPUT_LENGTH = 5000  # Maximum input text length
MAX_RESPONSE_LENGTH = 10000  # Maximum LLM response length to parse


@dataclass
class ExtractedIntent:
    """Extracted intent information."""
    type: str
    confidence: float
    is_continuation: bool = False


@dataclass
class ExtractedPerson:
    """Extracted person entity."""
    name: Optional[str] = None
    role: Optional[str] = None  # Chinese role: 老婆, 儿子
    relationship: Optional[str] = None  # Normalized: wife, son


@dataclass
class ExtractedDateTime:
    """Extracted date/time information."""
    date: Optional[str] = None
    time: Optional[str] = None
    is_lunar: bool = False
    relative: Optional[str] = None  # 明天, 下周二


@dataclass
class ExtractedAmount:
    """Extracted amount/money."""
    value: float
    unit: str = "元"


@dataclass
class ExtractedEntities:
    """All extracted entities."""
    persons: List[ExtractedPerson] = field(default_factory=list)
    locations: List[str] = field(default_factory=list)
    datetime: Optional[ExtractedDateTime] = None
    amounts: List[ExtractedAmount] = field(default_factory=list)
    items: List[str] = field(default_factory=list)
    content: Optional[str] = None


@dataclass
class ExtractedSlots:
    """Extracted slots based on intent."""
    values: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def __contains__(self, key: str) -> bool:
        return key in self.values


@dataclass
class ExtractedRelationship:
    """Extracted relationship between entities."""
    from_entity: str
    to_entity: str
    relationship_type: str


@dataclass
class ExtractionResult:
    """Complete extraction result from a single LLM call."""
    intent: ExtractedIntent
    entities: ExtractedEntities
    slots: ExtractedSlots
    relationships: List[ExtractedRelationship] = field(default_factory=list)
    reasoning: Optional[str] = None
    raw_text: str = ""
    from_cache: bool = False

    def is_complete(self, intent_type: str = None) -> bool:
        """Check if all required slots for the intent are filled."""
        target_intent = intent_type or self.intent.type
        required = INTENT_REQUIRED_SLOTS.get(target_intent, [])
        return all(slot in self.slots for slot in required)

    def get_missing_slots(self, intent_type: str = None) -> List[str]:
        """Get list of missing required slots."""
        target_intent = intent_type or self.intent.type
        required = INTENT_REQUIRED_SLOTS.get(target_intent, [])
        return [slot for slot in required if slot not in self.slots]

    def to_flat_entities(self) -> Dict[str, Any]:
        """Convert extracted entities to a flat dict format."""
        entities: Dict[str, Any] = {}
        if self.entities.persons:
            person = self.entities.persons[0]
            if person.role:
                entities["person"] = person.role
            if person.name:
                entities["name"] = person.name
        if self.entities.locations:
            entities["location"] = self.entities.locations[0]
        if self.entities.datetime:
            if self.entities.datetime.date:
                entities["date"] = self.entities.datetime.date
            if self.entities.datetime.time:
                entities["time"] = self.entities.datetime.time
        if self.entities.amounts:
            entities["amount"] = self.entities.amounts[0].value
        if self.entities.items:
            entities["item"] = self.entities.items
        if self.intent.is_continuation:
            entities["_is_continuation"] = True
        return entities


class UnifiedAgenticExtractor:
    """
    Unified extractor using LLM for semantic understanding.

    Replaces regex-based extraction with a single LLM call that extracts:
    - Intent
    - Entities
    - Slots
    - Relationships
    """

    def __init__(
        self,
        cache: Optional[ExtractionCache] = None,
        use_haiku: bool = True,
        timeout: float = 5.0,
        enable_cache: bool = True,
    ):
        """
        Initialize the extractor.

        Args:
            cache: Cache instance (uses global cache if None)
            use_haiku: Use Haiku model for faster/cheaper extraction
            timeout: LLM call timeout in seconds
            enable_cache: Whether to use caching
        """
        self.cache = cache or get_extraction_cache()
        self.use_haiku = use_haiku
        self.timeout = timeout
        self.enable_cache = enable_cache

        # Feature flag for enabling/disabling
        self.enabled = os.getenv("AGENTIC_EXTRACTION_ENABLED", "true").lower() == "true"

    async def extract(
        self,
        text: str,
        context: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[Union[UUID, str]] = None,
        force_llm: bool = False,
    ) -> ExtractionResult:
        """
        Extract intent, entities, and slots from user input.

        Args:
            text: User input text
            context: Conversation history (optional)
            user_id: User identifier for cache isolation (IMPORTANT for security)
            force_llm: Force LLM call even if disabled

        Returns:
            ExtractionResult with all extracted information
        """
        # Input validation and sanitization
        if len(text) > MAX_INPUT_LENGTH:
            logger.warning(f"Input truncated from {len(text)} to {MAX_INPUT_LENGTH} chars")
            text = text[:MAX_INPUT_LENGTH]

        text = text.strip()

        if not text:
            return self._fallback_extract("")

        # Check if agentic extraction is enabled
        if not self.enabled and not force_llm:
            logger.debug("Agentic extraction disabled, using fallback")
            return self._fallback_extract(text)

        # Build context string
        context_str = self._format_context(context)

        # Check cache with user-scoped key (CRITICAL: prevents cross-user data leakage)
        if self.enable_cache:
            cache_key = self._build_cache_key(text, context_str, user_id)
            cached = await self.cache.get(cache_key)
            if cached:
                return self._parse_cached_result(cached, text)

        # Call LLM for extraction
        try:
            result = await self._llm_extract(text, context_str)

            # Cache the result with user-scoped key
            if self.enable_cache and result:
                cache_key = self._build_cache_key(text, context_str, user_id)
                await self.cache.set(
                    cache_key,
                    self._result_to_dict(result),
                )

            return result

        except asyncio.TimeoutError:
            logger.warning(f"LLM extraction timed out for: {text[:50]}...")
            return self._fallback_extract(text)
        except Exception as e:
            logger.warning(f"LLM extraction error: {e}", exc_info=True)
            return self._fallback_extract(text)

    def _build_cache_key(
        self,
        text: str,
        context_str: str,
        user_id: Optional[Union[UUID, str]] = None,
    ) -> str:
        """
        Build a secure, hashed cache key.

        Includes user_id to prevent cross-user data leakage.
        Uses SHA256 hash to prevent cache poisoning attacks.

        Args:
            text: User input text
            context_str: Formatted context string
            user_id: User identifier

        Returns:
            Hashed cache key
        """
        # Include user_id in cache key for isolation
        user_part = str(user_id) if user_id else "anonymous"
        raw_key = f"{user_part}|{text}|{context_str}"

        # Hash to prevent cache poisoning and normalize key length
        return hashlib.sha256(raw_key.encode()).hexdigest()

    async def _llm_extract(
        self,
        text: str,
        context_str: str,
    ) -> ExtractionResult:
        """
        Call LLM for extraction.

        Args:
            text: User input text
            context_str: Formatted conversation context

        Returns:
            ExtractionResult from LLM
        """
        # Build prompt
        prompt = build_extraction_prompt(
            text=text,
            context=context_str,
            use_haiku=self.use_haiku,
        )

        # Call LLM with timeout
        response = await asyncio.wait_for(
            openai_adapter.generate_text(
                prompt,
                temperature=0.1,
                max_tokens=500,
            ),
            timeout=self.timeout,
        )

        # Parse response
        return self._parse_llm_response(response, text)

    def _parse_llm_response(self, response: str, original_text: str) -> ExtractionResult:
        """
        Parse LLM response into ExtractionResult.

        Args:
            response: Raw LLM response
            original_text: Original user input

        Returns:
            Parsed ExtractionResult
        """
        try:
            # Limit response length to prevent ReDoS
            if len(response) > MAX_RESPONSE_LENGTH:
                response = response[:MAX_RESPONSE_LENGTH]

            # Use shared utility for robust JSON extraction
            data = extract_json_from_response(response)
            if not data:
                logger.warning("No JSON found in LLM response")
                return self._fallback_extract(original_text)

            # Parse intent
            intent_data = data.get("intent", {})
            if isinstance(intent_data, str):
                # Handle simplified Haiku format
                intent = ExtractedIntent(
                    type=intent_data,
                    confidence=data.get("confidence", 0.8),
                )
            else:
                intent = ExtractedIntent(
                    type=intent_data.get("type", "unknown"),
                    confidence=intent_data.get("confidence", 0.5),
                    is_continuation=intent_data.get("is_continuation", False),
                )

            # Parse entities
            entities = self._parse_entities(data)

            # Parse slots
            slots = ExtractedSlots(values=data.get("slots", {}))

            # Merge entity-derived slots
            self._merge_entity_slots(entities, slots, intent.type)

            # Parse relationships
            relationships = []
            for rel_data in data.get("relationships", []):
                relationships.append(ExtractedRelationship(
                    from_entity=rel_data.get("from", ""),
                    to_entity=rel_data.get("to", ""),
                    relationship_type=rel_data.get("type", ""),
                ))

            return ExtractionResult(
                intent=intent,
                entities=entities,
                slots=slots,
                relationships=relationships,
                reasoning=data.get("reasoning"),
                raw_text=original_text,
                from_cache=False,
            )

        except json.JSONDecodeError as e:
            logger.warning(f"Failed to parse LLM response as JSON: {e}")
            return self._fallback_extract(original_text)

    def _parse_entities(self, data: Dict[str, Any]) -> ExtractedEntities:
        """Parse entities from LLM response data."""
        entities = ExtractedEntities()

        entities_data = data.get("entities", data)  # Handle flat format

        # Parse persons
        persons_data = entities_data.get("persons", [])
        if isinstance(persons_data, list):
            for p in persons_data:
                if isinstance(p, dict):
                    entities.persons.append(ExtractedPerson(
                        name=p.get("name"),
                        role=p.get("role"),
                        relationship=p.get("relationship"),
                    ))
                elif isinstance(p, str):
                    entities.persons.append(ExtractedPerson(role=p))

        # Parse locations
        locations = entities_data.get("locations", entities_data.get("location"))
        if locations:
            if isinstance(locations, list):
                entities.locations = locations
            else:
                entities.locations = [locations]

        # Parse datetime
        datetime_data = entities_data.get("datetime")
        if datetime_data:
            if isinstance(datetime_data, dict):
                entities.datetime = ExtractedDateTime(
                    date=datetime_data.get("date"),
                    time=datetime_data.get("time"),
                    is_lunar=datetime_data.get("is_lunar", False),
                    relative=datetime_data.get("relative"),
                )
            elif isinstance(datetime_data, str):
                entities.datetime = ExtractedDateTime(date=datetime_data)

        # Parse amounts (with safe float conversion)
        amounts_data = entities_data.get("amounts", [])
        if isinstance(amounts_data, list):
            for a in amounts_data:
                if isinstance(a, dict):
                    entities.amounts.append(ExtractedAmount(
                        value=self._safe_float(a.get("value", 0)),
                        unit=a.get("unit", "元"),
                    ))
        elif entities_data.get("amount"):
            entities.amounts.append(ExtractedAmount(
                value=self._safe_float(entities_data.get("amount")),
            ))

        # Parse items
        items = entities_data.get("items", [])
        if isinstance(items, list):
            entities.items = items
        elif items:
            entities.items = [items]

        # Parse content
        entities.content = entities_data.get("content")

        return entities

    def _merge_entity_slots(
        self,
        entities: ExtractedEntities,
        slots: ExtractedSlots,
        intent_type: str,
    ) -> None:
        """Merge entity-derived values into slots."""
        # Person-related slots
        if entities.persons and not slots.get("person"):
            person = entities.persons[0]
            if person.role:
                slots.values["person"] = person.role
            if person.name:
                slots.values["name"] = person.name
            if person.relationship:
                slots.values["relationship"] = person.relationship

        # Date-related slots
        if entities.datetime:
            dt = entities.datetime
            if dt.date and not slots.get("date_value"):
                slots.values["date_value"] = dt.date
            if dt.time and not slots.get("time"):
                slots.values["time"] = dt.time
            if dt.is_lunar:
                slots.values["is_lunar"] = True

        # Location-related slots
        if entities.locations and not slots.get("address"):
            slots.values["address"] = entities.locations[0]

        # Amount-related slots
        if entities.amounts and not slots.get("amount"):
            slots.values["amount"] = entities.amounts[0].value

        # Item-related slots
        if entities.items:
            if not slots.get("item_name"):
                slots.values["item_name"] = entities.items[0]
            if not slots.get("items"):
                slots.values["items"] = entities.items

        # Content slot
        if entities.content and not slots.get("content"):
            slots.values["content"] = entities.content

    def _format_context(self, context: Optional[List[Dict[str, str]]]) -> str:
        """Format conversation context for prompt."""
        if not context:
            return "无"

        recent = context[-5:]  # Last 5 turns
        lines = []
        for msg in recent:
            role = "用户" if msg.get("role") == "user" else "助手"
            content = msg.get("content", "")[:150]
            lines.append(f"{role}: {content}")

        return "\n".join(lines)

    def _safe_float(self, value: Any, default: float = 0.0) -> float:
        """
        Safely convert value to float.

        Args:
            value: Value to convert
            default: Default value if conversion fails

        Returns:
            Float value
        """
        if value is None:
            return default
        try:
            return float(value)
        except (ValueError, TypeError):
            return default

    def _fallback_extract(self, text: str) -> ExtractionResult:
        """
        Fallback extraction when LLM is unavailable or times out.

        Returns a minimal ExtractionResult with unknown intent and empty
        entities, signalling to callers that re-extraction should be
        attempted later.

        Args:
            text: User input text

        Returns:
            ExtractionResult with unknown intent
        """
        return ExtractionResult(
            intent=ExtractedIntent(
                type="unknown",
                confidence=0.0,
            ),
            entities=ExtractedEntities(),
            slots=ExtractedSlots(),
            raw_text=text,
            from_cache=False,
        )

    def _parse_cached_result(self, cached: Dict[str, Any], text: str) -> ExtractionResult:
        """Parse cached result back into ExtractionResult."""
        intent_data = cached.get("intent", {})
        intent = ExtractedIntent(
            type=intent_data.get("type", "unknown"),
            confidence=intent_data.get("confidence", 0.5),
            is_continuation=intent_data.get("is_continuation", False),
        )

        entities = self._parse_entities(cached)
        slots = ExtractedSlots(values=cached.get("slots", {}))

        relationships = []
        for rel_data in cached.get("relationships", []):
            relationships.append(ExtractedRelationship(
                from_entity=rel_data.get("from", ""),
                to_entity=rel_data.get("to", ""),
                relationship_type=rel_data.get("type", ""),
            ))

        return ExtractionResult(
            intent=intent,
            entities=entities,
            slots=slots,
            relationships=relationships,
            reasoning=cached.get("reasoning"),
            raw_text=text,
            from_cache=True,
        )

    def _result_to_dict(self, result: ExtractionResult) -> Dict[str, Any]:
        """Convert ExtractionResult to dict for caching."""
        return {
            "intent": {
                "type": result.intent.type,
                "confidence": result.intent.confidence,
                "is_continuation": result.intent.is_continuation,
            },
            "entities": {
                "persons": [
                    {"name": p.name, "role": p.role, "relationship": p.relationship}
                    for p in result.entities.persons
                ],
                "locations": result.entities.locations,
                "datetime": {
                    "date": result.entities.datetime.date,
                    "time": result.entities.datetime.time,
                    "is_lunar": result.entities.datetime.is_lunar,
                    "relative": result.entities.datetime.relative,
                } if result.entities.datetime else None,
                "amounts": [
                    {"value": a.value, "unit": a.unit}
                    for a in result.entities.amounts
                ],
                "items": result.entities.items,
                "content": result.entities.content,
            },
            "slots": result.slots.values,
            "relationships": [
                {"from": r.from_entity, "to": r.to_entity, "type": r.relationship_type}
                for r in result.relationships
            ],
            "reasoning": result.reasoning,
        }

    async def extract_slots_for_missing(
        self,
        text: str,
        intent: str,
        collected_slots: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Extract specific slots from user response during slot filling.

        Args:
            text: User input text
            intent: Current intent being filled
            collected_slots: Already collected slot values

        Returns:
            Dict of newly extracted slot values
        """
        missing_slots = [
            s for s in INTENT_REQUIRED_SLOTS.get(intent, [])
            if s not in collected_slots
        ]

        if not missing_slots:
            return {}

        prompt = build_slot_filling_prompt(
            text=text,
            intent=intent,
            collected_slots=collected_slots,
            missing_slots=missing_slots,
        )

        try:
            response = await asyncio.wait_for(
                openai_adapter.generate_text(
                    prompt,
                    temperature=0.1,
                    max_tokens=200,
                ),
                timeout=3.0,  # Shorter timeout for slot filling
            )

            # Use shared utility for JSON extraction
            result = extract_json_from_response(response)
            return result if isinstance(result, dict) else {}

        except Exception as e:
            logger.warning(f"Slot extraction error: {e}")
            return {}


# Global instance with thread-safe initialization
_extractor: Optional[UnifiedAgenticExtractor] = None
_extractor_lock = threading.Lock()


def get_extractor() -> UnifiedAgenticExtractor:
    """
    Get or create the global extractor instance (thread-safe).

    Uses double-checked locking pattern for thread safety.
    """
    global _extractor
    if _extractor is None:
        with _extractor_lock:
            # Double-check after acquiring lock
            if _extractor is None:
                _extractor = UnifiedAgenticExtractor()
    return _extractor


async def extract_all(
    text: str,
    context: Optional[List[Dict[str, str]]] = None,
    user_id: Optional[Union[UUID, str]] = None,
) -> ExtractionResult:
    """
    Convenience function for extraction.

    Args:
        text: User input text
        context: Conversation history
        user_id: User identifier for cache isolation

    Returns:
        ExtractionResult
    """
    return await get_extractor().extract(text, context, user_id=user_id)
