"""PySide6 Qt Widgets window for controlling a SARApp incident server."""

from __future__ import annotations

import logging
import threading
import webbrowser
from datetime import datetime, timezone
from typing import Callable

from pathlib import Path

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from lan_server.cloud_tunnel_client import generate_connect_code
from lan_server.networking.server_info import SARAPP_VERSION

from .controller import (
    ConsoleServerState,
    ServerConsoleController,
    check_port,
    fetch_client_connections,
    fetch_health,
)
from .log_model import ConsoleLogBuffer, QtLogHandler
from .settings import ServerConsoleSettings, ServerConsoleSettingsStore


class ServerConsoleWindow(QMainWindow):
    """Lightweight control panel for a dedicated SARApp server machine."""

    log_line = Signal(str)
    operation_done = Signal(str, bool)
    client_connections_updated = Signal(bool, list)

    def __init__(self, store: ServerConsoleSettingsStore | None = None) -> None:
        super().__init__()
        self.store = store or ServerConsoleSettingsStore()
        self.settings = self.store.load()
        self.controller = ServerConsoleController(self.settings)
        self.logs = ConsoleLogBuffer()
        self._last_health_status = "Stopped"
        self._client_connections_poll_active = False
        self._last_client_connections_ok: bool | None = None
        self._traffic_seq = -1
        self.setWindowTitle("SARApp Server Console")
        self.resize(900, 720)
        self._build_ui()
        self._load_settings_into_fields()
        self._connect_signals()
        self._refresh_status()
        self._append_log("Server Console opened. Settings loaded.")

        # Route the server engine's own logging (uvicorn, sarapp_db, the
        # cloud tunnel client) into this log view too, not just the
        # console's own start/stop/save messages.
        self._log_handler = QtLogHandler(self.log_line.emit)
        self._log_handler.setLevel(logging.INFO)
        root_logger = logging.getLogger()
        root_logger.addHandler(self._log_handler)
        if root_logger.level == logging.NOTSET or root_logger.level > logging.INFO:
            root_logger.setLevel(logging.INFO)

        # Periodic health monitoring updates labels without blocking the UI.
        self.health_timer = QTimer(self)
        self.health_timer.setInterval(3000)
        self.health_timer.timeout.connect(self._poll_health)
        self.health_timer.start()

        # Drain new API traffic entries into the traffic tab.
        self.traffic_timer = QTimer(self)
        self.traffic_timer.setInterval(1000)
        self.traffic_timer.timeout.connect(self._poll_traffic)
        self.traffic_timer.start()

    def _build_ui(self) -> None:
        self.tabs = QTabWidget(self)
        # Each tab stacks several group boxes vertically; scroll it instead
        # of letting the window grow taller than the screen.
        self.tabs.addTab(self._scrolled(self._build_monitoring_tab()), "Server Monitoring")
        self.tabs.addTab(self._scrolled(self._build_settings_tab()), "Settings")
        self.tabs.addTab(self._build_traffic_tab(), "API Monitor")
        self.setCentralWidget(self.tabs)

    def _scrolled(self, widget: QWidget) -> QScrollArea:
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(widget)
        return scroll

    def _build_monitoring_tab(self) -> QWidget:
        root = QWidget(self)
        layout = QVBoxLayout(root)

        status_box = QGroupBox("Server Status")
        form = QFormLayout(status_box)
        self.status_label = QLabel("Stopped")
        self.name_label = QLabel("")
        self.host_label = QLabel("")
        self.port_label = QLabel("")
        self.server_id_label = QLabel("Not started")
        self.version_label = QLabel(SARAPP_VERSION)
        self.started_label = QLabel("Not started")
        self.discovery_label = QLabel("Not broadcasting")
        self.health_label = QLabel("Stopped")
        self.tunnel_label = QLabel("Disabled")
        for title, widget in [
            ("Server status", self.status_label), ("Server name", self.name_label),
            ("Host", self.host_label), ("Port", self.port_label), ("Server ID", self.server_id_label),
            ("Version", self.version_label), ("Started time", self.started_label),
            ("Discovery status", self.discovery_label), ("Health", self.health_label),
            ("Cloud tunnel", self.tunnel_label),
        ]:
            form.addRow(title + ":", widget)
        layout.addWidget(status_box)

        controls = QGridLayout()
        self.start_button = QPushButton("Start Server")
        self.stop_button = QPushButton("Stop Server")
        self.restart_button = QPushButton("Restart Server")
        self.copy_button = QPushButton("Copy Server Address")
        self.copy_code_button = QPushButton("Copy Connect Code")
        self.health_button = QPushButton("Open Health Check")
        # Wrap into a fixed number of columns so new buttons stack into extra
        # rows instead of stretching the window wider.
        control_buttons = [self.start_button, self.stop_button, self.restart_button, self.copy_button, self.copy_code_button, self.health_button]
        columns = 3
        for index, button in enumerate(control_buttons):
            controls.addWidget(button, index // columns, index % columns)
        layout.addLayout(controls)

        clients_box = QGroupBox("Client Connections")
        clients_layout = QVBoxLayout(clients_box)
        self.clients_label = QLabel("Connected clients: 0")
        clients_layout.addWidget(self.clients_label)
        self.clients_table = QTableWidget(0, 8)
        self.clients_table.setHorizontalHeaderLabels([
            "User",
            "Team",
            "Platform",
            "Device",
            "Tracking",
            "Push",
            "Status",
            "Last heartbeat",
        ])
        self.clients_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.clients_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.clients_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        clients_layout.addWidget(self.clients_table)
        layout.addWidget(clients_box)

        logs_box = QGroupBox("Server Logs / Errors")
        logs_layout = QVBoxLayout(logs_box)
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True)
        logs_layout.addWidget(self.log_text)
        layout.addWidget(logs_box)
        return root

    def _build_settings_tab(self) -> QWidget:
        root = QWidget(self)
        layout = QVBoxLayout(root)

        settings_box = QGroupBox("Settings")
        settings_form = QFormLayout(settings_box)
        self.name_edit = QLineEdit()
        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox(); self.port_spin.setRange(1, 65535)
        self.discovery_check = QCheckBox("Enable LAN discovery broadcasting")
        self.discovery_port_spin = QSpinBox(); self.discovery_port_spin.setRange(1, 65535)
        self.cloud_url_edit = QLineEdit()
        self.cloud_url_edit.setPlaceholderText("wss://cloud-router.example/tunnel/register (blank = tunnel disabled)")
        self.connect_code_edit = QLineEdit()
        self.connect_code_edit.setPlaceholderText("Blank = auto-generated at start (e.g. ABCD-1234)")
        self.generate_code_button = QPushButton("Generate")
        connect_code_row = QHBoxLayout()
        connect_code_row.addWidget(self.connect_code_edit)
        connect_code_row.addWidget(self.generate_code_button)
        self.save_button = QPushButton("Save Settings")
        settings_form.addRow("Server name:", self.name_edit)
        settings_form.addRow("Host:", self.host_edit)
        settings_form.addRow("Port:", self.port_spin)
        settings_form.addRow("Discovery:", self.discovery_check)
        settings_form.addRow("Discovery port:", self.discovery_port_spin)
        settings_form.addRow("Cloud router URL:", self.cloud_url_edit)
        settings_form.addRow("Connect code:", connect_code_row)
        settings_form.addRow("", self.save_button)
        layout.addWidget(settings_box)

        firebase_box = QGroupBox("Firebase Push Notifications")
        firebase_form = QFormLayout(firebase_box)
        self.firebase_status_label = QLabel("Checking…")
        self.firebase_upload_button = QPushButton("Upload Firebase Key…")
        firebase_form.addRow("Active key:", self.firebase_status_label)
        firebase_form.addRow("", self.firebase_upload_button)
        layout.addWidget(firebase_box)
        layout.addStretch(1)
        return root

    # Requests the console generates itself while monitoring the server.
    _CONSOLE_POLL_PATHS = frozenset({"/health", "/server-info", "/api/client-connections"})

    def _build_traffic_tab(self) -> QWidget:
        widget = QWidget(self)
        layout = QVBoxLayout(widget)

        controls = QHBoxLayout()
        self.traffic_pause_check = QCheckBox("Pause")
        self.traffic_polling_check = QCheckBox("Show console polling traffic")
        self.traffic_clear_button = QPushButton("Clear")
        self.traffic_count_label = QLabel("0 requests shown")
        controls.addWidget(self.traffic_pause_check)
        controls.addWidget(self.traffic_polling_check)
        controls.addWidget(self.traffic_clear_button)
        controls.addStretch(1)
        controls.addWidget(self.traffic_count_label)
        layout.addLayout(controls)

        self.traffic_table = QTableWidget(0, 6)
        self.traffic_table.setHorizontalHeaderLabels(["Time", "Client", "Method", "Path", "Status", "Duration (ms)"])
        self.traffic_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self.traffic_table.setSelectionBehavior(QAbstractItemView.SelectRows)
        header = self.traffic_table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.Interactive)
        header.setStretchLastSection(True)
        layout.addWidget(self.traffic_table)
        return widget

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._start_server)
        self.stop_button.clicked.connect(self._stop_server)
        self.restart_button.clicked.connect(self._restart_server)
        self.copy_button.clicked.connect(self._copy_address)
        self.copy_code_button.clicked.connect(self._copy_connect_code)
        self.health_button.clicked.connect(self._open_health_check)
        self.save_button.clicked.connect(self._save_settings)
        self.generate_code_button.clicked.connect(self._generate_connect_code)
        self.firebase_upload_button.clicked.connect(self._upload_firebase_key)
        self.log_line.connect(self._append_log_from_thread)
        self.operation_done.connect(self._operation_finished)
        self.client_connections_updated.connect(self._apply_client_connections)
        self.traffic_clear_button.clicked.connect(self._clear_traffic)
        self.traffic_polling_check.toggled.connect(self._rebuild_traffic_table)

    def _settings_from_fields(self) -> ServerConsoleSettings:
        settings = ServerConsoleSettings(
            server_name=self.name_edit.text().strip(), host=self.host_edit.text().strip(),
            port=int(self.port_spin.value()), discovery_enabled=self.discovery_check.isChecked(),
            discovery_port=int(self.discovery_port_spin.value()),
            cloud_router_url=self.cloud_url_edit.text().strip(),
            connect_code=self.connect_code_edit.text().strip().upper(),
        )
        settings.validate()
        return settings

    def _load_settings_into_fields(self) -> None:
        self.name_edit.setText(self.settings.server_name)
        self.host_edit.setText(self.settings.host)
        self.port_spin.setValue(self.settings.port)
        self.discovery_check.setChecked(self.settings.discovery_enabled)
        self.discovery_port_spin.setValue(self.settings.discovery_port)
        self.cloud_url_edit.setText(self.settings.cloud_router_url)
        self.connect_code_edit.setText(self.settings.connect_code)
        self._refresh_firebase_status()

    def _save_settings(self) -> None:
        try:
            new_settings = self._settings_from_fields()
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Settings", str(exc)); return
        if self.controller.state == ConsoleServerState.RUNNING:
            QMessageBox.information(self, "Settings Saved", "Settings were saved and will apply on next start or restart.")
        self.store.save(new_settings)
        self.settings = new_settings
        if self.controller.state != ConsoleServerState.RUNNING:
            self.controller.settings = new_settings
        self._append_log("Settings saved.")
        self._refresh_status()

    # Cap how wide the Firebase status text can grow so an uploaded key with
    # a long filename can't stretch the whole console window (see the
    # window-too-wide report — this label was the main offender).
    _FIREBASE_LABEL_MAX_WIDTH = 420

    def _refresh_firebase_status(self) -> None:
        label, path = self.controller.firebase_credentials_status()
        if label == "not configured":
            text, tooltip = "Not configured — push notifications disabled", ""
        else:
            text, tooltip = f"{label} ({Path(path).name})", path
        metrics = self.firebase_status_label.fontMetrics()
        elided = metrics.elidedText(text, Qt.ElideMiddle, self._FIREBASE_LABEL_MAX_WIDTH)
        self.firebase_status_label.setText(elided)
        self.firebase_status_label.setToolTip(tooltip or text)

    def _upload_firebase_key(self) -> None:
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Select Firebase Service Account Key", "", "JSON Files (*.json)"
        )
        if not file_path:
            return
        try:
            destination = self.controller.upload_firebase_credentials(Path(file_path))
        except OSError as exc:
            QMessageBox.warning(self, "Upload Failed", str(exc))
            return
        self.settings.firebase_credentials_path = str(destination)
        self.store.save(self.settings)
        self._append_log(f"Firebase key uploaded ({destination}). Restart the server to apply.")
        self._refresh_firebase_status()

    def _run_operation(self, label: str, target: Callable[[], None]) -> None:
        def runner() -> None:
            try:
                target(); self.operation_done.emit(label, True)
            except Exception as exc:  # noqa: BLE001 - display operational errors to user
                self.log_line.emit(f"{label} failed: {exc}"); self.operation_done.emit(label, False)
        threading.Thread(target=runner, name=f"sarapp-console-{label.lower().replace(' ', '-')}", daemon=True).start()

    def _start_server(self) -> None:
        try:
            self.settings = self._settings_from_fields(); self.controller.settings = self.settings
            conflict = check_port(self.settings)
            if conflict.sarapp_server:
                if QMessageBox.question(self, "SARApp Server Already Running", conflict.message + " Monitor it instead?") == QMessageBox.Yes:
                    self.controller.monitor_existing(); self._append_log("Monitoring existing SARApp server."); self._refresh_status()
                return
            if not conflict.available:
                QMessageBox.critical(self, "Port Unavailable", conflict.message); self._append_log(conflict.message); return
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Settings", str(exc)); return
        self._append_log("Starting server...")
        self._run_operation("Start server", self.controller.start)

    def _stop_server(self) -> None:
        self._append_log("Stopping server...")
        self._run_operation("Stop server", self.controller.stop)

    def _restart_server(self) -> None:
        try:
            self.settings = self._settings_from_fields(); self.controller.settings = self.settings; self.store.save(self.settings)
        except ValueError as exc:
            QMessageBox.warning(self, "Invalid Settings", str(exc)); return
        self._append_log("Restarting server with current settings...")
        self._run_operation("Restart server", self.controller.restart)

    def _copy_address(self) -> None:
        QApplication.clipboard().setText(self.settings.base_url)
        self._append_log(f"Copied server address: {self.settings.base_url}")

    def _active_connect_code(self) -> str:
        """Return the code the running tunnel uses, or the configured one."""

        manager = self.controller.manager
        if manager is not None:
            return manager.tunnel_client.connect_code
        return self.settings.connect_code

    def _copy_connect_code(self) -> None:
        code = self._active_connect_code()
        if not code:
            QMessageBox.information(self, "No Connect Code", "No connect code is configured yet. Set one in Settings or start the server to auto-generate one.")
            return
        QApplication.clipboard().setText(code)
        self._append_log(f"Copied connect code: {code}")

    def _generate_connect_code(self) -> None:
        code = generate_connect_code()
        self.connect_code_edit.setText(code)
        self._append_log(f"Generated connect code {code}. Save settings to keep it.")

    def _open_health_check(self) -> None:
        url = f"{self.settings.base_url}/health"
        result = fetch_health(self.settings.base_url, timeout_seconds=2.0)
        self._append_log("Health check success." if result.ok else f"Health check failed: {result.message or result.status}")
        webbrowser.open(url)

    def _poll_health(self) -> None:
        if self.controller.state not in {ConsoleServerState.RUNNING, ConsoleServerState.MONITORING}:
            if self._last_health_status != "Stopped":
                self._last_health_status = "Stopped"; self._append_log("Health status changed to Stopped.")
                self._apply_client_connections(True, [])
            self._refresh_status(); return
        result = fetch_health(self.settings.base_url, timeout_seconds=1.0)
        status = result.status if result.ok else "Error"
        if status != self._last_health_status:
            self._last_health_status = status
            self._append_log("Health check success." if result.ok else f"Health check error: {result.message}")
        self.health_label.setText(status)
        self._poll_client_connections()
        self._refresh_status()

    def _poll_client_connections(self) -> None:
        """Refresh the client connections table off the UI thread."""

        if self._client_connections_poll_active:
            return
        self._client_connections_poll_active = True
        base_url = self.settings.base_url

        def runner() -> None:
            try:
                connections = fetch_client_connections(base_url, timeout_seconds=2.0)
                self.client_connections_updated.emit(True, connections)
            except Exception as exc:  # noqa: BLE001 - surface polling errors in the log
                if self._last_client_connections_ok is not False:
                    self.log_line.emit(self.logs.add(f"Client connection poll failed: {exc}"))
                self.client_connections_updated.emit(False, [])
            finally:
                self._client_connections_poll_active = False
        threading.Thread(target=runner, name="sarapp-console-client-connections-poll", daemon=True).start()

    def _apply_client_connections(self, ok: bool, connections: list) -> None:
        if not ok:
            if self._last_client_connections_ok is not False:
                self.clients_label.setText("Connected clients: unavailable (connection API unreachable)")
            self._last_client_connections_ok = False
            return
        self._last_client_connections_ok = True
        self.clients_label.setText(f"Connected clients: {len(connections)}")
        self.clients_table.setRowCount(len(connections))
        for row, connection in enumerate(connections):
            display = connection.get("display_name") or connection.get("person_id") or connection.get("person_record") or ""
            team = connection.get("team_name") or connection.get("team_id") or ""
            tracking = "On" if connection.get("location_tracking_enabled") else "Off"
            push = "FCM" if connection.get("fcm_token") else ""
            values = [
                str(display),
                str(team),
                str(connection.get("platform") or ""),
                str(connection.get("device_name") or connection.get("device_id") or ""),
                tracking,
                push,
                str(connection.get("status") or ""),
                str(connection.get("last_seen_at") or ""),
            ]
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.clients_table.setItem(row, column, item)

    @staticmethod
    def _traffic_time_display(timestamp: str) -> str:
        try:
            return datetime.fromisoformat(timestamp).astimezone().strftime("%H:%M:%S")
        except ValueError:
            return timestamp

    def _poll_traffic(self) -> None:
        if self.traffic_pause_check.isChecked():
            return
        entries = self.controller.traffic.entries_since(self._traffic_seq)
        if not entries:
            return
        self._traffic_seq = entries[-1]["seq"]
        self._append_traffic_rows(entries)

    def _append_traffic_rows(self, entries: list) -> None:
        show_polling = self.traffic_polling_check.isChecked()
        scrollbar = self.traffic_table.verticalScrollBar()
        follow_tail = scrollbar.value() >= scrollbar.maximum() - 4
        for entry in entries:
            if not show_polling and entry.get("path") in self._CONSOLE_POLL_PATHS:
                continue
            path = str(entry.get("path") or "")
            query = str(entry.get("query") or "")
            values = [
                self._traffic_time_display(str(entry.get("timestamp") or "")),
                str(entry.get("client") or ""),
                str(entry.get("method") or ""),
                f"{path}?{query}" if query else path,
                str(entry.get("status") or ""),
                str(entry.get("duration_ms") or ""),
            ]
            row = self.traffic_table.rowCount()
            self.traffic_table.insertRow(row)
            for column, value in enumerate(values):
                item = QTableWidgetItem(value)
                item.setFlags(item.flags() & ~Qt.ItemIsEditable)
                self.traffic_table.setItem(row, column, item)
        # Keep the widget bounded like the underlying ring buffer.
        while self.traffic_table.rowCount() > 1000:
            self.traffic_table.removeRow(0)
        self._update_traffic_count()
        if follow_tail:
            self.traffic_table.scrollToBottom()

    def _update_traffic_count(self) -> None:
        shown = self.traffic_table.rowCount()
        total = self.controller.traffic.total_recorded
        self.traffic_count_label.setText(f"{shown} requests shown / {total} recorded")

    def _rebuild_traffic_table(self) -> None:
        self.traffic_table.setRowCount(0)
        self._traffic_seq = -1
        entries = self.controller.traffic.entries_since(self._traffic_seq)
        if entries:
            self._traffic_seq = entries[-1]["seq"]
            self._append_traffic_rows(entries)
        else:
            self._update_traffic_count()

    def _clear_traffic(self) -> None:
        self.controller.traffic.clear()
        self.traffic_table.setRowCount(0)
        self._update_traffic_count()

    def _refresh_status(self) -> None:
        state = self.controller.state.value
        self.status_label.setText(state)
        self.name_label.setText(self.settings.server_name)
        self.host_label.setText(self.settings.host)
        self.port_label.setText(str(self.settings.port))
        manager = self.controller.manager
        self.server_id_label.setText(manager.server_info.server_id if manager else "Not started")
        self.started_label.setText(datetime.now(timezone.utc).isoformat() if state == "Running" and self.started_label.text() == "Not started" else self.started_label.text())
        broadcasting = state == "Running" and self.settings.discovery_enabled
        self.discovery_label.setText("Broadcasting" if broadcasting else "Not broadcasting")
        tunnel = manager.tunnel_client if manager else None
        if tunnel is None:
            if self.settings.cloud_router_url:
                code = self.settings.connect_code or "auto-generated at start"
                self.tunnel_label.setText(f"Configured — connect code {code}")
            else:
                self.tunnel_label.setText("Disabled")
        elif not tunnel.enabled:
            self.tunnel_label.setText("Disabled")
        elif tunnel.connected:
            self.tunnel_label.setText(f"Connected — connect code {tunnel.connect_code}")
        else:
            self.tunnel_label.setText(f"Connecting… — connect code {tunnel.connect_code}")
        self.stop_button.setEnabled(state in {"Running", "Starting", "Monitoring"})
        self.start_button.setEnabled(state in {"Stopped", "Error"})

    def _operation_finished(self, label: str, success: bool) -> None:
        self._append_log(f"{label} completed." if success else f"{label} did not complete.")
        if label.startswith("Stop"):
            self.started_label.setText("Not started")
        self._refresh_status()

    def closeEvent(self, event) -> None:  # noqa: N802 - Qt override signature
        logging.getLogger().removeHandler(self._log_handler)
        super().closeEvent(event)

    def _append_log(self, message: str) -> None:
        self._append_log_from_thread(self.logs.add(message))

    def _append_log_from_thread(self, line: str) -> None:
        self.log_text.append(line)
