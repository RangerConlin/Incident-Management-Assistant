from __future__ import annotations

from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QLabel,
    QPushButton,
    QHBoxLayout,
    QMessageBox,
)

from server import lan_host_service
from shared.lan_config import DEFAULT_LAN_PORT
from shared.lan_runtime import lan_runtime


class LanHostStatusPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LAN Host Status")
        root = QVBoxLayout(self)

        self.status = QLabel()
        self.address = QLabel()
        self.incident = QLabel()
        self.clients = QLabel()
        self.warn = QLabel()
        root.addWidget(self.status)
        root.addWidget(self.address)
        root.addWidget(self.incident)
        root.addWidget(self.clients)
        root.addWidget(self.warn)

        btns = QHBoxLayout()
        self.start_btn = QPushButton("Start hosting")
        self.stop_btn = QPushButton("Stop hosting")
        self.copy_btn = QPushButton("Copy address")
        self.refresh_btn = QPushButton("Refresh network info")
        btns.addWidget(self.start_btn)
        btns.addWidget(self.stop_btn)
        btns.addWidget(self.copy_btn)
        btns.addWidget(self.refresh_btn)
        root.addLayout(btns)
        root.addStretch(1)

        self.start_btn.clicked.connect(self._start)
        self.stop_btn.clicked.connect(self._stop)
        self.copy_btn.clicked.connect(self._copy)
        self.refresh_btn.clicked.connect(self.refresh)

        self.refresh()

    def _start(self) -> None:
        ok, msg = lan_host_service.start(port=DEFAULT_LAN_PORT)
        if ok:
            lan_runtime.set_mode("host")
        else:
            QMessageBox.warning(self, "Host Mode", msg)
        self.refresh()

    def _stop(self) -> None:
        lan_host_service.stop()
        if lan_runtime.mode == "host":
            lan_runtime.set_mode("local")
        self.refresh()

    def _copy(self) -> None:
        QGuiApplication.clipboard().setText(f"{lan_host_service.primary_lan_ip()}:{lan_host_service.port}")

    def refresh(self) -> None:
        active = lan_host_service.active_incident()
        ip = lan_host_service.primary_lan_ip()
        self.status.setText(f"Hosting: {'ON' if lan_host_service.is_running else 'OFF'}")
        self.address.setText(f"Connect clients to: {ip}:{lan_host_service.port}")
        self.incident.setText(f"Active incident: {active or '(none)'}")
        self.clients.setText(f"Connected clients: {lan_host_service.connected_clients}")
        if ip.startswith("127."):
            self.warn.setText("Warning: only localhost is available; LAN clients cannot connect.")
        else:
            ips = ", ".join(lan_host_service.lan_ipv4_addresses())
            self.warn.setText(f"LAN IPv4: {ips}")


__all__ = ["LanHostStatusPanel"]
