from __future__ import annotations

import pytest

from modules.devtools.panels.notification_test_panel import (
    LOCAL_DESKTOP_TARGET,
    build_notification_payload,
    connection_display_name,
)


def test_connection_display_name_uses_user_and_device() -> None:
    connection = {
        "person_id": "alice",
        "person_record": 42,
        "device_name": "Field Tablet",
        "device_id": "device-1",
    }

    assert connection_display_name(connection) == "alice - Field Tablet"


def test_connection_display_name_labels_current_desktop_session() -> None:
    assert connection_display_name({"target_type": LOCAL_DESKTOP_TARGET}) == "Current desktop session"


def test_build_notification_payload_targets_person_record() -> None:
    payload = build_notification_payload(
        connection={"person_record": "42"},
        title="  Test title  ",
        message="  Test message  ",
        category="safety",
        severity="priority",
        source_id="test-source",
        source_label="Dev Tester",
        requires_acknowledgement=True,
    )

    assert payload == {
        "title": "Test title",
        "message": "Test message",
        "category": "safety",
        "severity": "priority",
        "source_type": "dev_notification_test",
        "source_id": "test-source",
        "source_label": "Dev Tester",
        "audience_user_id": 42,
        "requires_acknowledgement": True,
    }


def test_build_notification_payload_requires_person_record() -> None:
    with pytest.raises(ValueError, match="person_record"):
        build_notification_payload(
            connection={},
            title="Test",
            message="Message",
            category="operations",
            severity="routine",
            source_id="test-source",
            source_label="Dev Tester",
            requires_acknowledgement=False,
        )
