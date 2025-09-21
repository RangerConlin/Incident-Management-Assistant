from __future__ import annotations

import logging
from PySide6.QtWidgets import QVBoxLayout, QWidget

from utils.app_signals import app_signals

from ..widgets import ICOverviewWidget

__all__ = ["IncidentDashboardPanel"]

_LOGGER = logging.getLogger(__name__)

# Map internal quick-action routes to existing application module keys so that
# pressing buttons inside the overview widget opens a reasonable destination in
# the legacy dock/command framework.
_ROUTE_MAP: dict[str, str] = {
    "command.alerts": "operations.team_status",
    "teams.overview": "operations.team_status",
    "tasks.board": "operations.task_board",
    "comms.plan": "comms.205",
    "logistics.requests": "logistics.requests",
    "logistics.new_request": "logistics.213rr",
    "planning.objectives.new": "command.objectives",
    "planning.iap": "command.iap",
}


class IncidentDashboardPanel(QWidget):
    """Dockable QWidget wrapper exposing the IC overview widget."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("IncidentDashboardPanel")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        self._overview = ICOverviewWidget(self)
        layout.addWidget(self._overview)

        # Wire global app signals so the widget refreshes when external state
        # changes (incident selection, user change, etc.).
        app_signals.incidentChanged.connect(self._refresh_overview)
        app_signals.userChanged.connect(self._refresh_overview)
        app_signals.opPeriodChanged.connect(self._refresh_overview)
        app_signals.teamStatusChanged.connect(self._refresh_overview)
        app_signals.taskHeaderChanged.connect(self._refresh_overview)

        # Quick actions bubble through the dock manager so they can reuse the
        # existing ``MainWindow.open_module`` router. Status messages surface to
        # the main window's status bar when available.
        self._overview.requestOpenModule.connect(self._handle_request_open_module)
        self._overview.statusMessage.connect(self._handle_status_message)

    # ------------------------------------------------------------------
    # Signal helpers
    # ------------------------------------------------------------------
    def _refresh_overview(self, *_args, **_kwargs) -> None:
        try:
            self._overview.refresh()
        except Exception:  # pragma: no cover - defensive UI refresh
            _LOGGER.exception("Failed to refresh incident dashboard overview")

    def _handle_request_open_module(self, module: str, payload: dict | None) -> None:
        del payload  # payload reserved for future deep links
        target = _ROUTE_MAP.get(module, module)
        window = self.window()
        opener = getattr(window, "open_module", None)
        if callable(opener):
            try:
                opener(target)
                if target != module:
                    # Provide a subtle hint when we redirected the action.
                    self._handle_status_message("Opening module via dashboard shortcut…", 2000)
                return
            except Exception as exc:  # pragma: no cover - UI integration guard
                _LOGGER.exception("Failed to open module %s: %s", target, exc)
                self._handle_status_message("Unable to open requested module", 4000)
                return

        _LOGGER.info("No handler available for dashboard route %s", module)
        self._handle_status_message("No handler registered for that shortcut", 3000)

    def _handle_status_message(self, message: str, msec: int) -> None:
        window = self.window()
        status_bar_fn = getattr(window, "statusBar", None) if window else None
        if callable(status_bar_fn):
            try:
                status_bar = status_bar_fn()
                if status_bar is not None:
                    status_bar.showMessage(message, msec)
                    return
            except Exception:  # pragma: no cover - optional UI element
                _LOGGER.debug("Unable to forward status message to status bar", exc_info=True)
        # Fallback: log so operators still see feedback in logs.
        _LOGGER.info("[ICOverview] %s", message)
