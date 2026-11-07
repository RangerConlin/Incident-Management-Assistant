from __future__ import annotations

import pytest

from ui.actions.quick_entry_actions import dispatch, execute_cli


def test_unbound_dispatch_does_not_report_fake_success() -> None:
    with pytest.raises(RuntimeError, match="not connected"):
        dispatch("tasks.create", {})


def test_cli_routes_task_creation_through_injected_dispatcher() -> None:
    calls: list[tuple[str, dict]] = []

    result = execute_cli(
        'task new "Ground Sweep Alpha" priority=High',
        dispatcher=lambda action, payload: calls.append((action, payload)),
    )

    assert calls == [
        (
            "tasks.create",
            {"title": "Ground Sweep Alpha", "priority": "High"},
        )
    ]
    assert result == "Task created: Ground Sweep Alpha"


def test_cli_describes_opened_workflow_without_claiming_record_creation() -> None:
    calls: list[tuple[str, dict]] = []

    result = execute_cli(
        'log new "Team B departed ICP"',
        dispatcher=lambda action, payload: calls.append((action, payload)),
    )

    assert calls == [
        ("logs.createActivity", {"text": "Team B departed ICP"})
    ]
    assert result == "Opened the ICS-214 activity log"
