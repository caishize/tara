"""
Unit tests for MemberService (new member module).
"""
import pytest
from uuid import UUID, uuid4
from sqlalchemy.ext.asyncio import AsyncSession

from src.modules.member.member_service import MemberService


@pytest.mark.unit
@pytest.mark.asyncio
class TestMemberService:
    """Test cases for MemberService."""

    @pytest.fixture
    async def member_service(self, db_session: AsyncSession):
        """Create MemberService instance with test dependencies."""
        return MemberService(db_session)

    @pytest.fixture
    def family_id(self, test_family_id: str):
        return test_family_id

    @pytest.fixture
    def user_id(self, test_user_id: str):
        return test_user_id

    async def _create(self, member_service, family_id, user_id, name, **kwargs):
        """Helper: create member with required created_by field."""
        return await member_service.create_member(
            family_id=family_id,
            name=name,
            created_by=UUID(user_id),
            **kwargs,
        )

    async def test_create_member_success(
        self, member_service, family_id, user_id
    ):
        """Test successful member creation."""
        member = await self._create(member_service, family_id, user_id, "张三")

        assert member is not None
        assert member.name == "张三"
        assert member.family_id == family_id
        assert member.id is not None

    async def test_create_member_with_relation(
        self, member_service, family_id, user_id
    ):
        """Test member creation with relation tag."""
        member = await member_service.create_member(
            family_id=family_id,
            name="李四",
            relation="spouse",
            created_by=UUID(user_id),
        )

        assert member is not None
        assert member.name == "李四"
        assert member.relation == "spouse"

    async def test_get_member_by_id(
        self, member_service, family_id, user_id
    ):
        """Test retrieving member by ID."""
        created = await self._create(member_service, family_id, user_id, "张三")
        member_id = created.id

        member = await member_service.get_member(member_id, family_id)

        assert member is not None
        assert member.id == member_id
        assert member.name == "张三"

    async def test_get_nonexistent_member(self, member_service, family_id):
        """Test retrieving non-existent member returns None."""
        member = await member_service.get_member(str(uuid4()), family_id)
        assert member is None

    async def test_list_members_by_family(
        self, member_service, family_id, user_id
    ):
        """Test listing all members in a family."""
        await self._create(member_service, family_id, user_id, "成员1")
        await self._create(member_service, family_id, user_id, "成员2")

        members = await member_service.list_members(family_id)

        assert len(members) == 2
        names = [m.name for m in members]
        assert "成员1" in names
        assert "成员2" in names

    async def test_update_member(
        self, member_service, family_id, user_id
    ):
        """Test updating member information."""
        created = await self._create(member_service, family_id, user_id, "张三")
        member_id = created.id

        updated = await member_service.update_member(
            member_id,
            family_id,
            {"name": "张三丰"},
        )

        assert updated is not None
        assert updated.name == "张三丰"

    async def test_delete_member(
        self, member_service, family_id, user_id
    ):
        """Test soft deleting a member."""
        created = await self._create(
            member_service, family_id, user_id, "删除测试",
        )
        member_id = created.id

        result = await member_service.delete_member(member_id, family_id)
        assert result is True

        member = await member_service.get_member(member_id, family_id)
        assert member is None
