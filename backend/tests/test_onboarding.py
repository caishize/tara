"""Tests for cold-start onboarding service and trust repair."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4

import pytest

from src.modules.conversation.onboarding_service import (
    ONBOARDING_STEPS,
    OnboardingCard,
    OnboardingPhase,
    OnboardingStep,
    advance_onboarding,
    get_next_onboarding_step,
    get_onboarding_card,
    get_onboarding_step,
    is_onboarding_complete,
    next_phase,
)
from src.modules.member.trust_repair import (
    CorrectionLog,
    CorrectionRecord,
    acknowledge_repair,
    contains_correction,
    format_repair_mention,
    get_pending_repairs,
    record_correction,
)


# ===========================================================================
# Onboarding service tests
# ===========================================================================


class TestOnboardingCardTemplates:
    """Verify card templates exist for each non-completed phase."""

    def test_welcome_card_exists(self):
        card = get_onboarding_card("welcome")
        assert card is not None
        assert card.phase == "welcome"
        assert card.progress_pct == 0
        assert len(card.suggested_prompts) > 0

    def test_family_basics_card(self):
        card = get_onboarding_card("family_basics")
        assert card is not None
        assert card.phase == "family_basics"
        assert card.progress_pct == 25

    def test_preferences_card(self):
        card = get_onboarding_card("preferences")
        assert card is not None
        assert card.phase == "preferences"
        assert card.progress_pct == 50

    def test_routines_card(self):
        card = get_onboarding_card("routines")
        assert card is not None
        assert card.phase == "routines"
        assert card.progress_pct == 75

    def test_completed_returns_none(self):
        card = get_onboarding_card("completed")
        assert card is None

    def test_unknown_phase_returns_none(self):
        card = get_onboarding_card("nonexistent_phase")
        assert card is None


class TestOnboardingCardImmutability:
    """OnboardingCard is frozen — mutation must raise."""

    def test_card_is_frozen(self):
        card = get_onboarding_card("welcome")
        with pytest.raises(AttributeError):
            card.title = "hacked"

    def test_card_to_dict(self):
        card = get_onboarding_card("welcome")
        d = card.to_dict()
        assert d["phase"] == "welcome"
        assert isinstance(d["suggested_prompts"], list)
        assert d["progress_pct"] == 0


class TestPhaseProgression:
    """Verify phase ordering and next_phase logic."""

    def test_welcome_to_family_basics(self):
        assert next_phase("welcome") == "family_basics"

    def test_family_basics_to_preferences(self):
        assert next_phase("family_basics") == "preferences"

    def test_preferences_to_routines(self):
        assert next_phase("preferences") == "routines"

    def test_routines_to_completed(self):
        assert next_phase("routines") == "completed"

    def test_completed_stays_completed(self):
        assert next_phase("completed") == "completed"

    def test_unknown_phase_goes_to_completed(self):
        assert next_phase("bogus") == "completed"

    def test_full_progression(self):
        phase = "welcome"
        expected_order = ["family_basics", "preferences", "routines", "completed"]
        for expected in expected_order:
            phase = next_phase(phase)
            assert phase == expected


class TestIsOnboardingComplete:
    def test_completed(self):
        assert is_onboarding_complete("completed") is True

    def test_not_completed(self):
        assert is_onboarding_complete("welcome") is False
        assert is_onboarding_complete("routines") is False


class TestGetOnboardingStep:
    """Test async get_onboarding_step with mocked Redis."""

    @pytest.mark.asyncio
    async def test_new_user_no_redis_returns_welcome(self):
        card = await get_onboarding_step(uuid4(), redis_client=None)
        assert card is not None
        assert card.phase == "welcome"

    @pytest.mark.asyncio
    async def test_user_with_redis_state(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"preferences"

        card = await get_onboarding_step(uuid4(), redis_client=mock_redis)
        assert card is not None
        assert card.phase == "preferences"

    @pytest.mark.asyncio
    async def test_user_completed_returns_none(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"completed"

        card = await get_onboarding_step(uuid4(), redis_client=mock_redis)
        assert card is None

    @pytest.mark.asyncio
    async def test_redis_returns_none_means_new_user(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = None

        card = await get_onboarding_step(uuid4(), redis_client=mock_redis)
        assert card is not None
        assert card.phase == "welcome"

    @pytest.mark.asyncio
    async def test_redis_error_falls_back_to_welcome(self):
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ConnectionError("Redis down")

        card = await get_onboarding_step(uuid4(), redis_client=mock_redis)
        assert card is not None
        assert card.phase == "welcome"


class TestAdvanceOnboarding:
    """Test async advance_onboarding with mocked Redis."""

    @pytest.mark.asyncio
    async def test_advance_from_welcome(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"welcome"

        card = await advance_onboarding(uuid4(), redis_client=mock_redis)
        assert card is not None
        assert card.phase == "family_basics"
        mock_redis.set.assert_called_once()

    @pytest.mark.asyncio
    async def test_advance_to_completed_returns_none(self):
        mock_redis = AsyncMock()
        mock_redis.get.return_value = b"routines"

        card = await advance_onboarding(uuid4(), redis_client=mock_redis)
        assert card is None  # completed has no card

    @pytest.mark.asyncio
    async def test_advance_without_redis_returns_none(self):
        card = await advance_onboarding(uuid4(), redis_client=None)
        assert card is None

    @pytest.mark.asyncio
    async def test_advance_redis_error_returns_none(self):
        mock_redis = AsyncMock()
        mock_redis.get.side_effect = ConnectionError("Redis down")

        card = await advance_onboarding(uuid4(), redis_client=mock_redis)
        assert card is None


# ===========================================================================
# Day-threshold onboarding step tests
# ===========================================================================


class TestOnboardingSteps:
    """Test ONBOARDING_STEPS list and OnboardingStep dataclass."""

    def test_steps_list_not_empty(self):
        assert len(ONBOARDING_STEPS) >= 4

    def test_step_is_frozen(self):
        step = ONBOARDING_STEPS[0]
        with pytest.raises(AttributeError):
            step.title = "hacked"

    def test_first_step_is_family(self):
        step = ONBOARDING_STEPS[0]
        assert step.category == "family"
        assert step.day_threshold == 0

    def test_step_categories(self):
        categories = {s.category for s in ONBOARDING_STEPS}
        assert "family" in categories
        assert "preference" in categories
        assert "routine" in categories

    def test_step_ids_unique(self):
        ids = [s.step_id for s in ONBOARDING_STEPS]
        assert len(ids) == len(set(ids))


class TestGetNextOnboardingStep:
    """Test get_next_onboarding_step day-threshold logic."""

    @pytest.mark.asyncio
    async def test_new_user_day_0(self):
        step = await get_next_onboarding_step(uuid4(), days_since_registration=0)
        assert step is not None
        assert step.day_threshold == 0

    @pytest.mark.asyncio
    async def test_completed_first_two_steps(self):
        step = await get_next_onboarding_step(
            uuid4(),
            days_since_registration=0,
            completed_steps=["family_size", "family_names"],
        )
        # Next eligible step with day_threshold=0 is done; day_threshold=3 not met yet
        assert step is None

    @pytest.mark.asyncio
    async def test_day_3_unlocks_preference(self):
        step = await get_next_onboarding_step(
            uuid4(),
            days_since_registration=3,
            completed_steps=["family_size", "family_names"],
        )
        assert step is not None
        assert step.category == "preference"

    @pytest.mark.asyncio
    async def test_day_7_unlocks_routine(self):
        step = await get_next_onboarding_step(
            uuid4(),
            days_since_registration=7,
            completed_steps=["family_size", "family_names", "food_pref"],
        )
        assert step is not None
        assert step.category == "routine"

    @pytest.mark.asyncio
    async def test_all_completed_returns_none(self):
        all_ids = [s.step_id for s in ONBOARDING_STEPS]
        step = await get_next_onboarding_step(
            uuid4(),
            days_since_registration=30,
            completed_steps=all_ids,
        )
        assert step is None

    @pytest.mark.asyncio
    async def test_no_completed_steps_returns_first(self):
        step = await get_next_onboarding_step(
            uuid4(),
            days_since_registration=30,
            completed_steps=None,
        )
        assert step is not None
        assert step.step_id == ONBOARDING_STEPS[0].step_id


# ===========================================================================
# Trust repair tests
# ===========================================================================


class TestContainsCorrection:
    """Test correction signal detection in user text."""

    def test_chinese_correction_bu_dui(self):
        assert contains_correction("不对，他的生日是3月") is True

    def test_chinese_correction_cuo_le(self):
        assert contains_correction("错了，应该是周三") is True

    def test_chinese_correction_gao_cuo(self):
        assert contains_correction("你搞错了") is True

    def test_chinese_correction_ji_cuo(self):
        assert contains_correction("记错了吧") is True

    def test_english_thats_wrong(self):
        assert contains_correction("No, that's wrong") is True

    def test_english_not_right(self):
        assert contains_correction("That's not right") is True

    def test_english_actually(self):
        assert contains_correction("Actually, it's Tuesday") is True

    def test_english_incorrect(self):
        assert contains_correction("That's incorrect") is True

    def test_english_youre_wrong(self):
        assert contains_correction("You're wrong about that") is True

    def test_normal_text_no_correction(self):
        assert contains_correction("Tell me about the weather") is False

    def test_empty_string(self):
        assert contains_correction("") is False

    def test_chinese_you_wu(self):
        assert contains_correction("这个信息有误") is True


class TestCorrectionRecordDataclass:
    """Test the frozen CorrectionRecord value object."""

    def test_creation(self):
        record = CorrectionRecord(
            id="abc",
            user_id="u1",
            family_id="f1",
            original_text="Birthday is June",
            corrected_text="Birthday is July",
        )
        assert record.original_text == "Birthday is June"
        assert record.corrected_text == "Birthday is July"
        assert record.is_surfaced is False

    def test_frozen(self):
        record = CorrectionRecord(
            id="abc",
            user_id="u1",
            family_id="f1",
            original_text="X",
            corrected_text="Y",
        )
        with pytest.raises(AttributeError):
            record.original_text = "hacked"


class TestRecordCorrection:
    """Test record_correction (no DB)."""

    @pytest.mark.asyncio
    async def test_record_without_db(self):
        uid = uuid4()
        fid = uuid4()
        record = await record_correction(
            user_id=uid,
            family_id=fid,
            original="His birthday is June 5",
            corrected="His birthday is July 5",
            context="Talking about Dad",
        )
        assert record.user_id == str(uid)
        assert record.original_text == "His birthday is June 5"
        assert record.corrected_text == "His birthday is July 5"
        assert record.context == "Talking about Dad"
        assert record.is_surfaced is False
        assert record.created_at is not None

    @pytest.mark.asyncio
    async def test_record_with_mock_db(self):
        uid = uuid4()
        fid = uuid4()
        mock_db = AsyncMock()

        record = await record_correction(
            user_id=uid,
            family_id=fid,
            original="Wrong name",
            corrected="Right name",
            db=mock_db,
        )
        assert record.corrected_text == "Right name"
        mock_db.add.assert_called_once()
        mock_db.flush.assert_called_once()


class TestGetPendingRepairs:
    """Test get_pending_repairs with mock DB."""

    @pytest.mark.asyncio
    async def test_returns_empty_on_error(self):
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB error")

        result = await get_pending_repairs(uuid4(), mock_db)
        assert result == []

    @pytest.mark.asyncio
    async def test_returns_correction_records(self):
        uid = uuid4()
        fid = uuid4()
        rid = uuid4()

        mock_row = MagicMock()
        mock_row.id = rid
        mock_row.user_id = uid
        mock_row.family_id = fid
        mock_row.original_text = "Old"
        mock_row.corrected_text = "New"
        mock_row.context = "ctx"
        mock_row.is_surfaced = False
        mock_row.created_at = None

        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [mock_row]

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        records = await get_pending_repairs(uid, mock_db)
        assert len(records) == 1
        assert records[0].original_text == "Old"
        assert records[0].corrected_text == "New"


class TestAcknowledgeRepair:
    """Test acknowledge_repair."""

    @pytest.mark.asyncio
    async def test_acknowledge_found(self):
        mock_log = MagicMock()
        mock_log.is_surfaced = False
        mock_log.surfaced_at = None

        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_log

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await acknowledge_repair(uuid4(), mock_db)
        assert result is True
        assert mock_log.is_surfaced is True
        assert mock_log.surfaced_at is not None

    @pytest.mark.asyncio
    async def test_acknowledge_not_found(self):
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None

        mock_db = AsyncMock()
        mock_db.execute.return_value = mock_result

        result = await acknowledge_repair(uuid4(), mock_db)
        assert result is False

    @pytest.mark.asyncio
    async def test_acknowledge_db_error(self):
        mock_db = AsyncMock()
        mock_db.execute.side_effect = Exception("DB down")

        result = await acknowledge_repair(uuid4(), mock_db)
        assert result is False


class TestFormatRepairMention:
    """Test format_repair_mention."""

    def test_format(self):
        record = CorrectionRecord(
            id="abc",
            user_id="u1",
            family_id="f1",
            original_text="Birthday is June",
            corrected_text="Birthday is July",
        )
        text = format_repair_mention(record)
        assert "June" in text
        assert "July" in text
        assert "corrected" in text


class TestCorrectionLogModel:
    """Test CorrectionLog ORM model."""

    def test_tablename(self):
        assert CorrectionLog.__tablename__ == "correction_logs"

    def test_to_dict(self):
        log = CorrectionLog(
            id=uuid4(),
            user_id=uuid4(),
            family_id=uuid4(),
            original_text="A",
            corrected_text="B",
            context="ctx",
            is_surfaced=False,
        )
        d = log.to_dict()
        assert d["original_text"] == "A"
        assert d["corrected_text"] == "B"
        assert d["is_surfaced"] is False
