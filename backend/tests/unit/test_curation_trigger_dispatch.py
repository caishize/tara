from datetime import date
from uuid import uuid4

from src.modules.curation.tasks import trigger_curation_async


def test_trigger_curation_async_passes_range_and_existing_job(monkeypatch):
    family_id = uuid4()
    job_id = uuid4()
    called = {}

    def _fake_delay(**kwargs):
        called.update(kwargs)

    monkeypatch.setattr(
        "src.modules.curation.tasks.curate_family_task.delay",
        _fake_delay,
    )

    dispatched = trigger_curation_async(
        family_id=family_id,
        trigger_type="manual",
        respect_cooldown=False,
        start_date=date(2026, 2, 15),
        end_date=date(2026, 2, 28),
        existing_job_id=job_id,
    )

    assert dispatched is True
    assert called["family_id"] == str(family_id)
    assert called["start_date"] == "2026-02-15"
    assert called["end_date"] == "2026-02-28"
    assert called["existing_job_id"] == str(job_id)
