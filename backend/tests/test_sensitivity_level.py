"""Tests for sensitivity_level field and classify_sensitivity logic.

Covers:
- SensitivityLevel enum values
- classify_sensitivity() rule-based classification
- ConversationMemory model column default
- to_dict() includes sensitivity_level
"""

import pytest
from uuid import uuid4

from src.modules.memory.models import (
    ConversationMemory,
    MemoryType,
    SensitivityLevel,
    classify_sensitivity,
    _flatten_entity_values,
)


# ---------------------------------------------------------------------------
# SensitivityLevel enum
# ---------------------------------------------------------------------------


class TestSensitivityLevelEnum:
    def test_enum_values(self):
        assert SensitivityLevel.PUBLIC.value == "public"
        assert SensitivityLevel.FAMILY.value == "family"
        assert SensitivityLevel.PRIVATE.value == "private"
        assert SensitivityLevel.SENSITIVE.value == "sensitive"

    def test_enum_is_str(self):
        """SensitivityLevel values can be compared to plain strings."""
        assert SensitivityLevel.PUBLIC == "public"
        assert SensitivityLevel.SENSITIVE == "sensitive"

    def test_all_four_levels(self):
        assert len(SensitivityLevel) == 4


# ---------------------------------------------------------------------------
# classify_sensitivity
# ---------------------------------------------------------------------------


class TestClassifySensitivity:
    """Test the rule-based sensitivity classifier."""

    # Rule 4: default -> PUBLIC
    def test_general_memory_is_public(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="We had dinner at the new Italian restaurant",
        )
        assert result == SensitivityLevel.PUBLIC

    def test_preference_memory_is_public(self):
        result = classify_sensitivity(
            memory_type=MemoryType.PREFERENCE.value,
            content="Mom likes green tea over black tea",
        )
        assert result == SensitivityLevel.PUBLIC

    def test_plan_memory_is_public(self):
        result = classify_sensitivity(
            memory_type=MemoryType.PLAN.value,
            content="Planning a weekend BBQ party",
        )
        assert result == SensitivityLevel.PUBLIC

    def test_location_memory_is_public(self):
        result = classify_sensitivity(
            memory_type=MemoryType.LOCATION.value,
            content="Visited the science museum downtown",
        )
        assert result == SensitivityLevel.PUBLIC

    # Rule 2: FAVOR -> FAMILY
    def test_favor_type_is_family(self):
        result = classify_sensitivity(
            memory_type=MemoryType.FAVOR.value,
            content="Asked uncle to help move furniture",
        )
        assert result == SensitivityLevel.FAMILY

    # Rule 3: HEALTH / EMOTION -> PRIVATE
    def test_health_type_is_private(self):
        result = classify_sensitivity(
            memory_type=MemoryType.HEALTH.value,
            content="Started a new vitamin regimen",
        )
        assert result == SensitivityLevel.PRIVATE

    def test_emotion_type_is_private(self):
        result = classify_sensitivity(
            memory_type=MemoryType.EMOTION.value,
            content="Feeling happy about the promotion",
        )
        assert result == SensitivityLevel.PRIVATE

    # Rule 1: Financial patterns in English -> SENSITIVE
    def test_bank_account_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="Bank account number is 12345678",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_salary_content_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.WORK.value,
            content="Monthly salary increased to 15000",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_credit_card_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="Credit card expires next month",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_loan_content_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="Applied for a mortgage for the new house",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_password_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="Need to remember the password for the account",
        )
        assert result == SensitivityLevel.SENSITIVE

    # Rule 1: Financial patterns in Chinese -> SENSITIVE
    def test_chinese_financial_content_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="公积金账号需要更新",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_chinese_salary_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="这个月工资到账了",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_chinese_bank_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="银行余额不足",
        )
        assert result == SensitivityLevel.SENSITIVE

    # Rule 1: Medical patterns in English -> SENSITIVE
    def test_diagnosis_english_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="Got the diagnosis from the doctor",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_prescription_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="New prescription for medication",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_psychiatric_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.EMOTION.value,
            content="Saw a psychiatric specialist today",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_blood_test_result_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.HEALTH.value,
            content="Got the blood test result from the hospital",
        )
        assert result == SensitivityLevel.SENSITIVE

    # Rule 1: Medical patterns in Chinese -> SENSITIVE
    def test_chinese_diagnosis_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.HEALTH.value,
            content="诊断结果出来了",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_chinese_surgery_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="下周要做手术",
        )
        assert result == SensitivityLevel.SENSITIVE

    # Rule 1 overrides type-based rules
    def test_financial_overrides_health_type(self):
        """Financial/medical patterns take priority over type-based rules."""
        result = classify_sensitivity(
            memory_type=MemoryType.HEALTH.value,
            content="诊断结果出来了",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_financial_overrides_favor_type(self):
        result = classify_sensitivity(
            memory_type=MemoryType.FAVOR.value,
            content="Lent money from bank account",
        )
        assert result == SensitivityLevel.SENSITIVE

    # Case insensitivity
    def test_case_insensitive_financial(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="CREDIT CARD statement arrived",
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_case_insensitive_medical(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="PRESCRIPTION needs to be refilled",
        )
        assert result == SensitivityLevel.SENSITIVE

    # Entity-based detection
    def test_financial_entity_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="Some innocuous content",
            entities={"银行": "工商银行", "账号": "6222021234"},
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_medical_entity_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="Meeting notes",
            entities={"health": "diagnosis confirmed"},
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_clean_entities_no_escalation(self):
        """Entities without sensitive keywords don't escalate."""
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="Weekend plans",
            entities={"location": "park", "persons": ["Alice"]},
        )
        assert result == SensitivityLevel.PUBLIC

    def test_password_in_entity_is_sensitive(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="Account setup",
            entities={"note": "password reset needed"},
        )
        assert result == SensitivityLevel.SENSITIVE

    def test_none_entities_treated_as_absent(self):
        result = classify_sensitivity(
            memory_type=MemoryType.GENERAL.value,
            content="Normal content",
            entities=None,
        )
        assert result == SensitivityLevel.PUBLIC


# ---------------------------------------------------------------------------
# _flatten_entity_values helper
# ---------------------------------------------------------------------------


class TestFlattenEntityValues:
    def test_flat_dict(self):
        result = _flatten_entity_values({"a": "1", "b": "2"})
        assert "a" in result
        assert "1" in result
        assert "b" in result
        assert "2" in result

    def test_nested_dict(self):
        result = _flatten_entity_values({"outer": {"inner": "val"}})
        assert "inner" in result
        assert "val" in result

    def test_list_values(self):
        result = _flatten_entity_values({"tags": ["x", "y"]})
        assert "x" in result
        assert "y" in result

    def test_empty_dict(self):
        result = _flatten_entity_values({})
        assert result == []


# ---------------------------------------------------------------------------
# ConversationMemory model integration
# ---------------------------------------------------------------------------


class TestConversationMemoryModel:
    def test_default_sensitivity_level_is_none_in_memory(self):
        """server_default='public' applies at DB level; in-memory is None."""
        mem = ConversationMemory(
            user_id=uuid4(),
            family_id=uuid4(),
            memory_type=MemoryType.GENERAL.value,
            content="test",
            summary="test summary",
        )
        # server_default only applies at INSERT time, not in-memory
        assert mem.sensitivity_level is None

    def test_explicit_sensitivity_level_public(self):
        """Explicitly setting sensitivity_level works."""
        mem = ConversationMemory(
            user_id=uuid4(),
            family_id=uuid4(),
            memory_type=MemoryType.GENERAL.value,
            content="test",
            summary="test summary",
            sensitivity_level=SensitivityLevel.PUBLIC.value,
        )
        assert mem.sensitivity_level == SensitivityLevel.PUBLIC.value

    def test_custom_sensitivity_level(self):
        mem = ConversationMemory(
            user_id=uuid4(),
            family_id=uuid4(),
            memory_type=MemoryType.HEALTH.value,
            content="test",
            summary="test summary",
            sensitivity_level=SensitivityLevel.PRIVATE.value,
        )
        assert mem.sensitivity_level == SensitivityLevel.PRIVATE.value

    def test_to_dict_includes_sensitivity_level(self):
        mem = ConversationMemory(
            user_id=uuid4(),
            family_id=uuid4(),
            memory_type=MemoryType.GENERAL.value,
            content="test",
            summary="test summary",
            sensitivity_level=SensitivityLevel.SENSITIVE.value,
        )
        d = mem.to_dict()
        assert "sensitivity_level" in d
        assert d["sensitivity_level"] == "sensitive"

    def test_sensitivity_level_in_dict_when_default(self):
        """server_default doesn't populate in-memory; to_dict returns None."""
        mem = ConversationMemory(
            user_id=uuid4(),
            family_id=uuid4(),
            memory_type=MemoryType.GENERAL.value,
            content="test",
            summary="test summary",
        )
        d = mem.to_dict()
        assert d["sensitivity_level"] is None
