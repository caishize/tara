"""Tests for commitment_items and exclusion_rules persistence.

Covers:
- CommitmentItemRecord CRUD and helper methods
- ExclusionRule CRUD and active-entity queries
- CommitmentRepository operations
- ExclusionRepository operations
- Integration with CommitmentPreFilter and ExclusionFilter
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.memory.commitment_models import CommitmentItemRecord
from src.modules.curation.models import ExclusionRule
from src.modules.memory.commitment_service import (
    CommitmentItem,
    CommitmentPreFilter,
    CommitmentStatus,
    CommitmentType,
    SocialIntentParser,
    SocialIntentType,
    VagueCommitmentTracker,
)


# ---------------------------------------------------------------------------
# Helper: fixed UTC time
# ---------------------------------------------------------------------------

def _utc_now():
    return datetime.now(timezone.utc)


def _past(days: int):
    return _utc_now() - timedelta(days=days)


def _future(days: int):
    return _utc_now() + timedelta(days=days)


# ===========================================================================
# CommitmentItemRecord model tests
# ===========================================================================


class TestCommitmentItemRecordModel:
    """Tests for the CommitmentItemRecord ORM model (unit-level)."""

    def test_default_values(self) -> None:
        """SQLAlchemy Column defaults apply on flush, not on construction.
        We verify nullable fields are None and explicit defaults are correct."""
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="Alice",
            what="Send report",
            to_whom="Bob",
            status="pending",
            follow_up_count=0,
            tracking_score=0.5,
        )
        assert record.status == "pending"
        assert record.follow_up_count == 0
        assert record.tracking_score == 0.5
        assert record.deadline is None
        assert record.social_intent is None
        assert record.next_follow_up_at is None

    def test_to_dict_keys(self) -> None:
        uid = uuid4()
        fid = uuid4()
        record = CommitmentItemRecord(
            id=uuid4(),
            user_id=uid,
            family_id=fid,
            commitment_type="vague",
            who="Charlie",
            what="Meet sometime",
            to_whom="Dave",
            status="pending",
            social_intent="social_courtesy",
            tracking_score=0.3,
        )
        d = record.to_dict()
        assert d["user_id"] == str(uid)
        assert d["family_id"] == str(fid)
        assert d["commitment_type"] == "vague"
        assert d["who"] == "Charlie"
        assert d["what"] == "Meet sometime"
        assert d["to_whom"] == "Dave"
        assert d["social_intent"] == "social_courtesy"
        assert d["tracking_score"] == 0.3
        assert d["status"] == "pending"
        assert "deadline" in d
        assert "next_follow_up_at" in d
        assert "created_at" in d
        assert "updated_at" in d

    def test_to_dict_with_deadline(self) -> None:
        dl = _utc_now()
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="A",
            what="B",
            to_whom="C",
            deadline=dl,
        )
        d = record.to_dict()
        assert d["deadline"] == dl.isoformat()

    def test_record_follow_up(self) -> None:
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="A",
            what="B",
            to_whom="C",
            follow_up_count=2,
        )
        record.record_follow_up()
        assert record.follow_up_count == 3

    def test_record_follow_up_from_none(self) -> None:
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="A",
            what="B",
            to_whom="C",
        )
        record.follow_up_count = None
        record.record_follow_up()
        assert record.follow_up_count == 1


# ===========================================================================
# ExclusionRule model tests
# ===========================================================================


class TestExclusionRuleModel:
    """Tests for the ExclusionRule ORM model (unit-level)."""

    def test_to_dict_keys(self) -> None:
        uid = uuid4()
        fid = uuid4()
        rule = ExclusionRule(
            id=uuid4(),
            user_id=uid,
            family_id=fid,
            entity_type="member",
            entity_id=str(uuid4()),
            reason="User dismissed",
        )
        d = rule.to_dict()
        assert d["user_id"] == str(uid)
        assert d["family_id"] == str(fid)
        assert d["entity_type"] == "member"
        assert d["reason"] == "User dismissed"
        assert "cooldown_until" in d
        assert "created_at" in d

    def test_not_expired_no_cooldown(self) -> None:
        rule = ExclusionRule(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="event",
            entity_id=str(uuid4()),
        )
        assert rule.is_expired is False

    def test_not_expired_future_cooldown(self) -> None:
        rule = ExclusionRule(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="event",
            entity_id=str(uuid4()),
            cooldown_until=_future(3),
        )
        assert rule.is_expired is False

    def test_expired_past_cooldown(self) -> None:
        rule = ExclusionRule(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="event",
            entity_id=str(uuid4()),
            cooldown_until=_past(1),
        )
        assert rule.is_expired is True

    def test_to_dict_with_cooldown(self) -> None:
        cd = _future(5)
        rule = ExclusionRule(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="insight",
            entity_id=str(uuid4()),
            cooldown_until=cd,
        )
        d = rule.to_dict()
        assert d["cooldown_until"] == cd.isoformat()


# ===========================================================================
# CommitmentRepository tests (mocked DB)
# ===========================================================================


class TestCommitmentRepository:
    """Tests for CommitmentRepository with mocked AsyncSession."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def repo(self, mock_db):
        from src.modules.memory.commitment_repository import CommitmentRepository
        return CommitmentRepository(mock_db)

    @pytest.mark.asyncio
    async def test_create_calls_add_and_flush(self, repo, mock_db) -> None:
        record = await repo.create(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="Alice",
            what="Send report by Friday",
            to_whom="Bob",
            social_intent="genuine",
            tracking_score=0.85,
        )
        mock_db.add.assert_called_once()
        mock_db.flush.assert_awaited_once()
        assert isinstance(record, CommitmentItemRecord)
        assert record.commitment_type == "firm"
        assert record.who == "Alice"
        assert record.social_intent == "genuine"

    @pytest.mark.asyncio
    async def test_create_with_deadline(self, repo, mock_db) -> None:
        dl = _future(2)
        record = await repo.create(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="conditional",
            who="X",
            what="Y",
            to_whom="Z",
            deadline=dl,
        )
        assert record.deadline == dl

    @pytest.mark.asyncio
    async def test_get_by_id_returns_none_when_missing(self, repo, mock_db) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(uuid4())
        assert result is None

    @pytest.mark.asyncio
    async def test_get_by_id_returns_record(self, repo, mock_db) -> None:
        expected = CommitmentItemRecord(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="A",
            what="B",
            to_whom="C",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = expected
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_by_id(expected.id)
        assert result is expected

    @pytest.mark.asyncio
    async def test_update_status(self, repo, mock_db) -> None:
        existing = CommitmentItemRecord(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="A",
            what="B",
            to_whom="C",
            status="pending",
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_status(existing.id, "fulfilled")
        assert result is not None
        assert result.status == "fulfilled"

    @pytest.mark.asyncio
    async def test_update_status_missing_returns_none(self, repo, mock_db) -> None:
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await repo.update_status(uuid4(), "fulfilled")
        assert result is None

    @pytest.mark.asyncio
    async def test_record_follow_up(self, repo, mock_db) -> None:
        existing = CommitmentItemRecord(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="vague",
            who="A",
            what="B",
            to_whom="C",
            follow_up_count=1,
        )
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing
        mock_db.execute = AsyncMock(return_value=mock_result)

        next_fu = _future(3)
        result = await repo.record_follow_up(existing.id, next_follow_up_at=next_fu)
        assert result is not None
        assert result.follow_up_count == 2
        assert result.next_follow_up_at == next_fu


# ===========================================================================
# ExclusionRepository tests (mocked DB)
# ===========================================================================


class TestExclusionRepository:
    """Tests for ExclusionRepository with mocked AsyncSession."""

    @pytest.fixture
    def mock_db(self):
        db = AsyncMock()
        db.add = MagicMock()
        db.flush = AsyncMock()
        return db

    @pytest.fixture
    def repo(self, mock_db):
        from src.ai_engine.exclusion_repository import ExclusionRepository
        return ExclusionRepository(mock_db)

    @pytest.mark.asyncio
    async def test_create_calls_add_and_flush(self, repo, mock_db) -> None:
        rule = await repo.create(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="member",
            entity_id=str(uuid4()),
            reason="User dismissed",
        )
        # add() is called for the rule and again for the audit log entry
        assert mock_db.add.call_count == 2
        assert mock_db.flush.await_count >= 1
        assert isinstance(rule, ExclusionRule)
        assert rule.entity_type == "member"

    @pytest.mark.asyncio
    async def test_create_with_cooldown(self, repo, mock_db) -> None:
        cd = _future(7)
        rule = await repo.create(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="insight",
            entity_id=str(uuid4()),
            cooldown_until=cd,
        )
        assert rule.cooldown_until == cd

    @pytest.mark.asyncio
    async def test_get_active_entity_ids(self, repo, mock_db) -> None:
        eid1 = str(uuid4())
        eid2 = str(uuid4())
        mock_result = MagicMock()
        mock_result.all.return_value = [(eid1,), (eid2,)]
        mock_db.execute = AsyncMock(return_value=mock_result)

        uid = uuid4()
        fid = uuid4()
        result = await repo.get_active_entity_ids(uid, fid)
        assert result == {eid1, eid2}
        mock_db.execute.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_get_active_entity_ids_empty(self, repo, mock_db) -> None:
        mock_result = MagicMock()
        mock_result.all.return_value = []
        mock_db.execute = AsyncMock(return_value=mock_result)

        result = await repo.get_active_entity_ids(uuid4(), uuid4())
        assert result == set()

    @pytest.mark.asyncio
    async def test_delete_rule_found(self, repo, mock_db) -> None:
        existing = ExclusionRule(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="member",
            entity_id=str(uuid4()),
        )
        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = existing
        delete_result = MagicMock()
        delete_result.rowcount = 1
        # First call: select for audit lookup, second: delete statement
        mock_db.execute = AsyncMock(side_effect=[select_result, delete_result])

        deleted = await repo.delete_rule(existing.id)
        assert deleted is True

    @pytest.mark.asyncio
    async def test_delete_rule_not_found(self, repo, mock_db) -> None:
        select_result = MagicMock()
        select_result.scalar_one_or_none.return_value = None
        delete_result = MagicMock()
        delete_result.rowcount = 0
        mock_db.execute = AsyncMock(side_effect=[select_result, delete_result])

        deleted = await repo.delete_rule(uuid4())
        assert deleted is False

    @pytest.mark.asyncio
    async def test_delete_for_entity(self, repo, mock_db) -> None:
        delete_result = MagicMock()
        delete_result.rowcount = 3
        mock_db.execute = AsyncMock(return_value=delete_result)

        count = await repo.delete_for_entity(uuid4(), uuid4(), str(uuid4()))
        assert count == 3


# ===========================================================================
# Integration: VagueCommitmentTracker with persisted dicts
# ===========================================================================


class TestVagueCommitmentTrackerWithPersistence:
    """Verify VagueCommitmentTracker works with to_dict() output from records."""

    def test_tracker_processes_record_dicts(self) -> None:
        tracker = VagueCommitmentTracker()
        now = _utc_now()

        record = CommitmentItemRecord(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="vague",
            who="Alice",
            what="Meet sometime",
            to_whom="Bob",
            status="pending",
            follow_up_count=0,
            created_at=now - timedelta(days=5),
            updated_at=now - timedelta(days=5),
        )
        d = record.to_dict()
        # VagueCommitmentTracker.check_and_follow_up expects list of dicts
        due = tracker.check_and_follow_up([d])
        # Vague commitments have 3-day threshold, 5 days ago -> should be due
        assert len(due) == 1

    def test_tracker_skips_recent_record(self) -> None:
        tracker = VagueCommitmentTracker()
        now = _utc_now()

        record = CommitmentItemRecord(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="vague",
            who="Alice",
            what="Meet sometime",
            to_whom="Bob",
            status="pending",
            follow_up_count=0,
            created_at=now - timedelta(hours=1),
            updated_at=now - timedelta(hours=1),
        )
        d = record.to_dict()
        due = tracker.check_and_follow_up([d])
        # Created 1 hour ago, vague threshold is 3 days -> not due
        assert len(due) == 0

    def test_tracker_skips_fulfilled_record(self) -> None:
        tracker = VagueCommitmentTracker()
        now = _utc_now()

        record = CommitmentItemRecord(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="A",
            what="B",
            to_whom="C",
            status="fulfilled",
            follow_up_count=0,
            created_at=now - timedelta(days=10),
            updated_at=now - timedelta(days=10),
        )
        d = record.to_dict()
        due = tracker.check_and_follow_up([d])
        assert len(due) == 0


# ===========================================================================
# Integration: CommitmentPreFilter with in-memory items
# ===========================================================================


class TestCommitmentPreFilterIntegration:
    """Verify filter_commitments returns items compatible with persistence."""

    def test_genuine_commitment_kept(self) -> None:
        pf = CommitmentPreFilter()
        item = CommitmentItem(
            id=uuid4(),
            commitment_type=CommitmentType.FIRM,
            who_promised="Alice",
            what_promised="周三给你报价",
            to_whom="Bob",
        )
        result = pf.filter_commitments([item])
        assert len(result) == 1
        assert result[0].who_promised == "Alice"

    def test_courtesy_commitment_excluded(self) -> None:
        pf = CommitmentPreFilter()
        item = CommitmentItem(
            id=uuid4(),
            commitment_type=CommitmentType.VAGUE,
            who_promised="Alice",
            what_promised="改天一起吃饭",
            to_whom="Bob",
        )
        result = pf.filter_commitments([item])
        assert len(result) == 0

    def test_obligation_commitment_extended(self) -> None:
        pf = CommitmentPreFilter()
        item = CommitmentItem(
            id=uuid4(),
            commitment_type=CommitmentType.FIRM,
            who_promised="Alice",
            what_promised="我答应了明天给你",
            to_whom="Bob",
            suggested_follow_up="Check in tomorrow",
        )
        result = pf.filter_commitments([item])
        assert len(result) == 1
        assert "extended" in (result[0].suggested_follow_up or "")


# ===========================================================================
# ExclusionRule + ExclusionFilter integration
# ===========================================================================


class TestExclusionFilterWithPersistedRules:
    """Verify ExclusionFilter.apply() works with persisted entity IDs."""

    def test_dismissed_entity_excluded(self) -> None:
        """Simulates passing persisted exclusion entity_ids to ExclusionFilter."""
        from src.ai_engine.context_assembler import ContextItem
        from src.ai_engine.context_filters import ExclusionFilter

        eid = str(uuid4())
        item = ContextItem(
            layer="l2",
            source="insight",
            content="Some insight about member",
            entity_ids=(eid,),
        )
        # Simulate what ExclusionRepository.get_active_entity_ids returns
        dismissed_ids = {eid}

        kept, filtered = ExclusionFilter.apply(
            items=[item],
            resolved_entity_ids=set(),
            dismissed_entity_ids=dismissed_ids,
        )
        assert filtered == 1
        assert len(kept) == 0

    def test_l2_override_allows_dismissed(self) -> None:
        """If user mentions the dismissed entity, exclusion is overridden."""
        from src.ai_engine.context_assembler import ContextItem
        from src.ai_engine.context_filters import ExclusionFilter

        eid = uuid4()
        item = ContextItem(
            layer="l2",
            source="insight",
            content="Some insight",
            entity_ids=(str(eid),),
        )
        dismissed_ids = {str(eid)}

        kept, filtered = ExclusionFilter.apply(
            items=[item],
            resolved_entity_ids={eid},  # user mentioned the entity
            dismissed_entity_ids=dismissed_ids,
        )
        assert filtered == 0
        assert len(kept) == 1

    def test_non_dismissed_entity_passes(self) -> None:
        from src.ai_engine.context_assembler import ContextItem
        from src.ai_engine.context_filters import ExclusionFilter

        eid = str(uuid4())
        other_eid = str(uuid4())
        item = ContextItem(
            layer="l2",
            source="memory",
            content="Info",
            entity_ids=(eid,),
        )
        dismissed_ids = {other_eid}  # different entity

        kept, filtered = ExclusionFilter.apply(
            items=[item],
            resolved_entity_ids=set(),
            dismissed_entity_ids=dismissed_ids,
        )
        assert filtered == 0
        assert len(kept) == 1
