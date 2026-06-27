"""Hazardous Weather Outlook viewer window."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QSpacerItem,
    QStatusBar,
    QTextEdit,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..services.api_link import WeatherApiManager
from ..services.settings import weather_settings


class HwoViewerWindow(QMainWindow):
    """Displays the Hazardous Weather Outlook product."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("hwoViewerWindow")
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self.setWindowTitle("Hazardous Weather Outlook")
        self.resize(900, 700)
        self.api = WeatherApiManager.instance()
        self.api.dataUpdated.connect(self._handle_data)
        self.api.fetchFailed.connect(self._handle_error)
        self._last_find_term = ""
        self._setup_ui()
        self._load_state()
        lat, lon = self.api.weather_location()
        if lat is not None and lon is not None:
            self.api.request_hwo(float(lat), float(lon))

    def _setup_ui(self) -> None:
        toolbar = QToolBar("HWO Toolbar", self)
        toolbar.setMovable(False)
        toolbar.setObjectName("hwoToolbar")
        copy_action = QAction("Copy", self)
        copy_action.triggered.connect(self._copy_text)
        toolbar.addAction(copy_action)
        find_action = QAction("Find", self)
        find_action.triggered.connect(self._find_in_text)
        toolbar.addAction(find_action)
        open_action = QAction("Open in Browser", self)
        open_action.triggered.connect(self._open_browser)
        toolbar.addAction(open_action)
        close_action = QAction("Close", self)
        close_action.triggered.connect(self.close)
        toolbar.addAction(close_action)
        self.addToolBar(toolbar)

        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.setContentsMargins(12, 12, 12, 12)
        layout.setSpacing(10)

        header = QHBoxLayout()
        self.issued_label = QLabel("Issued by: —", central)
        header.addWidget(self.issued_label)
        header.addItem(QSpacerItem(20, 20, QSizePolicy.Expanding, QSizePolicy.Minimum))
        self.time_label = QLabel("Time: —", central)
        header.addWidget(self.time_label)
        layout.addLayout(header)

        self.body = QTextEdit(central)
        self.body.setReadOnly(True)
        self.body.setAccessibleName("HWO Text")
        layout.addWidget(self.body)

        self.setCentralWidget(central)
        self.status_bar = QStatusBar(self)
        self.setStatusBar(self.status_bar)

        QWidget.setTabOrder(toolbar, self.body)

    def _copy_text(self) -> None:
        self.body.selectAll()
        self.body.copy()

    def _find_in_text(self) -> None:
        text, ok = QInputDialog.getText(self, "Find", "Find in HWO text:", text=self._last_find_term)
        if not ok or not text:
            return
        self._last_find_term = text
        found = self.body.find(text)
        if not found:
            # Wrap around: move cursor to start and try again.
            cursor = self.body.textCursor()
            cursor.movePosition(cursor.MoveOperation.Start)
            self.body.setTextCursor(cursor)
            found = self.body.find(text)
        if found:
            self.status_bar.showMessage(f"Found: {text}")
        else:
            self.status_bar.showMessage(f"'{text}' not found")

    def _open_browser(self) -> None:
        hwo = getattr(self.api, "_hwo_payload", None) or {}
        url = hwo.get("url")
        if not url:
            self.status_bar.showMessage("No live HWO URL available")
            return
        try:
            import webbrowser

            webbrowser.open(str(url))
            self.status_bar.showMessage("Opened HWO in browser")
        except Exception:
            self.status_bar.showMessage("Could not open browser")

    def _handle_data(self, payload: dict) -> None:
        hwo_text = payload.get("hwo")
        if hwo_text:
            self.body.setPlainText(hwo_text.get("text", ""))
            self.issued_label.setText(f"Issued by: {hwo_text.get('office', '—')}")
            self.time_label.setText(f"Time: {hwo_text.get('time', '—')}")
        else:
            self.body.setPlainText("No Hazardous Weather Outlook available for the current location.")
            self.issued_label.setText("Issued by: —")
            self.time_label.setText("Time: —")

    def _handle_error(self, context: str, error: Exception) -> None:
        if context != "hwo":
            return
        self.status_bar.showMessage(f"HWO load failed: {error}")

    def _load_state(self) -> None:
        settings_store = weather_settings()
        geometry = settings_store.value("geom/HwoViewerWindow")
        if geometry:
            self.restoreGeometry(geometry)

    def closeEvent(self, event) -> None:  # noqa: D401
        weather_settings().set_value("geom/HwoViewerWindow", self.saveGeometry())
        super().closeEvent(event)


def show_window() -> HwoViewerWindow:
    window = HwoViewerWindow()
    window.show()
    window.raise_()
    return window


__all__ = ["HwoViewerWindow", "show_window"]
