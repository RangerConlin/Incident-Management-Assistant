from __future__ import annotations

"""Dialogs used by the ICS-203 command panel."""

from typing import Dict, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from ..models import ICS203Repository, MasterPersonnelRepository

_UNIT_TYPES = ["Command", "Section", "Branch", "Division", "Group"]


class AddUnitDialog(QDialog):
    """Collect information required to create an organizational unit."""

    def __init__(
        self,
        repo: ICS203Repository,
        incident_id: str,
        parent: QWidget | None = None,
        preset_parent: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Unit")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.cmb_type = QComboBox(self)
        self.cmb_type.addItems(_UNIT_TYPES)
        form.addRow("Type", self.cmb_type)

        self.txt_name = QLineEdit(self)
        form.addRow("Name", self.txt_name)

        self.cmb_parent = QComboBox(self)
        self.cmb_parent.addItem("<none>", None)
        for unit in repo.list_units():
            label = f"{unit.unit_type}: {unit.name}"
            self.cmb_parent.addItem(label, unit.id)
        form.addRow("Parent", self.cmb_parent)

        self.spn_sort = QSpinBox(self)
        self.spn_sort.setRange(-9999, 9999)
        form.addRow("Sort", self.spn_sort)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if preset_parent is not None:
            index = self.cmb_parent.findData(preset_parent)
            if index >= 0:
                self.cmb_parent.setCurrentIndex(index)

    # ------------------------------------------------------------------
    def _handle_accept(self) -> None:
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Missing name", "Please provide a name for the unit.")
            return
        self.accept()

    def values(self) -> Dict[str, object]:
        return {
            "unit_type": self.cmb_type.currentText(),
            "name": self.txt_name.text().strip(),
            "parent_unit_id": self.cmb_parent.currentData(),
            "sort_order": int(self.spn_sort.value()),
        }


class AddPositionDialog(QDialog):
    """Collect information required to add a position to the org chart."""

    def __init__(
        self,
        repo: ICS203Repository,
        incident_id: str,
        parent: QWidget | None = None,
        preset_unit: int | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add Position")

        layout = QVBoxLayout(self)
        form = QFormLayout()

        self.txt_title = QLineEdit(self)
        form.addRow("Title", self.txt_title)

        self.cmb_unit = QComboBox(self)
        self.cmb_unit.addItem("<none>", None)
        for unit in repo.list_units():
            label = f"{unit.unit_type}: {unit.name}"
            self.cmb_unit.addItem(label, unit.id)
        form.addRow("Unit", self.cmb_unit)

        self.spn_sort = QSpinBox(self)
        self.spn_sort.setRange(-9999, 9999)
        form.addRow("Sort", self.spn_sort)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if preset_unit is not None:
            index = self.cmb_unit.findData(preset_unit)
            if index >= 0:
                self.cmb_unit.setCurrentIndex(index)

    def _handle_accept(self) -> None:
        if not self.txt_title.text().strip():
            QMessageBox.warning(self, "Missing title", "Please provide a title for the position.")
            return
        self.accept()

    def values(self) -> Dict[str, object]:
        return {
            "title": self.txt_title.text().strip(),
            "unit_id": self.cmb_unit.currentData(),
            "sort_order": int(self.spn_sort.value()),
        }


class AssignPersonDialog(QDialog):
    """Dialog allowing operators to assign personnel to a position."""

    def __init__(
        self,
        master_repo: MasterPersonnelRepository | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign Person")
        self._master_repo = master_repo or MasterPersonnelRepository()
        self._selected_person: Optional[dict[str, object]] = None

        layout = QVBoxLayout(self)

        search_layout = QFormLayout()
        self.txt_search = QLineEdit(self)
        self.txt_search.setPlaceholderText("Search master roster…")
        self.txt_search.textChanged.connect(self._perform_search)
        search_layout.addRow("Search", self.txt_search)
        layout.addLayout(search_layout)

        self.list_results = QListWidget(self)
        self.list_results.itemClicked.connect(self._apply_result)
        self.list_results.itemActivated.connect(self._apply_result)
        layout.addWidget(self.list_results, stretch=1)

        form = QFormLayout()
        self.txt_name = QLineEdit(self)
        self.txt_name.textEdited.connect(self._clear_selected_person)
        form.addRow("Name", self.txt_name)

        self.txt_callsign = QLineEdit(self)
        form.addRow("Callsign", self.txt_callsign)

        self.txt_phone = QLineEdit(self)
        form.addRow("Phone", self.txt_phone)

        self.txt_agency = QLineEdit(self)
        form.addRow("Agency", self.txt_agency)

        layout.addLayout(form)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, parent=self)
        buttons.accepted.connect(self._handle_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    def _perform_search(self, text: str) -> None:
        term = text.strip()
        self.list_results.clear()
        if len(term) < 2:
            return
        results = self._master_repo.search_people(term)
        for person in results:
            name = person.get("name") or "Unknown"
            callsign = person.get("callsign") or ""
            agency = person.get("agency") or ""
            subtitle = " "
            if callsign:
                subtitle = f"[{callsign}]"
            display = f"{name} {subtitle} {agency}".strip()
            item = QListWidgetItem(display)
            item.setData(Qt.UserRole, person)
            self.list_results.addItem(item)

    def _apply_result(self, item: QListWidgetItem) -> None:
        data = item.data(Qt.UserRole)
        if not isinstance(data, dict):
            return
        self._selected_person = data
        self.txt_name.setText(str(data.get("name", "")))
        self.txt_callsign.setText(str(data.get("callsign", "")))
        self.txt_phone.setText(str(data.get("phone", "")))
        self.txt_agency.setText(str(data.get("agency", "")))

    def _clear_selected_person(self, _text: str) -> None:
        self._selected_person = None

    def _handle_accept(self) -> None:
        if not self.txt_name.text().strip():
            QMessageBox.warning(self, "Missing name", "Please choose or enter a name.")
            return
        self.accept()

    def values(self) -> Dict[str, object | None]:
        person_id = None
        if self._selected_person:
            person_id = self._selected_person.get("id")
        return {
            "person_id": person_id,
            "display_name": self.txt_name.text().strip(),
            "callsign": self.txt_callsign.text().strip() or None,
            "phone": self.txt_phone.text().strip() or None,
            "agency": self.txt_agency.text().strip() or None,
        }
