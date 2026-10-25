from __future__ import annotations

from utils.audit import write_audit
from utils.state import AppState


def test_write_audit_can_emit_global_event(monkeypatch) -> None:
    from utils import api_client as api_client_module

    payloads: list[dict] = []
    monkeypatch.setattr(
        api_client_module.api_client,
        "post",
        lambda _path, *, json: payloads.append(json),
    )
    monkeypatch.setattr(AppState, "get_active_incident", lambda: "INC-123")

    write_audit("session.end", incident_scoped=False)

    assert payloads[0]["incident_id"] is None


def test_write_audit_scopes_to_active_incident_by_default(monkeypatch) -> None:
    from utils import api_client as api_client_module

    payloads: list[dict] = []
    monkeypatch.setattr(
        api_client_module.api_client,
        "post",
        lambda _path, *, json: payloads.append(json),
    )
    monkeypatch.setattr(AppState, "get_active_incident", lambda: "INC-456")

    write_audit("task.updated")

    assert payloads[0]["incident_id"] == "INC-456"
