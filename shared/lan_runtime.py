from __future__ import annotations

from typing import Any

from PySide6.QtCore import QObject, Signal

from client.lan_client_connector import LanClientConnector
from server.lan_host_service import lan_host_service


class LanRuntime(QObject):
    modeChanged = Signal(str)

    def __init__(self) -> None:
        super().__init__()
        self._mode = "local"
        self.client = LanClientConnector()

    @property
    def mode(self) -> str:
        return self._mode

    def set_mode(self, mode: str) -> None:
        mode = str(mode).strip().lower()
        if mode not in {"local", "host", "client"}:
            mode = "local"
        if mode != self._mode:
            self._mode = mode
            self.modeChanged.emit(self._mode)

    def is_host_mode(self) -> bool:
        return self._mode == "host"

    def is_client_mode(self) -> bool:
        return self._mode == "client"

    def writes_allowed(self) -> bool:
        if self.is_client_mode():
            return self.client.connected
        return True

    def apply_bootstrap_to_signals(self, snapshot: dict[str, Any]) -> None:
        from utils.app_signals import app_signals

        app_signals.lanSnapshotReceived.emit(snapshot)
        app_signals.lanEventReceived.emit({"type": "incident.snapshot", "payload": snapshot, "source": "host"})
        app_signals.teamStatusChanged.emit(-1)
        app_signals.taskHeaderChanged.emit(-1, {"refresh": True})
        app_signals.messageLogged.emit("LAN", "LAN")

    def apply_event_to_signals(self, event: dict[str, Any]) -> None:
        from utils.app_signals import app_signals

        app_signals.lanEventReceived.emit(event)
        event_type = str(event.get("type") or "")
        payload = event.get("payload") if isinstance(event.get("payload"), dict) else {}
        if event_type.startswith("team."):
            team_id = int(payload.get("team_id") or -1)
            app_signals.teamStatusChanged.emit(team_id)
        if event_type.startswith("task."):
            task_id = int(payload.get("task_id") or -1)
            app_signals.taskHeaderChanged.emit(task_id, {"refresh": True})
        if event_type.startswith("comms.") or event_type.startswith("alert."):
            app_signals.messageLogged.emit("LAN", "LAN")


lan_runtime = LanRuntime()
