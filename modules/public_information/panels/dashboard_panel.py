"""Main dashboard for the Public Information module."""
from __future__ import annotations

from typing import Any

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QHBoxLayout, QLabel, QListWidget, QListWidgetItem, QStackedWidget, QVBoxLayout, QWidget

from modules.public_information.panels.message_manager import MessageManagerPanel
from modules.public_information.panels.simple_panels import (
    DistributionLogPanel,
    MediaLogPanel,
    MisinformationPanel,
    TalkingPointsPanel,
    TemplateManagerPanel,
)
from modules.public_information.services import PublicInformationRepository
from modules.public_information.widgets.common import SummaryCard


class PublicInformationDashboardPanel(QWidget):
    """Top-level Public Information workspace with navigation and summaries."""

    def __init__(self, incident_id: str | None = None, current_user: dict[str, Any] | None = None, parent=None):
        super().__init__(parent)
        self.repo = PublicInformationRepository(incident_id)
        self.current_user = current_user or {}
        self.setWindowTitle("Public Information")
        root = QVBoxLayout(self)
        self.cards: dict[str, SummaryCard] = {}
        cards_layout = QHBoxLayout()
        for title in [
            "Pending Approvals",
            "Draft Messages",
            "Published / Released Messages",
            "Media Follow-Ups",
            "Active Misinformation Items",
            "Next Briefing / Next Update",
        ]:
            card = SummaryCard(title)
            self.cards[title] = card
            cards_layout.addWidget(card)
        root.addLayout(cards_layout)
        body = QHBoxLayout()
        self.nav = QListWidget()
        self.nav.setMaximumWidth(230)
        self.stack = QStackedWidget()
        self.sections = [
            ("Messages / Releases", MessageManagerPanel(self.repo, self.current_user)),
            ("Misinformation Tracker", MisinformationPanel(self.repo)),
            ("Media Log", MediaLogPanel(self.repo, self.current_user)),
            ("Talking Points", TalkingPointsPanel(self.repo)),
            ("Letterhead / Templates", TemplateManagerPanel(self.repo)),
            ("Distribution Log", DistributionLogPanel(self.repo)),
            ("Integration Hooks", self._integration_page()),
        ]
        for name, panel in self.sections:
            self.nav.addItem(QListWidgetItem(name))
            self.stack.addWidget(panel)
        self.nav.currentRowChanged.connect(self.stack.setCurrentIndex)
        self.nav.currentRowChanged.connect(lambda _row: self.refresh_summary())
        self.nav.setCurrentRow(0)
        body.addWidget(self.nav)
        body.addWidget(self.stack, 1)
        root.addLayout(body, 1)
        for _name, panel in self.sections:
            signal = getattr(panel, "changed", None)
            if signal is not None:
                signal.connect(self.refresh_summary)
        self.refresh_summary()

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
        counts = self.repo.summary_counts()
        for title, card in self.cards.items():
            card.set_value(counts.get(title, 0))
