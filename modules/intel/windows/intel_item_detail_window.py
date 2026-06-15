"""IntelItemDetailWindow — modeless window for a single Intel Item.

This is the most important detail window in the module.  It shows the full
item record and its chronological observation timeline.  Users can add new
observations directly from this window without returning to the items list.
"""

from __future__ import annotations

from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QPushButton, QScrollArea, QFrame, QTabWidget, QDialog,
    QFormLayout, QTextEdit, QComboBox, QDialogButtonBox,
    QSizePolicy,
)
from PySide6.QtCore import Qt, Signal

from modules.intel.models.intel_items import (
    IntelItem, Observation,
    PRIORITY_VALUES, CONFIDENCE_VALUES, TREND_VALUES,
)
from modules.intel.widgets.card_widget import CardWidget
from modules.intel.widgets.status_chip import StatusChip
from modules.intel.widgets.trend_indicator import TrendIndicator
from modules.intel.widgets.observation_entry_dialog import ObservationEntryDialog
from modules.intel.services.intel_service import IntelService


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
        self.resize(760, 580)
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
        self._tabs.addTab(QWidget(), "Attachments")
        self._tabs.addTab(QWidget(), "History")
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
            layout.addWidget(row("Source Lead", item.source_lead_id))

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

        # Add observation toolbar
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

        # Timeline
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

        # Sort chronologically (oldest first for a timeline)
        obs_sorted = sorted(
            self._item.observations,
            key=lambda o: o.observed_at,
        )
        if not obs_sorted:
            no_obs = QLabel("No observations yet. Add the first observation.")
            no_obs.setStyleSheet("color: palette(placeholderText); font-size: 13px;")
            no_obs.setAlignment(Qt.AlignCenter)
            self._obs_layout.addWidget(no_obs)
            return

        for obs in obs_sorted:
            row = _ObservationRow(obs)
            self._obs_layout.addWidget(row)

    def _build_links_tab(self) -> QWidget:
        w = QWidget()
        layout = QVBoxLayout(w)
        layout.setContentsMargins(20, 16, 20, 16)
        item = self._item
        if item.linked_subject_ids:
            layout.addWidget(QLabel(f"Linked Subjects ({len(item.linked_subject_ids)})"))
            for sid in item.linked_subject_ids:
                layout.addWidget(QLabel(f"  • {sid}"))
        if item.linked_task_ids:
            layout.addWidget(QLabel(f"Linked Tasks ({len(item.linked_task_ids)})"))
            for tid in item.linked_task_ids:
                layout.addWidget(QLabel(f"  • {tid}"))
        if not item.linked_subject_ids and not item.linked_task_ids:
            layout.addWidget(QLabel("No linked records."))
        layout.addStretch()
        return w

    def _add_observation(self) -> None:
        dlg = ObservationEntryDialog(self._item.title, self)
        if dlg.exec() == QDialog.Accepted and dlg.observation:
            updated = self._service.items.add_observation(self._item.id, dlg.observation)
            if updated:
                self._item = updated
                self._refresh_observations()
                # Update the observations tab label
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
                # Refresh header in-place
                self._header_title_lbl.setText(updated.title)
                self._header_priority_chip.set_value(updated.priority)
                self._header_confidence_chip.set_value(updated.confidence)
                self._header_trend.set_trend(updated.trend)
                self.setWindowTitle(f"Intel Item: {updated.title}")
                # Rebuild overview tab
                self._tabs.removeTab(0)
                self._tabs.insertTab(0, self._build_overview_tab(), "Overview")
                self._tabs.setCurrentIndex(0)
