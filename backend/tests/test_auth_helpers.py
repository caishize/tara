"""
Tests for auth_helpers — member ownership verification.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from uuid import uuid4, UUID

from fastapi import HTTPException


class FakeMember:
    """Lightweight stand-in for the Member ORM model."""
    def __init__(self, id: UUID, family_id: UUID):
        self.id = id
        self.family_id = family_id


@pytest.fixture
def mock_db():
    """Create a mock async DB session."""
    db = AsyncMock()
    return db


def _make_result(member):
    """Wrap a member into a mock execute result."""
    result = MagicMock()
    result.scalar_one_or_none.return_value = member
    return result


class TestVerifyMemberBelongsToFamily:
    """Tests for verify_member_belongs_to_family."""

    @pytest.mark.asyncio
    async def test_member_belongs_to_family(self, mock_db):
        """Should return the member when it belongs to the family."""
        from src.core.auth.auth_helpers import verify_member_belongs_to_family

        family_id = uuid4()
        member_id = uuid4()
        member = FakeMember(id=member_id, family_id=family_id)

        mock_db.execute.return_value = _make_result(member)

        result = await verify_member_belongs_to_family(member_id, family_id, mock_db)
        assert result.id == member_id
        assert result.family_id == family_id

    @pytest.mark.asyncio
    async def test_member_not_found(self, mock_db):
        """Should raise 404 when member does not exist."""
        from src.core.auth.auth_helpers import verify_member_belongs_to_family

        mock_db.execute.return_value = _make_result(None)

        with pytest.raises(HTTPException) as exc_info:
            await verify_member_belongs_to_family(uuid4(), uuid4(), mock_db)
        assert exc_info.value.status_code == 404

    @pytest.mark.asyncio
    async def test_member_wrong_family(self, mock_db):
        """Should raise 403 when member belongs to a different family."""
        from src.core.auth.auth_helpers import verify_member_belongs_to_family

        member_family = uuid4()
        request_family = uuid4()
        member_id = uuid4()
        member = FakeMember(id=member_id, family_id=member_family)

        mock_db.execute.return_value = _make_result(member)

        with pytest.raises(HTTPException) as exc_info:
            await verify_member_belongs_to_family(member_id, request_family, mock_db)
        assert exc_info.value.status_code == 403
        assert "does not belong to your family" in exc_info.value.detail


class TestHealthRouteRegistration:
    """Verify that health module sub-routes are registered in main.py.

    Note: Health module was deleted in Sprint 2 stub cleanup. These tests
    now verify the routers are NOT present (since the module is gone).
    """

    def test_health_module_removed(self):
        """Health module sub-routers should NOT be in main.py (module deleted)."""
        with open("src/main.py") as f:
            content = f.read()

        deleted_routers = [
            "health_profile_router",
            "health_record_router",
            "health_goal_router",
            "vital_signs_router",
            "medication_router",
            "checkup_report_router",
        ]
        for router_name in deleted_routers:
            assert router_name not in content, (
                f"Deleted health sub-router {router_name} still in main.py"
            )


class TestUnusedInterfacesDeleted:
    """Verify that unused interface files have been removed."""

    @pytest.mark.parametrize("filename", [
        "src/core/interfaces/vector_db_provider.py",
        "src/core/interfaces/vector_db.py",
        "src/core/interfaces/insurance_api.py",
        "src/core/interfaces/traffic_api.py",
        "src/core/interfaces/nutrition_service.py",
        "src/core/interfaces/asr_provider.py",
        "src/core/interfaces/vector_database.py",
        "src/core/interfaces/browser_operation.py",
        "src/core/interfaces/ocr_provider.py",
        "src/core/interfaces/price_service_provider.py",
    ])
    def test_unused_interface_deleted(self, filename):
        """Unused interface files should not exist."""
        import os
        assert not os.path.exists(filename), (
            f"Unused interface file {filename} should have been deleted"
        )

    @pytest.mark.parametrize("filename", [
        "src/core/interfaces/llm_provider.py",
        "src/core/interfaces/encryption.py",
        "src/core/interfaces/notification_provider.py",
        "src/core/interfaces/mcp_provider.py",
        "src/core/interfaces/permission.py",
        "src/core/interfaces/data_connector.py",
        "src/core/interfaces/lunar_calendar_provider.py",
    ])
    def test_used_interface_preserved(self, filename):
        """Interface files that are still imported should be preserved."""
        import os
        assert os.path.exists(filename), (
            f"Used interface file {filename} should NOT have been deleted"
        )
