"""Tests for SecretaryNote new fields: provenance, version, superseded_by, contradiction_flags."""

from uuid import uuid4

import pytest

from src.modules.memory.secretary_note_model import (
    NoteCategory,
    NoteLifeType,
    NoteStatus,
    SecretaryNote,
)


@pytest.fixture
def sample_note() -> SecretaryNote:
    """Create a sample SecretaryNote for testing."""
    return SecretaryNote(
        id=uuid4(),
        user_id=uuid4(),
        family_id=uuid4(),
        category=NoteCategory.PREFERENCE.value,
        title="Prefers aisle seats",
        content="User always prefers aisle seats on flights",
        confidence=0.9,
        is_user_confirmed=False,
        source_memory_ids=[],
        observation_count=1,
        priority=5,
        status=NoteStatus.ACTIVE.value,
        life_type=NoteLifeType.PERMANENT.value,
        valid_until=None,
        trigger_keywords=["flight", "seat"],
        trigger_contexts={},
        provenance=[],
        version=1,
        superseded_by=None,
        contradiction_flags=[],
    )


class TestNewFieldsExist:
    """Test that new fields are present on the model."""

    def test_provenance_field_exists(self, sample_note: SecretaryNote) -> None:
        assert hasattr(sample_note, "provenance")
        assert sample_note.provenance == []

    def test_version_field_exists(self, sample_note: SecretaryNote) -> None:
        assert hasattr(sample_note, "version")
        assert sample_note.version == 1

    def test_superseded_by_field_exists(self, sample_note: SecretaryNote) -> None:
        assert hasattr(sample_note, "superseded_by")
        assert sample_note.superseded_by is None

    def test_contradiction_flags_field_exists(self, sample_note: SecretaryNote) -> None:
        assert hasattr(sample_note, "contradiction_flags")
        assert sample_note.contradiction_flags == []


class TestToDict:
    """Test that to_dict() includes the new fields."""

    def test_to_dict_includes_provenance(self, sample_note: SecretaryNote) -> None:
        d = sample_note.to_dict()
        assert "provenance" in d
        assert d["provenance"] == []

    def test_to_dict_includes_version(self, sample_note: SecretaryNote) -> None:
        d = sample_note.to_dict()
        assert "version" in d
        assert d["version"] == 1

    def test_to_dict_includes_superseded_by_none(self, sample_note: SecretaryNote) -> None:
        d = sample_note.to_dict()
        assert "superseded_by" in d
        assert d["superseded_by"] is None

    def test_to_dict_includes_superseded_by_uuid(self, sample_note: SecretaryNote) -> None:
        new_id = uuid4()
        sample_note.superseded_by = new_id
        d = sample_note.to_dict()
        assert d["superseded_by"] == str(new_id)

    def test_to_dict_includes_contradiction_flags(self, sample_note: SecretaryNote) -> None:
        d = sample_note.to_dict()
        assert "contradiction_flags" in d
        assert d["contradiction_flags"] == []

    def test_to_dict_with_populated_provenance(self, sample_note: SecretaryNote) -> None:
        sample_note.provenance = [
            {"source": "conversation", "memory_id": str(uuid4()), "confidence": 0.85}
        ]
        d = sample_note.to_dict()
        assert len(d["provenance"]) == 1
        assert d["provenance"][0]["source"] == "conversation"


class TestSupersedeHelper:
    """Test the supersede() helper method."""

    def test_supersede_sets_superseded_by(self, sample_note: SecretaryNote) -> None:
        new_id = uuid4()
        sample_note.supersede(new_id)
        assert sample_note.superseded_by == new_id

    def test_supersede_sets_status_superseded(self, sample_note: SecretaryNote) -> None:
        new_id = uuid4()
        sample_note.supersede(new_id)
        assert sample_note.status == NoteStatus.SUPERSEDED.value

    def test_supersede_updates_timestamp(self, sample_note: SecretaryNote) -> None:
        original_updated = sample_note.updated_at
        new_id = uuid4()
        sample_note.supersede(new_id)
        # updated_at should be set (it was None before or different now)
        assert sample_note.updated_at is not None


class TestAddContradictionHelper:
    """Test the add_contradiction() helper method."""

    def test_add_contradiction_appends_flag(self, sample_note: SecretaryNote) -> None:
        conflicting_id = uuid4()
        sample_note.add_contradiction(conflicting_id, "content")
        assert len(sample_note.contradiction_flags) == 1
        flag = sample_note.contradiction_flags[0]
        assert flag["conflicting_note_id"] == str(conflicting_id)
        assert flag["field"] == "content"
        assert "detected_at" in flag

    def test_add_contradiction_immutable_append(self, sample_note: SecretaryNote) -> None:
        """Verify add_contradiction creates a new list (immutable pattern)."""
        sample_note.contradiction_flags = [{"existing": True}]
        original_list = sample_note.contradiction_flags
        conflicting_id = uuid4()
        sample_note.add_contradiction(conflicting_id)
        # Should be a new list object (immutable append via spread)
        assert sample_note.contradiction_flags is not original_list
        assert len(sample_note.contradiction_flags) == 2

    def test_add_contradiction_default_field(self, sample_note: SecretaryNote) -> None:
        conflicting_id = uuid4()
        sample_note.add_contradiction(conflicting_id)
        assert sample_note.contradiction_flags[0]["field"] == "content"

    def test_add_contradiction_handles_none_flags(self, sample_note: SecretaryNote) -> None:
        sample_note.contradiction_flags = None
        conflicting_id = uuid4()
        sample_note.add_contradiction(conflicting_id)
        assert len(sample_note.contradiction_flags) == 1

    def test_add_contradiction_updates_timestamp(self, sample_note: SecretaryNote) -> None:
        conflicting_id = uuid4()
        sample_note.add_contradiction(conflicting_id)
        assert sample_note.updated_at is not None


class TestIncrementVersionHelper:
    """Test the increment_version() helper method."""

    def test_increment_from_default(self, sample_note: SecretaryNote) -> None:
        assert sample_note.version == 1
        sample_note.increment_version()
        assert sample_note.version == 2

    def test_increment_multiple_times(self, sample_note: SecretaryNote) -> None:
        sample_note.increment_version()
        sample_note.increment_version()
        sample_note.increment_version()
        assert sample_note.version == 4

    def test_increment_handles_none_version(self, sample_note: SecretaryNote) -> None:
        sample_note.version = None
        sample_note.increment_version()
        assert sample_note.version == 2

    def test_increment_updates_timestamp(self, sample_note: SecretaryNote) -> None:
        sample_note.increment_version()
        assert sample_note.updated_at is not None
