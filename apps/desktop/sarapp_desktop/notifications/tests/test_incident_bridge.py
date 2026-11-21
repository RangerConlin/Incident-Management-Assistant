from __future__ import annotations

import notifications.services.incident_bridge as bridge_module


def test_target_person_records_shown_for_matching_user(monkeypatch) -> None:
    monkeypatch.setattr("utils.state.AppState.get_active_user_id", staticmethod(lambda: "42"))
    shown: list = []
    monkeypatch.setattr(
        "notifications.services.get_notifier",
        lambda: type("N", (), {"notify": staticmethod(lambda note: shown.append(note))})(),
    )

    bridge_module.handle_notification_event(
        "INC1",
        {
            "title": "Briefing reminder",
            "message": "Briefing in 15 minutes",
            "severity": "priority",
            "category": "planning",
            "target_person_records": [42, 7],
        },
    )

    assert len(shown) == 1
    assert shown[0].title == "Briefing reminder"


def test_target_person_records_suppressed_for_other_user(monkeypatch) -> None:
    monkeypatch.setattr("utils.state.AppState.get_active_user_id", staticmethod(lambda: "99"))
    shown: list = []
    monkeypatch.setattr(
        "notifications.services.get_notifier",
        lambda: type("N", (), {"notify": staticmethod(lambda note: shown.append(note))})(),
    )

    bridge_module.handle_notification_event(
        "INC1",
        {
            "title": "Briefing reminder",
            "message": "Briefing in 15 minutes",
            "target_person_records": [42, 7],
        },
    )

    assert shown == []


def test_target_person_records_takes_precedence_over_sections(monkeypatch) -> None:
    """A payload carrying both fields should use the exact person_record
    match and never fall back to (or require) section resolution."""
    monkeypatch.setattr("utils.state.AppState.get_active_user_id", staticmethod(lambda: "42"))

    def _boom(*_args, **_kwargs):
        raise AssertionError("section-based targeting should not run when target_person_records is set")

    monkeypatch.setattr(bridge_module, "_current_user_under_section", _boom)
    shown: list = []
    monkeypatch.setattr(
        "notifications.services.get_notifier",
        lambda: type("N", (), {"notify": staticmethod(lambda note: shown.append(note))})(),
    )

    bridge_module.handle_notification_event(
        "INC1",
        {
            "title": "Briefing reminder",
            "message": "Briefing in 15 minutes",
            "target_person_records": [42],
            "target_sections": ["Operations Section"],
        },
    )

    assert len(shown) == 1


def test_no_target_fields_broadcasts_to_all(monkeypatch) -> None:
    shown: list = []
    monkeypatch.setattr(
        "notifications.services.get_notifier",
        lambda: type("N", (), {"notify": staticmethod(lambda note: shown.append(note))})(),
    )

    bridge_module.handle_notification_event(
        "INC1",
        {"title": "System alert", "message": "Everyone sees this"},
    )

    assert len(shown) == 1
