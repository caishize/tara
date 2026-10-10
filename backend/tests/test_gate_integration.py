"""Tests for FactVerificationGate integration with SecretaryNoteService.

Verifies that generate_notes_from_memories() routes through the Gate
and handles accept, reject, pending, and contradiction scenarios.
"""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.memory.fact_verification import (
    FactVerificationGate,
    NoteCandidate,
    VerificationAction,
    VerificationResult,
)
from src.modules.memory.secretary_note_model import (
    NoteCategory,
    NoteStatus,
    SecretaryNote,
)
from src.modules.memory.secretary_note_service import SecretaryNoteService


@pytest.fixture
def user_id():
    return uuid4()


@pytest.fixture
def family_id():
    return uuid4()


@pytest.fixture
def mock_db():
    """Create an AsyncMock for the DB session."""
    db = AsyncMock()
    db.add = MagicMock()
    db.commit = AsyncMock()
    db.refresh = AsyncMock()
    return db


@pytest.fixture
def service(mock_db):
    return SecretaryNoteService(db=mock_db)


def _make_memory(content: str = "Test memory content"):
    """Create a mock ConversationMemory."""
    m = MagicMock()
    m.id = uuid4()
    m.content = content
    m.memory_type = "preference"
    m.summary = content
    m.status = "active"
    return m


def _make_existing_note(
    title: str = "Existing note",
    category: str = NoteCategory.PREFERENCE.value,
    note_id=None,
):
    """Create a mock existing SecretaryNote."""
    note = MagicMock(spec=SecretaryNote)
    note.id = note_id or uuid4()
    note.title = title
    note.category = category
    note.status = NoteStatus.ACTIVE.value
    note.content = "Existing content"
    note.contradiction_flags = []
    note.updated_at = None
    return note


class TestGateCalledOnGenerate:
    """Test that generate_notes_from_memories calls Gate.verify."""

    @pytest.mark.asyncio
    async def test_gate_verify_called_for_each_extracted_note(
        self, service, user_id, family_id,
    ):
        memories = [_make_memory("User prefers window seats")]

        extracted = [
            {
                "category": "preference",
                "title": "Window seats",
                "content": "User prefers window seats",
                "confidence": 0.9,
                "trigger_keywords": ["seat"],
            },
            {
                "category": "routine",
                "title": "Morning jog",
                "content": "User jogs every morning",
                "confidence": 0.85,
                "trigger_keywords": ["jog"],
            },
        ]

        with patch.object(service, "_get_relevant_memories", return_value=memories), \
             patch.object(service, "_extract_notes_via_llm", return_value=extracted), \
             patch.object(service, "_get_existing_notes", return_value=[]), \
             patch.object(service, "_create_note_if_new", return_value=None) as mock_create, \
             patch.object(
                 FactVerificationGate,
                 "verify",
                 return_value=VerificationResult(
                     action=VerificationAction.ACCEPT,
                     reason="High confidence",
                 ),
             ) as mock_verify:
            await service.generate_notes_from_memories(user_id, family_id)

            assert mock_verify.call_count == 2
            # Verify NoteCandidate was constructed properly
            first_call = mock_verify.call_args_list[0]
            candidate = first_call.kwargs.get("candidate") or first_call[0][0]
            assert isinstance(candidate, NoteCandidate)


class TestAcceptedNote:
    """Test that accepted notes are created normally."""

    @pytest.mark.asyncio
    async def test_accepted_note_is_created(
        self, service, user_id, family_id,
    ):
        memories = [_make_memory()]
        extracted = [
            {
                "category": "preference",
                "title": "Aisle seat",
                "content": "User prefers aisle seats on flights",
                "confidence": 0.9,
                "trigger_keywords": ["flight"],
            }
        ]

        created_note = MagicMock(spec=SecretaryNote)
        created_note.id = uuid4()

        with patch.object(service, "_get_relevant_memories", return_value=memories), \
             patch.object(service, "_extract_notes_via_llm", return_value=extracted), \
             patch.object(service, "_get_existing_notes", return_value=[]), \
             patch.object(service, "_create_note_if_new", return_value=created_note) as mock_create, \
             patch.object(
                 FactVerificationGate,
                 "verify",
                 return_value=VerificationResult(
                     action=VerificationAction.ACCEPT,
                     reason="High confidence with evidence",
                 ),
             ):
            result = await service.generate_notes_from_memories(user_id, family_id)

            assert len(result) == 1
            mock_create.assert_called_once()


class TestRejectedNote:
    """Test that rejected notes are NOT created."""

    @pytest.mark.asyncio
    async def test_rejected_note_is_not_created(
        self, service, user_id, family_id,
    ):
        memories = [_make_memory()]
        extracted = [
            {
                "category": "preference",
                "title": "Low confidence guess",
                "content": "User might prefer something",
                "confidence": 0.4,
                "trigger_keywords": [],
            }
        ]

        with patch.object(service, "_get_relevant_memories", return_value=memories), \
             patch.object(service, "_extract_notes_via_llm", return_value=extracted), \
             patch.object(service, "_get_existing_notes", return_value=[]), \
             patch.object(service, "_create_note_if_new") as mock_create, \
             patch.object(
                 FactVerificationGate,
                 "verify",
                 return_value=VerificationResult(
                     action=VerificationAction.REJECT,
                     reason="Confidence below threshold",
                 ),
             ):
            result = await service.generate_notes_from_memories(user_id, family_id)

            assert len(result) == 0
            mock_create.assert_not_called()


class TestPendingNote:
    """Test that pending notes have reduced confidence."""

    @pytest.mark.asyncio
    async def test_pending_note_has_reduced_confidence(
        self, service, user_id, family_id,
    ):
        memories = [_make_memory()]
        extracted = [
            {
                "category": "important",
                "title": "Health note",
                "content": "User has diabetes",
                "confidence": 0.8,
                "trigger_keywords": ["health"],
            }
        ]

        created_note = MagicMock(spec=SecretaryNote)
        created_note.id = uuid4()

        captured_note_data = {}

        async def capture_create(uid, fid, note_data, mems):
            captured_note_data.update(note_data)
            return created_note

        with patch.object(service, "_get_relevant_memories", return_value=memories), \
             patch.object(service, "_extract_notes_via_llm", return_value=extracted), \
             patch.object(service, "_get_existing_notes", return_value=[]), \
             patch.object(service, "_create_note_if_new", side_effect=capture_create), \
             patch.object(
                 FactVerificationGate,
                 "verify",
                 return_value=VerificationResult(
                     action=VerificationAction.PENDING,
                     reason="High-risk category",
                 ),
             ):
            result = await service.generate_notes_from_memories(user_id, family_id)

            assert len(result) == 1
            # Confidence should be reduced (0.8 * 0.7 = 0.56, capped at 0.6)
            assert captured_note_data["confidence"] <= 0.6
            assert captured_note_data["is_user_confirmed"] is False


class TestContradictionFlags:
    """Test that contradiction flags are set on both notes."""

    @pytest.mark.asyncio
    async def test_contradiction_flags_both_notes(
        self, service, user_id, family_id,
    ):
        memories = [_make_memory()]

        existing_note = _make_existing_note(
            title="Prefers aisle seats",
            category=NoteCategory.PREFERENCE.value,
        )
        # Reset the mock's add_contradiction to track calls
        existing_note.add_contradiction = MagicMock()

        extracted = [
            {
                "category": "preference",
                "title": "Window seats",
                "content": "User prefers window seats",
                "confidence": 0.75,
                "trigger_keywords": ["seat"],
            }
        ]

        created_note = MagicMock(spec=SecretaryNote)
        created_note.id = uuid4()
        created_note.add_contradiction = MagicMock()

        conflict_msg = f"Overlaps with existing note: '{existing_note.title}' (overlap=45%)"

        with patch.object(service, "_get_relevant_memories", return_value=memories), \
             patch.object(service, "_extract_notes_via_llm", return_value=extracted), \
             patch.object(service, "_get_existing_notes", return_value=[existing_note]), \
             patch.object(service, "_create_note_if_new", return_value=created_note), \
             patch.object(
                 FactVerificationGate,
                 "verify",
                 return_value=VerificationResult(
                     action=VerificationAction.PENDING,
                     reason="Contradicts existing notes",
                     conflicts=[conflict_msg],
                 ),
             ):
            result = await service.generate_notes_from_memories(user_id, family_id)

            assert len(result) == 1
            # The new note should have contradiction flagged
            created_note.add_contradiction.assert_called_once_with(existing_note.id)
            # The existing note should also be flagged
            existing_note.add_contradiction.assert_called_once_with(created_note.id)


class TestGateWithNoMemories:
    """Test that when no memories exist, the gate is never called."""

    @pytest.mark.asyncio
    async def test_no_memories_skips_gate(
        self, service, user_id, family_id,
    ):
        with patch.object(service, "_get_relevant_memories", return_value=[]), \
             patch.object(
                 FactVerificationGate, "verify",
             ) as mock_verify:
            result = await service.generate_notes_from_memories(user_id, family_id)

            assert len(result) == 0
            mock_verify.assert_not_called()
