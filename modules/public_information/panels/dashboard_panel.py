"""Main dashboard for the Public Information module."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QStackedWidget, QVBoxLayout, QWidget

from modules.public_information.panels.message_manager import MessageManagerPanel
from modules.public_information.panels.overview_panel import PIOOverviewPanel
from modules.public_information.panels.simple_panels import (
    DistributionLogPanel,
    MediaLogPanel,
    MisinformationPanel,
    TalkingPointsPanel,
    TemplateManagerPanel,
)
from modules.public_information.services import PublicInformationRepository


class PublicInformationDashboardPanel(QWidget):
    """Top-level Public Information workspace with navigation and overview dashboard."""

    def __init__(self, incident_id: str | None = None, current_user: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.repo = PublicInformationRepository(incident_id)
        self.current_user = current_user or {}
        self.setWindowTitle("Public Information")
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        self.nav = QListWidget()
        self.nav.setMaximumWidth(200)
        self.stack = QStackedWidget()
        self._overview = PIOOverviewPanel(self.repo)
        self.sections: list[tuple[str, QWidget]] = [
            ("Overview", self._overview),
            ("Messages / Releases", MessageManagerPanel(self.repo, self.current_user)),
            ("Rumor / Misinformation", MisinformationPanel(self.repo)),
            ("Media Log", MediaLogPanel(self.repo, self.current_user)),
            ("Talking Points", TalkingPointsPanel(self.repo)),
            ("Letterhead / Templates", TemplateManagerPanel(self.repo)),
            ("Distribution Log", DistributionLogPanel(self.repo)),
            ("Integration Hooks", self._integration_page()),
        ]
        self._section_index = {name: i for i, (name, _) in enumerate(self.sections)}
        for name, panel in self.sections:
            self.nav.addItem(QListWidgetItem(name))
            self.stack.addWidget(panel)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.currentRowChanged.connect(lambda _row: self._on_nav_change())
        self._overview.navigate_to.connect(self._navigate_by_name)
        self.nav.setCurrentRow(0)
        body.addWidget(self.nav)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)
        for _name, panel in self.sections:
            signal = getattr(panel, "changed", None)
            if signal is not None:
                signal.connect(self._overview.refresh)

    def _navigate_by_name(self, name: str) -> None:
        index = self._section_index.get(name)
        if index is not None:
            self.nav.setCurrentRow(index)

    def _on_nav_change(self) -> None:
        if self.nav.currentRow() == 0:
            self._overview.refresh()

    def _integration_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout(page)
        label = QLabel(
            "Future integration hooks are reserved for command approval, communications alerts, "
            "planning summaries, document export, audit trail, incident database migrations, and role permissions."
        )
        label.setWordWrap(True)
        label.setAlignment(Qt.AlignTop | Qt.AlignLeft)
        layout.addWidget(label)
        layout.addStretch(1)
        return page

    def refresh_summary(self) -> None:
        self._overview.refresh()
