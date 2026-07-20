"""IntelItemDetailWindow — modeless window for a single Intel Item.

This is the most important detail window in the module.  It shows the full
item record and its chronological observation timeline.  Users can add new
observations directly from this window without returning to the items list.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QTabWidget, QDialog,
    QFormLayout, QTextEdit, QComboBox, QDialogButtonBox,
    QSizePolicy, QTableWidget, QTableWidgetItem, QHeaderView,
    QFileDialog, QMessageBox,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtCore import QUrl

from modules.intel.models.intel_items import (
    IntelItem, Observation,
    PRIORITY_VALUES, CONFIDENCE_VALUES, TREND_VALUES,
)
from modules.intel.widgets.card_widget import CardWidget
from modules.intel.widgets.status_chip import StatusChip
from modules.intel.widgets.trend_indicator import TrendIndicator
from modules.intel.widgets.observation_entry_dialog import ObservationEntryDialog
from modules.intel.services.intel_service import IntelService

_log = logging.getLogger(__name__)


class _ObservationRow(CardWidget):
    """A single observation entry in the timeline."""

    def __init__(self, obs: Observation, parent=None) -> None:
        super().__init__(parent, padding=12)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)

        # Time + observer row
        meta_row = QHBoxLayout()
        time_str = obs.observed_at[11:16] if len(obs.observed_at) >= 16 else obs.observed_at
        date_str = obs.observed_at[:10] if obs.observed_at else ""
        time_lbl = QLabel(f"{date_str}  {time_str}")
        time_lbl.setStyleSheet("font-size: 12px; font-weight: 700;")
        observer_lbl = QLabel(f"— {obs.observer}")
        observer_lbl.setStyleSheet("font-size: 12px; color: palette(placeholderText);")
        severity_chip = StatusChip(obs.severity)
        confidence_chip = StatusChip(obs.confidence)
        meta_row.addWidget(time_lbl)
        meta_row.addWidget(observer_lbl)
        meta_row.addStretch()
        meta_row.addWidget(severity_chip)
        meta_row.addWidget(confidence_chip)

        # Summary
        summary_lbl = QLabel(obs.summary)
        summary_lbl.setStyleSheet("font-size: 13px;")
        summary_lbl.setWordWrap(True)

        # Location
        if obs.location_text:
            loc_lbl = QLabel(f"📍 {obs.location_text}")
            loc_lbl.setStyleSheet("font-size: 11px; color: palette(placeholderText);")

        # Detailed notes
        if obs.detailed_notes:
            notes_lbl = QLabel(obs.detailed_notes)
            notes_lbl.setWordWrap(True)
            notes_lbl.setStyleSheet(
                "font-size: 12px; color: palette(windowText); margin-top: 4px;"
            )

        # Source team
        if obs.source_team:
            team_lbl = QLabel(f"Team: {obs.source_team}")
            team_lbl.setStyleSheet("font-size: 11px; color: palette(placeholderText);")

        self.layout().addLayout(meta_row)
        self.layout().addWidget(summary_lbl)
        if obs.location_text:
            self.layout().addWidget(loc_lbl)
        if obs.detailed_notes:
            self.layout().addWidget(notes_lbl)
        if obs.source_team:
            self.layout().addWidget(team_lbl)


class _EditItemDialog(QDialog):
    """Dialog for editing the Intel Item's metadata (not observations)."""

    def __init__(self, item: IntelItem, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Intel Item")
        self.setMinimumWidth(460)
        self.updates: dict | None = None

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self._priority = QComboBox()
        self._priority.addItems(PRIORITY_VALUES)
        self._priority.setCurrentText(item.priority)
        form.addRow("Priority", self._priority)

        self._confidence = QComboBox()
        self._confidence.addItems(CONFIDENCE_VALUES)
        self._confidence.setCurrentText(item.confidence)
        form.addRow("Confidence", self._confidence)

        self._trend = QComboBox()
        self._trend.addItems(TREND_VALUES)
        self._trend.setCurrentText(item.trend)
        form.addRow("Trend", self._trend)

        self._status = QComboBox()
        from modules.intel.models.intel_items import STATUS_VALUES
        self._status.addItems(STATUS_VALUES)
        self._status.setCurrentText(item.status)
        form.addRow("Status", self._status)

        self._notes = QTextEdit()
        self._notes.setPlainText(item.notes or "")
        self._notes.setFixedHeight(80)
        form.addRow("Notes", self._notes)

        layout.addLayout(form)

        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _on_save(self) -> None:
        self.updates = {
            "priority": self._priority.currentText(),
            "confidence": self._confidence.currentText(),
            "trend": self._trend.currentText(),
            "status": self._status.currentText(),
            "notes": self._notes.toPlainText().strip() or None,
        }
        self.accept()


def _link_button(label: str, callback) -> QPushButton:
    """Return a QPushButton styled as a hyperlink."""
    btn = QPushButton(label)
    btn.setFlat(True)
    btn.setCursor(Qt.PointingHandCursor)
    btn.setStyleSheet(
        "QPushButton { color: palette(link); text-align: left; padding: 2px 0; "
        "border: none; font-size: 13px; }"
        "QPushButton:hover { text-decoration: underline; }"
    )
    btn.clicked.connect(callback)
    return btn


class IntelItemDetailWindow(QMainWindow):
    """Modeless window showing full detail for a single Intel Item.

    The Observations tab is the primary workspace — it shows the chronological
    history and provides a quick-add button for new observations.
    """

    item_updated = Signal(object)   # emits updated IntelItem

    def __init__(
        self,
        item: IntelItem,
        service: IntelService,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._item = item
        self._service = service

        self.setWindowTitle(f"Intel Item: {item.title}")
        self.resize(760, 620)
        self.setAttribute(Qt.WA_DeleteOnClose)

        central = QWidget()
        self.setCentralWidget(central)
        root = QVBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)

        root.addWidget(self._build_header())

        self._tabs = QTabWidget()
        self._tabs.addTab(self._build_overview_tab(), "Overview")
        self._observations_tab = self._build_observations_tab()
        self._tabs.addTab(self._observations_tab, f"Observations ({item.observation_count})")
        self._tabs.addTab(self._build_links_tab(), "Links")
        self._attachments_widget = self._build_attachments_tab()
        self._tabs.addTab(self._attachments_widget, "Attachments")
        self._tabs.addTab(self._build_history_tab(), "History")
        root.addWidget(self._tabs)

    def _build_header(self) -> QWidget:
        w = QWidget()
        w.setStyleSheet("background: palette(dark); padding: 12px;")
        layout = QHBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)

        self._header_type_lbl = QLabel(self._item.item_type)
        self._header_type_lbl.setStyleSheet("font-size: 12px; color: palette(placeholderText);")

        self._header_title_lbl = QLabel(self._item.title)
        self._header_title_lbl.setStyleSheet(
            "font-size: 18px; font-weight: 700; color: palette(bright-text);"
        )

        self._header_priority_chip = StatusChip(self._item.priority)
        self._header_confidence_chip = StatusChip(self._item.confidence)
        self._header_trend = TrendIndicator(self._item.trend)

        edit_btn = QPushButton("Edit")
        edit_btn.clicked.connect(self._edit_item)

        add_obs_btn = QPushButton("+ Observation")
        add_obs_btn.clicked.connect(self._add_observation)

        layout.addWidget(self._header_type_lbl)
        layout.addWidget(self._header_title_lbl)
        layout.addStretch()
        layout.addWidget(self._header_priority_chip)
        layout.addWidget(self._header_confidence_chip)
        layout.addWidget(self._header_trend)
        layout.addWidget(edit_btn)
        layout.addWidget(add_obs_btn)
        return w

    def _build_overview_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(6)

        item = self._item

        def row(label: str, value: str | None) -> QWidget:
            r = QWidget()
            h = QHBoxLayout(r)
            h.setContentsMargins(0, 2, 0, 2)
            lbl = QLabel(label + ":")
            lbl.setStyleSheet("font-weight: 600; min-width: 130px;")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
            val = QLabel(value or "—")
            val.setWordWrap(True)
            h.addWidget(lbl)
            h.addWidget(val, 1)
            return r

        layout.addWidget(row("Type", item.item_type))
        layout.addWidget(row("Status", item.status))
        layout.addWidget(row("Priority", item.priority))
        layout.addWidget(row("Confidence", item.confidence))
        layout.addWidget(row("Trend", item.trend))
        layout.addWidget(row("Location", item.location_text))
        layout.addWidget(row("Created By", item.created_by))
        layout.addWidget(row("Created", item.created_at[:16].replace("T", "  ")))
        layout.addWidget(row("Updated", item.updated_at[:16].replace("T", "  ")))

        if item.source_lead_id:
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            layout.addWidget(sep)

            lead_label = "Source Lead"
            lead_display = item.source_lead_id
            lead_obj = None
            try:
                lead_obj = self._service.leads.get(item.source_lead_id)
            except Exception:
                pass
            if lead_obj:
                lead_display = f"{lead_obj.display_number} — {lead_obj.title}"

            r = QWidget()
            h = QHBoxLayout(r)
            h.setContentsMargins(0, 2, 0, 2)
            lbl = QLabel(lead_label + ":")
            lbl.setStyleSheet("font-weight: 600; min-width: 130px;")
            lbl.setAlignment(Qt.AlignRight | Qt.AlignTop)
            if lead_obj:
                lo = lead_obj
                btn = _link_button(lead_display, lambda _, l=lo: self._open_lead(l))
                h.addWidget(lbl)
                h.addWidget(btn, 1)
            else:
                val = QLabel(lead_display)
                h.addWidget(lbl)
                h.addWidget(val, 1)
            layout.addWidget(r)

        if item.notes:
            sep2 = QFrame()
            sep2.setFrameShape(QFrame.HLine)
            layout.addWidget(sep2)
            notes_lbl = QLabel("Notes")
            notes_lbl.setStyleSheet("font-weight: 700;")
            layout.addWidget(notes_lbl)
            body = QLabel(item.notes)
            body.setWordWrap(True)
            layout.addWidget(body)

        layout.addStretch()
        return w

    def _build_observations_tab(self) -> QWidget:
        """Chronological observation timeline."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        obs_toolbar = QHBoxLayout()
        count_lbl = QLabel(
            f"{self._item.observation_count} observation"
            f"{'s' if self._item.observation_count != 1 else ''}"
        )
        count_lbl.setStyleSheet("font-size: 13px; font-weight: 600;")
        add_btn = QPushButton("+ Add Observation")
        add_btn.clicked.connect(self._add_observation)
        obs_toolbar.addWidget(count_lbl)
        obs_toolbar.addStretch()
        obs_toolbar.addWidget(add_btn)
        layout.addLayout(obs_toolbar)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.NoFrame)

        self._obs_container = QWidget()
        self._obs_layout = QVBoxLayout(self._obs_container)
        self._obs_layout.setContentsMargins(0, 0, 0, 0)
        self._obs_layout.setSpacing(8)
        self._obs_layout.setAlignment(Qt.AlignTop)

        self._refresh_observations()
        scroll.setWidget(self._obs_container)
        layout.addWidget(scroll)
        return w

    def _refresh_observations(self) -> None:
        while self._obs_layout.count():
            item = self._obs_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()

        obs_sorted = sorted(self._item.observations, key=lambda o: o.observed_at)
        if not obs_sorted:
            no_obs = QLabel("No observations yet. Add the first observation.")
            no_obs.setStyleSheet("color: palette(placeholderText); font-size: 13px;")
            no_obs.setAlignment(Qt.AlignCenter)
            self._obs_layout.addWidget(no_obs)
            return

        for obs in obs_sorted:
            self._obs_layout.addWidget(_ObservationRow(obs))

    def _build_links_tab(self) -> QWidget:
        """Links tab with human-readable subject/task/lead display and navigation."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)
        layout.setAlignment(Qt.AlignTop)

        item = self._item
        has_any = False

        # Linked subjects
        if item.linked_subject_ids:
            has_any = True
            subj_lbl = QLabel(f"Linked Subjects ({len(item.linked_subject_ids)})")
            subj_lbl.setStyleSheet("font-weight: 700; font-size: 13px;")
            layout.addWidget(subj_lbl)
            for sid in item.linked_subject_ids:
                subject = None
                try:
                    subject = self._service.subjects.get(sid)
                except Exception:
                    pass
                if subject:
                    display = f"{subject.name} — {subject.subject_type}"
                    btn = _link_button(f"  • {display}", lambda _, s=subject: self._open_subject(s))
                    layout.addWidget(btn)
                else:
                    layout.addWidget(QLabel(f"  • Unknown subject — {sid}"))

        # Linked tasks
        if item.linked_task_ids:
            has_any = True
            sep = QFrame()
            sep.setFrameShape(QFrame.HLine)
            layout.addWidget(sep)
            task_lbl = QLabel(f"Linked Tasks ({len(item.linked_task_ids)})")
            task_lbl.setStyleSheet("font-weight: 700; font-size: 13px;")
            layout.addWidget(task_lbl)
            for tid in item.linked_task_ids:
                task_display = None
                task_int_id = None
                try:
                    task_int_id = int(tid)
                    from modules.operations.taskings.repository import get_task
                    task = get_task(task_int_id)
                    task_display = f"{task.task_id} — {task.title}"
                except Exception:
                    pass
                if task_display and task_int_id is not None:
                    _tid = task_int_id
                    btn = _link_button(
                        f"  • {task_display}",
                        lambda _, t=_tid: self._open_task(t),
                    )
                    layout.addWidget(btn)
                else:
                    layout.addWidget(QLabel(f"  • Task — {tid}"))

        if not has_any:
            layout.addWidget(QLabel("No linked records."))

        layout.addStretch()
        return w

    def _build_attachments_tab(self) -> QWidget:
        """Attachments tab — real file attachment management for Intel Items."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        toolbar = QHBoxLayout()
        add_btn = QPushButton("+ Add Attachment")
        add_btn.clicked.connect(self._add_attachment)
        toolbar.addStretch()
        toolbar.addWidget(add_btn)
        layout.addLayout(toolbar)

        att_cols = ["Name", "Type", "Size", "Uploaded", "By", "Notes", ""]
        self._att_table = QTableWidget()
        self._att_table.setColumnCount(len(att_cols))
        self._att_table.setHorizontalHeaderLabels(att_cols)
        self._att_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._att_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._att_table.verticalHeader().setVisible(False)
        self._att_table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self._att_table.horizontalHeader().setSectionResizeMode(5, QHeaderView.Stretch)
        layout.addWidget(self._att_table)
        legend = QLabel("Legend: row colors reflect attachment type/status context.")
        legend.setStyleSheet("color: palette(placeholderText); font-size: 11px;")
        layout.addWidget(legend)

        self._refresh_attachments()
        return w

    def _refresh_attachments(self) -> None:
        from modules.intel.services.intel_attachments import list_attachments
        try:
            atts = list_attachments(self._item.id, self._service.incident_id)
        except Exception as exc:
            _log.warning("Could not load attachments: %s", exc)
            atts = []

        self._att_table.setRowCount(len(atts))
        for row, att in enumerate(atts):
            size_kb = att.get("size", 0) // 1024
            size_str = f"{size_kb} KB" if size_kb > 0 else "< 1 KB"
            uploaded_at = att.get("uploaded_at", "")[:16].replace("T", " ")
            self._att_table.setItem(row, 0, QTableWidgetItem(att.get("filename", "")))
            self._att_table.setItem(row, 1, QTableWidgetItem(att.get("mime_type", "")))
            self._att_table.setItem(row, 2, QTableWidgetItem(size_str))
            self._att_table.setItem(row, 3, QTableWidgetItem(uploaded_at))
            self._att_table.setItem(row, 4, QTableWidgetItem(att.get("uploaded_by", "")))
            self._att_table.setItem(row, 5, QTableWidgetItem(att.get("notes", "")))

            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(2, 1, 2, 1)
            al.setSpacing(4)
            att_id = att.get("id")
            open_btn = QPushButton("Open")
            open_btn.setFixedHeight(22)
            open_btn.clicked.connect(lambda _, aid=att_id: self._open_attachment(aid))
            remove_btn = QPushButton("Remove")
            remove_btn.setFixedHeight(22)
            remove_btn.clicked.connect(lambda _, aid=att_id: self._remove_attachment(aid))
            al.addWidget(open_btn)
            al.addWidget(remove_btn)
            self._att_table.setCellWidget(row, 6, actions)
            self._att_table.setRowHeight(row, 28)

        self._att_table.setColumnWidth(6, 120)

        if not atts:
            self._att_table.setRowCount(1)
            placeholder = QTableWidgetItem("No attachments yet.")
            placeholder.setForeground(self._att_table.palette().placeholderText())
            self._att_table.setItem(0, 0, placeholder)

    def _add_attachment(self) -> None:
        from modules.intel.services.intel_attachments import add_attachment
        path, _ = QFileDialog.getOpenFileName(self, "Select Attachment")
        if not path:
            return
        result = add_attachment(
            item_id=self._item.id,
            source_path=path,
            uploaded_by="",
            incident_id=self._service.incident_id,
        )
        if result.get("added"):
            if result.get("warning"):
                QMessageBox.information(self, "Large File", result["warning"])
            self._write_log("attachment_added", f"Attachment added: {Path(path).name}")
            self._refresh_attachments()
        else:
            QMessageBox.warning(self, "Attachment Error", result.get("error", "Could not add attachment."))

    def _open_attachment(self, attachment_id: int) -> None:
        from modules.intel.services.intel_attachments import get_attachment_path
        p = get_attachment_path(self._item.id, attachment_id, self._service.incident_id)
        if p:
            QDesktopServices.openUrl(QUrl.fromLocalFile(p))
        else:
            QMessageBox.warning(self, "Not Found", "Attachment file could not be located.")

    def _remove_attachment(self, attachment_id: int) -> None:
        from modules.intel.services.intel_attachments import remove_attachment, list_attachments
        atts = list_attachments(self._item.id, self._service.incident_id)
        att = next((a for a in atts if a.get("id") == attachment_id), None)
        name = att.get("filename", "") if att else ""
        reply = QMessageBox.question(
            self, "Remove Attachment",
            f"Remove '{name}'? The file will be deleted.",
            QMessageBox.Yes | QMessageBox.Cancel,
        )
        if reply != QMessageBox.Yes:
            return
        if remove_attachment(self._item.id, attachment_id, self._service.incident_id):
            self._write_log("attachment_removed", f"Attachment removed: {name}")
            self._refresh_attachments()

    def _build_history_tab(self) -> QWidget:
        """History tab — Intel Log entries for this Intel Item."""
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(8)

        hist_cols = ["Time", "Event", "Actor", "Summary"]
        self._hist_table = QTableWidget()
        self._hist_table.setColumnCount(len(hist_cols))
        self._hist_table.setHorizontalHeaderLabels(hist_cols)
        self._hist_table.setSelectionBehavior(QTableWidget.SelectRows)
        self._hist_table.setEditTriggers(QTableWidget.NoEditTriggers)
        self._hist_table.verticalHeader().setVisible(False)
        self._hist_table.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        layout.addWidget(self._hist_table)

        refresh_btn = QPushButton("Refresh")
        refresh_btn.clicked.connect(self._refresh_history)
        layout.addWidget(refresh_btn, alignment=Qt.AlignRight)

        self._refresh_history()
        return w

    def _refresh_history(self) -> None:
        try:
            entries = self._service.log.list(
                entity_type="item",
                entity_id=self._item.id,
                limit=200,
            )
        except Exception as exc:
            _log.warning("Could not load history: %s", exc)
            entries = []

        self._hist_table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            ts = entry.timestamp[:16].replace("T", " ") if entry.timestamp else ""
            self._hist_table.setItem(row, 0, QTableWidgetItem(ts))
            self._hist_table.setItem(row, 1, QTableWidgetItem(entry.event_label))
            self._hist_table.setItem(row, 2, QTableWidgetItem(entry.actor or "system"))
            self._hist_table.setItem(row, 3, QTableWidgetItem(entry.summary))
            self._hist_table.setRowHeight(row, 26)

        for col in (0, 1, 2):
            self._hist_table.resizeColumnToContents(col)

        if not entries:
            self._hist_table.setRowCount(1)
            placeholder = QTableWidgetItem("No history entries found.")
            placeholder.setForeground(self._hist_table.palette().placeholderText())
            self._hist_table.setItem(0, 0, placeholder)

    def _write_log(self, event_type: str, summary: str) -> None:
        """Write an Intel Log entry for an action taken on this item."""
        try:
            from utils.api_client import api_client
            api_client.post(
                f"/api/incidents/{self._service.incident_id}/intel/log",
                json={
                    "entity_type": "item",
                    "entity_id": self._item.id,
                    "event_type": event_type,
                    "summary": summary,
                    "actor": "user",
                },
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Navigation helpers

    def _open_subject(self, subject) -> None:
        try:
            from modules.intel.windows.subject_detail_window import SubjectDetailWindow
            win = SubjectDetailWindow(subject, self._service, parent=self)
            win.show()
            win.raise_()
        except Exception as exc:
            _log.warning("Could not open subject detail: %s", exc)

    def _open_lead(self, lead) -> None:
        try:
            from modules.intel.windows.lead_detail_window import LeadDetailWindow
            win = LeadDetailWindow(lead, self._service, parent=self)
            win.show()
            win.raise_()
        except Exception as exc:
            _log.warning("Could not open lead detail: %s", exc)

    def _open_task(self, task_id: int) -> None:
        try:
            from modules.operations.taskings.windows import open_task_detail_window
            open_task_detail_window(task_id)
        except Exception as exc:
            _log.warning("Could not open task detail: %s", exc)

    # ------------------------------------------------------------------
    # Actions

    def _add_observation(self) -> None:
        dlg = ObservationEntryDialog(self._item.title, self)
        if dlg.exec() == QDialog.Accepted and dlg.observation:
            updated = self._service.items.add_observation(self._item.id, dlg.observation)
            if updated:
                self._item = updated
                self._refresh_observations()
                self._tabs.setTabText(
                    1,
                    f"Observations ({updated.observation_count})"
                )
                self.item_updated.emit(updated)

    def _edit_item(self) -> None:
        dlg = _EditItemDialog(self._item, self)
        if dlg.exec() == QDialog.Accepted and dlg.updates:
            updated = self._service.items.update(self._item.id, dlg.updates)
            if updated:
                self._item = updated
                self.item_updated.emit(updated)
                self._header_title_lbl.setText(updated.title)
                self._header_priority_chip.set_value(updated.priority)
                self._header_confidence_chip.set_value(updated.confidence)
                self._header_trend.set_trend(updated.trend)
                self.setWindowTitle(f"Intel Item: {updated.title}")
                # Rebuild overview tab
                self._tabs.removeTab(0)
                self._tabs.insertTab(0, self._build_overview_tab(), "Overview")
                self._tabs.setCurrentIndex(0)
