"""Tests for chat history pagination API (GET /chat/history).

Covers:
- before_id pagination cursor behaviour
- has_more field correctness
- Cross-user session 404 enforcement
- Invalid UUID before_id returns 400
"""

from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.v1.chat import router as chat_router
from src.db.session import get_db
from src.core.auth import get_current_user, get_current_family


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TEST_USER_ID = uuid4()
_TEST_FAMILY_ID = uuid4()
_OTHER_USER_ID = uuid4()


def _mock_message(msg_id=None, session_id=None, role="user", content="hello"):
    m = MagicMock()
    m.id = msg_id or uuid4()
    m.session_id = session_id or uuid4()
    m.role = role
    m.content = content
    m.to_dict = MagicMock(return_value={
        "id": str(m.id),
        "session_id": str(m.session_id),
        "role": role,
        "content": content,
    })
    return m


def _mock_session(session_id=None, user_id=None):
    s = MagicMock()
    s.id = session_id or uuid4()
    s.user_id = user_id or _TEST_USER_ID
    return s


class _FakeScalarsResult:
    def __init__(self, items):
        self._items = items

    def all(self):
        return self._items


class _FakeResult:
    def __init__(self, items=None, scalar_value=None):
        self._items = items or []
        self._scalar_value = scalar_value

    def scalars(self):
        return _FakeScalarsResult(self._items)

    def scalar_one_or_none(self):
        return self._items[0] if self._items else None

    def scalar(self):
        return self._scalar_value


class _FakeDB:
    """Async DB session mock returning scripted results in call order."""

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

    Note: chat_router already has prefix="/chat" set internally, so no extra
    prefix is added here.
    """
    app = FastAPI()
    app.include_router(chat_router)

    uid = user_id or _TEST_USER_ID
    fid = family_id or _TEST_FAMILY_ID

    app.dependency_overrides[get_db] = lambda: db_instance
    app.dependency_overrides[get_current_user] = lambda: uid
    app.dependency_overrides[get_current_family] = lambda: fid

    return app


# MessageService is imported from the conversation package __init__:
#   from ...modules.conversation import SessionService, MessageService
# The local import in the route function re-binds each call, so we patch at
# the package-level name that the route's `from` import resolves against.
_MSG_SVC_PATH = "src.modules.conversation.MessageService"


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestChatHistoryBeforeIdPagination:
    def test_before_id_pagination_returns_correct_page(self):
        """Paginating with before_id of the 3rd message returns only the 2 preceding it."""
        session_id = uuid4()
        msg_ids = [uuid4() for _ in range(5)]
        page_messages = [
            _mock_message(msg_id=msg_ids[0], session_id=session_id),
            _mock_message(msg_id=msg_ids[1], session_id=session_id),
        ]
        session = _mock_session(session_id=session_id)

        mock_msg_svc_instance = MagicMock()
        mock_msg_svc_instance.get_history = AsyncMock(return_value=(page_messages, False))
        mock_msg_svc_class = MagicMock(return_value=mock_msg_svc_instance)

        db = _FakeDB([_FakeResult(items=[session])])
        app = _create_test_app(db)

        with (
            patch("src.api.v1.chat.settings") as mock_settings,
            patch(_MSG_SVC_PATH, mock_msg_svc_class),
        ):
            mock_settings.claude_agent_enabled = True
            mock_settings.anthropic_api_key = "test-key"
            client = TestClient(app)
            resp = client.get(
                f"/chat/history?session_id={session_id}&before_id={msg_ids[2]}&limit=2"
            )

        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 2
        assert data["items"][0]["id"] == str(msg_ids[0])
        assert data["items"][1]["id"] == str(msg_ids[1])
        assert data["has_more"] is False

    def test_has_more_true_when_more_messages_exist(self):
        """With limit=2 and more messages available, has_more must be True."""
        session_id = uuid4()
        two_messages = [
            _mock_message(session_id=session_id),
            _mock_message(session_id=session_id),
        ]
        session = _mock_session(session_id=session_id)

        mock_msg_svc_instance = MagicMock()
        mock_msg_svc_instance.get_history = AsyncMock(return_value=(two_messages, True))
        mock_msg_svc_class = MagicMock(return_value=mock_msg_svc_instance)

        db = _FakeDB([_FakeResult(items=[session])])
        app = _create_test_app(db)

        with (
            patch("src.api.v1.chat.settings") as mock_settings,
            patch(_MSG_SVC_PATH, mock_msg_svc_class),
        ):
            mock_settings.claude_agent_enabled = True
            mock_settings.anthropic_api_key = "test-key"
            client = TestClient(app)
            resp = client.get(f"/chat/history?session_id={session_id}&limit=2")

        assert resp.status_code == 200
        data = resp.json()
        assert data["has_more"] is True
        assert len(data["items"]) == 2

    def test_has_more_false_when_all_messages_fit(self):
        """With limit=3 and exactly 3 messages, has_more must be False."""
        session_id = uuid4()
        three_messages = [_mock_message(session_id=session_id) for _ in range(3)]
        session = _mock_session(session_id=session_id)

        mock_msg_svc_instance = MagicMock()
        mock_msg_svc_instance.get_history = AsyncMock(return_value=(three_messages, False))
        mock_msg_svc_class = MagicMock(return_value=mock_msg_svc_instance)

        db = _FakeDB([_FakeResult(items=[session])])
        app = _create_test_app(db)

        with (
            patch("src.api.v1.chat.settings") as mock_settings,
            patch(_MSG_SVC_PATH, mock_msg_svc_class),
        ):
            mock_settings.claude_agent_enabled = True
            mock_settings.anthropic_api_key = "test-key"
            client = TestClient(app)
            resp = client.get(f"/chat/history?session_id={session_id}&limit=3")

        assert resp.status_code == 200
        data = resp.json()
        assert data["has_more"] is False
        assert len(data["items"]) == 3


class TestChatHistoryCrossUserAccess:
    def test_cross_user_session_returns_404(self):
        """Session owned by another user must return 404."""
        session_id = uuid4()
        # DB returns nothing: session+user_id predicate finds no match
        db = _FakeDB([_FakeResult(items=[])])
        app = _create_test_app(db, user_id=_OTHER_USER_ID)

        with patch("src.api.v1.chat.settings") as mock_settings:
            mock_settings.claude_agent_enabled = True
            mock_settings.anthropic_api_key = "test-key"
            client = TestClient(app)
            resp = client.get(f"/chat/history?session_id={session_id}")

        assert resp.status_code == 404
        assert "not found" in resp.json()["detail"].lower()


class TestChatHistoryInvalidUuid:
    def test_before_id_invalid_uuid_returns_400(self):
        """A non-UUID before_id must produce a 400 Bad Request."""
        session_id = uuid4()
        session = _mock_session(session_id=session_id)
        db = _FakeDB([_FakeResult(items=[session])])
        app = _create_test_app(db)

        with patch("src.api.v1.chat.settings") as mock_settings:
            mock_settings.claude_agent_enabled = True
            mock_settings.anthropic_api_key = "test-key"
            client = TestClient(app)
            resp = client.get(
                f"/chat/history?session_id={session_id}&before_id=not-a-uuid"
            )

        assert resp.status_code == 400
        assert "before_id" in resp.json()["detail"].lower()
