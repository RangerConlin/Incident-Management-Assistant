"""Main dashboard panel for the intel module."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QTabWidget,
    QDialog,
)

from .clue_panel import CluePanel
from .subject_panel import SubjectPanel
from .env_panel import EnvironmentPanel
from .form_center_panel import FormCenterPanel
from .report_panel import ReportPanel
from .clue_editor_dialog import ClueEditorDialog
from .subject_editor import SubjectEditor
from ..models import IntelReport
from .report_panel import _ReportDialog  # reuse internal dialog
from .. import services


class IntelDashboard(QWidget):
    """Top level dashboard combining all intel panels."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.clues = CluePanel()
        self.subjects = SubjectPanel()
        self.env = EnvironmentPanel()
        self.forms = FormCenterPanel()
        self.reports = ReportPanel()

        self.tabs = QTabWidget()
        self.tabs.addTab(self.clues, "Clues")
        self.tabs.addTab(self.subjects, "Subjects")
        self.tabs.addTab(self.env, "Environment")
        self.tabs.addTab(self.forms, "Forms")
        self.tabs.addTab(self.reports, "Reports")

        self.new_clue_btn = QPushButton("New Clue")
        self.new_subject_btn = QPushButton("New Subject")
        self.new_report_btn = QPushButton("New Report")

        quick = QHBoxLayout()
        quick.addWidget(self.new_clue_btn)
        quick.addWidget(self.new_subject_btn)
        quick.addWidget(self.new_report_btn)
        quick.addStretch()

        layout = QVBoxLayout(self)
        layout.addLayout(quick)
        layout.addWidget(self.tabs)

        self.new_clue_btn.clicked.connect(self._new_clue)
        self.new_subject_btn.clicked.connect(self._new_subject)
        self.new_report_btn.clicked.connect(self._new_report)

    def _new_clue(self) -> None:
        dlg = ClueEditorDialog(parent=self)
        if dlg.exec() == QDialog.Accepted:
            try:
                services.add_clue(dlg.clue)
                self.clues.refresh()
            except Exception:
                pass

    def _new_subject(self) -> None:
        dlg = SubjectEditor(parent=self)
        if dlg.exec() == QDialog.Accepted:
            try:
                services.add_subject(dlg.subject)
                self.subjects.refresh()
            except Exception:
                pass

    def _new_report(self) -> None:
        dlg = _ReportDialog(self)
        if dlg.exec() == QDialog.Accepted:
            try:
                services.add_report(dlg.report)
                self.reports.refresh()
            except Exception:
                pass
