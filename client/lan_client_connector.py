from __future__ import annotations

import logging
from typing import Any

import httpx
from PySide6.QtCore import QObject, QSettings, QTimer, Signal
from PySide6.QtNetwork import QAbstractSocket
from PySide6.QtWebSockets import QWebSocket

from shared.lan_config import (
    DEFAULT_LAN_CLIENT_TIMEOUT_S,
    DEFAULT_LAN_HOST,
    DEFAULT_LAN_PORT,
    SETTINGS_GROUP,
    SETTINGS_HOST_KEY,
    SETTINGS_PORT_KEY,
)

logger = logging.getLogger(__name__)


class LanClientConnector(QObject):
    connectionStateChanged = Signal(str, str)
    bootstrapReceived = Signal(dict)
    eventReceived = Signal(dict)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self._host = DEFAULT_LAN_HOST
        self._port = DEFAULT_LAN_PORT
        self._state = "disconnected"
        self._ws: QWebSocket | None = None
        self._reconnect_timer = QTimer(self)
        self._reconnect_timer.setInterval(3000)
        self._reconnect_timer.timeout.connect(self._try_reconnect)
        self._last_error = ""
        self._load_last_target()

    @property
    def state(self) -> str:
        return self._state

    @property
    def host(self) -> str:
        return self._host

    @property
    def port(self) -> int:
        return int(self._port)

    @property
    def connected(self) -> bool:
        return self._state == "connected"

    def _set_state(self, state: str, detail: str = "") -> None:
        self._state = state
        self._last_error = detail
        self.connectionStateChanged.emit(state, detail)

    def _load_last_target(self) -> None:
        s = QSettings()
        s.beginGroup(SETTINGS_GROUP)
        self._host = str(s.value(SETTINGS_HOST_KEY, DEFAULT_LAN_HOST))
        self._port = int(s.value(SETTINGS_PORT_KEY, DEFAULT_LAN_PORT))
        s.endGroup()

    def _save_last_target(self) -> None:
        s = QSettings()
        s.beginGroup(SETTINGS_GROUP)
        s.setValue(SETTINGS_HOST_KEY, self._host)
        s.setValue(SETTINGS_PORT_KEY, int(self._port))
        s.endGroup()

    def connect_to_host(self, host: str, port: int) -> tuple[bool, str]:
        self._host = str(host).strip()
        self._port = int(port)
        self._save_last_target()
        self._set_state("reconnecting", "Connecting to host...")
        ok, msg = self.refresh_from_host()
        if not ok:
            self._set_state("disconnected", msg)
            return False, msg
        self._start_websocket()
        return True, "Connected to host."

    def disconnect(self) -> None:
        self._reconnect_timer.stop()
        if self._ws is not None:
            try:
                self._ws.abort()
                self._ws.deleteLater()
            except Exception:
                pass
            self._ws = None
        self._set_state("disconnected", "Disconnected")

    def refresh_from_host(self) -> tuple[bool, str]:
        try:
            with httpx.Client(timeout=DEFAULT_LAN_CLIENT_TIMEOUT_S) as client:
                session = client.get(f"http://{self._host}:{self._port}/lan/session")
                session.raise_for_status()
                payload = session.json()
                if not bool(payload.get("hosting")):
                    return False, "Host is not currently hosting."
                snap = client.get(f"http://{self._host}:{self._port}/lan/bootstrap")
                snap.raise_for_status()
                snapshot = snap.json()
                self.bootstrapReceived.emit(snapshot)
                return True, "Bootstrap synced."
        except Exception as exc:
            logger.warning("LAN refresh failed: %s", exc)
            return False, f"Connection failed: {exc}"

    def post(self, path: str, payload: dict[str, Any]) -> tuple[bool, dict[str, Any] | str]:
        try:
            with httpx.Client(timeout=DEFAULT_LAN_CLIENT_TIMEOUT_S) as client:
                res = client.post(f"http://{self._host}:{self._port}{path}", json=payload)
                res.raise_for_status()
                return True, res.json()
        except Exception as exc:
            return False, str(exc)

    def update_team(self, *, team_id: int, status: str) -> tuple[bool, str]:
        ok, res = self.post("/lan/team/update", {"team_id": int(team_id), "status": str(status), "status_only": True})
        return ok, "ok" if ok else str(res)

    def update_task(self, *, task_id: int, status: str) -> tuple[bool, str]:
        ok, res = self.post("/lan/task/update", {"task_id": int(task_id), "status": str(status), "status_only": True})
        return ok, "ok" if ok else str(res)

    def create_comms(self, payload: dict[str, Any]) -> tuple[bool, dict[str, Any] | str]:
        return self.post("/lan/comms/create", payload)

    def create_alert(self, payload: dict[str, Any]) -> tuple[bool, dict[str, Any] | str]:
        return self.post("/lan/alert/create", payload)

    def _start_websocket(self) -> None:
        if self._ws is not None:
            try:
                self._ws.abort()
                self._ws.deleteLater()
            except Exception:
                pass
        self._ws = QWebSocket()
        self._ws.connected.connect(self._on_ws_connected)
        self._ws.disconnected.connect(self._on_ws_disconnected)
        self._ws.textMessageReceived.connect(self._on_ws_message)
        self._ws.errorOccurred.connect(self._on_ws_error)
        self._ws.open(f"ws://{self._host}:{self._port}/lan/ws")

    def _on_ws_connected(self) -> None:
        self._set_state("connected", f"Connected to {self._host}:{self._port}")
        self._reconnect_timer.stop()

    def _on_ws_disconnected(self) -> None:
        if self._state == "disconnected":
            return
        self._set_state("reconnecting", "Connection lost. Reconnecting...")
        if not self._reconnect_timer.isActive():
            self._reconnect_timer.start()

    def _on_ws_error(self, _err: QAbstractSocket.SocketError) -> None:
        if self._ws is None:
            return
        self._set_state("reconnecting", self._ws.errorString())
        if not self._reconnect_timer.isActive():
            self._reconnect_timer.start()

    def _try_reconnect(self) -> None:
        ok, msg = self.refresh_from_host()
        if not ok:
            self._set_state("reconnecting", msg)
            return
        self._start_websocket()

    def _on_ws_message(self, text: str) -> None:
        import json

        try:
            payload = json.loads(text)
            if isinstance(payload, dict):
                self.eventReceived.emit(payload)
        except Exception:
            logger.debug("Ignoring malformed WS event payload")


__all__ = ["LanClientConnector"]
