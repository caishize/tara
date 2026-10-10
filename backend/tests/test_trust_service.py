"""Tests for trust level evaluation, demotion, and feature gating."""
import pytest

from src.modules.member.trust_service import (
    TrustLevel,
    check_feature_access,
    evaluate_trust,
    should_demote,
    FEATURE_TRUST_REQUIREMENTS,
    ReflectionLog,
)


# ---------------------------------------------------------------------------
# evaluate_trust tests
# ---------------------------------------------------------------------------


class TestEvaluateTrust:
    """Test trust level upgrade logic."""

    def test_l0_stays_when_too_few_days(self):
        assert evaluate_trust(confirmation_count=10, rejection_count=0, days_registered=3, current_level=0) == 0

    def test_l0_stays_when_too_few_confirmations(self):
        assert evaluate_trust(confirmation_count=3, rejection_count=0, days_registered=10, current_level=0) == 0

    def test_l0_to_l1(self):
        assert evaluate_trust(confirmation_count=5, rejection_count=0, days_registered=7, current_level=0) == 1

    def test_l0_to_l1_with_rejections(self):
        # Has enough confirmations and days, even with some rejections
        assert evaluate_trust(confirmation_count=5, rejection_count=2, days_registered=7, current_level=0) == 1

    def test_l1_stays_when_too_few_days(self):
        assert evaluate_trust(confirmation_count=50, rejection_count=0, days_registered=20, current_level=1) == 1

    def test_l1_stays_when_low_confirm_rate(self):
        # 70% confirm rate < 80% threshold
        assert evaluate_trust(confirmation_count=7, rejection_count=3, days_registered=30, current_level=1) == 1

    def test_l1_to_l2(self):
        assert evaluate_trust(confirmation_count=80, rejection_count=10, days_registered=30, current_level=1) == 2

    def test_l2_stays_when_too_few_days(self):
        assert evaluate_trust(confirmation_count=100, rejection_count=0, days_registered=60, current_level=2) == 2

    def test_l2_stays_when_high_rejection_rate(self):
        # 10% rejection rate >= 5% threshold
        assert evaluate_trust(confirmation_count=9, rejection_count=1, days_registered=90, current_level=2) == 2

    def test_l2_to_l3(self):
        # 2% rejection rate < 5%
        assert evaluate_trust(confirmation_count=98, rejection_count=2, days_registered=90, current_level=2) == 3

    def test_l3_stays_at_l3(self):
        # Already at max level
        assert evaluate_trust(confirmation_count=100, rejection_count=0, days_registered=365, current_level=3) == 3

    def test_no_interactions_stays_at_current(self):
        assert evaluate_trust(confirmation_count=0, rejection_count=0, days_registered=100, current_level=0) == 0
        assert evaluate_trust(confirmation_count=0, rejection_count=0, days_registered=100, current_level=2) == 2

    def test_boundary_l1_exactly_5_confirmations_7_days(self):
        assert evaluate_trust(confirmation_count=5, rejection_count=0, days_registered=7, current_level=0) == 1

    def test_boundary_l2_exactly_80_percent(self):
        assert evaluate_trust(confirmation_count=80, rejection_count=20, days_registered=30, current_level=1) == 2

    def test_boundary_l3_exactly_5_percent_rejection(self):
        # 5% rejection = NOT < 5%, so should NOT upgrade
        assert evaluate_trust(confirmation_count=95, rejection_count=5, days_registered=90, current_level=2) == 2


# ---------------------------------------------------------------------------
# should_demote tests
# ---------------------------------------------------------------------------


class TestShouldDemote:
    """Test demotion trigger logic."""

    def test_demote_at_3_consecutive(self):
        assert should_demote(consecutive_rejections=3, same_type=True) is True

    def test_no_demote_at_2(self):
        assert should_demote(consecutive_rejections=2, same_type=True) is False

    def test_no_demote_different_type(self):
        assert should_demote(consecutive_rejections=5, same_type=False) is False

    def test_demote_at_high_count(self):
        assert should_demote(consecutive_rejections=10, same_type=True) is True

    def test_no_demote_zero(self):
        assert should_demote(consecutive_rejections=0, same_type=True) is False


# ---------------------------------------------------------------------------
# check_feature_access tests
# ---------------------------------------------------------------------------


class TestCheckFeatureAccess:
    """Test feature gating by trust level."""

    def test_l0_cannot_access_auto_booking(self):
        assert check_feature_access(0, "auto_booking") is False

    def test_l2_can_access_auto_booking(self):
        assert check_feature_access(2, "auto_booking") is True

    def test_l3_can_access_auto_payment(self):
        assert check_feature_access(3, "auto_payment") is True

    def test_l2_cannot_access_auto_payment(self):
        assert check_feature_access(2, "auto_payment") is False

    def test_l1_can_access_proactive_suggestions(self):
        assert check_feature_access(1, "proactive_suggestions") is True

    def test_l0_cannot_access_proactive_suggestions(self):
        assert check_feature_access(0, "proactive_suggestions") is False

    def test_unknown_feature_defaults_to_l0(self):
        assert check_feature_access(0, "unknown_feature") is True

    def test_higher_trust_always_passes(self):
        for feature in FEATURE_TRUST_REQUIREMENTS:
            assert check_feature_access(3, feature) is True

    def test_l2_can_access_sensitive_data(self):
        assert check_feature_access(2, "sensitive_data_access") is True

    def test_l1_cannot_access_sensitive_data(self):
        assert check_feature_access(1, "sensitive_data_access") is False


# ---------------------------------------------------------------------------
# TrustLevel enum
# ---------------------------------------------------------------------------


class TestTrustLevelEnum:
    """Test TrustLevel IntEnum values."""

    def test_values(self):
        assert TrustLevel.L0_NOVICE == 0
        assert TrustLevel.L1_FAMILIAR == 1
        assert TrustLevel.L2_TRUSTED == 2
        assert TrustLevel.L3_RAPPORT == 3

    def test_comparison(self):
        assert TrustLevel.L0_NOVICE < TrustLevel.L3_RAPPORT
        assert TrustLevel.L2_TRUSTED >= TrustLevel.L1_FAMILIAR


# ---------------------------------------------------------------------------
# ReflectionLog model
# ---------------------------------------------------------------------------


class TestReflectionLogModel:
    """Test that ReflectionLog model has correct table name."""

    def test_tablename(self):
        assert ReflectionLog.__tablename__ == "reflection_logs"
