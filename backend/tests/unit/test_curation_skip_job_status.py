from datetime import date
from types import SimpleNamespace
from uuid import uuid4

import pytest

from src.modules.curation.tasks import _curate_family_with_cooldown


class _FakeSkipSession:
    def __init__(self, job):
        self._job = job
        self.committed = False

    async def get(self, model, job_id):  # noqa: ARG002
        return self._job

    async def commit(self):
        self.committed = True


class _FakeSessionCtx:
    def __init__(self, session):
        self._session = session

    async def __aenter__(self):
        return self._session

    async def __aexit__(self, exc_type, exc, tb):  # noqa: ANN001, ARG002
        return False


@pytest.mark.asyncio
async def test_lock_held_marks_existing_job_skipped(monkeypatch):
    family_id = uuid4()
    job_id = uuid4()
    fake_job = SimpleNamespace(
        id=job_id,
        status="pending",
        started_at=None,
        completed_at=None,
        error_message=None,
    )
    fake_session = _FakeSkipSession(fake_job)

    monkeypatch.setattr(
        "src.modules.curation.tasks._acquire_curation_lock",
        lambda *_args, **_kwargs: False,
    )
    monkeypatch.setattr(
        "src.db.session.AsyncSessionLocal",
        lambda: _FakeSessionCtx(fake_session),
    )

    result = await _curate_family_with_cooldown(
        family_id=family_id,
        date_range=(date(2026, 2, 15), date(2026, 2, 15)),
        trigger_type="manual",
        respect_cooldown=False,
        existing_job_id=job_id,
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "lock_held"
    assert fake_job.status == "completed"
    assert fake_job.started_at is not None
    assert fake_job.completed_at is not None
    assert fake_job.error_message == "Skipped curation: lock_held"
    assert fake_session.committed is True
