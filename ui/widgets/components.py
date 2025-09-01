from __future__ import annotations

from datetime import datetime, timezone
from typing import Callable

try:
    from zoneinfo import ZoneInfo  # py3.9+
except Exception:  # pragma: no cover
    ZoneInfo = None  # type: ignore

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QListWidget, QListWidgetItem, QHBoxLayout,
    QPushButton, QLineEdit, QMessageBox
)
from PySide6.QtCore import Qt, QTimer

from utils.settingsmanager import SettingsManager


def _vbox(widget: QWidget) -> QVBoxLayout:
    layout = QVBoxLayout(widget)
    try:
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)
    except Exception:
        pass
    return layout


class PlaceholderListWidget(QWidget):
    def __init__(self, title: str, items: list[str] | None = None, parent=None):
        super().__init__(parent)
        layout = _vbox(self)
        layout.addWidget(QLabel(title))
        lst = QListWidget(self)
        for it in (items or []):
            QListWidgetItem(it, lst)
        layout.addWidget(lst)


class IncidentInfoWidget(QWidget):
    def __init__(self, incident_provider: Callable, user_provider: Callable, parent=None):
        super().__init__(parent)
        layout = _vbox(self)
        data_i = incident_provider() if incident_provider else {}
        data_u = user_provider() if user_provider else {}
        layout.addWidget(QLabel(f"Incident: {data_i.get('name','-')} ({data_i.get('number','-')})"))
        layout.addWidget(QLabel(f"Type/Status: {data_i.get('type','-')} / {data_i.get('status','-')}"))
        layout.addWidget(QLabel(f"User: {data_u.get('name','-')} ({data_u.get('role','-')})"))
        layout.addWidget(QLabel(f"Login/Check-in: {data_u.get('login','-')} / {data_u.get('check_in','-')}"))


class TeamStatusBoardWidget(PlaceholderListWidget):
    pass


class TaskStatusBoardWidget(PlaceholderListWidget):
    pass


class PersonnelAvailabilityWidget(PlaceholderListWidget):
    pass


class EquipmentSnapshotWidget(PlaceholderListWidget):
    pass


class VehicleSnapshotWidget(PlaceholderListWidget):
    pass


class OpsDashboardFeedWidget(PlaceholderListWidget):
    pass


class RecentMessagesWidget(PlaceholderListWidget):
    pass


class NotificationsWidget(PlaceholderListWidget):
    pass


class ICS205CommPlanWidget(PlaceholderListWidget):
    pass


class CommLogFeedWidget(PlaceholderListWidget):
    pass


class ObjectivesTrackerWidget(PlaceholderListWidget):
    pass


class FormsInProgressWidget(PlaceholderListWidget):
    pass


class SitrepFeedWidget(PlaceholderListWidget):
    pass


class UpcomingTasksWidget(PlaceholderListWidget):
    pass


class SafetyAlertsWidget(PlaceholderListWidget):
    pass


class MedicalIncidentLogWidget(PlaceholderListWidget):
    pass


class ICS206SnapshotWidget(PlaceholderListWidget):
    pass


class IntelDashboardWidget(PlaceholderListWidget):
    pass


class ClueLogSnapshotWidget(PlaceholderListWidget):
    pass


class MapSnapshotWidget(PlaceholderListWidget):
    pass


class PressDraftsWidget(PlaceholderListWidget):
    pass


class MediaLogWidget(PlaceholderListWidget):
    pass


class BriefingQueueWidget(PlaceholderListWidget):
    pass


class QuickEntryWidget(QWidget):
    """Quick actions toolbar + simple command line."""

    def __init__(self, action_router: Callable[[str, dict], None], cli_execute: Callable[[str], str], parent=None):
        super().__init__(parent)
        self._router = action_router
        self._cli = cli_execute

        layout = _vbox(self)
        row = QHBoxLayout()
        layout.addLayout(row)

        def btn(text: str, action: str, payload: dict | None = None):
            b = QPushButton(text, self)
            b.clicked.connect(lambda: self._safe_dispatch(action, payload or {}))
            row.addWidget(b)

        # Buttons per spec
        btn("New Task", "tasks.create", {})
        btn("New Log Entry (214)", "logs.createActivity", {})
        btn("New Comm Entry (213/309)", "comms.createLogEntry", {})
        btn("New Resource Request (213-RR)", "logistics.createResourceRequest", {})
        btn("New Message", "comms.createMessage", {})
        btn("New Safety Report", "safety.createReport", {})
        btn("Upload Media/Document", "files.upload", {"incidentId": None})

        # CLI
        cli_row = QHBoxLayout()
        layout.addLayout(cli_row)
        self.cli_edit = QLineEdit(self)
        self.cli_edit.setPlaceholderText("Type a command, e.g., task new \"Ground Sweep Alpha\" priority=High team=G-2")
        run = QPushButton("Run", self)
        run.clicked.connect(self._run_cli)
        cli_row.addWidget(self.cli_edit)
        cli_row.addWidget(run)

    def _safe_dispatch(self, action: str, payload: dict):
        try:
            self._router(action, payload)
            QMessageBox.information(self, "Success", f"Action executed: {action}")
        except PermissionError as e:  # handle permission on action time
            QMessageBox.warning(self, "Permission", str(e))
        except Exception as e:
            QMessageBox.critical(self, "Error", f"Action failed: {e}")

    def _run_cli(self):
        cmd = self.cli_edit.text().strip()
        if not cmd:
            return
        try:
            res = self._cli(cmd)
            QMessageBox.information(self, "CLI", res or "OK")
        except Exception as e:
            QMessageBox.critical(self, "CLI Error", str(e))


class ClockDualWidget(QWidget):
    """Always shows Local + UTC times. Local tz from Settings."""

    def __init__(self, settings: SettingsManager | None = None, parent=None):
        super().__init__(parent)
        self._settings = settings or SettingsManager()
        layout = _vbox(self)
        self.local_lbl = QLabel("Local: --:--:--")
        self.utc_lbl = QLabel("UTC: --:--:--")
        layout.addWidget(self.local_lbl)
        layout.addWidget(self.utc_lbl)

        self._timer = QTimer(self)
        self._timer.timeout.connect(self._tick)
        self._timer.start(1000)
        self._tick()

    def _tick(self):
        now_utc = datetime.now(timezone.utc)
        tzname = self._settings.get("timezone", None)
        if ZoneInfo and tzname:
            try:
                local_dt = now_utc.astimezone(ZoneInfo(tzname))
            except Exception:
                local_dt = datetime.now()
        else:
            local_dt = datetime.now()
        self.local_lbl.setText(f"Local: {local_dt.strftime('%Y-%m-%d %H:%M:%S')} ({tzname or 'Local'})")
        self.utc_lbl.setText(f"UTC:   {now_utc.strftime('%Y-%m-%d %H:%M:%S')} (UTC)")

