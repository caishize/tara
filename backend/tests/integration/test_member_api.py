"""
Integration tests for Member Management API endpoints.
"""
import pytest
from httpx import AsyncClient


@pytest.mark.integration
@pytest.mark.asyncio
class TestMemberAPI:
    """Test cases for Member Management API."""

    async def test_health_check(self, async_client: AsyncClient):
        """Test health check endpoint."""
        response = await async_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "healthy"
        assert data["service"] == "Secretary"

    async def test_root_endpoint(self, async_client: AsyncClient):
        """Test root endpoint."""
        response = await async_client.get("/")
        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert "version" in data

    async def test_create_member(
        self,
        async_client: AsyncClient,
        test_family_id: str,
        test_user_id: str
    ):
        """Test POST /api/v1/members."""
        payload = {
            "family_id": test_family_id,
            "created_by": test_user_id,
            "name": "集成测试成员",
            "gender": "male",
            "phone": "13900139000"
        }

        response = await async_client.post("/api/v1/members/", json=payload)
        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "集成测试成员"
        assert "id" in data

    async def test_list_members(
        self,
        async_client: AsyncClient,
        test_family_id: str,
        test_user_id: str
    ):
        """Test GET /api/v1/members."""
        # Create a member first
        payload = {
            "family_id": test_family_id,
            "created_by": test_user_id,
            "name": "列表测试"
        }
        await async_client.post("/api/v1/members/", json=payload)

        # List members
        response = await async_client.get(
            f"/api/v1/members/?family_id={test_family_id}"
        )
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) >= 1

    async def test_get_member_by_id(
        self,
        async_client: AsyncClient,
        test_family_id: str,
        test_user_id: str
    ):
        """Test GET /api/v1/members/{id}."""
        # Create member
        payload = {
            "family_id": test_family_id,
            "created_by": test_user_id,
            "name": "获取测试"
        }
        create_response = await async_client.post("/api/v1/members/", json=payload)
        member_id = create_response.json()["id"]

        # Get member
        response = await async_client.get(f"/api/v1/members/{member_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == member_id
        assert data["name"] == "获取测试"

    async def test_update_member(
        self,
        async_client: AsyncClient,
        test_family_id: str,
        test_user_id: str
    ):
        """Test PUT /api/v1/members/{id}."""
        # Create member
        payload = {
            "family_id": test_family_id,
            "created_by": test_user_id,
            "name": "更新前"
        }
        create_response = await async_client.post("/api/v1/members/", json=payload)
        member_id = create_response.json()["id"]

        # Update member (MemberResponse only includes core fields, not occupation)
        update_payload = {"name": "更新后", "nickname": "小更"}
        response = await async_client.put(
            f"/api/v1/members/{member_id}",
            json=update_payload
        )
        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "更新后"
        assert data["nickname"] == "小更"

    async def test_delete_member(
        self,
        async_client: AsyncClient,
        test_family_id: str,
        test_user_id: str
    ):
        """Test DELETE /api/v1/members/{id}."""
        # Create member
        payload = {
            "family_id": test_family_id,
            "created_by": test_user_id,
            "name": "删除测试"
        }
        create_response = await async_client.post("/api/v1/members/", json=payload)
        member_id = create_response.json()["id"]

        # Delete member
        response = await async_client.delete(f"/api/v1/members/{member_id}")
        assert response.status_code == 204

        # Verify deletion
        get_response = await async_client.get(f"/api/v1/members/{member_id}")
        assert get_response.status_code == 404

    async def test_create_member_validation(
        self,
        async_client: AsyncClient
    ):
        """Test validation on member creation."""
        # Missing required field
        payload = {
            "family_id": "invalid-uuid"
            # Missing name
        }

        response = await async_client.post("/api/v1/members/", json=payload)
        assert response.status_code == 422  # Validation error
