"""
Unit tests for DateService.
"""
import pytest
from uuid import uuid4
from datetime import date, timedelta
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.date_manager.date_service import DateService


@pytest.mark.unit
@pytest.mark.asyncio
class TestDateService:
    """Test cases for DateService."""

    @pytest.fixture
    async def date_service(self, db_session: AsyncSession):
        """Create DateService instance with test dependencies."""
        return DateService(db_session)

    @pytest.fixture
    def sample_date_data(self, test_family_id: str, test_user_id: str):
        """Sample date data for testing."""
        return {
            "family_id": test_family_id,
            "created_by": test_user_id,
            "title": "妈妈生日",
            "date_type": "birthday",
            "date_value": date(1960, 5, 20),
            "recurrence": "yearly",
            "reminder_days": [-30, -7, -3, 0],
        }

    async def test_create_date_success(
        self,
        date_service: DateService,
        sample_date_data: dict,
    ):
        """Test successfully creating an important date."""
        result = await date_service.create_date(**sample_date_data)

        assert result is not None
        assert result.title == "妈妈生日"
        assert result.date_type == "birthday"
        assert result.is_recurring is True
        assert result.id is not None

    async def test_create_lunar_birthday(
        self,
        date_service: DateService,
        test_family_id: str,
        test_user_id: str,
    ):
        """Test creating a birthday with lunar flag."""
        result = await date_service.create_date(
            family_id=test_family_id,
            created_by=test_user_id,
            title="奶奶生日(农历)",
            date_type="birthday",
            date_value=date(1950, 3, 15),
            recurrence="yearly",
        )

        assert result is not None
        assert result.title == "奶奶生日(农历)"
        assert result.is_recurring is True

    async def test_get_upcoming_dates(
        self,
        date_service: DateService,
        test_family_id: str,
        test_user_id: str,
    ):
        """Test retrieving upcoming important dates."""
        today = date.today()

        # Add a past non-recurring date
        await date_service.create_date(
            family_id=test_family_id,
            created_by=test_user_id,
            title="过去的日期",
            date_type="anniversary",
            date_value=today - timedelta(days=100),
        )

        # Add an upcoming date
        await date_service.create_date(
            family_id=test_family_id,
            created_by=test_user_id,
            title="即将到来的日期",
            date_type="anniversary",
            date_value=today + timedelta(days=10),
        )

        # Add a far-future date
        await date_service.create_date(
            family_id=test_family_id,
            created_by=test_user_id,
            title="很远的日期",
            date_type="anniversary",
            date_value=today + timedelta(days=100),
        )

        # Get upcoming dates (next 30 days)
        upcoming = await date_service.get_upcoming_dates(test_family_id, days=30)

        titles = [u.title for u in upcoming]
        assert "即将到来的日期" in titles
        assert "很远的日期" not in titles

    async def test_get_upcoming_dates_supports_days_ahead_and_target_date(
        self,
        date_service: DateService,
        test_family_id: str,
        test_user_id: str,
    ):
        """Ensure insight-style kwargs work and are evaluated from target_date."""
        reference_date = date.today() + timedelta(days=30)

        await date_service.create_date(
            family_id=test_family_id,
            created_by=test_user_id,
            title="目标窗口内日期",
            date_type="anniversary",
            date_value=reference_date + timedelta(days=3),
        )
        await date_service.create_date(
            family_id=test_family_id,
            created_by=test_user_id,
            title="目标窗口外日期",
            date_type="anniversary",
            date_value=reference_date + timedelta(days=20),
        )

        upcoming = await date_service.get_upcoming_dates(
            test_family_id,
            days_ahead=7,
            target_date=reference_date,
        )

        titles = [u.title for u in upcoming]
        assert "目标窗口内日期" in titles
        assert "目标窗口外日期" not in titles

    async def test_list_dates_by_type(
        self,
        date_service: DateService,
        test_family_id: str,
        test_user_id: str,
    ):
        """Test filtering dates by type."""
        await date_service.create_date(
            family_id=test_family_id,
            created_by=test_user_id,
            title="生日1",
            date_type="birthday",
            date_value=date(1990, 1, 1),
        )

        await date_service.create_date(
            family_id=test_family_id,
            created_by=test_user_id,
            title="疫苗1",
            date_type="vaccine",
            date_value=date(2024, 6, 1),
        )

        birthdays = await date_service.list_dates(
            family_id=test_family_id,
            date_type="birthday",
        )

        assert len(birthdays) == 1
        assert birthdays[0].title == "生日1"

    async def test_delete_important_date(
        self,
        date_service: DateService,
        sample_date_data: dict,
        test_family_id: str,
    ):
        """Test deleting an important date."""
        created = await date_service.create_date(**sample_date_data)
        date_id = created.id

        result = await date_service.delete_date(date_id, test_family_id)
        assert result is True

        date_obj = await date_service.get_date(date_id, test_family_id)
        assert date_obj is None

    async def test_recurring_date_next_occurrence(
        self,
        date_service: DateService,
        test_family_id: str,
        test_user_id: str,
    ):
        """Test recurring date calculates next occurrence correctly."""
        result = await date_service.create_date(
            family_id=test_family_id,
            created_by=test_user_id,
            title="年度生日",
            date_type="birthday",
            date_value=date(1990, 5, 20),
            recurrence="yearly",
        )

        assert result.is_recurring is True

    async def test_member_association(
        self,
        date_service: DateService,
        test_family_id: str,
        test_user_id: str,
    ):
        """Test associating dates with specific members."""
        member_id = uuid4()

        result = await date_service.create_date(
            family_id=test_family_id,
            created_by=test_user_id,
            linked_member_id=str(member_id),
            title="小明生日",
            date_type="birthday",
            date_value=date(2010, 8, 15),
            recurrence="yearly",
        )

        assert result.linked_member_id == str(member_id)
