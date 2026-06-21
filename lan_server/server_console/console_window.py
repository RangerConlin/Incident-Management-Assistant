"""PySide6 Qt Widgets window for controlling a SARApp incident server."""

from __future__ import annotations

import threading
import webbrowser
from datetime import datetime, timezone
from typing import Callable

from PySide6.QtCore import QTimer, Qt, Signal
from PySide6.QtWidgets import (
    QApplication,
    QCheckBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSpinBox,
    QTableWidget,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from networking.server_info import SARAPP_VERSION

from .controller import ConsoleServerState, ServerConsoleController, check_port, fetch_health
from .log_model import ConsoleLogBuffer
from .settings import ServerConsoleSettings, ServerConsoleSettingsStore


class ServerConsoleWindow(QMainWindow):
    """Lightweight control panel for a dedicated SARApp server machine."""

    log_line = Signal(str)
    operation_done = Signal(str, bool)

    def __init__(self, store: ServerConsoleSettingsStore | None = None) -> None:
        super().__init__()
        self.store = store or ServerConsoleSettingsStore()
        self.settings = self.store.load()
        self.controller = ServerConsoleController(self.settings)
        self.logs = ConsoleLogBuffer()
        self._last_health_status = "Stopped"
        self.setWindowTitle("SARApp Server Console")
        self.resize(900, 720)
        self._build_ui()
        self._load_settings_into_fields()
        self._connect_signals()
        self._refresh_status()
        self._append_log("Server Console opened. Settings loaded.")

        # Periodic health monitoring updates labels without blocking the UI.
        self.health_timer = QTimer(self)
        self.health_timer.setInterval(3000)
        self.health_timer.timeout.connect(self._poll_health)
        self.health_timer.start()

    def _build_ui(self) -> None:
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
        for title, widget in [
            ("Server status", self.status_label), ("Server name", self.name_label),
            ("Host", self.host_label), ("Port", self.port_label), ("Server ID", self.server_id_label),
            ("Version", self.version_label), ("Started time", self.started_label),
            ("Discovery status", self.discovery_label), ("Health", self.health_label),
        ]:
            form.addRow(title + ":", widget)
        layout.addWidget(status_box)

        controls = QHBoxLayout()
        self.start_button = QPushButton("Start Server")
        self.stop_button = QPushButton("Stop Server")
        self.restart_button = QPushButton("Restart Server")
        self.copy_button = QPushButton("Copy Server Address")
        self.health_button = QPushButton("Open Health Check")
        for button in [self.start_button, self.stop_button, self.restart_button, self.copy_button, self.health_button]:
            controls.addWidget(button)
        layout.addLayout(controls)

        settings_box = QGroupBox("Settings")
        settings_form = QFormLayout(settings_box)
        self.name_edit = QLineEdit()
        self.host_edit = QLineEdit()
        self.port_spin = QSpinBox(); self.port_spin.setRange(1, 65535)
        self.discovery_check = QCheckBox("Enable LAN discovery broadcasting")
        self.discovery_port_spin = QSpinBox(); self.discovery_port_spin.setRange(1, 65535)
        self.save_button = QPushButton("Save Settings")
        settings_form.addRow("Server name:", self.name_edit)
        settings_form.addRow("Host:", self.host_edit)
        settings_form.addRow("Port:", self.port_spin)
        settings_form.addRow("Discovery:", self.discovery_check)
        settings_form.addRow("Discovery port:", self.discovery_port_spin)
        settings_form.addRow("", self.save_button)
        layout.addWidget(settings_box)

        clients_box = QGroupBox("Client Connections")
        clients_layout = QVBoxLayout(clients_box)
        clients_layout.addWidget(QLabel("Connected Clients: Not implemented yet"))
        table = QTableWidget(0, 4)
        table.setHorizontalHeaderLabels(["Client name", "IP address", "Connected time", "Last heartbeat"])
        table.setEditTriggers(QTableWidget.NoEditTriggers)
        clients_layout.addWidget(table)
        layout.addWidget(clients_box)

        logs_box = QGroupBox("Server Logs / Errors")
        logs_layout = QVBoxLayout(logs_box)
        self.log_text = QTextEdit(); self.log_text.setReadOnly(True)
        logs_layout.addWidget(self.log_text)
        layout.addWidget(logs_box)
        self.setCentralWidget(root)

    def _connect_signals(self) -> None:
        self.start_button.clicked.connect(self._start_server)
        self.stop_button.clicked.connect(self._stop_server)
        self.restart_button.clicked.connect(self._restart_server)
        self.copy_button.clicked.connect(self._copy_address)
        self.health_button.clicked.connect(self._open_health_check)
        self.save_button.clicked.connect(self._save_settings)
        self.log_line.connect(self._append_log_from_thread)
        self.operation_done.connect(self._operation_finished)

    def _settings_from_fields(self) -> ServerConsoleSettings:
        settings = ServerConsoleSettings(
            server_name=self.name_edit.text().strip(), host=self.host_edit.text().strip(),
            port=int(self.port_spin.value()), discovery_enabled=self.discovery_check.isChecked(),
            discovery_port=int(self.discovery_port_spin.value()),
        )
        settings.validate()
        return settings

    def _load_settings_into_fields(self) -> None:
        self.name_edit.setText(self.settings.server_name)
        self.host_edit.setText(self.settings.host)
        self.port_spin.setValue(self.settings.port)
        self.discovery_check.setChecked(self.settings.discovery_enabled)
        self.discovery_port_spin.setValue(self.settings.discovery_port)

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

    def _open_health_check(self) -> None:
        url = f"{self.settings.base_url}/health"
        result = fetch_health(self.settings.base_url, timeout_seconds=2.0)
        self._append_log("Health check success." if result.ok else f"Health check failed: {result.message or result.status}")
        webbrowser.open(url)

    def _poll_health(self) -> None:
        if self.controller.state not in {ConsoleServerState.RUNNING, ConsoleServerState.MONITORING}:
            if self._last_health_status != "Stopped":
                self._last_health_status = "Stopped"; self._append_log("Health status changed to Stopped.")
            self._refresh_status(); return
        result = fetch_health(self.settings.base_url, timeout_seconds=1.0)
        status = result.status if result.ok else "Error"
        if status != self._last_health_status:
            self._last_health_status = status
            self._append_log("Health check success." if result.ok else f"Health check error: {result.message}")
        self.health_label.setText(status)
        self._refresh_status()

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
        self.stop_button.setEnabled(state in {"Running", "Starting", "Monitoring"})
        self.start_button.setEnabled(state in {"Stopped", "Error"})

    def _operation_finished(self, label: str, success: bool) -> None:
        self._append_log(f"{label} completed." if success else f"{label} did not complete.")
        if label.startswith("Stop"):
            self.started_label.setText("Not started")
        self._refresh_status()

    def _append_log(self, message: str) -> None:
        self._append_log_from_thread(self.logs.add(message))

    def _append_log_from_thread(self, line: str) -> None:
        self.log_text.append(line)
