from __future__ import annotations

import modules.checklists.record_links as record_links


def _clear_registry(monkeypatch) -> None:
    monkeypatch.setattr(record_links, "_REGISTRY", {})


def test_describe_falls_back_when_no_handler_registered(monkeypatch) -> None:
    _clear_registry(monkeypatch)
    assert record_links.describe("INC1", "unregistered_type", "42") == "unregistered_type: 42"


def test_describe_uses_registered_handler(monkeypatch) -> None:
    _clear_registry(monkeypatch)
    record_links.register(
        "planned_schedule_item",
        record_links.RecordLinkHandler(type_label="Schedule Activity", resolve_label=lambda i, r: "Opening Ceremony"),
    )
    assert record_links.describe("INC1", "planned_schedule_item", "7") == "Schedule Activity: Opening Ceremony"


def test_describe_handles_resolver_failure_gracefully(monkeypatch) -> None:
    _clear_registry(monkeypatch)

    def _boom(incident_id, record_id):
        raise RuntimeError("deleted")

    record_links.register(
        "planned_schedule_item", record_links.RecordLinkHandler(type_label="Schedule Activity", resolve_label=_boom)
    )
    assert record_links.describe("INC1", "planned_schedule_item", "7") == "Schedule Activity: 7 (unavailable)"


def test_can_open_reflects_whether_handler_has_opener(monkeypatch) -> None:
    _clear_registry(monkeypatch)
    record_links.register(
        "planned_schedule_item",
        record_links.RecordLinkHandler(type_label="Schedule Activity", resolve_label=lambda i, r: r),
    )
    assert record_links.can_open("planned_schedule_item") is False

    record_links.register(
        "planned_schedule_item",
        record_links.RecordLinkHandler(
            type_label="Schedule Activity", resolve_label=lambda i, r: r, open_record=lambda i, r, p: None
        ),
    )
    assert record_links.can_open("planned_schedule_item") is True


def test_open_record_calls_registered_opener(monkeypatch) -> None:
    _clear_registry(monkeypatch)
    calls = []
    record_links.register(
        "planned_schedule_item",
        record_links.RecordLinkHandler(
            type_label="Schedule Activity",
            resolve_label=lambda i, r: r,
            open_record=lambda incident_id, record_id, parent: calls.append((incident_id, record_id, parent)),
        ),
    )
    record_links.open_record("INC1", "planned_schedule_item", "7", "parent-widget")
    assert calls == [("INC1", "7", "parent-widget")]
