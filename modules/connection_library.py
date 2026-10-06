"""Saved-connection library for the login screen.

Lets a user keep several cloud connect codes on hand (e.g. for switching
between incidents/command posts quickly) instead of retyping a code every
time. Reachable from ``LoginDialog`` via a "Connection Library..." button.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, List

import httpx
from PySide6.QtCore import QObject, QRunnable, QThreadPool, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from core.networking.connection_manager import DEFAULT_CLOUD_ROUTER_URL, build_cloud_url
from core.networking.tls import system_ssl_context
from utils.itemview_delegates import RowOutlineSelectionDelegate
from utils.styles import connection_status_colors, get_palette, subscribe_theme

_SETTINGS_KEY = "savedConnections"
_HEALTH_TIMEOUT_SECONDS = 2.0


@dataclass
class SavedConnection:
    name: str
    connect_code: str
    server_url: str = ""
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    last_status: str = "checking"
    last_checked: str = ""

    def resolved_url(self) -> str | None:
        return build_cloud_url(self.server_url or DEFAULT_CLOUD_ROUTER_URL, self.connect_code)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "connect_code": self.connect_code,
            "server_url": self.server_url,
            "last_status": self.last_status,
            "last_checked": self.last_checked,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "SavedConnection":
        return cls(
            id=str(data.get("id") or uuid.uuid4().hex),
            name=str(data.get("name") or ""),
            connect_code=str(data.get("connect_code") or ""),
            server_url=str(data.get("server_url") or ""),
            last_status=str(data.get("last_status") or "checking"),
            last_checked=str(data.get("last_checked") or ""),
        )


def load_saved_connections(settings_manager) -> List[SavedConnection]:
    raw = settings_manager.get(_SETTINGS_KEY) or []
    items: List[SavedConnection] = []
    for entry in raw:
        try:
            items.append(SavedConnection.from_dict(entry))
        except Exception:
            continue
    return items


def save_saved_connections(settings_manager, items: List[SavedConnection]) -> None:
    settings_manager.set(_SETTINGS_KEY, [item.to_dict() for item in items])


def check_connection_status(server_url: str, connect_code: str) -> str:
    """Pings a connection's ``/health`` endpoint. Returns 'online' or 'offline'."""

    url = build_cloud_url(server_url or DEFAULT_CLOUD_ROUTER_URL, connect_code)
    if not url:
        return "offline"
    try:
        response = httpx.get(
            f"{url}/health",
            timeout=_HEALTH_TIMEOUT_SECONDS,
            verify=system_ssl_context(),
        )
        return "online" if 200 <= response.status_code < 300 else "offline"
    except httpx.HTTPError:
        return "offline"


class _StatusCheckSignals(QObject):
    finished = Signal(str, str)  # (connection_id, status)


# Keeps a running check's QRunnable/QObject alive on its own, independent of
# whatever dialog started it. Without this, closing the Connection Library
# while a probe is still in flight (slow/offline connect code) lets Python
# garbage-collect the runnable's signals object out from under the still
# running background thread, crashing on emit.
_INFLIGHT_CHECKS: set["_StatusCheckRunnable"] = set()


class _StatusCheckRunnable(QRunnable):
    def __init__(self, connection_id: str, server_url: str, connect_code: str) -> None:
        super().__init__()
        self._connection_id = connection_id
        self._server_url = server_url
        self._connect_code = connect_code
        self.signals = _StatusCheckSignals()

    def run(self) -> None:  # type: ignore[override]
        try:
            status = check_connection_status(self._server_url, self._connect_code)
            self.signals.finished.emit(self._connection_id, status)
        finally:
            _INFLIGHT_CHECKS.discard(self)


class AddEditConnectionDialog(QDialog):
    """Collects a name + connect code (and optional custom server URL)."""

    def __init__(self, parent: QWidget | None = None, connection: SavedConnection | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Connection" if connection else "Add Connection")
        self.setModal(True)

        self.name_edit = QLineEdit(connection.name if connection else "")
        self.name_edit.setPlaceholderText("e.g. Exercise HQ")
        self.connect_code_edit = QLineEdit(connection.connect_code if connection else "")
        self.connect_code_edit.setPlaceholderText("e.g. ABCD-1234")
        self.connect_code_edit.textChanged.connect(self._normalize_connect_code)
        self.server_url_edit = QLineEdit(connection.server_url if connection else "")
        self.server_url_edit.setPlaceholderText("Blank = built-in default cloud router")

        form = QFormLayout()
        form.addRow("Name:", self.name_edit)
        form.addRow("Connect code:", self.connect_code_edit)
        form.addRow("Server URL (advanced):", self.server_url_edit)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, self)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(self.buttons)

    def _normalize_connect_code(self, text: str) -> None:
        upper = text.upper()
        if upper != text:
            cursor = self.connect_code_edit.cursorPosition()
            self.connect_code_edit.blockSignals(True)
            self.connect_code_edit.setText(upper)
            self.connect_code_edit.setCursorPosition(cursor)
            self.connect_code_edit.blockSignals(False)

    def _on_accept(self) -> None:
        if not self.name_edit.text().strip() or not self.connect_code_edit.text().strip():
            QMessageBox.warning(self, "Missing Info", "Enter a name and a connect code.")
            return
        self.accept()

    def values(self) -> tuple[str, str, str]:
        return (
            self.name_edit.text().strip(),
            self.connect_code_edit.text().strip(),
            self.server_url_edit.text().strip(),
        )


class ConnectionLibraryDialog(QDialog):
    """Modal table of saved connections; opens an incident picker on selection.

    Emits ``sessionReady`` when a remembered login lets the incident pick
    finish sign-in immediately, or ``connectionSelected`` when the caller
    (``LoginDialog``) should fall back to its normal username/password step
    with the connect code and incident already filled in.
    """

    sessionReady = Signal(str, str, str)  # (incident_id, person_record, role)
    connectionSelected = Signal(object, str)  # (SavedConnection, incident_number)

    _COL_NAME, _COL_CODE, _COL_STATUS = range(3)

    def __init__(self, parent: QWidget | None, settings_manager) -> None:
        super().__init__(parent)
        self.setWindowTitle("Connection Library")
        self.setModal(True)
        self.resize(560, 360)
        self._settings_manager = settings_manager
        self._connections: List[SavedConnection] = load_saved_connections(settings_manager)
        self._pool = QThreadPool.globalInstance()

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Name", "Connect Code", "Status"])
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.verticalHeader().setVisible(False)
        self.table.setStyleSheet("QTableView { selection-background-color: transparent; }")
        header = self.table.horizontalHeader()
        header.setSectionsMovable(True)
        header.setStretchLastSection(False)
        for col in range(self.table.columnCount()):
            header.setSectionResizeMode(col, QHeaderView.Interactive)
        self.table.itemDoubleClicked.connect(lambda *_: self._on_open())

        pal = get_palette()
        color = pal.get("ctrl_focus", pal.get("accent"))
        self._outline_delegate = RowOutlineSelectionDelegate(self.table, color)
        self.table.setItemDelegate(self._outline_delegate)

        self.btn_add = QPushButton("Add Connection...")
        self.btn_edit = QPushButton("Edit...")
        self.btn_remove = QPushButton("Remove")
        self.btn_open = QPushButton("Open")
        self.btn_open.setEnabled(False)
        self.btn_close = QPushButton("Close")

        self.btn_add.clicked.connect(self._on_add)
        self.btn_edit.clicked.connect(self._on_edit)
        self.btn_remove.clicked.connect(self._on_remove)
        self.btn_open.clicked.connect(self._on_open)
        self.btn_close.clicked.connect(self.reject)
        self.table.itemSelectionChanged.connect(self._update_buttons_enabled)

        button_row = QHBoxLayout()
        button_row.addWidget(self.btn_add)
        button_row.addWidget(self.btn_edit)
        button_row.addWidget(self.btn_remove)
        button_row.addStretch(1)
        button_row.addWidget(self.btn_open)
        button_row.addWidget(self.btn_close)

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Saved server connections:"))
        layout.addWidget(self.table)
        layout.addLayout(button_row)

        subscribe_theme(self, lambda *_: self._on_theme_changed())
        self._reload_table()

    def _on_theme_changed(self) -> None:
        pal = get_palette()
        color = pal.get("ctrl_focus", pal.get("accent"))
        self._outline_delegate.setColor(color)
        self._repaint_status_cells()

    def _update_buttons_enabled(self) -> None:
        has_selection = bool(self.table.selectedItems())
        self.btn_edit.setEnabled(has_selection)
        self.btn_remove.setEnabled(has_selection)
        self.btn_open.setEnabled(has_selection)

    def _selected_connection(self) -> SavedConnection | None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._connections):
            return None
        return self._connections[row]

    def _reload_table(self) -> None:
        self.table.setRowCount(len(self._connections))
        for row, conn in enumerate(self._connections):
            self.table.setItem(row, self._COL_NAME, QTableWidgetItem(conn.name))
            self.table.setItem(row, self._COL_CODE, QTableWidgetItem(conn.connect_code))
            self.table.setItem(row, self._COL_STATUS, QTableWidgetItem("checking..."))
            self._start_status_check(conn)
        self._repaint_status_cells()
        self._update_buttons_enabled()

    def _start_status_check(self, conn: SavedConnection) -> None:
        runnable = _StatusCheckRunnable(conn.id, conn.server_url, conn.connect_code)
        runnable.signals.finished.connect(self._on_status_checked)
        _INFLIGHT_CHECKS.add(runnable)
        self._pool.start(runnable)

    def _on_status_checked(self, connection_id: str, status: str) -> None:
        for conn in self._connections:
            if conn.id == connection_id:
                conn.last_status = status
                conn.last_checked = datetime.now(timezone.utc).isoformat()
                break
        else:
            return
        save_saved_connections(self._settings_manager, self._connections)
        self._repaint_status_cells()

    def _repaint_status_cells(self) -> None:
        colors = connection_status_colors()
        for row, conn in enumerate(self._connections):
            item = self.table.item(row, self._COL_STATUS)
            if item is None:
                continue
            item.setText(conn.last_status)
            style = colors.get(conn.last_status)
            if style is not None:
                item.setBackground(style["bg"])
                item.setForeground(style["fg"])

    def _on_add(self) -> None:
        dlg = AddEditConnectionDialog(self)
        if dlg.exec() != QDialog.Accepted:
            return
        name, code, server_url = dlg.values()
        conn = SavedConnection(name=name, connect_code=code, server_url=server_url)
        self._connections.append(conn)
        save_saved_connections(self._settings_manager, self._connections)
        self._reload_table()

    def _on_edit(self) -> None:
        conn = self._selected_connection()
        if conn is None:
            return
        dlg = AddEditConnectionDialog(self, connection=conn)
        if dlg.exec() != QDialog.Accepted:
            return
        conn.name, conn.connect_code, conn.server_url = dlg.values()
        conn.last_status = "checking"
        save_saved_connections(self._settings_manager, self._connections)
        self._reload_table()

    def _on_remove(self) -> None:
        conn = self._selected_connection()
        if conn is None:
            return
        if QMessageBox.question(
            self, "Remove Connection", f"Remove '{conn.name}' from the library?"
        ) != QMessageBox.Yes:
            return
        self._connections = [c for c in self._connections if c.id != conn.id]
        save_saved_connections(self._settings_manager, self._connections)
        self._reload_table()

    def _point_app_at(self, url: str, server_name: str) -> bool:
        """Make this saved connection the app's active server.

        Routes through the global ``ConnectionManager`` (if one is running)
        rather than only reconfiguring ``api_client`` directly. The manager
        is the single source of truth other code reads from — notably
        main.py re-syncs ``api_client`` from ``ConnectionManager.snapshot``
        right after login — so bypassing it left the app silently reverting
        to whatever server LAN discovery found at startup even after a user
        picked a different saved connection here.
        """

        from utils.api_client import api_client

        app = QApplication.instance()
        manager = app.property("sarapp_connection_manager") if app is not None else None
        if manager is not None:
            snapshot = manager.connect_to_url(url, server_name=server_name)
            if not snapshot.is_connected:
                return False

        api_client.configure(url)
        return True

    def _on_open(self) -> None:
        conn = self._selected_connection()
        if conn is None:
            return
        url = conn.resolved_url()
        if not url:
            QMessageBox.warning(self, "Invalid Connection", "This connection has no connect code set.")
            return

        from utils.api_client import api_client
        from modules.login_dialog import IncidentSelectionDialog, _finish_session, _resolve_person_record

        previous_base_url = api_client.base_url
        connected = self._point_app_at(url, conn.name or conn.connect_code)
        if not connected:
            QMessageBox.warning(
                self, "Connection Failed", f"Could not reach '{conn.name}' at this time."
            )
            api_client.configure(previous_base_url)
            return

        picker = IncidentSelectionDialog(self, api_available=True)
        if picker.exec() != QDialog.Accepted:
            return
        incident_id = picker.selected_incident_id()
        if not incident_id:
            return
        selected = next((it for it in picker._incidents if it.incident_id == incident_id), None)
        incident_number = selected.number if selected is not None else str(incident_id)

        self._settings_manager.set("cloudServerUrl", conn.server_url)
        self._settings_manager.set("cloudConnectCode", conn.connect_code)
        self._settings_manager.set("lastConnectionId", conn.id)
        self._settings_manager.set("lastIncidentNumber", incident_number)

        if self._settings_manager.get("rememberLogin"):
            username = str(self._settings_manager.get("rememberedUsername") or "").strip()
            role = str(self._settings_manager.get("rememberedRole") or "").strip()
            if username and role:
                display_name = _resolve_person_record(self, username)
                if display_name is not None:
                    result = _finish_session(
                        parent=self,
                        username=username,
                        role=role,
                        incident_id=incident_id,
                        display_name=display_name,
                        incidents=picker._incidents,
                    )
                    if result is not None:
                        self.sessionReady.emit(*result)
                        self.accept()
                        return

        self.connectionSelected.emit(conn, incident_number)
        self.accept()


__all__ = [
    "AddEditConnectionDialog",
    "ConnectionLibraryDialog",
    "SavedConnection",
    "check_connection_status",
    "load_saved_connections",
    "save_saved_connections",
]
