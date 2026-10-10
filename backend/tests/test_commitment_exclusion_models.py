"""Tests for CommitmentItemRecord and ExclusionRule persistence models."""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.modules.memory.commitment_models import CommitmentItemRecord
from src.modules.curation.models import ExclusionRule


# ---------------------------------------------------------------------------
# CommitmentItemRecord
# ---------------------------------------------------------------------------


class TestCommitmentItemRecord:
    """Test CommitmentItemRecord model."""

    def test_create_basic(self):
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="张三",
            what="周三给报价",
            to_whom="李四",
            status="pending",
        )
        assert record.commitment_type == "firm"
        assert record.who == "张三"
        assert record.what == "周三给报价"
        assert record.to_whom == "李四"
        assert record.status == "pending"

    def test_default_tracking_score(self):
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="vague",
            who="me",
            what="some day",
            to_whom="you",
            tracking_score=0.5,
        )
        assert record.tracking_score == 0.5

    def test_default_follow_up_count(self):
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="vague",
            who="me",
            what="something",
            to_whom="you",
            follow_up_count=0,
        )
        assert record.follow_up_count == 0

    def test_to_dict(self):
        uid = uuid4()
        fid = uuid4()
        record = CommitmentItemRecord(
            id=uuid4(),
            user_id=uid,
            family_id=fid,
            commitment_type="conditional",
            who="Alice",
            what="Start project if approved",
            to_whom="Bob",
            social_intent="genuine",
            status="pending",
        )
        d = record.to_dict()
        assert d["commitment_type"] == "conditional"
        assert d["who"] == "Alice"
        assert d["what"] == "Start project if approved"
        assert d["to_whom"] == "Bob"
        assert d["social_intent"] == "genuine"
        assert d["user_id"] == str(uid)
        assert d["family_id"] == str(fid)

    def test_to_dict_with_deadline(self):
        now = datetime.now(timezone.utc)
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="a",
            what="b",
            to_whom="c",
            deadline=now,
        )
        d = record.to_dict()
        assert d["deadline"] is not None
        assert now.isoformat() in d["deadline"]

    def test_to_dict_without_deadline(self):
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="firm",
            who="a",
            what="b",
            to_whom="c",
        )
        d = record.to_dict()
        assert d["deadline"] is None

    def test_record_follow_up(self):
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="vague",
            who="me",
            what="something",
            to_whom="you",
            follow_up_count=0,
        )
        record.record_follow_up()
        assert record.follow_up_count == 1
        record.record_follow_up()
        assert record.follow_up_count == 2

    def test_record_follow_up_from_none(self):
        record = CommitmentItemRecord(
            user_id=uuid4(),
            family_id=uuid4(),
            commitment_type="vague",
            who="me",
            what="something",
            to_whom="you",
        )
        record.follow_up_count = None
        record.record_follow_up()
        assert record.follow_up_count == 1

    def test_tablename(self):
        assert CommitmentItemRecord.__tablename__ == "commitment_items"

    def test_all_commitment_types(self):
        """Verify all expected commitment types can be stored."""
        for ct in ["firm", "vague", "conditional", "delegated"]:
            record = CommitmentItemRecord(
                user_id=uuid4(),
                family_id=uuid4(),
                commitment_type=ct,
                who="x",
                what="y",
                to_whom="z",
            )
            assert record.commitment_type == ct


# ---------------------------------------------------------------------------
# ExclusionRule
# ---------------------------------------------------------------------------


class TestExclusionRule:
    """Test ExclusionRule model."""

    def test_create_basic(self):
        rule = ExclusionRule(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="memory",
            entity_id=str(uuid4()),
        )
        assert rule.entity_type == "memory"
        assert rule.reason is None
        assert rule.cooldown_until is None

    def test_create_with_reason(self):
        rule = ExclusionRule(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="member",
            entity_id=str(uuid4()),
            reason="User dismissed this memory",
        )
        assert rule.reason == "User dismissed this memory"

    def test_create_with_cooldown(self):
        future = datetime.now(timezone.utc) + timedelta(days=7)
        rule = ExclusionRule(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="event",
            entity_id=str(uuid4()),
            cooldown_until=future,
        )
        assert rule.cooldown_until == future

    def test_is_expired_no_cooldown(self):
        rule = ExclusionRule(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="memory",
            entity_id=str(uuid4()),
        )
        assert rule.is_expired is False

    def test_is_expired_future_cooldown(self):
        future = datetime.now(timezone.utc) + timedelta(days=7)
        rule = ExclusionRule(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="memory",
            entity_id=str(uuid4()),
            cooldown_until=future,
        )
        assert rule.is_expired is False

    def test_is_expired_past_cooldown(self):
        past = datetime.now(timezone.utc) - timedelta(days=1)
        rule = ExclusionRule(
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="memory",
            entity_id=str(uuid4()),
            cooldown_until=past,
        )
        assert rule.is_expired is True

    def test_to_dict(self):
        uid = uuid4()
        fid = uuid4()
        eid = str(uuid4())
        rule = ExclusionRule(
            id=uuid4(),
            user_id=uid,
            family_id=fid,
            entity_type="insight",
            entity_id=eid,
            reason="Not relevant",
        )
        d = rule.to_dict()
        assert d["entity_type"] == "insight"
        assert d["entity_id"] == eid
        assert d["reason"] == "Not relevant"
        assert d["user_id"] == str(uid)
        assert d["family_id"] == str(fid)
        assert d["cooldown_until"] is None

    def test_to_dict_with_cooldown(self):
        future = datetime.now(timezone.utc) + timedelta(days=3)
        rule = ExclusionRule(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="memory",
            entity_id=str(uuid4()),
            cooldown_until=future,
        )
        d = rule.to_dict()
        assert d["cooldown_until"] is not None

    def test_repr(self):
        eid = str(uuid4())
        rule = ExclusionRule(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            entity_type="memory",
            entity_id=eid,
        )
        r = repr(rule)
        assert "ExclusionRule" in r
        assert "memory" in r

    def test_tablename(self):
        assert ExclusionRule.__tablename__ == "exclusion_rules"

    def test_all_entity_types(self):
        """Verify all expected entity types can be stored."""
        for et in ["memory", "member", "event", "insight"]:
            rule = ExclusionRule(
                user_id=uuid4(),
                family_id=uuid4(),
                entity_type=et,
                entity_id=str(uuid4()),
            )
            assert rule.entity_type == et
