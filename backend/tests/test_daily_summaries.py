"""Tests for daily summaries API (GET /chat/daily-summaries).

Covers:
- Empty array returned gracefully when no summaries cached
- 404 returned when session is not found (or belongs to another user)
"""

from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.v1.chat import router as chat_router
from src.db.session import get_db
from src.core.auth import get_current_user, get_current_family


# ---------------------------------------------------------------------------
# Helpers (mirror the pattern in test_chat_history_pagination.py)
# ---------------------------------------------------------------------------

_TEST_USER_ID = uuid4()
_TEST_FAMILY_ID = uuid4()


def _mock_session(session_id=None, user_id=None):
    s = MagicMock()
    s.id = session_id or uuid4()
    s.user_id = user_id or _TEST_USER_ID
    return s


class _FakeResult:
    def __init__(self, items=None):
        self._items = items or []

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None


class _FakeDB:
    def __init__(self, results=None):
        self._results = list(results or [])
        self._call_idx = 0

    async def execute(self, stmt):
        if self._call_idx < len(self._results):
            result = self._results[self._call_idx]
            self._call_idx += 1
            return result
        return _FakeResult()

    async def commit(self):
        pass

    async def refresh(self, obj):
        pass

    def add(self, obj):
        pass


def _create_test_app(db_instance, user_id=None, family_id=None):
    """Create a test FastAPI app with dependency overrides for the chat router.

    Note: chat_router already has prefix="/chat" set internally.
    """
    app = FastAPI()
    app.include_router(chat_router)

    uid = user_id or _TEST_USER_ID
    fid = family_id or _TEST_FAMILY_ID

    app.dependency_overrides[get_db] = lambda: db_instance
    app.dependency_overrides[get_current_user] = lambda: uid
    app.dependency_overrides[get_current_family] = lambda: fid

    return app


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestDailySummaries:
    def test_returns_empty_array_gracefully_when_no_summaries(self):
        """When a valid session exists but has no cached summaries, return []."""
        session_id = uuid4()
        session = _mock_session(session_id=session_id)
        db = _FakeDB([_FakeResult(items=[session])])
        app = _create_test_app(db)

        mock_svc_instance = MagicMock()
        mock_svc_instance.get_summaries = AsyncMock(return_value=[])
        mock_svc_class = MagicMock(return_value=mock_svc_instance)

        with (
            patch("src.api.v1.chat.settings") as mock_settings,
            patch(
                "src.modules.conversation.daily_summary_service.DailySummaryService",
                mock_svc_class,
            ),
        ):
            mock_settings.claude_agent_enabled = True
            mock_settings.anthropic_api_key = "test-key"
            client = TestClient(app)
            resp = client.get(f"/chat/daily-summaries?session_id={session_id}")

        assert resp.status_code == 200
        assert resp.json() == []

    def test_session_not_found_returns_404(self):
        """A non-existent (or other user's) session_id must return 404."""
        nonexistent_session_id = uuid4()
        db = _FakeDB([_FakeResult(items=[])])  # scalar_one_or_none() → None
        app = _create_test_app(db)

        with patch("src.api.v1.chat.settings") as mock_settings:
            mock_settings.claude_agent_enabled = True
            mock_settings.anthropic_api_key = "test-key"
            client = TestClient(app)
            resp = client.get(
                f"/chat/daily-summaries?session_id={nonexistent_session_id}"
            )

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()
