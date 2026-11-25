from __future__ import annotations

from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QFormLayout,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.finance import services
from modules.finance.models.schemas import RateTableEntryCreate, RateTableEntryUpdate
from styles.styles import finance_estimate_status_colors, subscribe_theme
from utils.table_view_styles import apply_statusboard_table_behavior

RATE_CATEGORIES = [
    "personnel", "aircraft", "vehicle", "equipment", "fuel",
    "lodging", "meals", "rentals", "contracted_services", "other",
]
COLUMNS = ["ID", "Name", "Category", "Amount", "Unit", "Rate Kind", "Effective Start", "Effective End", "Active", "Notes"]


class RateTablesPanel(QWidget):
    """Finance/Admin > Rate Tables — manages reusable/standard and
    incident-specific rate entries for every rate category (personnel,
    aircraft, vehicle, equipment, fuel, lodging, meals/per diem, rentals/
    contracted services, other)."""

    def __init__(self, incident_id: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.incident_id = incident_id
        self._build_ui()
        subscribe_theme(self, lambda *_: self._repaint_rows())
        self.refresh()

    def _build_ui(self) -> None:
        layout = QVBoxLayout(self)
        layout.setContentsMargins(16, 16, 16, 16)
        layout.setSpacing(12)

        title = QLabel("Rate Tables")
        title.setObjectName("SectionTitle")
        layout.addWidget(title)

        filter_row = QHBoxLayout()
        self.category_filter = QComboBox()
        self.category_filter.addItem("All categories", None)
        for category in RATE_CATEGORIES:
            self.category_filter.addItem(category.replace("_", " ").title(), category)
        self.category_filter.currentIndexChanged.connect(self.refresh)
        self.active_only = QCheckBox("Active only")
        self.active_only.stateChanged.connect(self.refresh)
        filter_row.addWidget(QLabel("Category"))
        filter_row.addWidget(self.category_filter)
        filter_row.addWidget(self.active_only)
        filter_row.addStretch(1)
        layout.addLayout(filter_row)

        self.table = QTableWidget(0, len(COLUMNS))
        self.table.setHorizontalHeaderLabels(COLUMNS)
        apply_statusboard_table_behavior(self.table, stretch_last_section=True)
        self.table.itemSelectionChanged.connect(self._load_selected_into_form)
        layout.addWidget(self.table, 1)

        form_frame = QFrame()
        form_frame.setObjectName("SectionFrame")
        form_layout = QFormLayout(form_frame)
        self.name_edit = QLineEdit()
        self.category_edit = QComboBox()
        self.category_edit.addItems(RATE_CATEGORIES)
        self.amount_edit = QLineEdit()
        self.unit_edit = QLineEdit()
        self.rate_kind_edit = QComboBox()
        self.rate_kind_edit.addItems(["", "regular", "overtime"])
        self.effective_start_edit = QLineEdit()
        self.effective_start_edit.setPlaceholderText("YYYY-MM-DD")
        self.effective_end_edit = QLineEdit()
        self.effective_end_edit.setPlaceholderText("YYYY-MM-DD (optional)")
        self.applies_to_type_edit = QLineEdit()
        self.applies_to_type_edit.setPlaceholderText("person | resource | resource_type | organization | global")
        self.applies_to_id_edit = QLineEdit()
        self.is_active_edit = QCheckBox("Active")
        self.is_active_edit.setChecked(True)
        self.notes_edit = QLineEdit()
        form_layout.addRow("Name", self.name_edit)
        form_layout.addRow("Category", self.category_edit)
        form_layout.addRow("Amount", self.amount_edit)
        form_layout.addRow("Unit", self.unit_edit)
        form_layout.addRow("Rate Kind", self.rate_kind_edit)
        form_layout.addRow("Applies To Type", self.applies_to_type_edit)
        form_layout.addRow("Applies To ID", self.applies_to_id_edit)
        form_layout.addRow("Effective Start", self.effective_start_edit)
        form_layout.addRow("Effective End", self.effective_end_edit)
        form_layout.addRow("", self.is_active_edit)
        form_layout.addRow("Notes", self.notes_edit)
        layout.addWidget(form_frame)

        buttons = QHBoxLayout()
        new_button = QPushButton("New Entry")
        new_button.clicked.connect(self._clear_form)
        save_button = QPushButton("Save")
        save_button.setProperty("variant", "success")
        save_button.clicked.connect(self._save_entry)
        buttons.addWidget(new_button)
        buttons.addStretch(1)
        buttons.addWidget(save_button)
        layout.addLayout(buttons)

        self._selected_id: int | None = None

    def refresh(self) -> None:
        category = self.category_filter.currentData()
        entries = services.list_rate_tables(self.incident_id, category=category, active_only=self.active_only.isChecked())
        self._entries = entries
        self.table.setRowCount(len(entries))
        for row, entry in enumerate(entries):
            values = [
                entry.id, entry.name, entry.category, f"{entry.amount:,.2f}", entry.unit,
                entry.rate_kind or "-", entry.effective_start or "-", entry.effective_end or "-",
                "Yes" if entry.is_active else "No", entry.notes or "",
            ]
            for col, value in enumerate(values):
                item = QTableWidgetItem(str(value))
                self.table.setItem(row, col, item)
        self._repaint_rows()

    def _repaint_rows(self) -> None:
        colors = finance_estimate_status_colors()
        for row in range(self.table.rowCount()):
            entry = self._entries[row]
            tint = colors.get("active" if entry.is_active else "inactive")
            if not tint:
                continue
            for col in range(self.table.columnCount()):
                item = self.table.item(row, col)
                if item is not None:
                    item.setBackground(tint["bg"])
                    item.setForeground(tint["fg"])

    def _load_selected_into_form(self) -> None:
        row = self.table.currentRow()
        if row < 0 or row >= len(self._entries):
            return
        entry = self._entries[row]
        self._selected_id = entry.id
        self.name_edit.setText(entry.name)
        self.category_edit.setCurrentText(entry.category)
        self.amount_edit.setText(str(entry.amount))
        self.unit_edit.setText(entry.unit)
        self.rate_kind_edit.setCurrentText(entry.rate_kind or "")
        self.applies_to_type_edit.setText(entry.applies_to_type or "")
        self.applies_to_id_edit.setText(entry.applies_to_id or "")
        self.effective_start_edit.setText(entry.effective_start or "")
        self.effective_end_edit.setText(entry.effective_end or "")
        self.is_active_edit.setChecked(entry.is_active)
        self.notes_edit.setText(entry.notes or "")

    def _clear_form(self) -> None:
        self._selected_id = None
        self.name_edit.clear()
        self.amount_edit.clear()
        self.unit_edit.clear()
        self.rate_kind_edit.setCurrentIndex(0)
        self.applies_to_type_edit.clear()
        self.applies_to_id_edit.clear()
        self.effective_start_edit.clear()
        self.effective_end_edit.clear()
        self.is_active_edit.setChecked(True)
        self.notes_edit.clear()

    def _save_entry(self) -> None:
        try:
            if not self.name_edit.text().strip():
                raise ValueError("Name is required.")
            amount = float(self.amount_edit.text() or "0")
            if self._selected_id is None:
                services.create_rate_table_entry(
                    self.incident_id,
                    RateTableEntryCreate(
                        name=self.name_edit.text(),
                        category=self.category_edit.currentText(),
                        applies_to_type=self.applies_to_type_edit.text() or None,
                        applies_to_id=self.applies_to_id_edit.text() or None,
                        amount=amount,
                        unit=self.unit_edit.text() or "unit",
                        rate_kind=self.rate_kind_edit.currentText() or None,
                        effective_start=self.effective_start_edit.text() or None,
                        effective_end=self.effective_end_edit.text() or None,
                        is_active=self.is_active_edit.isChecked(),
                        notes=self.notes_edit.text() or None,
                    ),
                )
            else:
                services.update_rate_table_entry(
                    self.incident_id, self._selected_id,
                    RateTableEntryUpdate(
                        name=self.name_edit.text(),
                        applies_to_type=self.applies_to_type_edit.text() or None,
                        applies_to_id=self.applies_to_id_edit.text() or None,
                        amount=amount,
                        unit=self.unit_edit.text() or "unit",
                        rate_kind=self.rate_kind_edit.currentText() or None,
                        effective_start=self.effective_start_edit.text() or None,
                        effective_end=self.effective_end_edit.text() or None,
                        is_active=self.is_active_edit.isChecked(),
                        notes=self.notes_edit.text() or None,
                        changed_by="Finance/Admin",
                    ),
                )
            self._clear_form()
            self.refresh()
        except Exception as exc:
            QMessageBox.warning(self, "Rate Table Entry", str(exc))
