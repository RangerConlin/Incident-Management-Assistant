"""PublicInformationWindow — standalone QMainWindow for the PIO dashboard overview.

Each toolbar button opens a separate modeless window for that section.
Never docked. Appears in the Windows taskbar.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from modules.public_information.panels.overview_panel import PIOOverviewPanel
from modules.public_information.services import PublicInformationRepository


_BTN_STYLE = (
    "QPushButton { background:#1E3A5F; color:#FFFFFF; border:none; border-radius:4px; "
    "font-weight:600; font-size:12px; padding:6px 14px; }"
    "QPushButton:hover { background:#2D5282; }"
    "QPushButton:pressed { background:#1A2F4A; }"
)


class _SectionWindow(QMainWindow):
    """Generic wrapper that hosts one PIO section panel as a standalone window."""

    def __init__(self, title: str, widget: QWidget, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Public Information — {title}")
        self.resize(1200, 750)
        self.setMinimumSize(700, 500)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.Window)
        self.setCentralWidget(widget)


class PublicInformationWindow(QMainWindow):
    """PIO dashboard overview window.

    A top button bar opens each section (Messages, Media Log, etc.) in its
    own independent modeless window.  This overview window never contains tabs.
    """

    def __init__(
        self,
        incident_id: Optional[str] = None,
        current_user: Optional[dict[str, Any]] = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._incident_id = incident_id
        self._current_user = current_user or {}
        self._repo = PublicInformationRepository(incident_id)
        self._section_windows: dict[str, _SectionWindow] = {}

        self.setWindowTitle("Public Information")
        self.resize(1400, 820)
        self.setMinimumSize(900, 600)
        self.setAttribute(Qt.WA_DeleteOnClose)
        self.setWindowFlags(Qt.Window)

        # ── central widget ────────────────────────────────────────────────────
        central = QWidget()
        self.setCentralWidget(central)
        from PySide6.QtWidgets import QVBoxLayout
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ── top button bar ────────────────────────────────────────────────────
        bar_widget = QWidget()
        bar_widget.setStyleSheet("background:#111827;")
        bar_widget.setFixedHeight(44)
        bar = QHBoxLayout(bar_widget)
        bar.setContentsMargins(8, 6, 8, 6)
        bar.setSpacing(6)

        self._sections: list[tuple[str, str]] = [
            ("Messages / Releases",    "Messages / Releases"),
            ("Rumor / Misinformation", "Rumor / Misinformation"),
            ("Media Log",              "Media Log"),
            ("Talking Points",         "Talking Points"),
            ("Letterhead / Templates", "Letterhead / Templates"),
            ("Distribution Log",       "Distribution Log"),
        ]
        for label, key in self._sections:
            btn = QPushButton(label)
            btn.setStyleSheet(_BTN_STYLE)
            btn.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
            btn.clicked.connect(lambda _=False, k=key: self._open_section(k))
            bar.addWidget(btn)
        bar.addStretch(1)

        root.addWidget(bar_widget)

        # ── overview panel ────────────────────────────────────────────────────
        self._overview = PIOOverviewPanel(self._repo)
        self._overview.navigate_to.connect(self._open_section)
        root.addWidget(self._overview, 1)

    def _open_section(self, key: str) -> None:
        # Raise existing window if still alive
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
        from modules.public_information.panels.message_manager import MessageManagerPanel
        from modules.public_information.panels.simple_panels import (
            DistributionLogPanel,
            MediaLogPanel,
            MisinformationPanel,
            TalkingPointsPanel,
            TemplateManagerPanel,
        )
        match key:
            case "Messages / Releases":
                return MessageManagerPanel(self._repo, self._current_user)
            case "Rumor / Misinformation":
                return MisinformationPanel(self._repo)
            case "Media Log":
                return MediaLogPanel(self._repo, self._current_user)
            case "Talking Points":
                return TalkingPointsPanel(self._repo)
            case "Letterhead / Templates":
                return TemplateManagerPanel(self._repo)
            case "Distribution Log":
                return DistributionLogPanel(self._repo)
            case _:
                return None

    def load_incident(self, incident_id: str) -> None:
        self._incident_id = incident_id
        self._repo = PublicInformationRepository(incident_id)
        self._overview.repo = self._repo
        self._overview.refresh()

    def switch_to_section(self, key: str) -> None:
        self._open_section(key)
