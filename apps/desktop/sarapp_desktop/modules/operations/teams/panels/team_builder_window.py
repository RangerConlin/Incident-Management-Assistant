"""Team Builder (Stage 5).

A minimal, new window for assembling an incident team from one or more
standing Resource Packages, individual resources, and substitutions --
reusing `team_detail_window.py`'s composition primitives (its Add*Dialog
pickers and `team_repo`) rather than duplicating them, and activating the
assembled set through the same `operations.py` team-creation path every
other team already goes through (so numbering/team_type behavior is
unchanged). "Save as Package" is a distinct, explicit action on an already
assembled/activated team -- ordinary team edits never silently write back
to a standing package.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTabWidget,
    QVBoxLayout,
    QWidget,
)

from modules.admin.resource_associations.widgets.resource_picker_dialog import ResourcePickerDialog
from modules.admin.resource_packages.data.repository import ApiResourcePackageRepository
from modules.operations.teams.data.team import Team
from modules.operations.teams.data import repository as team_repo
from modules.operations.teams.panels.team_detail_window import (
    AddEquipmentDialog,
    AddTeamMemberDialog,
    AddVehicleDialog,
)
from utils.constants import TEAM_TYPE_DETAILS

_RESOURCE_KIND_LABELS = {"personnel": "Personnel", "vehicle": "Vehicles", "aircraft": "Aircraft", "equipment": "Equipment"}


class _PackageBrowserDialog(QDialog):
    """Browse standing packages and see which members are checked in at
    the active incident. Returns the ids of checked-in members the
    operator chose to pull in."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Add From Package")
        self.resize(760, 520)
        self._packages_repo = ApiResourcePackageRepository()
        self._status_payload: Optional[dict[str, Any]] = None
        self.selected_refs: list[dict[str, Any]] = []

        layout = QVBoxLayout(self)
        top = QHBoxLayout()
        top.addWidget(QLabel("Package:"))
        self.package_combo = QComboBox()
        top.addWidget(self.package_combo, 1)
        layout.addLayout(top)

        self.summary_label = QLabel("")
        layout.addWidget(self.summary_label)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Include", "Resource", "Role", "Status"])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.package_combo.currentIndexChanged.connect(self._load_status)
        self._load_packages()

    def _load_packages(self) -> None:
        try:
            packages = self._packages_repo.list_packages(active_filter="Active")
        except Exception:
            packages = []
        self.package_combo.clear()
        for pkg in packages:
            self.package_combo.addItem(pkg.name, pkg.id)
        if packages:
            self._load_status()

    def _load_status(self) -> None:
        package_id = self.package_combo.currentData()
        self.table.setRowCount(0)
        self._status_payload = None
        if not package_id:
            self.summary_label.setText("")
            return
        from modules.logistics.checkin import repository as checkin_repo

        self._status_payload = checkin_repo.fetch_package_status(package_id)
        if not self._status_payload:
            self.summary_label.setText("Unable to load this package's check-in status.")
            return
        members = self._status_payload.get("members") or []
        self.summary_label.setText(
            f"{self._status_payload.get('checked_in_count', 0)} of "
            f"{self._status_payload.get('total_count', 0)} members currently checked in at this incident."
        )
        self.table.setRowCount(len(members))
        for row, member in enumerate(members):
            checked_in = bool(member.get("checked_in"))
            checkbox = QCheckBox()
            checkbox.setChecked(checked_in)
            checkbox.setEnabled(checked_in)  # only checked-in resources can be pulled into the team
            self.table.setCellWidget(row, 0, checkbox)
            self.table.setItem(row, 1, QTableWidgetItem(f"{member.get('label', '')} ({member.get('resource_type', '')})"))
            self.table.setItem(row, 2, QTableWidgetItem(member.get("role", "")))
            self.table.setItem(row, 3, QTableWidgetItem("Checked In" if checked_in else "Not checked in"))

    def _accept(self) -> None:
        if not self._status_payload:
            self.reject()
            return
        members = self._status_payload.get("members") or []
        self.selected_refs = []
        for row, member in enumerate(members):
            checkbox = self.table.cellWidget(row, 0)
            if isinstance(checkbox, QCheckBox) and checkbox.isChecked() and checkbox.isEnabled():
                self.selected_refs.append(
                    {"resource_type": member["resource_type"], "resource_id": member["resource_id"]}
                )
        if not self.selected_refs:
            QMessageBox.information(self, "Add From Package", "No checked-in members were selected.")
            return
        self.accept()


class TeamBuilderWindow(QDialog):
    """Assemble resources from multiple packages/individuals into one
    incident team."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Team Builder")
        self.resize(820, 640)
        self._members: list[int] = []
        self._vehicles: list[int] = []
        self._equipment: list[int] = []
        self._aircraft: list[int] = []
        self._source_package_ids: set[str] = set()
        self._activated_team_id: Optional[int] = None

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        header.addWidget(QLabel("Team Name:"))
        self.name_edit = QLineEdit()
        header.addWidget(self.name_edit, 1)
        header.addWidget(QLabel("Team Type:"))
        self.type_combo = QComboBox()
        for code, info in TEAM_TYPE_DETAILS.items():
            if not info.get("planned_only"):
                self.type_combo.addItem(info["label"], code)
        header.addWidget(self.type_combo)
        layout.addLayout(header)

        actions = QHBoxLayout()
        self.add_package_button = QPushButton("Add From Package…")
        self.add_person_button = QPushButton("Add Individual Personnel…")
        self.add_vehicle_button = QPushButton("Add Individual Vehicle…")
        self.add_aircraft_button = QPushButton("Add Individual Aircraft…")
        self.add_equipment_button = QPushButton("Add Individual Equipment…")
        for btn in (
            self.add_package_button,
            self.add_person_button,
            self.add_vehicle_button,
            self.add_aircraft_button,
            self.add_equipment_button,
        ):
            actions.addWidget(btn)
        layout.addLayout(actions)

        self.tabs = QTabWidget()
        self._lists: dict[str, QListWidget] = {}
        for kind in ("personnel", "vehicle", "aircraft", "equipment"):
            lst = QListWidget()
            self._lists[kind] = lst
            tab = QWidget()
            tab_layout = QVBoxLayout(tab)
            tab_layout.addWidget(lst)
            remove_btn = QPushButton("Remove Selected")
            remove_btn.clicked.connect(lambda _=None, k=kind: self._remove_selected(k))
            tab_layout.addWidget(remove_btn)
            self.tabs.addTab(tab, _RESOURCE_KIND_LABELS[kind])
        layout.addWidget(self.tabs, 1)

        layout.addWidget(QLabel("Outstanding requirements from contributing packages:"))
        self.requirements_list = QListWidget()
        self.requirements_list.setMaximumHeight(120)
        layout.addWidget(self.requirements_list)

        footer = QHBoxLayout()
        self.activate_button = QPushButton("Activate as Incident Team")
        self.save_as_package_button = QPushButton("Save as Package…")
        self.save_as_package_button.setEnabled(False)
        self.close_button = QPushButton("Close")
        footer.addWidget(self.activate_button)
        footer.addWidget(self.save_as_package_button)
        footer.addStretch()
        footer.addWidget(self.close_button)
        layout.addLayout(footer)

        self.add_package_button.clicked.connect(self._add_from_package)
        self.add_person_button.clicked.connect(self._add_individual_person)
        self.add_vehicle_button.clicked.connect(self._add_individual_vehicle)
        self.add_aircraft_button.clicked.connect(self._add_individual_aircraft)
        self.add_equipment_button.clicked.connect(self._add_individual_equipment)
        self.activate_button.clicked.connect(self._activate_team)
        self.save_as_package_button.clicked.connect(self._save_as_package)
        self.close_button.clicked.connect(self.accept)

    # ------------------------------------------------------------------
    # Assembly
    # ------------------------------------------------------------------
    def _kind_list(self, resource_type: str) -> list[int]:
        return {
            "personnel": self._members,
            "vehicle": self._vehicles,
            "aircraft": self._aircraft,
            "equipment": self._equipment,
        }[resource_type]

    def _append_resource(self, resource_type: str, resource_id: int, label: str = "") -> None:
        ids = self._kind_list(resource_type)
        if resource_id in ids:
            return  # combining packages/individuals never adds the same resource twice
        ids.append(resource_id)
        item = QListWidgetItem(label or str(resource_id))
        item.setData(Qt.UserRole, resource_id)
        self._lists[resource_type].addItem(item)

    def _remove_selected(self, resource_type: str) -> None:
        lst = self._lists[resource_type]
        row = lst.currentRow()
        if row < 0:
            return
        item = lst.takeItem(row)
        resource_id = item.data(Qt.UserRole)
        ids = self._kind_list(resource_type)
        if resource_id in ids:
            ids.remove(resource_id)

    def _add_from_package(self) -> None:
        dialog = _PackageBrowserDialog(self)
        if dialog.exec() != QDialog.Accepted:
            return
        package_id = dialog.package_combo.currentData()
        if package_id:
            self._source_package_ids.add(package_id)
        for ref in dialog.selected_refs:
            self._append_resource(ref["resource_type"], int(ref["resource_id"]))
        self._refresh_requirements()
        self.save_as_package_button.setEnabled(bool(self._members or self._vehicles or self._equipment or self._aircraft))

    def _add_individual_person(self) -> None:
        dialog = AddTeamMemberDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_person_id:
            self._append_resource("personnel", int(dialog.selected_person_id))

    def _add_individual_vehicle(self) -> None:
        dialog = AddVehicleDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_id:
            self._append_resource("vehicle", int(dialog.selected_id))

    def _add_individual_equipment(self) -> None:
        dialog = AddEquipmentDialog(self)
        if dialog.exec() == QDialog.Accepted and dialog.selected_id:
            self._append_resource("equipment", int(dialog.selected_id))

    def _add_individual_aircraft(self) -> None:
        dialog = ResourcePickerDialog(self, allowed_kinds=("aircraft",))
        if dialog.exec() == QDialog.Accepted and dialog.selected_resource_id is not None:
            self._append_resource("aircraft", int(dialog.selected_resource_id), dialog.selected_label)

    def substitute_resource(self, resource_type: str, old_resource_id: int) -> None:
        """Replace one assembled vehicle/equipment resource with another."""
        dialog = ResourcePickerDialog(self, allowed_kinds=(resource_type,))
        if dialog.exec() != QDialog.Accepted or dialog.selected_resource_id is None:
            return
        ids = self._kind_list(resource_type)
        if old_resource_id in ids:
            ids.remove(old_resource_id)
        lst = self._lists[resource_type]
        for row in range(lst.count()):
            if lst.item(row).data(Qt.UserRole) == old_resource_id:
                lst.takeItem(row)
                break
        self._append_resource(resource_type, int(dialog.selected_resource_id), dialog.selected_label)

    # ------------------------------------------------------------------
    # Requirements review (lightweight here; Stage 6 adds the authoritative
    # Ready/Not Ready evaluation against the Resource Type Library on top
    # of this same assembled set)
    # ------------------------------------------------------------------
    def _refresh_requirements(self) -> None:
        self.requirements_list.clear()
        packages_repo = ApiResourcePackageRepository()
        for package_id in self._source_package_ids:
            package = packages_repo.get_package(package_id)
            if package is None:
                continue
            for position in package.required_positions:
                self.requirements_list.addItem(
                    f"[{package.name}] Requires {position.quantity}x {position.role}"
                    + (f" ({position.qualification})" if position.qualification else "")
                )
            for minimum in package.minimum_quantities:
                have = len(self._kind_list(minimum.resource_kind)) if minimum.resource_kind in ("personnel", "vehicle", "aircraft", "equipment") else None
                status = "" if have is None else f" -- have {have}"
                self.requirements_list.addItem(f"[{package.name}] {minimum.description} (min {minimum.minimum_count}){status}")
        if self.requirements_list.count() == 0:
            self.requirements_list.addItem("No outstanding requirements from contributing packages.")

    # ------------------------------------------------------------------
    # Activation
    # ------------------------------------------------------------------
    def _activate_team(self) -> None:
        name = self.name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Team Builder", "Enter a team name first.")
            return
        if not (self._members or self._vehicles or self._equipment or self._aircraft):
            QMessageBox.warning(self, "Team Builder", "Add at least one resource before activating.")
            return
        team = Team(
            name=name,
            team_type=self.type_combo.currentData() or "GT",
            members=list(self._members),
            vehicles=[str(v) for v in self._vehicles],
            equipment=[str(e) for e in self._equipment],
            aircraft=[str(a) for a in self._aircraft],
        )
        try:
            saved = team_repo.save_team(team)
        except Exception as exc:
            QMessageBox.critical(self, "Team Builder", f"Failed to activate team: {exc}")
            return
        self._activated_team_id = saved.team_id
        self.save_as_package_button.setEnabled(True)
        QMessageBox.information(self, "Team Builder", f"Team '{name}' activated (ID {saved.team_id}).")

    def _save_as_package(self) -> None:
        """Explicit, separate action -- never triggered by ordinary team
        edits or by activation itself."""
        from modules.admin.resource_packages.models import PackageResourceRef, ResourcePackage
        from modules.admin.resource_packages.windows.resource_package_editor_window import (
            ResourcePackageEditorWindow,
        )

        resources = (
            [PackageResourceRef(resource_type="personnel", resource_id=pid, membership="fixed") for pid in self._members]
            + [PackageResourceRef(resource_type="vehicle", resource_id=vid, membership="fixed") for vid in self._vehicles]
            + [PackageResourceRef(resource_type="aircraft", resource_id=aid, membership="fixed") for aid in self._aircraft]
            + [PackageResourceRef(resource_type="equipment", resource_id=eid, membership="fixed") for eid in self._equipment]
        )
        draft = ResourcePackage(
            name=self.name_edit.text().strip() or "New Package",
            default_team_designation=self.name_edit.text().strip(),
            resources=resources,
        )
        # `draft.id` is always None here, so the editor and the save call
        # below both take the create path -- this can never silently
        # overwrite one of the source packages this team was built from.
        packages_repo = ApiResourcePackageRepository()
        dialog = ResourcePackageEditorWindow(packages_repo, draft, self)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            packages_repo.save_package(dialog.to_model())
        except Exception as exc:
            QMessageBox.critical(self, "Save as Package", f"Failed to save package: {exc}")
            return
        QMessageBox.information(self, "Save as Package", "Saved as a new Resource Package.")


_open_windows: list[TeamBuilderWindow] = []


def open_team_builder(parent: Optional[QWidget] = None) -> TeamBuilderWindow:
    window = TeamBuilderWindow(parent=parent)
    window.show()
    _open_windows.append(window)

    def _cleanup() -> None:
        try:
            _open_windows.remove(window)
        except ValueError:
            pass

    window.destroyed.connect(lambda *_: _cleanup())
    return window
