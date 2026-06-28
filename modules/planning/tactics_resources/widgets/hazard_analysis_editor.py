"""
HazardAnalysisEditor
====================
Tab widget for managing hazards on a Work Assignment (ICS 215A style).

Users can add library hazards (via HazardTypeSearchBox) or free-type new ones.
Applies default hazards from resource types using HazardPrefillService.
"""
from __future__ import annotations

from typing import Optional

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from modules.planning.tactics_resources.data.hazard_prefill_service import HazardPrefillService
from modules.planning.tactics_resources.data.work_assignment_repository import WorkAssignmentRepository
from modules.planning.tactics_resources.models.work_assignment_models import WorkAssignmentHazard
from utils.table_view_styles import apply_statusboard_table_behavior

# Try to import the HazardTypeSearchBox — degrade gracefully if unavailable
try:
    from modules.admin.hazard_types.widgets.hazard_type_search_box import HazardTypeSearchBox
    _HAS_HAZARD_SEARCH = True
except ImportError:
    _HAS_HAZARD_SEARCH = False

_RISK_VALUES = ["Unknown", "Low", "Medium", "High", "Extreme"]
_LIKELIHOOD_VALUES = ["Unknown", "Unlikely", "Possible", "Likely", "Almost Certain"]
_SEVERITY_VALUES = ["Unknown", "Negligible", "Marginal", "Critical", "Catastrophic"]


class HazardAnalysisEditor(QWidget):
    """
    Displays and edits the hazard analysis for one Work Assignment.

    Signals:
        changed() — emitted after any add/update/remove/resolve operation.
    """

    changed = Signal()

    def __init__(
        self,
        work_assignment_id: int,
        db_path: str | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._work_assignment_id = work_assignment_id
        self._db_path = db_path
        self._prefill_service = HazardPrefillService()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)

        # Toolbar
        btn_bar = QHBoxLayout()
        self._add_btn = QPushButton("Add Hazard")
        self._edit_btn = QPushButton("Edit")
        self._remove_btn = QPushButton("Remove")
        self._apply_btn = QPushButton("Apply Default Hazards")
        self._apply_btn.setToolTip("Adds default hazards from this assignment's resource types.")
        self._resolve_btn = QPushButton("Mark Resolved / Reopen")
        for btn in (self._add_btn, self._edit_btn, self._remove_btn,
                    self._apply_btn, self._resolve_btn):
            btn_bar.addWidget(btn)
        btn_bar.addStretch(1)
        layout.addLayout(btn_bar)

        # Hazard table
        columns = [
            "Hazard", "Category", "Risk", "Likelihood", "Severity",
            "Control Measure", "Mitigation", "PPE", "Resolved", "Source", "Notes",
        ]
        self._table = QTableWidget(0, len(columns))
        self._table.setHorizontalHeaderLabels(columns)
        apply_statusboard_table_behavior(self._table, stretch_last_section=True)
        self._table.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        layout.addWidget(self._table)

        self._add_btn.clicked.connect(self._add_hazard)
        self._edit_btn.clicked.connect(self._edit_hazard)
        self._remove_btn.clicked.connect(self._remove_hazard)
        self._apply_btn.clicked.connect(self._apply_default_hazards)
        self._resolve_btn.clicked.connect(self._toggle_resolved)

        self.reload()

    # ------------------------------------------------------------------
    def reload(self) -> None:
        try:
            repo = WorkAssignmentRepository(self._db_path)
            hazards = repo.list_hazards(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Hazards", f"Failed to load hazards:\n{exc}")
            return
        self._table.setRowCount(0)
        for h in hazards:
            self._populate_row(h)

    def _populate_row(self, h: WorkAssignmentHazard) -> None:
        row = self._table.rowCount()
        self._table.insertRow(row)
        self._table.setItem(row, 0, QTableWidgetItem(h.hazard_type_text))
        self._table.setItem(row, 1, QTableWidgetItem(h.category))
        self._table.setItem(row, 2, QTableWidgetItem(h.risk_level))
        self._table.setItem(row, 3, QTableWidgetItem(h.likelihood))
        self._table.setItem(row, 4, QTableWidgetItem(h.severity))
        self._table.setItem(row, 5, QTableWidgetItem(h.control_measure))
        self._table.setItem(row, 6, QTableWidgetItem(h.mitigation_text))
        self._table.setItem(row, 7, QTableWidgetItem(h.ppe_text))
        resolved_text = "Yes" if h.is_resolved else "No"
        resolved_item = QTableWidgetItem(resolved_text)
        if not h.is_resolved:
            resolved_item.setForeground(Qt.darkRed)
        self._table.setItem(row, 8, resolved_item)
        self._table.setItem(row, 9, QTableWidgetItem(h.source))
        self._table.setItem(row, 10, QTableWidgetItem(h.notes))
        self._table.item(row, 0).setData(Qt.UserRole, h.id)

    def _current_hazard_id(self) -> int | None:
        row = self._table.currentRow()
        if row < 0:
            return None
        item = self._table.item(row, 0)
        return item.data(Qt.UserRole) if item else None

    # ------------------------------------------------------------------

    def _add_hazard(self) -> None:
        dialog = _HazardDialog(prefill_service=self._prefill_service, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        if not data.get("hazard_type_text"):
            QMessageBox.warning(self, "Add Hazard", "Hazard text is required.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.add_hazard(self._work_assignment_id, data)
        except Exception as exc:
            QMessageBox.critical(self, "Add Hazard", f"Failed to add hazard:\n{exc}")
            return
        self.reload()
        self.changed.emit()

    def _edit_hazard(self) -> None:
        hazard_id = self._current_hazard_id()
        if hazard_id is None:
            QMessageBox.information(self, "Edit", "Select a hazard first.")
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            hazards = repo.list_hazards(self._work_assignment_id)
            hazard = next((h for h in hazards if h.id == hazard_id), None)
        except Exception:
            hazard = None
        if not hazard:
            return
        dialog = _HazardDialog(existing=hazard, prefill_service=self._prefill_service, parent=self)
        if dialog.exec() != QDialog.Accepted:
            return
        data = dialog.get_data()
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.update_hazard(hazard_id, data)
        except Exception as exc:
            QMessageBox.critical(self, "Edit Hazard", f"Failed to update:\n{exc}")
            return
        self.reload()
        self.changed.emit()

    def _remove_hazard(self) -> None:
        hazard_id = self._current_hazard_id()
        if hazard_id is None:
            QMessageBox.information(self, "Remove", "Select a hazard first.")
            return
        if QMessageBox.question(self, "Remove Hazard", "Remove this hazard?") != QMessageBox.Yes:
            return
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.remove_hazard(hazard_id)
        except Exception as exc:
            QMessageBox.critical(self, "Remove", f"Failed to remove:\n{exc}")
            return
        self.reload()
        self.changed.emit()

    def _apply_default_hazards(self) -> None:
        try:
            added, skipped = self._prefill_service.apply_default_hazards(self._work_assignment_id)
        except Exception as exc:
            QMessageBox.critical(self, "Apply Defaults", f"Failed to apply defaults:\n{exc}")
            return
        self.reload()
        self.changed.emit()
        QMessageBox.information(
            self,
            "Default Hazards",
            f"Added {added} hazard(s). Skipped {skipped} (already present or unavailable).",
        )

    def _toggle_resolved(self) -> None:
        hazard_id = self._current_hazard_id()
        if hazard_id is None:
            QMessageBox.information(self, "Resolve", "Select a hazard first.")
            return
        row = self._table.currentRow()
        currently_resolved = self._table.item(row, 8).text() == "Yes" if row >= 0 else False
        try:
            repo = WorkAssignmentRepository(self._db_path)
            repo.mark_hazard_resolved(hazard_id, not currently_resolved)
        except Exception as exc:
            QMessageBox.critical(self, "Resolve", f"Failed to update:\n{exc}")
            return
        self.reload()
        self.changed.emit()


# ---------------------------------------------------------------------------
# Add/Edit hazard dialog
# ---------------------------------------------------------------------------

class _HazardDialog(QDialog):
    """Dialog for adding or editing a single hazard entry."""

    def __init__(
        self,
        existing: WorkAssignmentHazard | None = None,
        prefill_service: HazardPrefillService | None = None,
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Hazard")
        self.setModal(True)
        self.setMinimumWidth(520)
        self._hazard_type_id: int | None = None
        self._prefill_service = prefill_service

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        # Hazard type — smart search or plain text
        if _HAS_HAZARD_SEARCH:
            self._hazard_search = HazardTypeSearchBox()
            self._hazard_search.hazardTypeSelected.connect(self._on_hazard_selected)
            form.addRow("Hazard *", self._hazard_search)
        else:
            self._hazard_search = None
            self._hazard_text = QLineEdit()
            self._hazard_text.setPlaceholderText("Hazard name (required)")
            form.addRow("Hazard *", self._hazard_text)

        self._category_edit = QLineEdit()
        form.addRow("Category", self._category_edit)

        self._risk_combo = QComboBox()
        self._risk_combo.addItems(_RISK_VALUES)
        form.addRow("Risk Level", self._risk_combo)

        self._likelihood_combo = QComboBox()
        self._likelihood_combo.addItems(_LIKELIHOOD_VALUES)
        form.addRow("Likelihood", self._likelihood_combo)

        self._severity_combo = QComboBox()
        self._severity_combo.addItems(_SEVERITY_VALUES)
        form.addRow("Severity", self._severity_combo)

        self._control_edit = QLineEdit()
        form.addRow("Control Measure", self._control_edit)

        self._mitigation_edit = QTextEdit()
        self._mitigation_edit.setFixedHeight(60)
        form.addRow("Mitigation", self._mitigation_edit)

        self._ppe_edit = QLineEdit()
        form.addRow("PPE Required", self._ppe_edit)

        self._safety_msg_edit = QLineEdit()
        form.addRow("Safety Message", self._safety_msg_edit)

        self._notes_edit = QLineEdit()
        form.addRow("Notes", self._notes_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if existing:
            self._populate(existing)

    def _on_hazard_selected(self, hazard_type_id, hazard_type_text: str) -> None:
        """Auto-fill fields from the library when a hazard type is selected."""
        self._hazard_type_id = hazard_type_id
        if hazard_type_id and self._prefill_service:
            data = self._prefill_service.build_hazard_from_hazard_type(int(hazard_type_id))
            if data:
                self._category_edit.setText(data.get("category", ""))
                self._risk_combo.setCurrentText(data.get("risk_level", "Unknown"))
                self._likelihood_combo.setCurrentText(data.get("likelihood", "Unknown"))
                self._severity_combo.setCurrentText(data.get("severity", "Unknown"))
                self._control_edit.setText(data.get("control_measure", ""))
                self._mitigation_edit.setPlainText(data.get("mitigation_text", ""))
                self._ppe_edit.setText(data.get("ppe_text", ""))
                self._safety_msg_edit.setText(data.get("safety_message", ""))

    def _populate(self, h: WorkAssignmentHazard) -> None:
        self._hazard_type_id = h.hazard_type_id
        if _HAS_HAZARD_SEARCH and self._hazard_search:
            self._hazard_search.set_value(h.hazard_type_id, h.hazard_type_text)
        elif hasattr(self, "_hazard_text"):
            self._hazard_text.setText(h.hazard_type_text)
        self._category_edit.setText(h.category)
        self._risk_combo.setCurrentText(h.risk_level)
        self._likelihood_combo.setCurrentText(h.likelihood)
        self._severity_combo.setCurrentText(h.severity)
        self._control_edit.setText(h.control_measure)
        self._mitigation_edit.setPlainText(h.mitigation_text)
        self._ppe_edit.setText(h.ppe_text)
        self._safety_msg_edit.setText(h.safety_message)
        self._notes_edit.setText(h.notes)

    def get_data(self) -> dict:
        if _HAS_HAZARD_SEARCH and self._hazard_search:
            text = self._hazard_search.hazard_type_text or ""
            htid = self._hazard_search.hazard_type_id
        else:
            text = self._hazard_text.text().strip() if hasattr(self, "_hazard_text") else ""
            htid = self._hazard_type_id
        return {
            "hazard_type_id": htid,
            "hazard_type_text": text,
            "category": self._category_edit.text().strip(),
            "risk_level": self._risk_combo.currentText(),
            "likelihood": self._likelihood_combo.currentText(),
            "severity": self._severity_combo.currentText(),
            "control_measure": self._control_edit.text().strip(),
            "mitigation_text": self._mitigation_edit.toPlainText().strip(),
            "ppe_text": self._ppe_edit.text().strip(),
            "safety_message": self._safety_msg_edit.text().strip(),
            "notes": self._notes_edit.text().strip(),
        }
