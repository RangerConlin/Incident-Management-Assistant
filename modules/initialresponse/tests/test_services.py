from __future__ import annotations

import importlib
from pathlib import Path

import pytest


def _reload_initialresponse_modules():
    import utils.incident_context as incident_context

    importlib.reload(incident_context)
    from modules.initialresponse import repository
    from modules.initialresponse import services

    importlib.reload(repository)
    importlib.reload(services)
    return repository, services


@pytest.fixture
def initialresponse_modules(tmp_path, monkeypatch):
    monkeypatch.setenv("CHECKIN_DATA_DIR", str(tmp_path))
    repository, services = _reload_initialresponse_modules()

    from utils import incident_context

    incident_context.set_active_incident("TEST-INCIDENT")

    # Ensure the incident database directory exists for sqlite connections
    incident_dir = Path(tmp_path) / "incidents"
    incident_dir.mkdir(parents=True, exist_ok=True)
    return repository, services


def test_repository_persists_logistics_and_task_id(initialresponse_modules):
    repository, _ = initialresponse_modules
    from modules.initialresponse.models.records import HastyTaskRecord

    record = HastyTaskRecord(
        id=None,
        incident_id="",
        area="Sector 7",
        priority="High",
        notes="Power line assessment",
    )

    saved = repository.add_hasty_task(record)
    assert saved.id is not None

    repository.update_hasty_task_task_id(saved.id, operations_task_id=42)
    repository.update_hasty_task_logistics(saved.id, logistics_request_id="REQ-42")

    rows = repository.list_hasty_tasks()
    assert len(rows) == 1
    stored = rows[0]
    assert stored.operations_task_id == 42
    assert stored.logistics_request_id == "REQ-42"


def test_create_hasty_task_integration_flags(initialresponse_modules, monkeypatch):
    _, services = initialresponse_modules
    from modules.initialresponse.models import HastyTaskCreate

    monkeypatch.setattr(services, "_create_operations_task", lambda record: 77)
    monkeypatch.setattr(services, "_create_logistics_request", lambda record: "LOG-9")

    result = services.create_hasty_task(
        HastyTaskCreate(
            area="Grid A1",
            priority="Critical",
            notes="Rapid sweep",
            create_task=True,
            request_logistics=False,
        )
    )

    assert result.operations_task_id == 77
    assert result.logistics_request_id == "LOG-9"

    rows = services.list_hasty_task_entries()
    assert rows[0].operations_task_id == 77
    assert rows[0].logistics_request_id == "LOG-9"


def test_create_reflex_action_stores_alert(initialresponse_modules, monkeypatch):
    _, services = initialresponse_modules
    from modules.initialresponse.models import ReflexActionCreate

    monkeypatch.setattr(
        services,
        "_emit_notification",
        lambda **kwargs: "ALERT-1",
    )

    result = services.create_reflex_action(
        ReflexActionCreate(trigger="Severe weather", action="Activate shelter", notify=True)
    )

    assert result.communications_alert_id == "ALERT-1"

    rows = services.list_reflex_action_entries()
    assert rows[0].communications_alert_id == "ALERT-1"
