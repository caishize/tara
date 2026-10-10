"""Tests for CurationEnricher - LLM pre-generation during curation."""

import json
from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.core.utils.timezone import utc_now
from src.modules.curation.services.curation_enricher import (
    CurationEnricher,
    _build_event_xml,
)


def _make_event(**overrides):
    """Create a mock CuratedEvent with sensible defaults."""
    ev = MagicMock()
    ev.id = overrides.get("id", uuid4())
    ev.title = overrides.get("title", "体检")
    ev.event_type = overrides.get("event_type", "medical")
    ev.location = overrides.get("location", "协和医院")
    ev.notes = overrides.get("notes", None)
    ev.priority = overrides.get("priority", "normal")
    ev.enrichment_generated_at = overrides.get("enrichment_generated_at", None)
    ev.life_context_hint = overrides.get("life_context_hint", None)
    ev.secretary_note = overrides.get("secretary_note", None)
    ev.prep_hint = overrides.get("prep_hint", None)
    return ev


def _mock_haiku_response(payload: dict) -> MagicMock:
    """Build a mock Anthropic response with JSON payload."""
    block = MagicMock()
    block.text = json.dumps(payload, ensure_ascii=False)
    response = MagicMock()
    response.content = [block]
    return response


# ---------------------------------------------------------------------------
# _build_event_xml
# ---------------------------------------------------------------------------


class TestBuildEventXml:
    def test_escapes_special_characters(self):
        ev = _make_event(title="A & B <test>")
        xml = _build_event_xml(ev)
        assert "A &amp; B &lt;test&gt;" in xml

    def test_includes_all_fields(self):
        ev = _make_event(
            title="看医生", event_type="medical",
            location="北京", notes="带病历", priority="high",
        )
        xml = _build_event_xml(ev)
        assert "<title>看医生</title>" in xml
        assert "<event_type>medical</event_type>" in xml
        assert "<location>北京</location>" in xml
        assert "<notes>带病历</notes>" in xml
        assert "<priority>high</priority>" in xml

    def test_truncates_long_notes(self):
        ev = _make_event(notes="x" * 500)
        xml = _build_event_xml(ev)
        # Notes are truncated to 300 chars
        assert len(xml) < 600


# ---------------------------------------------------------------------------
# CurationEnricher.enrich
# ---------------------------------------------------------------------------


class TestCurationEnricher:

    @pytest.fixture()
    def mock_db(self):
        return AsyncMock()

    @pytest.fixture()
    def enricher(self, mock_db):
        return CurationEnricher(
            db=mock_db, user_id=uuid4(), family_id=uuid4(),
        )

    @pytest.mark.asyncio
    async def test_valid_json_populates_fields(self, enricher):
        """Valid LLM JSON populates all three enrichment fields."""
        event = _make_event()
        payload = {
            "life_context_hint": "记得带病历",
            "secretary_note": "明天早上空腹去检查",
            "prep_hint": "准备身份证",
        }

        with (
            patch.object(enricher, "_get_static_context_xml", return_value=""),
            patch(
                "src.modules.curation.services.curation_enricher._call_haiku_enrichment",
                new_callable=AsyncMock,
                return_value=payload,
            ),
        ):
            await enricher.enrich(event)

        assert event.life_context_hint == "记得带病历"
        assert event.secretary_note == "明天早上空腹去检查"
        assert event.prep_hint == "准备身份证"
        assert event.enrichment_generated_at is not None

    @pytest.mark.asyncio
    async def test_invalid_json_leaves_fields_untouched(self, enricher):
        """LLM returning None (parse failure) leaves existing fields untouched."""
        event = _make_event(life_context_hint="existing")

        with (
            patch.object(enricher, "_get_static_context_xml", return_value=""),
            patch(
                "src.modules.curation.services.curation_enricher._call_haiku_enrichment",
                new_callable=AsyncMock,
                return_value=None,
            ),
        ):
            await enricher.enrich(event)

        assert event.life_context_hint == "existing"
        assert event.enrichment_generated_at is None

    @pytest.mark.asyncio
    async def test_ttl_guard_skips_recent_enrichment(self, enricher):
        """Events enriched within 24 hours are skipped."""
        event = _make_event(
            enrichment_generated_at=utc_now() - timedelta(hours=1),
        )

        with patch(
            "src.modules.curation.services.curation_enricher._call_haiku_enrichment",
            new_callable=AsyncMock,
        ) as mock_call:
            await enricher.enrich(event)

        mock_call.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_stale_enrichment_regenerates(self, enricher):
        """Events enriched >24 hours ago are re-enriched."""
        event = _make_event(
            enrichment_generated_at=utc_now() - timedelta(hours=25),
        )
        payload = {
            "life_context_hint": "new hint",
            "secretary_note": "new note",
            "prep_hint": None,
        }

        with (
            patch.object(enricher, "_get_static_context_xml", return_value=""),
            patch(
                "src.modules.curation.services.curation_enricher._call_haiku_enrichment",
                new_callable=AsyncMock,
                return_value=payload,
            ),
        ):
            await enricher.enrich(event)

        assert event.life_context_hint == "new hint"

    @pytest.mark.asyncio
    async def test_truncates_long_values(self, enricher):
        """Fields exceeding column limits are truncated."""
        event = _make_event()
        payload = {
            "life_context_hint": "x" * 300,
            "secretary_note": "y" * 600,
            "prep_hint": "z" * 300,
        }

        with (
            patch.object(enricher, "_get_static_context_xml", return_value=""),
            patch(
                "src.modules.curation.services.curation_enricher._call_haiku_enrichment",
                new_callable=AsyncMock,
                return_value=payload,
            ),
        ):
            await enricher.enrich(event)

        assert len(event.life_context_hint) <= 200
        assert len(event.secretary_note) <= 500
        assert len(event.prep_hint) <= 200
