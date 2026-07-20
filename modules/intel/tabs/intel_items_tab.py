"""IntelItemsTab — table view for verified intel items."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QFrame, QComboBox, QTableWidget, QTableWidgetItem,
    QHeaderView, QAbstractItemView, QDialog, QFormLayout,
    QTextEdit, QDialogButtonBox, QCheckBox, QFileDialog,
)
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QBrush

from modules.intel.models.intel_items import (
    IntelItem, ITEM_TYPES, PRIORITY_VALUES, CONFIDENCE_VALUES, TREND_VALUES,
)
from modules.intel.models.leads import Lead
from modules.intel.services.intel_service import IntelService
from modules.intel.services.intel_attachments import add_attachment
from utils.table_view_styles import apply_statusboard_table_behavior
from utils.styles import intel_item_status_colors, get_palette, subscribe_theme


def _color_blob(hex_color: str, label: str) -> str:
    return (
        f'<span style="color: {hex_color}; font-size: 16px; vertical-align: middle;">&#9679;</span> '
        f'<span style="vertical-align: middle;">{label}</span>'
    )


def _source_label(item: IntelItem, leads_by_id: dict[str, Lead]) -> str:
    """Best available readable source string for the Source column."""
    if item.source_lead_id:
        lead = leads_by_id.get(item.source_lead_id)
        if lead:
            return f"{lead.display_number} — {lead.title}"
        return "Lead"
    if item.created_by:
        return item.created_by
    latest = item.latest_observation
    if latest and latest.source_team:
        return latest.source_team
    return "—"

def _row_color(item: IntelItem) -> QBrush | None:
    colors = intel_item_status_colors()
    if (item.confidence or "").lower() == "ruled out":
        return colors["ruled_out"]["bg"]
    if (item.priority or "").lower() == "critical":
        return colors["critical"]["bg"]
    if (item.trend or "").lower() == "worsening":
        return colors["worsening"]["bg"]
    if (item.priority or "").lower() == "high":
        return colors["high"]["bg"]
    if (item.trend or "").lower() == "improving":
        return colors["improving"]["bg"]
    return None


def _btn(label: str, callback, width: int = 52) -> QPushButton:
    b = QPushButton(label)
    b.setFixedHeight(22)
    b.setFixedWidth(width)
    b.clicked.connect(callback)
    return b


class _NewItemDialog(QDialog):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Intel Item")
        self.setMinimumWidth(480)
        self.item: IntelItem | None = None
        self.pending_attachments: list[str] = []

        layout = QVBoxLayout(self)
        form = QFormLayout()
        form.setSpacing(8)

        self._type = QComboBox()
        self._type.addItems(ITEM_TYPES)
        form.addRow("Type *", self._type)

        self._title = QLineEdit()
        self._title.setPlaceholderText("Description (required)")
        form.addRow("Description *", self._title)

        self._location = QLineEdit()
        form.addRow("Location", self._location)

        self._priority = QComboBox()
        self._priority.addItems(PRIORITY_VALUES)
        self._priority.setCurrentText("Medium")
        form.addRow("Priority", self._priority)

        self._confidence = QComboBox()
        self._confidence.addItems(CONFIDENCE_VALUES)
        self._confidence.setCurrentText("Unconfirmed")
        form.addRow("Confidence", self._confidence)

        self._urgent = QCheckBox("Urgent response needed (SAR 135)")
        form.addRow("", self._urgent)

        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Optional notes")
        self._notes.setMinimumHeight(60)
        form.addRow("Notes", self._notes)

        attach_row = QHBoxLayout()
        self._attach_btn = QPushButton("+ Add File(s)")
        self._attach_btn.clicked.connect(self._pick_attachments)
        self._attach_label = QLabel("No files attached")
        self._attach_label.setStyleSheet("color: palette(placeholderText);")
        attach_row.addWidget(self._attach_btn)
        attach_row.addWidget(self._attach_label)
        attach_row.addStretch()
        form.addRow("Attachments", attach_row)

        layout.addLayout(form)
        btns = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        btns.accepted.connect(self._on_save)
        btns.rejected.connect(self.reject)
        layout.addWidget(btns)

    def _pick_attachments(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(self, "Select Attachments")
        if not paths:
            return
        self.pending_attachments.extend(paths)
        names = ", ".join(Path(p).name for p in self.pending_attachments)
        self._attach_label.setText(names)

    def _on_save(self) -> None:
        title = self._title.text().strip()
        if not title:
            self._title.setStyleSheet(f"border: 1px solid {get_palette()['error'].name()};")
            return
        self.item = IntelItem(
            id="", incident_id="",
            item_type=self._type.currentText(),
            title=title,
            location_text=self._location.text().strip() or None,
            priority=self._priority.currentText(),
            confidence=self._confidence.currentText(),
            urgent_response_needed=self._urgent.isChecked(),
            notes=self._notes.toPlainText().strip() or None,
        )
        self.accept()


class IntelItemsTab(QWidget):
    open_item_detail = Signal(object)

    _COLS = ["Type", "Description", "Status", "Priority", "Confidence", "Trend", "Obs", "Source", "Location", "Updated", "Actions"]

    def __init__(self, service: IntelService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._service = service
        self._items: list[IntelItem] = []
        self._filtered: list[IntelItem] = []
        self._leads_by_id: dict[str, Lead] = {}

        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 12, 16, 12)
        layout.setSpacing(10)

        toolbar = QHBoxLayout()
        title = QLabel("Intel Items")
        title.setStyleSheet("font-size: 18px; font-weight: 700; color: palette(windowText);")

        self._search = QLineEdit()
        self._search.setPlaceholderText("Search…")
        self._search.setFixedWidth(200)
        self._search.textChanged.connect(self._apply_filter)

        self._type_filter = QComboBox()
        self._type_filter.addItem("All Types")
        self._type_filter.addItems(ITEM_TYPES)
        self._type_filter.currentTextChanged.connect(self._apply_filter)

        self._priority_filter = QComboBox()
        self._priority_filter.addItem("All Priorities")
        self._priority_filter.addItems(PRIORITY_VALUES)
        self._priority_filter.currentTextChanged.connect(self._apply_filter)

        self._trend_filter = QComboBox()
        self._trend_filter.addItem("All Trends")
        self._trend_filter.addItems(TREND_VALUES)
        self._trend_filter.currentTextChanged.connect(self._apply_filter)

        new_btn = QPushButton("+ New Intel Item")
        new_btn.clicked.connect(self._new_item)

        toolbar.addWidget(title)
        toolbar.addStretch()
        toolbar.addWidget(self._search)
        toolbar.addWidget(self._type_filter)
        toolbar.addWidget(self._priority_filter)
        toolbar.addWidget(self._trend_filter)
        toolbar.addWidget(new_btn)
        layout.addLayout(toolbar)

        sep = QFrame()
        sep.setFrameShape(QFrame.HLine)
        layout.addWidget(sep)

        self._table = QTableWidget()
        self._table.setColumnCount(len(self._COLS))
        self._table.setHorizontalHeaderLabels(self._COLS)
        apply_statusboard_table_behavior(self._table)
        self._table.horizontalHeader().setSectionResizeMode(1, QHeaderView.Stretch)
        self._table.horizontalHeader().setSectionResizeMode(8, QHeaderView.Stretch)
        self._table.verticalHeader().setVisible(False)
        self._table.setSortingEnabled(True)
        self._table.doubleClicked.connect(self._on_double_click)
        layout.addWidget(self._table)
        self._legend = QLabel()
        self._legend.setTextFormat(Qt.RichText)
        self._legend.setStyleSheet("font-size: 11px; color: palette(placeholderText);")
        layout.addWidget(self._legend)
        self._update_legend()

        subscribe_theme(self, self._on_theme_changed)
        self.refresh()

    def _update_legend(self) -> None:
        colors = intel_item_status_colors()
        self._legend.setText(
            "  ".join([
                _color_blob(colors["critical"]["fg"].color().name(), "Critical"),
                _color_blob(colors["high"]["fg"].color().name(), "High"),
                _color_blob(colors["worsening"]["fg"].color().name(), "Worsening"),
                _color_blob(colors["improving"]["fg"].color().name(), "Improving"),
                _color_blob(colors["ruled_out"]["fg"].color().name(), "Ruled Out"),
            ])
        )

    def _on_theme_changed(self, *_: object) -> None:
        self._update_legend()
        self._render()

    def refresh(self) -> None:
        if self._service is None:
            return
        self._items = self._service.items.list()
        leads = self._service.leads.list()
        self._leads_by_id = {lead.id: lead for lead in leads}
        self._apply_filter()

    def _apply_filter(self) -> None:
        q = self._search.text().lower()
        type_sel = self._type_filter.currentText()
        priority_sel = self._priority_filter.currentText()
        trend_sel = self._trend_filter.currentText()
        self._filtered = [
            i for i in self._items
            if (not q or q in i.title.lower() or q in (i.item_type or "").lower())
            and (type_sel == "All Types" or i.item_type == type_sel)
            and (priority_sel == "All Priorities" or i.priority == priority_sel)
            and (trend_sel == "All Trends" or i.trend == trend_sel)
        ]
        self._render()

    def _render(self) -> None:
        self._table.setSortingEnabled(False)
        self._table.setRowCount(len(self._filtered))
        for row, item in enumerate(self._filtered):
            cells = [
                item.item_type or "", item.title,
                item.status or "", item.priority or "", item.confidence or "", item.trend or "",
                str(item.observation_count), _source_label(item, self._leads_by_id),
                item.location_text or "",
                item.updated_at[:16].replace("T", " ") if item.updated_at else "",
            ]
            brush = _row_color(item)
            for col, val in enumerate(cells):
                ti = QTableWidgetItem(val)
                if brush:
                    ti.setBackground(brush)
                self._table.setItem(row, col, ti)

            actions = QWidget()
            al = QHBoxLayout(actions)
            al.setContentsMargins(4, 2, 4, 2)
            al.setSpacing(4)
            it = item
            al.addWidget(_btn("View", lambda _, x=it: self.open_item_detail.emit(x)))
            self._table.setCellWidget(row, len(self._COLS) - 1, actions)
            self._table.setRowHeight(row, 30)

        for col in (0, 2, 3, 4, 5, 6, 9):
            self._table.resizeColumnToContents(col)
        self._table.setColumnWidth(len(self._COLS) - 1, 70)
        self._table.setSortingEnabled(True)

    def _on_double_click(self, index) -> None:
        col, row = index.column(), index.row()
        if col < len(self._COLS) - 1 and 0 <= row < len(self._filtered):
            self.open_item_detail.emit(self._filtered[row])

    def _new_item(self) -> None:
        if self._service is None:
            return
        dlg = _NewItemDialog(self)
        if dlg.exec() == QDialog.Accepted and dlg.item:
            created = self._service.items.create(dlg.item)
            if created and dlg.pending_attachments:
                for path in dlg.pending_attachments:
                    add_attachment(
                        item_id=created.id,
                        source_path=path,
                        incident_id=self._service.incident_id,
                    )
            self.refresh()
