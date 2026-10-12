"""Main dashboard for the Public Information module."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QStackedWidget, QVBoxLayout, QWidget

from modules.public_information import open_release_editor, open_release_manager
from modules.public_information.panels.overview_panel import PIOOverviewPanel
from modules.public_information.panels.release_manager import ReleaseManagerPanel
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
            ("Messages / Releases", ReleaseManagerPanel(self.repo, self.current_user)),
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
        self._overview.action_requested.connect(self._handle_action_request)
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

    def _handle_action_request(self, action: str) -> None:
        match action:
            case "new_release":
                open_release_editor(self.repo.incident_id, self.current_user, parent=self)
            case "draft_response":
                open_release_editor(
                    self.repo.incident_id,
                    self.current_user,
                    defaults={
                        "status": "Draft",
                        "type": "Holding Statement",
                        "audience": "Media",
                        "priority": "Normal",
                    },
                    parent=self,
                )
            case "approval_queue":
                open_release_manager(self.repo.incident_id, self.current_user, "Pending Approval", parent=self)
            case "publish_update":
                self.nav.setCurrentRow(self._section_index["Distribution Log"])
            case "media_log":
                self.nav.setCurrentRow(self._section_index["Media Log"])

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
