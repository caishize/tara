"""Tests for CommitmentPreFilter, SocialIntentParser, and VagueCommitmentTracker.

Covers:
- SocialIntentParser: genuine vs courtesy vs obligation classification
- CommitmentPreFilter: filtering by social intent, obligation extension
- VagueCommitmentTracker: follow-up timing by commitment type
- Data class immutability
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.modules.memory.commitment_service import (
    CommitmentItem,
    CommitmentPreFilter,
    CommitmentStatus,
    CommitmentType,
    SocialIntentParser,
    SocialIntentResult,
    SocialIntentType,
    VagueCommitmentTracker,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_commitment(
    what_promised: str,
    commitment_type: CommitmentType = CommitmentType.VAGUE,
    deadline: str = None,
    suggested_follow_up: str = None,
    status: CommitmentStatus = CommitmentStatus.PENDING,
    follow_up_count: int = 0,
) -> CommitmentItem:
    return CommitmentItem(
        id=uuid4(),
        commitment_type=commitment_type,
        who_promised="Alice",
        what_promised=what_promised,
        to_whom="Bob",
        deadline=deadline,
        suggested_follow_up=suggested_follow_up,
        status=status,
        follow_up_count=follow_up_count,
    )


# ---------------------------------------------------------------------------
# SocialIntentParser
# ---------------------------------------------------------------------------


class TestSocialIntentParser:
    def setup_method(self):
        self.parser = SocialIntentParser()

    # Genuine signals
    def test_genuine_with_specific_day(self):
        result = self.parser.classify("周三给你报价")
        assert result.type == SocialIntentType.GENUINE
        assert result.score >= 0.6

    def test_genuine_with_tomorrow(self):
        result = self.parser.classify("明天下午三点开会")
        assert result.type == SocialIntentType.GENUINE
        assert result.score >= 0.6

    def test_genuine_english_tomorrow(self):
        result = self.parser.classify("I will send it tomorrow")
        assert result.type == SocialIntentType.GENUINE
        assert result.score >= 0.6

    def test_genuine_english_day_of_week(self):
        result = self.parser.classify("Let's meet on Wednesday")
        assert result.type == SocialIntentType.GENUINE
        assert result.score >= 0.6

    # Courtesy signals
    def test_courtesy_with_vague_signal(self):
        result = self.parser.classify("改天一起吃饭")
        assert result.type == SocialIntentType.SOCIAL_COURTESY
        assert result.score < 0.6

    def test_courtesy_with_multiple_signals(self):
        result = self.parser.classify("有空改天找机会聊聊")
        assert result.type == SocialIntentType.SOCIAL_COURTESY
        assert result.score < 0.4

    def test_courtesy_english(self):
        result = self.parser.classify("We should grab coffee sometime")
        assert result.type == SocialIntentType.SOCIAL_COURTESY
        assert result.score < 0.6

    def test_courtesy_english_maybe_later(self):
        result = self.parser.classify("Maybe later we can discuss")
        assert result.type == SocialIntentType.SOCIAL_COURTESY
        assert result.score < 0.6

    # Obligation signals
    def test_obligation_chinese(self):
        result = self.parser.classify("我答应了帮你做这件事")
        assert result.type == SocialIntentType.OBLIGATION

    def test_obligation_must(self):
        result = self.parser.classify("必须在月底前完成")
        assert result.type == SocialIntentType.OBLIGATION

    def test_obligation_english_promised(self):
        result = self.parser.classify("I promised to help with the project")
        assert result.type == SocialIntentType.OBLIGATION

    # Edge cases
    def test_empty_string(self):
        result = self.parser.classify("")
        assert result.type == SocialIntentType.SOCIAL_COURTESY
        assert result.score == 0.0

    def test_whitespace_only(self):
        result = self.parser.classify("   ")
        assert result.type == SocialIntentType.SOCIAL_COURTESY
        assert result.score == 0.0

    def test_no_signals_baseline(self):
        result = self.parser.classify("帮我拿一下快递")
        assert result.score == 0.5

    def test_score_clamped_to_max(self):
        result = self.parser.classify("明天后天下周这周周一具体10:30")
        assert result.score <= 1.0

    def test_score_clamped_to_min(self):
        result = self.parser.classify("改天有空下次回头以后再说抽空找机会")
        assert result.score >= 0.0

    def test_context_parameter_accepted(self):
        result = self.parser.classify("周三开会", context={"topic": "work"})
        assert result.type == SocialIntentType.GENUINE

    def test_result_is_frozen(self):
        result = self.parser.classify("明天见")
        with pytest.raises(AttributeError):
            result.score = 0.0


# ---------------------------------------------------------------------------
# CommitmentPreFilter
# ---------------------------------------------------------------------------


class TestCommitmentPreFilter:
    def setup_method(self):
        self.pre_filter = CommitmentPreFilter()

    def test_genuine_commitment_kept(self):
        commitments = [_make_commitment("周三给你报价")]
        result = self.pre_filter.filter_commitments(commitments)
        assert len(result) == 1
        assert result[0].what_promised == "周三给你报价"

    def test_courtesy_commitment_excluded(self):
        commitments = [_make_commitment("改天一起吃饭")]
        result = self.pre_filter.filter_commitments(commitments)
        assert len(result) == 0

    def test_obligation_commitment_kept(self):
        commitments = [
            _make_commitment(
                "我答应了帮你做这件事",
                suggested_follow_up="in 3 days",
            )
        ]
        result = self.pre_filter.filter_commitments(commitments)
        assert len(result) == 1

    def test_obligation_follow_up_extended(self):
        commitments = [
            _make_commitment(
                "我答应了帮你做这件事",
                suggested_follow_up="in 3 days",
            )
        ]
        result = self.pre_filter.filter_commitments(commitments)
        assert len(result) == 1
        assert "extended" in result[0].suggested_follow_up
        assert "2x window" in result[0].suggested_follow_up

    def test_obligation_without_follow_up_unchanged(self):
        commitments = [
            _make_commitment(
                "我保证完成这个任务",
                suggested_follow_up=None,
            )
        ]
        result = self.pre_filter.filter_commitments(commitments)
        assert len(result) == 1
        assert result[0].suggested_follow_up is None

    def test_empty_list_returns_empty(self):
        result = self.pre_filter.filter_commitments([])
        assert result == []

    def test_none_context_accepted(self):
        commitments = [_make_commitment("明天给你答复")]
        result = self.pre_filter.filter_commitments(
            commitments, conversation_context=None,
        )
        assert len(result) == 1

    def test_mixed_commitments_filtered(self):
        commitments = [
            _make_commitment("周三给你报价"),   # genuine -> keep
            _make_commitment("改天一起吃饭"),    # courtesy -> exclude
            _make_commitment("明天交报告"),      # genuine -> keep
        ]
        result = self.pre_filter.filter_commitments(commitments)
        assert len(result) == 2
        promises = [c.what_promised for c in result]
        assert "周三给你报价" in promises
        assert "明天交报告" in promises
        assert "改天一起吃饭" not in promises

    def test_commitment_item_immutability(self):
        commitment = _make_commitment("周三给你报价")
        with pytest.raises(AttributeError):
            commitment.status = CommitmentStatus.FULFILLED

    def test_custom_parser_injected(self):
        """CommitmentPreFilter accepts a custom parser."""
        custom_parser = SocialIntentParser()
        pre_filter = CommitmentPreFilter(parser=custom_parser)
        commitments = [_make_commitment("明天见")]
        result = pre_filter.filter_commitments(commitments)
        assert len(result) == 1


# ---------------------------------------------------------------------------
# VagueCommitmentTracker
# ---------------------------------------------------------------------------


class TestVagueCommitmentTracker:
    def setup_method(self):
        self.tracker = VagueCommitmentTracker()

    def test_check_and_follow_up_returns_due_items(self):
        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(days=5)).isoformat()
        commitments = [
            {
                "commitment_type": CommitmentType.VAGUE.value,
                "status": CommitmentStatus.PENDING.value,
                "created_at": old_time,
                "follow_up_count": 0,
            },
        ]
        due = self.tracker.check_and_follow_up(commitments)
        assert len(due) == 1

    def test_check_and_follow_up_skips_non_pending(self):
        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(days=5)).isoformat()
        commitments = [
            {
                "commitment_type": CommitmentType.VAGUE.value,
                "status": CommitmentStatus.FULFILLED.value,
                "created_at": old_time,
                "follow_up_count": 0,
            },
        ]
        due = self.tracker.check_and_follow_up(commitments)
        assert len(due) == 0

    def test_check_and_follow_up_skips_max_followed_up(self):
        now = datetime.now(timezone.utc)
        old_time = (now - timedelta(days=5)).isoformat()
        commitments = [
            {
                "commitment_type": CommitmentType.VAGUE.value,
                "status": CommitmentStatus.PENDING.value,
                "created_at": old_time,
                "follow_up_count": 3,
            },
        ]
        due = self.tracker.check_and_follow_up(commitments)
        assert len(due) == 0

    def test_vague_default_3_days(self):
        now = datetime.now(timezone.utc)
        # 2 days ago: not yet due for vague (default 3 days)
        recent = (now - timedelta(days=2)).isoformat()
        commitments = [
            {
                "commitment_type": CommitmentType.VAGUE.value,
                "status": CommitmentStatus.PENDING.value,
                "created_at": recent,
                "follow_up_count": 0,
            },
        ]
        due = self.tracker.check_and_follow_up(commitments)
        assert len(due) == 0

    def test_conditional_default_7_days(self):
        now = datetime.now(timezone.utc)
        # 5 days ago: not yet due for conditional (default 7 days)
        five_days_ago = (now - timedelta(days=5)).isoformat()
        commitments = [
            {
                "commitment_type": CommitmentType.CONDITIONAL.value,
                "status": CommitmentStatus.PENDING.value,
                "created_at": five_days_ago,
                "follow_up_count": 0,
            },
        ]
        due = self.tracker.check_and_follow_up(commitments)
        assert len(due) == 0

        # 8 days ago: should be due
        eight_days_ago = (now - timedelta(days=8)).isoformat()
        commitments[0] = {**commitments[0], "created_at": eight_days_ago}
        due = self.tracker.check_and_follow_up(commitments)
        assert len(due) == 1

    def test_delegated_default_2_days(self):
        now = datetime.now(timezone.utc)
        # 3 days ago: due for delegated (default 2 days)
        three_days_ago = (now - timedelta(days=3)).isoformat()
        commitments = [
            {
                "commitment_type": CommitmentType.DELEGATED.value,
                "status": CommitmentStatus.PENDING.value,
                "created_at": three_days_ago,
                "follow_up_count": 0,
            },
        ]
        due = self.tracker.check_and_follow_up(commitments)
        assert len(due) == 1

    def test_last_follow_up_at_used_over_created_at(self):
        now = datetime.now(timezone.utc)
        # created_at long ago, but last_follow_up_at recently
        old = (now - timedelta(days=30)).isoformat()
        recent = (now - timedelta(days=1)).isoformat()
        commitments = [
            {
                "commitment_type": CommitmentType.VAGUE.value,
                "status": CommitmentStatus.PENDING.value,
                "created_at": old,
                "last_follow_up_at": recent,
                "follow_up_count": 1,
            },
        ]
        due = self.tracker.check_and_follow_up(commitments)
        # 1 day since last follow-up < 3 day threshold for vague
        assert len(due) == 0

    def test_no_reference_time_triggers_follow_up(self):
        commitments = [
            {
                "commitment_type": CommitmentType.VAGUE.value,
                "status": CommitmentStatus.PENDING.value,
                "follow_up_count": 0,
            },
        ]
        due = self.tracker.check_and_follow_up(commitments)
        assert len(due) == 1

    def test_custom_follow_up_days(self):
        now = datetime.now(timezone.utc)
        two_days_ago = (now - timedelta(days=2)).isoformat()
        # Custom: VAGUE -> 1 day (instead of default 3)
        tracker = VagueCommitmentTracker(
            follow_up_days={CommitmentType.VAGUE: 1},
        )
        commitments = [
            {
                "commitment_type": CommitmentType.VAGUE.value,
                "status": CommitmentStatus.PENDING.value,
                "created_at": two_days_ago,
                "follow_up_count": 0,
            },
        ]
        due = tracker.check_and_follow_up(commitments)
        assert len(due) == 1

    def test_custom_max_follow_ups(self):
        now = datetime.now(timezone.utc)
        old = (now - timedelta(days=5)).isoformat()
        tracker = VagueCommitmentTracker(max_follow_ups=1)
        commitments = [
            {
                "commitment_type": CommitmentType.VAGUE.value,
                "status": CommitmentStatus.PENDING.value,
                "created_at": old,
                "follow_up_count": 1,
            },
        ]
        due = tracker.check_and_follow_up(commitments)
        assert len(due) == 0


# ---------------------------------------------------------------------------
# Enum values
# ---------------------------------------------------------------------------


class TestEnumValues:
    def test_commitment_types(self):
        assert CommitmentType.FIRM.value == "firm"
        assert CommitmentType.VAGUE.value == "vague"
        assert CommitmentType.CONDITIONAL.value == "conditional"
        assert CommitmentType.DELEGATED.value == "delegated"

    def test_social_intent_types(self):
        assert SocialIntentType.GENUINE.value == "genuine"
        assert SocialIntentType.SOCIAL_COURTESY.value == "social_courtesy"
        assert SocialIntentType.OBLIGATION.value == "obligation"

    def test_commitment_status(self):
        assert CommitmentStatus.PENDING.value == "pending"
        assert CommitmentStatus.FOLLOWED_UP.value == "followed_up"
        assert CommitmentStatus.FULFILLED.value == "fulfilled"
        assert CommitmentStatus.EXPIRED.value == "expired"
        assert CommitmentStatus.DROPPED.value == "dropped"
