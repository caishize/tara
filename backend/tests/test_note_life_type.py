"""Tests for NoteLifeType classification and TransientFactManager."""

from datetime import timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.memory.secretary_note_model import (
    NoteCategory,
    NoteLifeType,
    NoteStatus,
    SecretaryNote,
)
from src.modules.memory.secretary_note_service import (
    SecretaryNoteService,
    TransientFactManager,
    TRANSIENT_SIGNALS,
    TRANSIENT_DEFAULT_DAYS,
)


# ---------------------------------------------------------------------------
# NoteLifeType enum basics
# ---------------------------------------------------------------------------


class TestNoteLifeType:
    def test_enum_values(self):
        assert NoteLifeType.PERMANENT.value == "permanent"
        assert NoteLifeType.TRANSIENT.value == "transient"

    def test_is_str_enum(self):
        assert isinstance(NoteLifeType.PERMANENT, str)
        assert NoteLifeType.PERMANENT == "permanent"


# ---------------------------------------------------------------------------
# classify_life_type — Chinese transient signal detection
# ---------------------------------------------------------------------------


class TestClassifyLifeType:
    def test_permanent_by_default(self):
        life_type, valid_until = SecretaryNoteService.classify_life_type(
            "用户喜欢靠窗的座位"
        )
        assert life_type == NoteLifeType.PERMANENT
        assert valid_until is None

    @pytest.mark.parametrize("signal", TRANSIENT_SIGNALS)
    def test_transient_for_each_signal(self, signal):
        content = f"用户{signal}在节食"
        life_type, valid_until = SecretaryNoteService.classify_life_type(content)
        assert life_type == NoteLifeType.TRANSIENT
        assert valid_until is not None

    def test_transient_valid_until_is_future(self):
        from src.core.utils.timezone import utc_now

        life_type, valid_until = SecretaryNoteService.classify_life_type(
            "最近在减肥"
        )
        assert life_type == NoteLifeType.TRANSIENT
        now = utc_now()
        assert valid_until > now
        # Should be approximately TRANSIENT_DEFAULT_DAYS from now
        diff = (valid_until - now).days
        assert TRANSIENT_DEFAULT_DAYS - 1 <= diff <= TRANSIENT_DEFAULT_DAYS + 1

    def test_empty_content_is_permanent(self):
        life_type, valid_until = SecretaryNoteService.classify_life_type("")
        assert life_type == NoteLifeType.PERMANENT
        assert valid_until is None

    def test_english_content_is_permanent(self):
        life_type, valid_until = SecretaryNoteService.classify_life_type(
            "User prefers aisle seats"
        )
        assert life_type == NoteLifeType.PERMANENT
        assert valid_until is None


# ---------------------------------------------------------------------------
# SecretaryNote model — is_expired
# ---------------------------------------------------------------------------


class TestSecretaryNoteIsExpired:
    def _make_note(self, life_type, valid_until):
        note = MagicMock(spec=SecretaryNote)
        note.life_type = life_type
        note.valid_until = valid_until
        # Bind the real is_expired method to the mock
        note.is_expired = lambda: SecretaryNote.is_expired(note)
        return note

    def test_permanent_never_expires(self):
        note = self._make_note(NoteLifeType.PERMANENT.value, None)
        assert note.is_expired() is False

    def test_transient_not_expired_yet(self):
        from src.core.utils.timezone import utc_now

        future = utc_now() + timedelta(days=10)
        note = self._make_note(NoteLifeType.TRANSIENT.value, future)
        assert note.is_expired() is False

    def test_transient_expired(self):
        from src.core.utils.timezone import utc_now

        past = utc_now() - timedelta(days=1)
        note = self._make_note(NoteLifeType.TRANSIENT.value, past)
        assert note.is_expired() is True

    def test_transient_no_valid_until(self):
        note = self._make_note(NoteLifeType.TRANSIENT.value, None)
        assert note.is_expired() is False


# ---------------------------------------------------------------------------
# TransientFactManager
# ---------------------------------------------------------------------------


class TestTransientFactManager:
    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.execute = AsyncMock()
        db.commit = AsyncMock()
        return db

    @pytest.mark.asyncio
    async def test_process_expiring_facts_no_expired(self, mock_db):
        # Setup: no expired notes found
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = []
        mock_db.execute.return_value = mock_result

        manager = TransientFactManager(mock_db)
        result = await manager.process_expiring_facts(uuid4())

        assert result["archived"] == 0
        assert result["restored"] == 0

    @pytest.mark.asyncio
    async def test_process_expiring_facts_archives_expired(self, mock_db):
        from src.core.utils.timezone import utc_now

        user_id = uuid4()

        # Create a mock expired note
        expired_note = MagicMock(spec=SecretaryNote)
        expired_note.user_id = user_id
        expired_note.status = NoteStatus.ACTIVE.value
        expired_note.life_type = NoteLifeType.TRANSIENT.value
        expired_note.valid_until = utc_now() - timedelta(days=1)
        expired_note.category = NoteCategory.PREFERENCE.value
        expired_note.title = "最近在减肥"

        # First call returns expired notes, second call (restore check) returns None
        mock_result_expired = MagicMock()
        mock_result_expired.scalars.return_value.all.return_value = [expired_note]

        mock_result_restore = MagicMock()
        mock_result_restore.scalar_one_or_none.return_value = None

        mock_db.execute.side_effect = [mock_result_expired, mock_result_restore]

        manager = TransientFactManager(mock_db)
        result = await manager.process_expiring_facts(user_id)

        assert result["archived"] == 1
        assert result["restored"] == 0
        assert expired_note.status == NoteStatus.ARCHIVED.value

    @pytest.mark.asyncio
    async def test_process_expiring_facts_restores_permanent(self, mock_db):
        from src.core.utils.timezone import utc_now

        user_id = uuid4()

        # Create a mock expired transient note
        expired_note = MagicMock(spec=SecretaryNote)
        expired_note.user_id = user_id
        expired_note.status = NoteStatus.ACTIVE.value
        expired_note.life_type = NoteLifeType.TRANSIENT.value
        expired_note.valid_until = utc_now() - timedelta(days=1)
        expired_note.category = NoteCategory.PREFERENCE.value
        expired_note.title = "最近在减肥"

        # Create a mock superseded permanent note to restore
        permanent_note = MagicMock(spec=SecretaryNote)
        permanent_note.status = NoteStatus.SUPERSEDED.value
        permanent_note.life_type = NoteLifeType.PERMANENT.value
        permanent_note.title = "最近在减肥"

        mock_result_expired = MagicMock()
        mock_result_expired.scalars.return_value.all.return_value = [expired_note]

        mock_result_restore = MagicMock()
        mock_result_restore.scalar_one_or_none.return_value = permanent_note

        mock_db.execute.side_effect = [mock_result_expired, mock_result_restore]

        manager = TransientFactManager(mock_db)
        result = await manager.process_expiring_facts(user_id)

        assert result["archived"] == 1
        assert result["restored"] == 1
        assert expired_note.status == NoteStatus.ARCHIVED.value
        assert permanent_note.status == NoteStatus.ACTIVE.value


# ---------------------------------------------------------------------------
# Alembic migration structure check
# ---------------------------------------------------------------------------


class TestAlembicMigration088:
    def test_migration_has_upgrade_and_downgrade(self):
        import importlib

        mod = importlib.import_module(
            "src.db.migrations.versions.088_add_note_life_type_valid_until"
        )
        assert hasattr(mod, "upgrade")
        assert hasattr(mod, "downgrade")
        assert callable(mod.upgrade)
        assert callable(mod.downgrade)

    def test_migration_revision_chain(self):
        import importlib

        mod = importlib.import_module(
            "src.db.migrations.versions.088_add_note_life_type_valid_until"
        )
        assert mod.revision == "088"
        assert mod.down_revision == "087"
