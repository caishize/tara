"""Tests for privacy downgrade audit events in MemoryRepository.

V8-AI S8.3: AUDIT_EVENTS must include "privacy_downgrade" when
sensitivity_level is lowered.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

from src.modules.memory.repository import MemoryRepository, _SENSITIVITY_RANK


# ---------------------------------------------------------------------------
# Sensitivity rank ordering
# ---------------------------------------------------------------------------


class TestSensitivityRank:

    def test_ordering(self):
        assert _SENSITIVITY_RANK["public"] < _SENSITIVITY_RANK["family"]
        assert _SENSITIVITY_RANK["family"] < _SENSITIVITY_RANK["private"]
        assert _SENSITIVITY_RANK["private"] < _SENSITIVITY_RANK["sensitive"]

    def test_all_levels_present(self):
        assert set(_SENSITIVITY_RANK.keys()) == {
            "public", "family", "private", "sensitive",
        }


# ---------------------------------------------------------------------------
# Privacy downgrade detection in update_memory
# ---------------------------------------------------------------------------


def _make_memory_stub(
    memory_id=None,
    user_id=None,
    family_id=None,
    sensitivity_level="private",
):
    """Return a lightweight mock that quacks like a ConversationMemory row."""
    mem = MagicMock()
    mem.id = memory_id or uuid4()
    mem.user_id = user_id or uuid4()
    mem.family_id = family_id or uuid4()
    mem.sensitivity_level = sensitivity_level
    return mem


class TestPrivacyDowngradeAudit:

    @pytest.fixture()
    def db(self):
        """Fake async session with execute/commit/refresh as AsyncMocks."""
        session = AsyncMock()
        session.execute = AsyncMock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture()
    def repo(self, db):
        with patch(
            "src.modules.memory.repository.AuditService"
        ) as mock_audit_cls:
            audit_instance = AsyncMock()
            audit_instance.log_event = AsyncMock()
            mock_audit_cls.return_value = audit_instance
            r = MemoryRepository(db)
            r._audit = audit_instance
            return r

    @pytest.mark.asyncio
    async def test_downgrade_logs_audit_event(self, repo, db):
        """Lowering sensitivity from SENSITIVE -> PUBLIC logs privacy_downgrade."""
        memory_id = uuid4()
        mem = _make_memory_stub(
            memory_id=memory_id, sensitivity_level="sensitive",
        )

        # get_memory returns the existing memory before the update
        repo.get_memory = AsyncMock(return_value=mem)

        await repo.update_memory(memory_id, sensitivity_level="public")

        repo._audit.log_event.assert_called_once()
        call_kwargs = repo._audit.log_event.call_args
        assert call_kwargs[1]["event_type"] == "privacy_downgrade"
        assert call_kwargs[1]["event_data"]["old_level"] == "sensitive"
        assert call_kwargs[1]["event_data"]["new_level"] == "public"
        assert call_kwargs[1]["event_data"]["memory_id"] == str(memory_id)

    @pytest.mark.asyncio
    async def test_downgrade_private_to_family(self, repo, db):
        """PRIVATE -> FAMILY is a downgrade and should be logged."""
        memory_id = uuid4()
        mem = _make_memory_stub(
            memory_id=memory_id, sensitivity_level="private",
        )
        repo.get_memory = AsyncMock(return_value=mem)

        await repo.update_memory(memory_id, sensitivity_level="family")

        repo._audit.log_event.assert_called_once()
        data = repo._audit.log_event.call_args[1]["event_data"]
        assert data["old_level"] == "private"
        assert data["new_level"] == "family"

    @pytest.mark.asyncio
    async def test_upgrade_does_not_log(self, repo, db):
        """Raising sensitivity (PUBLIC -> PRIVATE) is NOT a downgrade."""
        memory_id = uuid4()
        mem = _make_memory_stub(
            memory_id=memory_id, sensitivity_level="public",
        )
        repo.get_memory = AsyncMock(return_value=mem)

        await repo.update_memory(memory_id, sensitivity_level="private")

        repo._audit.log_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_same_level_does_not_log(self, repo, db):
        """Unchanged sensitivity_level should not trigger audit."""
        memory_id = uuid4()
        mem = _make_memory_stub(
            memory_id=memory_id, sensitivity_level="family",
        )
        repo.get_memory = AsyncMock(return_value=mem)

        await repo.update_memory(memory_id, sensitivity_level="family")

        repo._audit.log_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_no_sensitivity_change_skips_audit(self, repo, db):
        """update_memory without sensitivity_level should not audit."""
        memory_id = uuid4()
        mem = _make_memory_stub(memory_id=memory_id)
        repo.get_memory = AsyncMock(return_value=mem)

        await repo.update_memory(memory_id, importance=8)

        repo._audit.log_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_memory_not_found_skips_audit(self, repo, db):
        """If the memory doesn't exist, no audit event is logged."""
        memory_id = uuid4()
        repo.get_memory = AsyncMock(return_value=None)

        result = await repo.update_memory(memory_id, sensitivity_level="public")

        repo._audit.log_event.assert_not_called()
        assert result is None
