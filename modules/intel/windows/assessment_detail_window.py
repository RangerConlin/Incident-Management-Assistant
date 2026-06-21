"""AssessmentDetailWindow — modeless window for a single Assessment record."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QTabWidget, QDialog,
    QFormLayout, QTextEdit, QComboBox, QDialogButtonBox, QLineEdit,
)
from PySide6.QtCore import Qt, Signal

from modules.intel.models.assessments import Assessment, AssessmentStatus
from modules.intel.widgets.status_chip import StatusChip
from modules.intel.services.intel_service import IntelService


class _FieldRow(QWidget):
    def __init__(self, label: str, value: str | None, parent=None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 2, 0, 2)
        lbl = QLabel(label + ":")
        lbl.setStyleSheet("font-weight: 600; min-width: 140px;")
        lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
        val = QLabel(value or "—")
        val.setWordWrap(True)
        layout.addWidget(lbl)
        layout.addWidget(val, 1)


class _EditAssessmentDialog(QDialog):
    def __init__(self, assessment: Assessment, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Assessment")
        self.setMinimumWidth(480)
        self.updates: dict | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self._title = QLineEdit(assessment.title)
        form.addRow("Title *", self._title)

        self._status = QComboBox()
        self._status.addItems([
            AssessmentStatus.DRAFT,
            AssessmentStatus.IN_PROGRESS,
            AssessmentStatus.COMPLETE,
            AssessmentStatus.ARCHIVED,
        ])
        self._status.setCurrentText(assessment.status)
        form.addRow("Status", self._status)

        self._analyst = QLineEdit(assessment.analyst or "")
        form.addRow("Analyst", self._analyst)

        self._summary = QTextEdit()
        self._summary.setPlainText(assessment.summary or "")
        self._summary.setFixedHeight(80)
        form.addRow("Summary", self._summary)

        self._findings = QTextEdit()
        self._findings.setPlainText(assessment.findings or "")
        self._findings.setFixedHeight(100)
        form.addRow("Findings", self._findings)

        self._recommendations = QTextEdit()
        self._recommendations.setPlainText(assessment.recommendations or "")
        self._recommendations.setFixedHeight(80)
        form.addRow("Recommendations", self._recommendations)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_save(self) -> None:
        title = self._title.text().strip()
        if not title:
            return
        self.updates = {
            "title": title,
            "status": self._status.currentText(),
            "analyst": self._analyst.text().strip() or None,
            "summary": self._summary.toPlainText().strip() or None,
            "findings": self._findings.toPlainText().strip() or None,
            "recommendations": self._recommendations.toPlainText().strip() or None,
        }
        self.accept()


class AssessmentDetailWindow(QMainWindow):
    """Modeless window showing full detail for a single Assessment."""

    assessment_updated = Signal(object)   # emits updated Assessment

    def __init__(
        self,
        assessment: Assessment,
        service: IntelService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._assessment = assessment
        self._service = service

        self.setWindowTitle(f"Assessment {assessment.display_number}: {assessment.title}")
        self.resize(700, 540)
        self.setAttribute(Qt.WA_DeleteOnClose)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_header())

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_overview_tab(), "Overview")
        self._tabs.addTab(self._build_findings_tab(), "Findings & Recommendations")
        self._tabs.addTab(self._build_links_tab(), "Linked Records")
        self._tabs.addTab(QWidget(), "History")
        root.addWidget(self._tabs)

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: palette(dark); padding: 12px;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        num_lbl = QLabel(self._assessment.display_number)
        num_lbl.setStyleSheet("font-size: 13px; font-weight: 700; color: palette(placeholderText);")

        title_lbl = QLabel(self._assessment.title)
        title_lbl.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: palette(bright-text);"
        )

        status_chip = StatusChip(self._assessment.status)

        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit)

        layout.addWidget(num_lbl)
        layout.addWidget(title_lbl)
        layout.addStretch()
        layout.addWidget(status_chip)
        layout.addWidget(edit_btn)
        return w

    def _build_overview_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        a = self._assessment
        layout.addWidget(_FieldRow("Assessment #", a.display_number))
        layout.addWidget(_FieldRow("Status", a.status))
        layout.addWidget(_FieldRow("Analyst", a.analyst))
        layout.addWidget(_FieldRow("Created By", a.created_by))
        layout.addWidget(_FieldRow("Created", a.created_at[:16].replace("T", "  ")))
        layout.addWidget(_FieldRow("Updated", a.updated_at[:16].replace("T", "  ")))

        if a.summary:
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            layout.addWidget(sep)
            lbl = QLabel("Summary")
            lbl.setStyleSheet("font-weight: 700;")
            layout.addWidget(lbl)
            body = QLabel(a.summary)
            body.setWordWrap(True)
            layout.addWidget(body)

        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_findings_tab(self) -> QWidget:
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        inner = QWidget()
        layout = QVBoxLayout(inner)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(12)

        a = self._assessment

        findings_lbl = QLabel("Findings")
        findings_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(findings_lbl)
        findings_body = QLabel(a.findings or "No findings recorded.")
        findings_body.setWordWrap(True)
        layout.addWidget(findings_body)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        rec_lbl = QLabel("Recommendations")
        rec_lbl.setStyleSheet("font-size: 14px; font-weight: 700;")
        layout.addWidget(rec_lbl)
        rec_body = QLabel(a.recommendations or "No recommendations recorded.")
        rec_body.setWordWrap(True)
        layout.addWidget(rec_body)

        layout.addStretch()
        scroll.setWidget(inner)
        return scroll

    def _build_links_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)

        a = self._assessment
        has_any = False

        if a.linked_subject_ids:
            has_any = True
            layout.addWidget(QLabel(f"Linked Subjects ({len(a.linked_subject_ids)})"))
            for sid in a.linked_subject_ids:
                layout.addWidget(QLabel(f"  • {sid}"))

        if a.linked_item_ids:
            has_any = True
            layout.addWidget(QLabel(f"Linked Intel Items ({len(a.linked_item_ids)})"))
            for iid in a.linked_item_ids:
                layout.addWidget(QLabel(f"  • {iid}"))

        if not has_any:
            layout.addWidget(QLabel("No linked records."))

        layout.addStretch()
        return w

    def _edit(self) -> None:
        dlg = _EditAssessmentDialog(self._assessment, self)
        if dlg.exec() == QDialog.Accepted and dlg.updates:
            updated = self._service.assessments.update(self._assessment.id, dlg.updates)
            if updated:
                self._assessment = updated
                self.setWindowTitle(
                    f"Assessment {updated.display_number}: {updated.title}"
                )
                self.assessment_updated.emit(updated)
                # Rebuild overview and findings tabs
                self._tabs.removeTab(0)
                self._tabs.insertTab(0, self._build_overview_tab(), "Overview")
                self._tabs.removeTab(1)
                self._tabs.insertTab(1, self._build_findings_tab(), "Findings & Recommendations")
                self._tabs.setCurrentIndex(0)
