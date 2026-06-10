"""Sunrise and sunset information panel."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import (
    QLabel,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services.api_link import WeatherApiManager


class SunTimesPanel(QWidget):
    """Provides sunrise/sunset and civil twilight times."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("sunTimesPanel")
        self.setWindowFlags(Qt.Tool | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Sunrise / Sunset")
        self.resize(420, 320)
        self.api = WeatherApiManager.instance()
        self.api.dataUpdated.connect(self._handle_data)
        self._setup_ui()

    def _setup_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(8)

        self.location_label = QLabel("Location: —", self)
        layout.addWidget(self.location_label)

        self.today_label = QLabel("Today: Sunrise — / Sunset —", self)
        layout.addWidget(self.today_label)

        self.table = QTableWidget(0, 3, self)
        self.table.setHorizontalHeaderLabels(["Date", "Civil AM", "Civil PM"])
        layout.addWidget(self.table)

        self.copy_button = QPushButton("Copy to Clipboard", self)
        self.copy_button.clicked.connect(self._copy)
        layout.addWidget(self.copy_button)

        QWidget.setTabOrder(self.table, self.copy_button)

    def _handle_data(self, payload: dict) -> None:
        self.table.setRowCount(0)
        self.today_label.setText("Today: Sunrise — / Sunset —")

    def _copy(self) -> None:
        rows = []
        for row in range(self.table.rowCount()):
            values = []
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                values.append(item.text() if item else "")
            rows.append("\t".join(values))
        QGuiApplication.clipboard().setText("\n".join(rows))


def show_window(parent: QWidget | None = None) -> SunTimesPanel:
    panel = SunTimesPanel(parent)
    panel.show()
    panel.raise_()
    return panel


__all__ = ["SunTimesPanel", "show_window"]
