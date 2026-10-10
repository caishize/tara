"""Tests for V8 progressive feature unlock (4-tier system)."""

import pytest

from src.modules.member.trust_service import (
    FeatureTier,
    TIER_FEATURES,
    _is_tier_unlocked,
    get_available_features,
    check_tier_feature_access,
    get_feature_tiers,
    _get_unlock_conditions,
    # Legacy compat
    FEATURE_TRUST_REQUIREMENTS,
    check_feature_access,
    TrustLevel,
)


# ===========================================================================
# FeatureTier enum
# ===========================================================================


class TestFeatureTierEnum:
    """Verify the FeatureTier enum values."""

    def test_all_tiers_present(self):
        tiers = {t.value for t in FeatureTier}
        assert tiers == {"basic", "advanced", "premium", "expert"}

    def test_tier_string_values(self):
        assert FeatureTier.BASIC.value == "basic"
        assert FeatureTier.ADVANCED.value == "advanced"
        assert FeatureTier.PREMIUM.value == "premium"
        assert FeatureTier.EXPERT.value == "expert"


# ===========================================================================
# TIER_FEATURES data
# ===========================================================================


class TestTierFeatures:
    """Verify the TIER_FEATURES mapping."""

    def test_basic_features(self):
        features = TIER_FEATURES[FeatureTier.BASIC.value]
        assert "conversation" in features
        assert "reminders" in features
        assert "weather" in features

    def test_advanced_features(self):
        features = TIER_FEATURES[FeatureTier.ADVANCED.value]
        assert "kanban" in features
        assert "briefing" in features
        assert "memory" in features

    def test_premium_features(self):
        features = TIER_FEATURES[FeatureTier.PREMIUM.value]
        assert "trip_planning" in features
        assert "gifts" in features
        assert "relationships" in features

    def test_expert_features(self):
        features = TIER_FEATURES[FeatureTier.EXPERT.value]
        assert "graph_view" in features
        assert "global_orchestration" in features

    def test_no_duplicate_features_across_tiers(self):
        all_features = []
        for tier_features in TIER_FEATURES.values():
            all_features.extend(tier_features)
        assert len(all_features) == len(set(all_features))


# ===========================================================================
# _is_tier_unlocked
# ===========================================================================


class TestIsTierUnlocked:
    """Verify tier unlock logic."""

    # BASIC tier
    def test_basic_always_unlocked(self):
        assert _is_tier_unlocked(FeatureTier.BASIC, 0, 0) is True

    def test_basic_unlocked_with_zero_everything(self):
        assert _is_tier_unlocked(FeatureTier.BASIC, 0, 0, None) is True

    # ADVANCED tier
    def test_advanced_locked_day_0(self):
        assert _is_tier_unlocked(FeatureTier.ADVANCED, 0, 0) is False

    def test_advanced_locked_7_days_but_no_members(self):
        assert _is_tier_unlocked(FeatureTier.ADVANCED, 7, 0) is False

    def test_advanced_locked_7_days_1_member(self):
        assert _is_tier_unlocked(FeatureTier.ADVANCED, 7, 1) is False

    def test_advanced_unlocked_7_days_2_members(self):
        assert _is_tier_unlocked(FeatureTier.ADVANCED, 7, 2) is True

    def test_advanced_unlocked_30_days_5_members(self):
        assert _is_tier_unlocked(FeatureTier.ADVANCED, 30, 5) is True

    def test_advanced_locked_6_days_2_members(self):
        assert _is_tier_unlocked(FeatureTier.ADVANCED, 6, 2) is False

    def test_advanced_unlocked_with_manual_override(self):
        assert _is_tier_unlocked(
            FeatureTier.ADVANCED, 0, 0, {"advanced": True},
        ) is True

    # PREMIUM tier
    def test_premium_locked_day_0(self):
        assert _is_tier_unlocked(FeatureTier.PREMIUM, 0, 0) is False

    def test_premium_locked_day_29(self):
        assert _is_tier_unlocked(FeatureTier.PREMIUM, 29, 5) is False

    def test_premium_unlocked_day_30(self):
        assert _is_tier_unlocked(FeatureTier.PREMIUM, 30, 0) is True

    def test_premium_unlocked_with_manual_override(self):
        assert _is_tier_unlocked(
            FeatureTier.PREMIUM, 0, 0, {"premium": True},
        ) is True

    # EXPERT tier
    def test_expert_locked_without_override(self):
        assert _is_tier_unlocked(FeatureTier.EXPERT, 365, 100) is False

    def test_expert_unlocked_with_override(self):
        assert _is_tier_unlocked(
            FeatureTier.EXPERT, 0, 0, {"expert": True},
        ) is True

    def test_expert_locked_with_false_override(self):
        assert _is_tier_unlocked(
            FeatureTier.EXPERT, 365, 100, {"expert": False},
        ) is False


# ===========================================================================
# get_available_features
# ===========================================================================


class TestGetAvailableFeatures:
    """Verify the feature list returned for various user states."""

    def test_new_user_gets_basic_only(self):
        features = get_available_features(0, 0)
        assert set(features) == {"conversation", "reminders", "weather"}

    def test_7_day_2_member_gets_basic_plus_advanced(self):
        features = get_available_features(7, 2)
        expected = {
            "conversation", "reminders", "weather",
            "kanban", "briefing", "memory",
        }
        assert set(features) == expected

    def test_30_day_user_gets_basic_advanced_premium(self):
        features = get_available_features(30, 2)
        expected = {
            "conversation", "reminders", "weather",
            "kanban", "briefing", "memory",
            "trip_planning", "gifts", "relationships",
        }
        assert set(features) == expected

    def test_all_tiers_with_expert_override(self):
        features = get_available_features(30, 2, {"expert": True})
        expected = {
            "conversation", "reminders", "weather",
            "kanban", "briefing", "memory",
            "trip_planning", "gifts", "relationships",
            "graph_view", "global_orchestration",
        }
        assert set(features) == expected

    def test_only_basic_and_expert_with_override(self):
        features = get_available_features(0, 0, {"expert": True})
        expected = {
            "conversation", "reminders", "weather",
            "graph_view", "global_orchestration",
        }
        assert set(features) == expected


# ===========================================================================
# check_tier_feature_access
# ===========================================================================


class TestCheckTierFeatureAccess:
    """Verify per-feature access checks."""

    def test_conversation_always_accessible(self):
        assert check_tier_feature_access("conversation", 0, 0) is True

    def test_kanban_locked_for_new_user(self):
        assert check_tier_feature_access("kanban", 0, 0) is False

    def test_kanban_unlocked_after_7_days_2_members(self):
        assert check_tier_feature_access("kanban", 7, 2) is True

    def test_trip_planning_locked_for_7_day_user(self):
        assert check_tier_feature_access("trip_planning", 7, 2) is False

    def test_trip_planning_unlocked_after_30_days(self):
        assert check_tier_feature_access("trip_planning", 30, 0) is True

    def test_graph_view_locked_without_manual(self):
        assert check_tier_feature_access("graph_view", 365, 100) is False

    def test_graph_view_unlocked_with_manual(self):
        assert check_tier_feature_access(
            "graph_view", 0, 0, {"expert": True},
        ) is True

    def test_unknown_feature_defaults_to_accessible(self):
        assert check_tier_feature_access("nonexistent_feature", 0, 0) is True


# ===========================================================================
# get_feature_tiers
# ===========================================================================


class TestGetFeatureTiers:
    """Verify the tier status dict."""

    def test_returns_all_tiers(self):
        result = get_feature_tiers(0, 0)
        assert set(result.keys()) == {"basic", "advanced", "premium", "expert"}

    def test_new_user_only_basic_unlocked(self):
        result = get_feature_tiers(0, 0)
        assert result["basic"]["unlocked"] is True
        assert result["advanced"]["unlocked"] is False
        assert result["premium"]["unlocked"] is False
        assert result["expert"]["unlocked"] is False

    def test_7_day_2_member_basic_and_advanced(self):
        result = get_feature_tiers(7, 2)
        assert result["basic"]["unlocked"] is True
        assert result["advanced"]["unlocked"] is True
        assert result["premium"]["unlocked"] is False
        assert result["expert"]["unlocked"] is False

    def test_tiers_contain_features(self):
        result = get_feature_tiers(0, 0)
        assert "features" in result["basic"]
        assert len(result["basic"]["features"]) > 0

    def test_tiers_contain_unlock_conditions(self):
        result = get_feature_tiers(0, 0)
        for tier_name, tier_info in result.items():
            assert "unlock_conditions" in tier_info
            conditions = tier_info["unlock_conditions"]
            assert "description" in conditions


# ===========================================================================
# _get_unlock_conditions
# ===========================================================================


class TestGetUnlockConditions:
    """Verify unlock conditions descriptions."""

    def test_basic_conditions(self):
        conds = _get_unlock_conditions(FeatureTier.BASIC)
        assert conds["auto"] is True

    def test_advanced_conditions(self):
        conds = _get_unlock_conditions(FeatureTier.ADVANCED)
        assert conds["days_required"] == 7
        assert conds["family_members_required"] == 2
        assert conds["auto"] is True

    def test_premium_conditions(self):
        conds = _get_unlock_conditions(FeatureTier.PREMIUM)
        assert conds["days_required"] == 30
        assert conds["manual_unlock_available"] is True

    def test_expert_conditions(self):
        conds = _get_unlock_conditions(FeatureTier.EXPERT)
        assert conds["auto"] is False
        assert conds["manual_unlock_available"] is True


# ===========================================================================
# Legacy compatibility
# ===========================================================================


class TestLegacyBackwardCompat:
    """Ensure the original 4 FEATURE_TRUST_REQUIREMENTS still work."""

    def test_original_features_still_present(self):
        assert "auto_booking" in FEATURE_TRUST_REQUIREMENTS
        assert "auto_payment" in FEATURE_TRUST_REQUIREMENTS
        assert "proactive_suggestions" in FEATURE_TRUST_REQUIREMENTS
        assert "sensitive_data_access" in FEATURE_TRUST_REQUIREMENTS

    def test_legacy_check_feature_access(self):
        assert check_feature_access(0, "proactive_suggestions") is False
        assert check_feature_access(1, "proactive_suggestions") is True
        assert check_feature_access(2, "auto_booking") is True
        assert check_feature_access(3, "auto_payment") is True

    def test_unknown_feature_defaults_to_l0(self):
        assert check_feature_access(0, "some_random_feature") is True
