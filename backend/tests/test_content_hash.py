"""Tests for content_hash idempotent writes on ConversationMemory.

Tests cover:
- compute_content_hash determinism and uniqueness
- content_hash column exists on model
- to_dict includes content_hash
- Repository idempotent skip via content_hash
"""

from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.memory.models import ConversationMemory, MemoryStatus
from src.modules.memory.repository import MemoryRepository, compute_content_hash


class TestComputeContentHash:
    """Test the compute_content_hash helper function."""

    def test_deterministic(self) -> None:
        h1 = compute_content_hash("hello", "preference", {"key": "val"})
        h2 = compute_content_hash("hello", "preference", {"key": "val"})
        assert h1 == h2

    def test_different_content_different_hash(self) -> None:
        h1 = compute_content_hash("hello", "preference")
        h2 = compute_content_hash("world", "preference")
        assert h1 != h2

    def test_different_type_different_hash(self) -> None:
        h1 = compute_content_hash("hello", "preference")
        h2 = compute_content_hash("hello", "routine")
        assert h1 != h2

    def test_different_entities_different_hash(self) -> None:
        h1 = compute_content_hash("hello", "preference", {"a": 1})
        h2 = compute_content_hash("hello", "preference", {"a": 2})
        assert h1 != h2

    def test_entity_key_order_irrelevant(self) -> None:
        """Sorted JSON means key order does not affect hash."""
        h1 = compute_content_hash("hello", "preference", {"a": 1, "b": 2})
        h2 = compute_content_hash("hello", "preference", {"b": 2, "a": 1})
        assert h1 == h2

    def test_none_entities_same_as_empty(self) -> None:
        h1 = compute_content_hash("hello", "preference", None)
        h2 = compute_content_hash("hello", "preference", {})
        assert h1 == h2

    def test_whitespace_normalized(self) -> None:
        h1 = compute_content_hash("  hello  ", "preference")
        h2 = compute_content_hash("hello", "preference")
        assert h1 == h2

    def test_returns_hex_string(self) -> None:
        h = compute_content_hash("test", "general")
        assert isinstance(h, str)
        assert len(h) == 32  # MD5 hex digest length
        # Only hex characters
        int(h, 16)


class TestContentHashModelField:
    """Test that content_hash field exists on ConversationMemory."""

    def test_field_exists(self) -> None:
        memory = ConversationMemory(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            memory_type="preference",
            content="Test",
            summary="Test summary",
            content_hash="abc123",
        )
        assert memory.content_hash == "abc123"

    def test_field_defaults_to_none(self) -> None:
        memory = ConversationMemory(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            memory_type="preference",
            content="Test",
            summary="Test summary",
        )
        assert memory.content_hash is None

    def test_to_dict_includes_content_hash(self) -> None:
        memory = ConversationMemory(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            memory_type="preference",
            content="Test",
            summary="Test summary",
            content_hash="abc123def456",
        )
        d = memory.to_dict()
        assert "content_hash" in d
        assert d["content_hash"] == "abc123def456"


class TestRepositoryIdempotentWrite:
    """Test that create_memory skips insertion when content_hash matches."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.commit = AsyncMock()
        db.refresh = AsyncMock()
        return db

    @pytest.fixture
    def repo(self, mock_db):
        return MemoryRepository(db=mock_db)

    @pytest.mark.asyncio
    async def test_idempotent_skip_when_hash_exists(self, repo, mock_db) -> None:
        existing = MagicMock(spec=ConversationMemory)
        existing.id = uuid4()
        existing.content_hash = "somehash"

        with patch.object(repo, "_find_by_content_hash", return_value=existing):
            result = await repo.create_memory(
                user_id=uuid4(),
                family_id=uuid4(),
                memory_type="preference",
                content="User prefers aisle seats",
                summary="Aisle seat preference",
            )

            assert result is existing
            mock_db.add.assert_not_called()

    @pytest.mark.asyncio
    async def test_creates_when_no_hash_match(self, repo, mock_db) -> None:
        with patch.object(repo, "_find_by_content_hash", return_value=None), \
             patch.object(repo, "_find_duplicate", return_value=None):
            result = await repo.create_memory(
                user_id=uuid4(),
                family_id=uuid4(),
                memory_type="preference",
                content="User prefers window seats",
                summary="Window seat preference",
            )

            mock_db.add.assert_called_once()
            added_memory = mock_db.add.call_args[0][0]
            assert added_memory.content_hash is not None
            assert len(added_memory.content_hash) == 32

    @pytest.mark.asyncio
    async def test_hash_set_on_created_memory(self, repo, mock_db) -> None:
        with patch.object(repo, "_find_by_content_hash", return_value=None), \
             patch.object(repo, "_find_duplicate", return_value=None):
            await repo.create_memory(
                user_id=uuid4(),
                family_id=uuid4(),
                memory_type="preference",
                content="Likes spicy food",
                summary="Spicy food preference",
                entities={"food": "spicy"},
            )

            added_memory = mock_db.add.call_args[0][0]
            expected_hash = compute_content_hash(
                "Likes spicy food", "preference", {"food": "spicy"}
            )
            assert added_memory.content_hash == expected_hash

    @pytest.mark.asyncio
    async def test_falls_through_to_duplicate_check(self, repo, mock_db) -> None:
        """When no hash match, still falls through to semantic duplicate check."""
        duplicate = MagicMock(spec=ConversationMemory)
        duplicate.id = uuid4()
        duplicate.importance = 5
        duplicate.summary = "Aisle seat preference"

        with patch.object(repo, "_find_by_content_hash", return_value=None), \
             patch.object(repo, "_find_duplicate", return_value=duplicate):
            result = await repo.create_memory(
                user_id=uuid4(),
                family_id=uuid4(),
                memory_type="preference",
                content="User prefers aisle seats",
                summary="Aisle seat preference",
            )

            # Should return the duplicate, not create new
            assert result is duplicate
            assert duplicate.importance == 6
            mock_db.add.assert_not_called()
