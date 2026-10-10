"""Tests for PendingAction generation from EventAssociations.

Covers:
- _should_generate_pending_action() decision logic
- _generate_action_draft() Haiku draft + fallback templates
- _create_pending_action_from_association() flood-control guards

Source: src.modules.curation.services.association_service
"""
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.modules.curation.models import CuratedEvent, EventAssociation
from src.modules.curation.services.association_service import (
    CurationAssociationMixin,
    _SUGGEST_ACTION_COOLDOWN_DAYS,
    _SUGGEST_ACTION_MAX_PENDING,
    _SUGGEST_GREETING_DAYS_THRESHOLD,
    _SUGGEST_GREETING_DEPARTURE_DAYS,
    _SUGGEST_MEETING_CONFIDENCE_THRESHOLD,
    _SUGGEST_REJECT_SUPPRESS_DAYS,
    _SUGGEST_MEETING_ALLOWED_TEMPS,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_dt(days_offset: int = 0, hours_offset: int = 0) -> datetime:
    """Return a timezone-aware UTC datetime relative to 'now'."""
    return datetime.now(timezone.utc) + timedelta(days=days_offset, hours=hours_offset)


def _make_event(
    *,
    event_type: str = "business_trip",
    location: str = "Shanghai",
    city: str = "Shanghai",
    days_until_start: int = 3,
    duration_hours: int = 8,
    user_id: uuid.UUID = None,
) -> CuratedEvent:
    """Build a minimal CuratedEvent for testing."""
    ev = CuratedEvent()
    ev.id = uuid.uuid4()
    ev.user_id = user_id or uuid.uuid4()
    ev.family_id = uuid.uuid4()
    ev.title = f"Test Event {ev.id.hex[:6]}"
    ev.event_type = event_type
    ev.location = location
    ev.city = city
    ev.normalized_start = _utc_dt(days_offset=days_until_start)
    ev.normalized_end = _utc_dt(
        days_offset=days_until_start,
        hours_offset=duration_hours,
    )
    ev.original_event_ids = []
    ev.source_types = ["test"]
    ev.confidence = 0.9
    ev.status = "confirmed"
    ev.priority = "normal"
    return ev


def _make_association(
    event: CuratedEvent,
    *,
    association_type: str = "location",
    target_type: str = "person",
    confidence: float = 0.8,
    title: str = "Visit old colleague",
    reason: str = "Lives near destination",
    target_id: str = None,
) -> EventAssociation:
    """Build a minimal EventAssociation for testing."""
    assoc = EventAssociation()
    assoc.id = uuid.uuid4()
    assoc.family_id = event.family_id
    assoc.source_event_id = event.id
    assoc.target_id = target_id or str(uuid.uuid4())
    assoc.target_type = target_type
    assoc.association_type = association_type
    assoc.title = title
    assoc.reason = reason
    assoc.priority = "convenient"
    assoc.confidence = confidence
    return assoc


def _make_mixin(session: AsyncMock = None) -> CurationAssociationMixin:
    """Construct a mixin instance with mock session."""
    mixin = CurationAssociationMixin.__new__(CurationAssociationMixin)
    mixin.session = session or AsyncMock()
    return mixin


# ===================================================================
# Test: _should_generate_pending_action()
# ===================================================================

class TestShouldGeneratePendingAction:
    """Tests for the decision logic that maps association -> action_type."""

    @pytest.mark.asyncio
    async def test_suggest_meeting_location_cold_high_confidence(self):
        """location + person + confidence >= 0.7 + cold → suggest_meeting."""
        event = _make_event()
        assoc = _make_association(
            event,
            association_type="location",
            target_type="person",
            confidence=_SUGGEST_MEETING_CONFIDENCE_THRESHOLD,
        )
        mixin = _make_mixin()
        mixin._get_target_temperature = AsyncMock(return_value="cold")

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result == "suggest_meeting"
        mixin._get_target_temperature.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_suggest_meeting_location_cool_high_confidence(self):
        """location + person + confidence >= 0.7 + cool → suggest_meeting."""
        event = _make_event()
        assoc = _make_association(
            event,
            association_type="location",
            target_type="person",
            confidence=0.85,
        )
        mixin = _make_mixin()
        mixin._get_target_temperature = AsyncMock(return_value="cool")

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result == "suggest_meeting"

    @pytest.mark.asyncio
    async def test_suggest_meeting_rejected_for_warm_temperature(self):
        """location + person + high confidence + warm → NOT suggest_meeting."""
        event = _make_event()
        assoc = _make_association(
            event,
            association_type="location",
            target_type="person",
            confidence=0.9,
        )
        mixin = _make_mixin()
        mixin._get_target_temperature = AsyncMock(return_value="warm")

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result is None

    @pytest.mark.asyncio
    async def test_suggest_meeting_rejected_below_confidence_threshold(self):
        """location + person + confidence < 0.7 → NOT suggest_meeting."""
        event = _make_event()
        assoc = _make_association(
            event,
            association_type="location",
            target_type="person",
            confidence=_SUGGEST_MEETING_CONFIDENCE_THRESHOLD - 0.01,
        )
        mixin = _make_mixin()
        mixin._get_target_temperature = AsyncMock(return_value="cold")

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result is None
        mixin._get_target_temperature.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_suggest_greeting_person_assoc_departing_soon_stale(self):
        """stale_contact + person + event within 7 days + 60+ days no contact → suggest_greeting."""
        event = _make_event(days_until_start=5)
        assoc = _make_association(
            event,
            association_type="stale_contact",
            target_type="person",
        )
        mixin = _make_mixin()
        mixin._get_days_since_contact = AsyncMock(
            return_value=_SUGGEST_GREETING_DAYS_THRESHOLD,
        )

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result == "suggest_greeting"

    @pytest.mark.asyncio
    async def test_suggest_greeting_person_assoc_too_far_out(self):
        """stale_contact + person + event > 7 days out → None (regardless of staleness)."""
        event = _make_event(
            days_until_start=_SUGGEST_GREETING_DEPARTURE_DAYS + 1,
        )
        assoc = _make_association(
            event,
            association_type="stale_contact",
            target_type="person",
        )
        mixin = _make_mixin()

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result is None

    @pytest.mark.asyncio
    async def test_suggest_greeting_person_assoc_60_days_no_contact(self):
        """stale_contact + person + 60+ days since contact + within 7 days → suggest_greeting."""
        event = _make_event(days_until_start=3)
        assoc = _make_association(
            event,
            association_type="stale_contact",
            target_type="person",
        )
        mixin = _make_mixin()
        mixin._get_days_since_contact = AsyncMock(
            return_value=_SUGGEST_GREETING_DAYS_THRESHOLD,
        )

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result == "suggest_greeting"

    @pytest.mark.asyncio
    async def test_suggest_greeting_person_assoc_recent_contact(self):
        """stale_contact + person + days_since_contact < 60 → None."""
        event = _make_event(days_until_start=3)
        assoc = _make_association(
            event,
            association_type="stale_contact",
            target_type="person",
        )
        mixin = _make_mixin()
        mixin._get_days_since_contact = AsyncMock(
            return_value=_SUGGEST_GREETING_DAYS_THRESHOLD - 1,
        )

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result is None

    @pytest.mark.asyncio
    async def test_suggest_gift_temporal_birthday(self):
        """temporal + date + birthday keyword → suggest_gift."""
        event = _make_event()
        assoc = _make_association(
            event,
            association_type="temporal",
            target_type="date",
            title="妈妈的生日",
            reason="3月5日是妈妈的生日",
        )
        mixin = _make_mixin()

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result == "suggest_gift"

    @pytest.mark.asyncio
    async def test_suggest_gift_temporal_anniversary(self):
        """temporal + date + anniversary keyword → suggest_gift."""
        event = _make_event()
        assoc = _make_association(
            event,
            association_type="temporal",
            target_type="date",
            title="Wedding anniversary",
            reason="Their anniversary is coming up",
        )
        mixin = _make_mixin()

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result == "suggest_gift"

    @pytest.mark.asyncio
    async def test_suggest_gift_not_triggered_without_keywords(self):
        """temporal + date but no gift keywords → None."""
        event = _make_event()
        assoc = _make_association(
            event,
            association_type="temporal",
            target_type="date",
            title="Monthly team sync",
            reason="Recurring team event",
        )
        mixin = _make_mixin()

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result is None

    @pytest.mark.asyncio
    async def test_returns_none_for_unrecognised_combination(self):
        """semantic + memory → None (no matching rule)."""
        event = _make_event()
        assoc = _make_association(
            event,
            association_type="semantic",
            target_type="memory",
        )
        mixin = _make_mixin()

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result is None

    @pytest.mark.asyncio
    async def test_no_start_time_for_greeting_returns_none(self):
        """person + person + no normalized_start → None."""
        event = _make_event()
        event.normalized_start = None
        assoc = _make_association(
            event,
            association_type="person",
            target_type="person",
        )
        mixin = _make_mixin()

        result = await mixin._should_generate_pending_action(assoc, event)

        assert result is None


# ===================================================================
# Test: _create_pending_action_from_association() flood control
# ===================================================================

class TestFloodControl:
    """Flood-control guards inside _create_pending_action_from_association()."""

    @pytest.mark.asyncio
    async def test_max_pending_limit_blocks_creation(self):
        """If user already has 3 suggest_* PENDING actions, reject new ones."""
        event = _make_event()
        assoc = _make_association(event)
        session = AsyncMock()
        # First scalar call: count of pending suggest_* → 3 (at limit)
        session.scalar = AsyncMock(return_value=_SUGGEST_ACTION_MAX_PENDING)
        mixin = _make_mixin(session=session)

        created = await mixin._create_pending_action_from_association(
            association=assoc,
            event=event,
            action_type="suggest_meeting",
            draft_content="Test draft",
            user_id=event.user_id,
            family_id=event.family_id,
        )

        assert created is False
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_below_max_pending_and_no_cooldown_creates_action(self):
        """Happy path: no flood-control issues → PendingAction created."""
        event = _make_event()
        assoc = _make_association(event)
        session = AsyncMock()
        # count pending < limit, no recent cooldown, no reject suppress
        session.scalar = AsyncMock(side_effect=[
            _SUGGEST_ACTION_MAX_PENDING - 1,  # pending count
            None,                              # cooldown query
            None,                              # reject suppress query
        ])
        mixin = _make_mixin(session=session)

        created = await mixin._create_pending_action_from_association(
            association=assoc,
            event=event,
            action_type="suggest_meeting",
            draft_content="Hi, want to meet?",
            user_id=event.user_id,
            family_id=event.family_id,
        )

        assert created is True
        session.add.assert_called_once()
        added_obj = session.add.call_args[0][0]
        assert added_obj.action_type == "suggest_meeting"
        assert added_obj.draft_content == "Hi, want to meet?"

    @pytest.mark.asyncio
    async def test_cooldown_blocks_same_target_and_type(self):
        """Same (target, action_type) within 7 days → reject."""
        event = _make_event()
        assoc = _make_association(event)
        session = AsyncMock()
        session.scalar = AsyncMock(side_effect=[
            0,                  # pending count: OK
            uuid.uuid4(),       # cooldown query: found recent match
        ])
        mixin = _make_mixin(session=session)

        created = await mixin._create_pending_action_from_association(
            association=assoc,
            event=event,
            action_type="suggest_meeting",
            draft_content="Draft",
            user_id=event.user_id,
            family_id=event.family_id,
        )

        assert created is False
        session.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_reject_suppress_blocks_for_30_days(self):
        """User rejected same (target, action_type) within 30 days → reject."""
        event = _make_event()
        assoc = _make_association(event)
        session = AsyncMock()
        session.scalar = AsyncMock(side_effect=[
            0,                  # pending count: OK
            None,               # cooldown: no recent
            uuid.uuid4(),       # reject suppress: found rejected match
        ])
        mixin = _make_mixin(session=session)

        created = await mixin._create_pending_action_from_association(
            association=assoc,
            event=event,
            action_type="suggest_greeting",
            draft_content="Draft",
            user_id=event.user_id,
            family_id=event.family_id,
        )

        assert created is False
        session.add.assert_not_called()


# ===================================================================
# Test: _generate_action_draft() Haiku draft + fallback
# ===================================================================

class TestGenerateActionDraft:
    """Tests for LLM draft generation with Haiku and template fallback."""

    @pytest.mark.asyncio
    async def test_haiku_returns_draft_text(self):
        """When Haiku succeeds, return the generated text."""
        event = _make_event(location="Beijing")
        assoc = _make_association(event, reason="Old friend lives there")
        mixin = _make_mixin()

        mock_block = MagicMock()
        mock_block.text = "  小明，我下周去北京出差，要不要一起吃个饭？  "
        mock_response = MagicMock()
        mock_response.content = [mock_block]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "src.modules.curation.services.association_service.get_haiku_client",
            return_value=mock_client,
        ):
            draft = await mixin._generate_action_draft(
                "suggest_meeting", assoc, event, "小明",
            )

        assert draft == "小明，我下周去北京出差，要不要一起吃个饭？"
        mock_client.messages.create.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_haiku_failure_falls_back_to_template(self):
        """When Haiku raises an exception, fallback template is used."""
        event = _make_event(location="Shenzhen")
        assoc = _make_association(event, reason="College roommate")
        mixin = _make_mixin()

        with patch(
            "src.modules.curation.services.association_service.get_haiku_client",
            side_effect=RuntimeError("API unavailable"),
        ):
            draft = await mixin._generate_action_draft(
                "suggest_meeting", assoc, event, "李华",
            )

        assert "李华" in draft
        assert "Shenzhen" in draft or "见面" in draft

    @pytest.mark.asyncio
    async def test_fallback_template_suggest_greeting(self):
        """Verify greeting fallback template contains member name."""
        event = _make_event(location="Tokyo")
        assoc = _make_association(event, reason="Haven't spoken in a while")
        mixin = _make_mixin()

        with patch(
            "src.modules.curation.services.association_service.get_haiku_client",
            side_effect=RuntimeError("LLM down"),
        ):
            draft = await mixin._generate_action_draft(
                "suggest_greeting", assoc, event, "王芳",
            )

        assert "王芳" in draft
        assert "好久不见" in draft

    @pytest.mark.asyncio
    async def test_fallback_template_suggest_gift(self):
        """Verify gift fallback template contains reason text."""
        event = _make_event(location="Home")
        reason_text = "3月5日是妈妈的生日"
        assoc = _make_association(event, reason=reason_text)
        mixin = _make_mixin()

        with patch(
            "src.modules.curation.services.association_service.get_haiku_client",
            side_effect=RuntimeError("LLM down"),
        ):
            draft = await mixin._generate_action_draft(
                "suggest_gift", assoc, event, "妈妈",
            )

        assert "妈妈" in draft
        assert reason_text in draft

    @pytest.mark.asyncio
    async def test_haiku_empty_response_falls_back(self):
        """When Haiku returns no text blocks, fallback template is used."""
        event = _make_event(location="Guangzhou")
        assoc = _make_association(event, reason="Classmate")
        mixin = _make_mixin()

        mock_response = MagicMock()
        mock_response.content = []  # no text blocks

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        with patch(
            "src.modules.curation.services.association_service.get_haiku_client",
            return_value=mock_client,
        ):
            draft = await mixin._generate_action_draft(
                "suggest_meeting", assoc, event, "张三",
            )

        # Should fall through to template
        assert "张三" in draft


# ===================================================================
# Test: constants sanity checks
# ===================================================================

class TestConstants:
    """Verify critical constants have expected values."""

    def test_confidence_threshold(self):
        assert _SUGGEST_MEETING_CONFIDENCE_THRESHOLD == 0.7

    def test_max_pending(self):
        assert _SUGGEST_ACTION_MAX_PENDING == 3

    def test_cooldown_days(self):
        assert _SUGGEST_ACTION_COOLDOWN_DAYS == 7

    def test_reject_suppress_days(self):
        assert _SUGGEST_REJECT_SUPPRESS_DAYS == 30

    def test_greeting_days_threshold(self):
        assert _SUGGEST_GREETING_DAYS_THRESHOLD == 60

    def test_greeting_departure_days(self):
        assert _SUGGEST_GREETING_DEPARTURE_DAYS == 7

    def test_meeting_allowed_temps(self):
        assert "cold" in _SUGGEST_MEETING_ALLOWED_TEMPS
        assert "cool" in _SUGGEST_MEETING_ALLOWED_TEMPS
        assert "warm" not in _SUGGEST_MEETING_ALLOWED_TEMPS
        assert "hot" not in _SUGGEST_MEETING_ALLOWED_TEMPS
