"""Tests for Secretary Notes CRUD API (/api/v1/notes/*).

Covers:
- List notes with filtering (category, status, pagination)
- Get single note
- Create manual note
- Update note (PUT - title, content, category, priority, trigger_keywords)
- Partial update note (PATCH)
- Archive (soft-delete) note
- Confirm note accuracy
- Auth enforcement (ownership verification via Depends)
- Version increment on content/title changes
- Response schema includes updated_at
"""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from uuid import uuid4, UUID

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.v1.notes import router as notes_router, get_db, get_current_user, get_current_family


# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

_TEST_USER_ID = uuid4()
_TEST_FAMILY_ID = uuid4()


def _mock_note(
    note_id=None,
    user_id=None,
    family_id=None,
    category="preference",
    title="Test Note",
    content="Test content",
    status="active",
    confidence=0.8,
    priority=5,
    version=1,
    is_user_confirmed=False,
    life_type="permanent",
    valid_until=None,
    observation_count=1,
    trigger_keywords=None,
    created_at=None,
    updated_at=None,
    superseded_by=None,
    contradiction_flags=None,
):
    note = MagicMock()
    note.id = note_id or uuid4()
    note.user_id = user_id or _TEST_USER_ID
    note.family_id = family_id or _TEST_FAMILY_ID
    note.category = category
    note.title = title
    note.content = content
    note.status = status
    note.confidence = confidence
    note.priority = priority
    note.version = version
    note.is_user_confirmed = is_user_confirmed
    note.life_type = life_type
    note.valid_until = valid_until
    note.observation_count = observation_count
    note.trigger_keywords = trigger_keywords or []
    note.created_at = created_at
    note.updated_at = updated_at
    note.superseded_by = superseded_by
    note.contradiction_flags = contradiction_flags
    note.increment_version = MagicMock()
    return note


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
    """Minimal async DB session mock that returns scripted results."""

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
    """Create a test FastAPI app with dependency overrides."""
    app = FastAPI()
    app.include_router(notes_router, prefix="/api/v1")

    uid = user_id or _TEST_USER_ID
    fid = family_id or _TEST_FAMILY_ID

    app.dependency_overrides[get_db] = lambda: db_instance
    app.dependency_overrides[get_current_user] = lambda: uid
    app.dependency_overrides[get_current_family] = lambda: fid

    return app, uid, fid


# ---------------------------------------------------------------------------
# Tests: List notes
# ---------------------------------------------------------------------------


class TestListNotes:
    def test_list_notes_returns_notes(self):
        note = _mock_note()
        db = _FakeDB([
            _FakeResult(items=[note]),
            _FakeResult(scalar_value=1),
        ])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.get("/api/v1/notes")

        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 1
        assert len(data["notes"]) == 1
        assert data["notes"][0]["title"] == "Test Note"

    def test_list_notes_filter_by_category(self):
        note = _mock_note(category="routine")
        db = _FakeDB([
            _FakeResult(items=[note]),
            _FakeResult(scalar_value=1),
        ])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.get("/api/v1/notes?category=routine")

        assert resp.status_code == 200
        assert resp.json()["notes"][0]["category"] == "routine"

    def test_list_notes_invalid_category_returns_400(self):
        db = _FakeDB([])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.get("/api/v1/notes?category=invalid_cat")

        assert resp.status_code == 400

    def test_list_notes_invalid_status_returns_400(self):
        db = _FakeDB([])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.get("/api/v1/notes?status=invalid_status")

        assert resp.status_code == 400

    def test_list_notes_empty(self):
        db = _FakeDB([
            _FakeResult(items=[]),
            _FakeResult(scalar_value=0),
        ])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.get("/api/v1/notes")

        assert resp.status_code == 200
        assert resp.json()["total"] == 0
        assert resp.json()["notes"] == []


# ---------------------------------------------------------------------------
# Tests: Get single note
# ---------------------------------------------------------------------------


class TestGetNote:
    def test_get_note_found(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id)
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.get(f"/api/v1/notes/{note_id}")

        assert resp.status_code == 200
        assert resp.json()["id"] == str(note_id)

    def test_get_note_not_found(self):
        db = _FakeDB([_FakeResult(items=[])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.get(f"/api/v1/notes/{uuid4()}")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Create note
# ---------------------------------------------------------------------------


class TestCreateNote:
    def test_create_note_success(self):
        note_id = uuid4()
        created_note = _mock_note(
            note_id=note_id,
            category="preference",
            title="Aisle seat",
            content="User prefers aisle seats on flights",
            confidence=1.0,
            is_user_confirmed=True,
        )
        db = _FakeDB([])
        app, uid, fid = _create_test_app(db)

        mock_service = MagicMock()
        mock_service.create_note = AsyncMock(return_value=created_note)

        with patch("src.api.v1.notes.SecretaryNoteService", return_value=mock_service):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/notes",
                json={
                    "category": "preference",
                    "title": "Aisle seat",
                    "content": "User prefers aisle seats on flights",
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["id"] == str(note_id)
        assert data["category"] == "preference"
        assert data["title"] == "Aisle seat"

        mock_service.create_note.assert_called_once_with(
            user_id=uid,
            family_id=fid,
            category="preference",
            title="Aisle seat",
            content="User prefers aisle seats on flights",
            trigger_keywords=None,
            priority=5,
        )

    def test_create_note_with_keywords_and_priority(self):
        note_id = uuid4()
        created_note = _mock_note(
            note_id=note_id,
            category="important",
            title="Nut allergy",
            content="Dad is allergic to peanuts",
            trigger_keywords=["allergy", "food", "peanut"],
            priority=9,
            confidence=1.0,
            is_user_confirmed=True,
        )
        db = _FakeDB([])
        app, uid, fid = _create_test_app(db)

        mock_service = MagicMock()
        mock_service.create_note = AsyncMock(return_value=created_note)

        with patch("src.api.v1.notes.SecretaryNoteService", return_value=mock_service):
            client = TestClient(app)
            resp = client.post(
                "/api/v1/notes",
                json={
                    "category": "important",
                    "title": "Nut allergy",
                    "content": "Dad is allergic to peanuts",
                    "trigger_keywords": ["allergy", "food", "peanut"],
                    "priority": 9,
                },
            )

        assert resp.status_code == 201
        data = resp.json()
        assert data["priority"] == 9
        assert "allergy" in data["trigger_keywords"]

    def test_create_note_invalid_category_returns_400(self):
        db = _FakeDB([])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/notes",
            json={
                "category": "bogus",
                "title": "Test",
                "content": "Test content",
            },
        )

        assert resp.status_code == 400
        assert "Invalid category" in resp.json()["detail"]

    def test_create_note_missing_title_returns_422(self):
        db = _FakeDB([])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/notes",
            json={
                "category": "preference",
                "content": "Some content",
            },
        )

        assert resp.status_code == 422

    def test_create_note_missing_content_returns_422(self):
        db = _FakeDB([])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/notes",
            json={
                "category": "preference",
                "title": "Some title",
            },
        )

        assert resp.status_code == 422

    def test_create_note_priority_out_of_range_returns_422(self):
        db = _FakeDB([])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.post(
            "/api/v1/notes",
            json={
                "category": "preference",
                "title": "Test",
                "content": "Test content",
                "priority": 11,
            },
        )

        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Tests: Update note (PUT)
# ---------------------------------------------------------------------------


class TestUpdateNote:
    def test_update_title_increments_version(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id, version=1)
        updated_note = _mock_note(note_id=note_id, title="Updated Title", version=2)
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)

        mock_service = MagicMock()
        mock_service.update_note = AsyncMock(return_value=updated_note)

        with patch("src.api.v1.notes.SecretaryNoteService", return_value=mock_service):
            client = TestClient(app)
            resp = client.put(
                f"/api/v1/notes/{note_id}",
                json={"title": "Updated Title"},
            )

        assert resp.status_code == 200
        note.increment_version.assert_called_once()

    def test_update_content_increments_version(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id, version=1)
        updated_note = _mock_note(note_id=note_id, content="New content", version=2)
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)

        mock_service = MagicMock()
        mock_service.update_note = AsyncMock(return_value=updated_note)

        with patch("src.api.v1.notes.SecretaryNoteService", return_value=mock_service):
            client = TestClient(app)
            resp = client.put(
                f"/api/v1/notes/{note_id}",
                json={"content": "New content"},
            )

        assert resp.status_code == 200
        note.increment_version.assert_called_once()

    def test_update_priority_does_not_increment_version(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id, version=1)
        updated_note = _mock_note(note_id=note_id, priority=8, version=1)
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)

        mock_service = MagicMock()
        mock_service.update_note = AsyncMock(return_value=updated_note)

        with patch("src.api.v1.notes.SecretaryNoteService", return_value=mock_service):
            client = TestClient(app)
            resp = client.put(
                f"/api/v1/notes/{note_id}",
                json={"priority": 8},
            )

        assert resp.status_code == 200
        note.increment_version.assert_not_called()

    def test_update_not_found(self):
        db = _FakeDB([_FakeResult(items=[])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.put(
            f"/api/v1/notes/{uuid4()}",
            json={"title": "X"},
        )

        assert resp.status_code == 404

    def test_update_empty_body_returns_unchanged(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id)
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.put(
            f"/api/v1/notes/{note_id}",
            json={},
        )

        assert resp.status_code == 200
        assert resp.json()["id"] == str(note_id)

    def test_update_category_validates(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id)
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.put(
            f"/api/v1/notes/{note_id}",
            json={"category": "invalid_cat"},
        )

        assert resp.status_code == 400
        assert "Invalid category" in resp.json()["detail"]

    def test_update_category_accepted(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id, category="preference")
        updated_note = _mock_note(note_id=note_id, category="routine")
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)

        mock_service = MagicMock()
        mock_service.update_note = AsyncMock(return_value=updated_note)

        with patch("src.api.v1.notes.SecretaryNoteService", return_value=mock_service):
            client = TestClient(app)
            resp = client.put(
                f"/api/v1/notes/{note_id}",
                json={"category": "routine"},
            )

        assert resp.status_code == 200
        assert resp.json()["category"] == "routine"


# ---------------------------------------------------------------------------
# Tests: Partial update note (PATCH)
# ---------------------------------------------------------------------------


class TestPatchNote:
    def test_patch_content_only(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id, content="Old content")
        updated_note = _mock_note(note_id=note_id, content="New content", version=2)
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)

        mock_service = MagicMock()
        mock_service.update_note = AsyncMock(return_value=updated_note)

        with patch("src.api.v1.notes.SecretaryNoteService", return_value=mock_service):
            client = TestClient(app)
            resp = client.patch(
                f"/api/v1/notes/{note_id}",
                json={"content": "New content"},
            )

        assert resp.status_code == 200
        assert resp.json()["content"] == "New content"
        note.increment_version.assert_called_once()

    def test_patch_not_found(self):
        db = _FakeDB([_FakeResult(items=[])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.patch(
            f"/api/v1/notes/{uuid4()}",
            json={"content": "X"},
        )

        assert resp.status_code == 404

    def test_patch_category_change(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id, category="preference")
        updated_note = _mock_note(note_id=note_id, category="important")
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)

        mock_service = MagicMock()
        mock_service.update_note = AsyncMock(return_value=updated_note)

        with patch("src.api.v1.notes.SecretaryNoteService", return_value=mock_service):
            client = TestClient(app)
            resp = client.patch(
                f"/api/v1/notes/{note_id}",
                json={"category": "important"},
            )

        assert resp.status_code == 200
        assert resp.json()["category"] == "important"


# ---------------------------------------------------------------------------
# Tests: Archive note
# ---------------------------------------------------------------------------


class TestArchiveNote:
    def test_archive_note_success(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id)
        archived_note = _mock_note(note_id=note_id, status="archived")
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)

        mock_service = MagicMock()
        mock_service.archive_note = AsyncMock(return_value=archived_note)

        with patch("src.api.v1.notes.SecretaryNoteService", return_value=mock_service):
            client = TestClient(app)
            resp = client.delete(f"/api/v1/notes/{note_id}")

        assert resp.status_code == 200
        assert resp.json()["status"] == "archived"

    def test_archive_not_found(self):
        db = _FakeDB([_FakeResult(items=[])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.delete(f"/api/v1/notes/{uuid4()}")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Confirm note
# ---------------------------------------------------------------------------


class TestConfirmNote:
    def test_confirm_note_success(self):
        note_id = uuid4()
        note = _mock_note(note_id=note_id)
        confirmed_note = _mock_note(
            note_id=note_id, is_user_confirmed=True, confidence=1.0,
        )
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)

        mock_service = MagicMock()
        mock_service.confirm_note = AsyncMock(return_value=confirmed_note)

        with patch("src.api.v1.notes.SecretaryNoteService", return_value=mock_service):
            client = TestClient(app)
            resp = client.post(f"/api/v1/notes/{note_id}/confirm")

        assert resp.status_code == 200
        data = resp.json()
        assert data["is_user_confirmed"] is True
        assert data["confidence"] == 1.0

    def test_confirm_not_found(self):
        db = _FakeDB([_FakeResult(items=[])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.post(f"/api/v1/notes/{uuid4()}/confirm")

        assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Tests: Response schema
# ---------------------------------------------------------------------------


class TestNoteResponseFormat:
    def test_response_includes_all_fields(self):
        note_id = uuid4()
        note = _mock_note(
            note_id=note_id,
            category="important",
            title="Health Info",
            content="Allergic to peanuts",
            confidence=0.95,
            is_user_confirmed=True,
            priority=9,
            version=3,
            trigger_keywords=["allergy", "food"],
        )
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.get(f"/api/v1/notes/{note_id}")

        data = resp.json()
        assert data["category"] == "important"
        assert data["title"] == "Health Info"
        assert data["content"] == "Allergic to peanuts"
        assert data["confidence"] == 0.95
        assert data["is_user_confirmed"] is True
        assert data["priority"] == 9
        assert data["version"] == 3
        assert "allergy" in data["trigger_keywords"]

    def test_response_includes_updated_at(self):
        from datetime import datetime, timezone

        note_id = uuid4()
        ts = datetime(2026, 2, 18, 12, 0, 0, tzinfo=timezone.utc)
        note = _mock_note(note_id=note_id, created_at=ts, updated_at=ts)
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.get(f"/api/v1/notes/{note_id}")

        data = resp.json()
        assert "updated_at" in data
        assert data["updated_at"] is not None
        assert "created_at" in data
        assert data["created_at"] is not None

    def test_response_includes_life_type_and_valid_until(self):
        note_id = uuid4()
        note = _mock_note(
            note_id=note_id,
            life_type="transient",
            valid_until=MagicMock(isoformat=lambda: "2026-03-18T00:00:00+00:00"),
        )
        db = _FakeDB([_FakeResult(items=[note])])
        app, uid, fid = _create_test_app(db)
        client = TestClient(app)
        resp = client.get(f"/api/v1/notes/{note_id}")

        data = resp.json()
        assert data["life_type"] == "transient"
        assert data["valid_until"] is not None
