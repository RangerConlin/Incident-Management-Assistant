"""AssessmentDetailWindow — modeless window for a single Assessment record."""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QTabWidget, QDialog,
    QFormLayout, QTextEdit, QComboBox, QDialogButtonBox, QLineEdit,
    QMessageBox, QTableWidget, QTableWidgetItem, QHeaderView,
    QAbstractItemView,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QColor, QBrush

from modules.intel.models.assessments import Assessment, AssessmentStatus
from modules.intel.widgets.status_chip import StatusChip
from modules.intel.services.intel_service import IntelService
from utils.table_view_styles import apply_statusboard_table_behavior


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


class _LinkSubjectDialog(QDialog):
    """Prompt the analyst to enter a Subject ID to link."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Link Subject")
        self.setMinimumWidth(340)
        self.subject_id: str = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enter Subject ID to link:"))
        self._id_edit = QLineEdit()
        self._id_edit.setPlaceholderText("Subject ID")
        layout.addWidget(self._id_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_ok(self) -> None:
        v = self._id_edit.text().strip()
        if v:
            self.subject_id = v
            self.accept()


class _LinkItemDialog(QDialog):
    """Prompt the analyst to enter an Intel Item ID to link."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Link Intel Item")
        self.setMinimumWidth(340)
        self.item_id: str = ""

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Enter Intel Item ID to link:"))
        self._id_edit = QLineEdit()
        self._id_edit.setPlaceholderText("Intel Item ID")
        layout.addWidget(self._id_edit)

        btns = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_ok)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_ok(self) -> None:
        v = self._id_edit.text().strip()
        if v:
            self.item_id = v
            self.accept()


# Log entry background tints (matches log_tab.py palette)
_LOG_BG: dict[str, QColor] = {
    "subject":     QColor(180, 40,  40,  90),
    "lead":        QColor(180, 140, 20,  80),
    "item":        QColor(30,  100, 200, 80),
    "assessment":  QColor(40,  160, 80,  70),
    "observation": QColor(20,  140, 180, 70),
}
_LOG_EVENT_LABELS = {
    "created": "Created", "updated": "Updated", "status_changed": "Status Changed",
    "completed": "Completed", "archived": "Archived", "linked": "Linked",
    "unlinked": "Unlinked",
}


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
        self.resize(720, 580)
        self.setAttribute(Qt.WA_DeleteOnClose)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_header())
        root.addWidget(self._build_action_bar())

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_overview_tab(), "Overview")
        self._tabs.addTab(self._build_findings_tab(), "Findings & Recommendations")
        self._links_tab_index = 2
        self._history_tab_index = 3
        self._tabs.addTab(self._build_links_tab(), "Linked Records")
        self._tabs.addTab(self._build_history_tab(), "History")
        root.addWidget(self._tabs)

    # ------------------------------------------------------------------
    # Header and action bar

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

        self._status_chip = StatusChip(self._assessment.status)

        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit)

        layout.addWidget(num_lbl)
        layout.addWidget(title_lbl)
        layout.addStretch()
        layout.addWidget(self._status_chip)
        layout.addWidget(edit_btn)
        return w

    def _build_action_bar(self) -> QWidget:
        w = QWidget()
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 6, 16, 6)
        layout.setSpacing(8)

        self._complete_btn = QPushButton("Mark Complete")
        self._complete_btn.clicked.connect(self._mark_complete)
        self._complete_btn.setEnabled(
            self._assessment.status not in (AssessmentStatus.COMPLETE, AssessmentStatus.ARCHIVED)
        )

        self._archive_btn = QPushButton("Archive")
        self._archive_btn.clicked.connect(self._archive)
        self._archive_btn.setEnabled(self._assessment.status != AssessmentStatus.ARCHIVED)

        layout.addWidget(self._complete_btn)
        layout.addWidget(self._archive_btn)
        layout.addStretch()
        return w

    # ------------------------------------------------------------------
    # Tab builders

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
        layout.addWidget(_FieldRow("Created", a.created_at[:16].replace("T", "  ") if a.created_at else ""))
        layout.addWidget(_FieldRow("Updated", a.updated_at[:16].replace("T", "  ") if a.updated_at else ""))

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
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        # Action buttons
        btn_row = QHBoxLayout()
        link_sub_btn = QPushButton("+ Link Subject")
        link_sub_btn.clicked.connect(self._link_subject)
        link_item_btn = QPushButton("+ Link Intel Item")
        link_item_btn.clicked.connect(self._link_item)
        btn_row.addWidget(link_sub_btn)
        btn_row.addWidget(link_item_btn)
        btn_row.addStretch()
        layout.addLayout(btn_row)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._links_body = QVBoxLayout()
        self._links_body.setSpacing(4)
        layout.addLayout(self._links_body)
        layout.addStretch()

        self._populate_links_body()
        return w

    def _populate_links_body(self) -> None:
        """Clear and repopulate the links body layout."""
        while self._links_body.count():
            item = self._links_body.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        a = self._assessment
        has_any = False

        if a.linked_subject_ids:
            has_any = True
            hdr = QLabel(f"Subjects ({len(a.linked_subject_ids)})")
            hdr.setStyleSheet("font-weight: 700; margin-top: 4px;")
            self._links_body.addWidget(hdr)
            for sid in a.linked_subject_ids:
                self._links_body.addWidget(self._make_link_row("subject", sid))

        if a.linked_item_ids:
            has_any = True
            hdr = QLabel(f"Intel Items ({len(a.linked_item_ids)})")
            hdr.setStyleSheet("font-weight: 700; margin-top: 8px;")
            self._links_body.addWidget(hdr)
            for iid in a.linked_item_ids:
                self._links_body.addWidget(self._make_link_row("item", iid))

        if not has_any:
            self._links_body.addWidget(QLabel("No linked records."))

    def _make_link_row(self, kind: str, record_id: str) -> QWidget:
        row = QWidget()
        hl = QHBoxLayout(row)
        hl.setContentsMargins(0, 2, 0, 2)
        hl.setSpacing(6)

        # Resolve label
        label_text = record_id
        record_obj = None
        try:
            if kind == "subject" and self._service:
                record_obj = self._service.subjects.get(record_id)
                if record_obj:
                    subject_type = getattr(record_obj, "subject_type", "") or ""
                    label_text = f"{record_obj.name} — {subject_type}" if subject_type else record_obj.name
            elif kind == "item" and self._service:
                record_obj = self._service.items.get(record_id)
                if record_obj:
                    item_type = getattr(record_obj, "item_type", "") or ""
                    label_text = f"{record_obj.title} — {item_type}" if item_type else record_obj.title
        except Exception:
            pass

        lbl = QLabel(f"• {label_text}")
        lbl.setWordWrap(True)
        hl.addWidget(lbl, 1)

        if record_obj is not None:
            open_btn = QPushButton("Open")
            open_btn.setFixedWidth(52)
            open_btn.setFixedHeight(22)
            if kind == "subject":
                open_btn.clicked.connect(lambda _, o=record_obj: self._open_subject(o))
            else:
                open_btn.clicked.connect(lambda _, o=record_obj: self._open_item(o))
            hl.addWidget(open_btn)

        rm_btn = QPushButton("Remove")
        rm_btn.setFixedWidth(60)
        rm_btn.setFixedHeight(22)
        if kind == "subject":
            rm_btn.clicked.connect(lambda _, sid=record_id: self._unlink_subject(sid))
        else:
            rm_btn.clicked.connect(lambda _, iid=record_id: self._unlink_item(iid))
        hl.addWidget(rm_btn)

        return row

    def _refresh_links_tab(self) -> None:
        self._populate_links_body()

    def _build_history_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(0, 0, 0, 0)

        cols = ["Time", "Date", "Event", "Summary", "Actor"]
        self._history_table = QTableWidget()
        self._history_table.setColumnCount(len(cols))
        self._history_table.setHorizontalHeaderLabels(cols)
        apply_statusboard_table_behavior(self._history_table)
        self._history_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self._history_table.verticalHeader().setVisible(False)
        self._history_table.setSortingEnabled(False)
        layout.addWidget(self._history_table)
        legend = QLabel("Legend: row colors reflect assessment history context.")
        legend.setStyleSheet("color: palette(placeholderText); font-size: 11px;")
        layout.addWidget(legend)

        self._load_history()
        return w

    def _load_history(self) -> None:
        if not self._service:
            return
        try:
            entries = self._service.log.list(
                entity_type="assessment",
                entity_id=self._assessment.id,
                limit=200,
            )
        except Exception:
            entries = []

        self._history_table.setRowCount(len(entries))
        bg = QBrush(QColor(40, 160, 80, 70))
        for row, e in enumerate(entries):
            ts = e.timestamp or ""
            time_str = ts[11:16] if len(ts) >= 16 else ""
            date_str = ts[:10] if ts else ""
            event_label = _LOG_EVENT_LABELS.get(e.event_type, e.event_type.replace("_", " ").title())
            cells = [time_str, date_str, event_label, e.summary or "", e.actor or ""]
            for col, val in enumerate(cells):
                item = QTableWidgetItem(val)
                item.setBackground(bg)
                self._history_table.setItem(row, col, item)
            self._history_table.setRowHeight(row, 30)
        for col in (0, 1, 2, 4):
            self._history_table.resizeColumnToContents(col)

    # ------------------------------------------------------------------
    # Actions

    def _edit(self) -> None:
        dlg = _EditAssessmentDialog(self._assessment, self)
        if dlg.exec() == QDialog.Accepted and dlg.updates:
            updated = self._service.assessments.update(self._assessment.id, dlg.updates)
            if updated:
                self._assessment = updated
                self._refresh_after_update()

    def _mark_complete(self) -> None:
        updated = self._service.assessments.update(
            self._assessment.id, {"status": AssessmentStatus.COMPLETE}
        )
        if updated:
            self._assessment = updated
            self._refresh_after_update()

    def _archive(self) -> None:
        reply = QMessageBox.question(
            self, "Archive Assessment",
            f"Archive {self._assessment.display_number}? It will be marked as archived.",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply == QMessageBox.Yes:
            updated = self._service.assessments.update(
                self._assessment.id, {"status": AssessmentStatus.ARCHIVED}
            )
            if updated:
                self._assessment = updated
                self._refresh_after_update()

    def _link_subject(self) -> None:
        dlg = _LinkSubjectDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.subject_id:
            ids = list(self._assessment.linked_subject_ids or [])
            if dlg.subject_id not in ids:
                ids.append(dlg.subject_id)
                updated = self._service.assessments.update(
                    self._assessment.id, {"linked_subject_ids": ids}
                )
                if updated:
                    self._assessment = updated
                    self._refresh_links_tab()
                    self.assessment_updated.emit(updated)

    def _unlink_subject(self, subject_id: str) -> None:
        ids = [s for s in (self._assessment.linked_subject_ids or []) if s != subject_id]
        updated = self._service.assessments.update(
            self._assessment.id, {"linked_subject_ids": ids}
        )
        if updated:
            self._assessment = updated
            self._refresh_links_tab()
            self.assessment_updated.emit(updated)

    def _link_item(self) -> None:
        dlg = _LinkItemDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.item_id:
            ids = list(self._assessment.linked_item_ids or [])
            if dlg.item_id not in ids:
                ids.append(dlg.item_id)
                updated = self._service.assessments.update(
                    self._assessment.id, {"linked_item_ids": ids}
                )
                if updated:
                    self._assessment = updated
                    self._refresh_links_tab()
                    self.assessment_updated.emit(updated)

    def _unlink_item(self, item_id: str) -> None:
        ids = [i for i in (self._assessment.linked_item_ids or []) if i != item_id]
        updated = self._service.assessments.update(
            self._assessment.id, {"linked_item_ids": ids}
        )
        if updated:
            self._assessment = updated
            self._refresh_links_tab()
            self.assessment_updated.emit(updated)

    def _open_subject(self, subject) -> None:
        try:
            from modules.intel.windows.subject_detail_window import SubjectDetailWindow
            win = SubjectDetailWindow(subject, self._service, parent=self)
            win.show()
            win.raise_()
        except Exception:
            pass

    def _open_item(self, item) -> None:
        try:
            from modules.intel.windows.intel_item_detail_window import IntelItemDetailWindow
            win = IntelItemDetailWindow(item, self._service, parent=self)
            win.show()
            win.raise_()
        except Exception:
            pass

    def _refresh_after_update(self) -> None:
        self.setWindowTitle(
            f"Assessment {self._assessment.display_number}: {self._assessment.title}"
        )
        self.assessment_updated.emit(self._assessment)

        # Refresh action bar button states
        self._complete_btn.setEnabled(
            self._assessment.status not in (AssessmentStatus.COMPLETE, AssessmentStatus.ARCHIVED)
        )
        self._archive_btn.setEnabled(self._assessment.status != AssessmentStatus.ARCHIVED)

        # Rebuild overview and findings tabs
        self._tabs.removeTab(0)
        self._tabs.insertTab(0, self._build_overview_tab(), "Overview")
        self._tabs.removeTab(1)
        self._tabs.insertTab(1, self._build_findings_tab(), "Findings & Recommendations")
        self._tabs.setCurrentIndex(0)

        # Refresh history
        self._load_history()
