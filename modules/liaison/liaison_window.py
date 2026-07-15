"""LiaisonWindow — standalone dashboard for the Liaison module.

A top button bar and the overview's own quick links open each section
(Agency Directory, Reporting Board, Customer Requests & Feedback) in its
own modeless window, mirroring the Public Information dashboard's
structure.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from modules.liaison.panels.overview_panel import LiaisonOverviewPanel


class _SectionWindow(QMainWindow):
    """Generic wrapper that hosts one Liaison section panel as a standalone window."""

    def __init__(self, title: str, widget: QWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Liaison — {title}")
        self.resize(1200, 750)
        self.setMinimumSize(700, 500)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.Window)
        self.setCentralWidget(widget)


class LiaisonWindow(QMainWindow):
    """Liaison dashboard overview window.

    A top button bar opens each section (Agency Directory, External
    Coordination) in its own independent modeless window. This overview
    window never contains tabs.
    """

    def __init__(self, incident_id: object | None = None, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._incident_id = incident_id
        self._section_windows: dict[str, _SectionWindow] = {}

        self.setWindowTitle("Liaison")
        self.resize(1300, 800)
        self.setMinimumSize(900, 600)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.Window)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        bar_widget = QWidget()
        bar_widget.setFixedHeight(44)
        bar = QHBoxLayout(bar_widget)
        bar.setContentsMargins(8, 6, 8, 6)
        bar.setSpacing(6)

        self._sections: list[str] = [
            "Agency Directory",
            "Reporting Board",
            "Customer Requests & Feedback",
        ]
        for key in self._sections:
            btn = QPushButton(key)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            btn.clicked.connect(lambda _=False, k=key: self._open_section(k))
            bar.addWidget(btn)
        bar.addStretch(1)
        root.addWidget(bar_widget)

        self._overview = LiaisonOverviewPanel(self._incident_id)
        self._overview.navigate_to.connect(self._open_section)
        self._overview.action_requested.connect(self._handle_action_request)
        root.addWidget(self._overview, 1)

    def _open_section(self, key: str) -> None:
        existing = self._section_windows.get(key)
        if existing is not None:
            try:
                if existing.isVisible():
                    existing.raise_()
                    existing.activateWindow()
                    return
            except RuntimeError:
                pass
            self._section_windows.pop(key, None)

        panel = self._build_panel(key)
        if panel is None:
            return
        win = _SectionWindow(key, panel, parent=None)
        win.destroyed.connect(lambda: self._section_windows.pop(key, None))
        self._section_windows[key] = win
        win.show()

    def _build_panel(self, key: str) -> Optional[QWidget]:
        from modules import liaison

        match key:
            case "Agency Directory":
                return liaison.get_agencies_panel(self._incident_id)
            case "Reporting Board":
                return liaison.get_reporting_panel(self._incident_id)
            case "Customer Requests & Feedback":
                return liaison.get_customer_panel(self._incident_id)
            case _:
                return None

    def load_incident(self, incident_id: object | None) -> None:
        self._incident_id = incident_id
        self._overview.incident_id = incident_id
        self._overview.refresh()
        for win in list(self._section_windows.values()):
            win.close()
        self._section_windows.clear()

    def switch_to_section(self, key: str) -> None:
        self._open_section(key)

    def _handle_action_request(self, action: str) -> None:
        from modules.liaison.windows import AgencyEditDialog
        from modules.liaison.repository import create_agency

        match action:
            case "add_agency":
                dialog = AgencyEditDialog(self)
                if dialog.exec() == QDialog.Accepted:
                    create_agency(dialog.values(), self._incident_id)
                    self._overview.refresh()
            case "log_interaction":
                QMessageBox.information(
                    self,
                    "Log Interaction",
                    "Select an agency in the Agency Directory, then right-click it "
                    "and choose \"Add Interaction\".",
                )
                self._open_section("Agency Directory")
