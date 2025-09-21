from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

try:
    from PySide6.QtCore import Qt
    from PySide6.QtWidgets import QApplication
except ImportError as exc:  # pragma: no cover - environment-specific
    pytest.skip(f"PySide6 unavailable: {exc}", allow_module_level=True)

from modules.operations.panels import team_status_panel as tsp  # noqa: E402
from modules.operations.panels.team_alerts import (  # noqa: E402
    AlertKind,
    compute_alert_kind,
)


def _ensure_app() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_reset_timer_updates_checkin_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    _ensure_app()

    monkeypatch.setattr(tsp, "fetch_team_assignment_rows", lambda: [], raising=False)
    monkeypatch.setattr(tsp, "subscribe_theme", lambda *args, **kwargs: None, raising=False)

    calls: list[tuple[int, datetime | None, datetime | None]] = []

    def _record_touch(team_id: int, *, checkin_time=None, reference_time=None) -> None:
        calls.append((team_id, checkin_time, reference_time))

    monkeypatch.setattr(tsp, "touch_team_checkin", _record_touch, raising=False)

    panel = tsp.TeamStatusPanel()
    try:
        old_dt = datetime.now(timezone.utc) - timedelta(minutes=75)
        old_iso = old_dt.isoformat()

        panel._add_team_row(
            {
                "sortie": "S1",
                "name": "Alpha",
                "leader": "Lead",
                "contact": "555-0000",
                "status": "Enroute",
                "assignment": "",
                "location": "",
                "last_updated": old_iso,
                "last_checkin_at": old_iso,
                "needs_assistance_flag": False,
                "emergency_flag": False,
                "team_status_updated": old_iso,
                "team_id": 42,
            }
        )

        icon_item = panel.table.item(0, 0)
        assert icon_item is not None
        payload_before = icon_item.data(tsp._ALERT_DATA_ROLE)
        assert isinstance(payload_before, dict)
        assert payload_before.get("last_checkin_at") == old_iso

        panel._reset_last_update_row(0)

        payload_after = icon_item.data(tsp._ALERT_DATA_ROLE)
        assert isinstance(payload_after, dict)
        new_iso = payload_after.get("last_checkin_at")
        assert isinstance(new_iso, str)
        assert new_iso != old_iso
        assert payload_after.get("reference_time") == new_iso

        new_dt = datetime.fromisoformat(new_iso)
        now = datetime.now(timezone.utc)
        assert 0 <= (now - new_dt).total_seconds() < 30

        state = panel._icon_delegate._state_from_payload(payload_after)
        assert state is not None
        assert (
            compute_alert_kind(state, now=now, thresholds=panel._thresholds)
            == AlertKind.NONE
        )

        last_item = panel.table.item(0, 8)
        assert last_item is not None
        assert last_item.data(Qt.UserRole) == new_iso

        assert calls
        touched_id, touch_check, touch_ref = calls[-1]
        assert touched_id == 42
        assert isinstance(touch_check, datetime)
        assert isinstance(touch_ref, datetime)
    finally:
        try:
            timer = getattr(panel, "_last_update_timer", None)
            if timer is not None:
                timer.stop()
        except Exception:
            pass
        panel.deleteLater()
