from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QMessageBox,
)

from shared.lan_runtime import lan_runtime


class LanClientConnectionPanel(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("LAN Client Connection")
        root = QVBoxLayout(self)

        host_row = QHBoxLayout()
        host_row.addWidget(QLabel("Host IP:"))
        self.host_edit = QLineEdit(lan_runtime.client.host)
        host_row.addWidget(self.host_edit, 1)
        root.addLayout(host_row)

        port_row = QHBoxLayout()
        port_row.addWidget(QLabel("Port:"))
        self.port_edit = QLineEdit(str(lan_runtime.client.port))
        port_row.addWidget(self.port_edit)
        root.addLayout(port_row)

        btn_row = QHBoxLayout()
        self.connect_btn = QPushButton("Connect")
        self.disconnect_btn = QPushButton("Disconnect")
        self.refresh_btn = QPushButton("Refresh from host")
        btn_row.addWidget(self.connect_btn)
        btn_row.addWidget(self.disconnect_btn)
        btn_row.addWidget(self.refresh_btn)
        root.addLayout(btn_row)

        self.status_label = QLabel("Disconnected")
        self.target_label = QLabel("Host: -")
        root.addWidget(self.status_label)
        root.addWidget(self.target_label)
        root.addStretch(1)

        self.connect_btn.clicked.connect(self._connect)
        self.disconnect_btn.clicked.connect(self._disconnect)
        self.refresh_btn.clicked.connect(self._refresh)

        lan_runtime.client.connectionStateChanged.connect(self._on_state_changed)
        lan_runtime.client.bootstrapReceived.connect(lan_runtime.apply_bootstrap_to_signals)
        lan_runtime.client.eventReceived.connect(lan_runtime.apply_event_to_signals)

    def _connect(self) -> None:
        host = self.host_edit.text().strip()
        try:
            port = int(self.port_edit.text().strip())
        except Exception:
            QMessageBox.warning(self, "LAN", "Port must be a number")
            return
        ok, msg = lan_runtime.client.connect_to_host(host, port)
        if ok:
            lan_runtime.set_mode("client")
        else:
            QMessageBox.warning(self, "LAN Connect Failed", msg)

    def _disconnect(self) -> None:
        lan_runtime.client.disconnect()
        if lan_runtime.mode == "client":
            lan_runtime.set_mode("local")

    def _refresh(self) -> None:
        ok, msg = lan_runtime.client.refresh_from_host()
        if not ok:
            QMessageBox.warning(self, "LAN Refresh", msg)

    def _on_state_changed(self, state: str, detail: str) -> None:
        self.status_label.setText(f"State: {state.title()}" + (f" ({detail})" if detail else ""))
        self.target_label.setText(f"Host: {lan_runtime.client.host}:{lan_runtime.client.port}")


__all__ = ["LanClientConnectionPanel"]
