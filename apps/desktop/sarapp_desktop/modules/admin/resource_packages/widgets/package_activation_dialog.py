"""Package activation confirmation dialog (Stage 4).

Shown after a person/vehicle/other resource checks in and is found to
belong to one or more standing Resource Packages. Lets the operator see
which other expected package members have/haven't checked in, and confirm
which actually arrived -- with substitution or omission -- before anything
is checked in. Nothing here ever auto-checks-in an absent member.
"""
from __future__ import annotations

from typing import Any, Optional

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from modules.admin.resource_associations.widgets.resource_picker_dialog import ResourcePickerDialog

_ACTIONS = ("Pending (decide later)", "Confirm Arrived", "Substitute…", "Omit (not coming)")


class PackageActivationDialog(QDialog):
    """One package's activation confirmation. ``package`` is the
    package-suggestions/status payload from checkin.py (package_id,
    package_name, members: [{resource_type, resource_id, label, membership,
    role, checked_in}, ...])."""

    def __init__(self, package: dict[str, Any], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self._package = package
        self._substitutes: dict[int, dict[str, Any]] = {}
        self.setWindowTitle(f"Package Activation — {package.get('package_name', '')}")
        self.resize(720, 420)

        layout = QVBoxLayout(self)
        layout.addWidget(
            QLabel(
                f"{package.get('checked_in_count', 0)} of {package.get('total_count', 0)} members "
                "already checked in. Confirm which of the remaining members actually arrived."
            )
        )

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(["Resource", "Role", "Status", "Action"])
        self.table.setEditTriggers(QTableWidget.NoEditTriggers)
        layout.addWidget(self.table, 1)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._combos: dict[int, QComboBox] = {}
        self._populate()

    def _populate(self) -> None:
        members = self._package.get("members") or []
        self.table.setRowCount(len(members))
        for row, member in enumerate(members):
            label_item = QTableWidgetItem(f"{member.get('label', '')} ({member.get('resource_type', '')})")
            label_item.setData(Qt.UserRole, row)
            self.table.setItem(row, 0, label_item)
            self.table.setItem(row, 1, QTableWidgetItem(member.get("role", "")))

            already = bool(member.get("checked_in"))
            self.table.setItem(row, 2, QTableWidgetItem("Already checked in" if already else "Not checked in"))

            if already:
                self.table.setCellWidget(row, 3, QLabel("—"))
                continue

            combo = QComboBox()
            combo.addItems(_ACTIONS)
            combo.currentIndexChanged.connect(lambda idx, r=row: self._on_action_changed(r, idx))
            self._combos[row] = combo
            self.table.setCellWidget(row, 3, combo)

    def _on_action_changed(self, row: int, index: int) -> None:
        if _ACTIONS[index] != "Substitute…":
            self._substitutes.pop(row, None)
            return
        dialog = ResourcePickerDialog(self)
        if dialog.exec() != QDialog.Accepted:
            self._combos[row].setCurrentIndex(0)
            return
        self._substitutes[row] = {
            "resource_type": dialog.selected_resource_type,
            "resource_id": dialog.selected_resource_id,
        }

    def _accept(self) -> None:
        for row, combo in self._combos.items():
            if _ACTIONS[combo.currentIndex()] == "Substitute…" and row not in self._substitutes:
                QMessageBox.warning(self, "Package Activation", "Select a substitute resource, or choose a different action.")
                return
        self.accept()

    def result_payload(self) -> dict[str, list[dict[str, Any]]]:
        """Return {confirmed, substitutions, omitted} ready for
        checkin.activate_package()."""
        members = self._package.get("members") or []
        confirmed: list[dict[str, Any]] = []
        substitutions: list[dict[str, Any]] = []
        omitted: list[dict[str, Any]] = []
        for row, member in enumerate(members):
            combo = self._combos.get(row)
            if combo is None:
                continue  # already checked in before the dialog opened
            action = _ACTIONS[combo.currentIndex()]
            ref = {"resource_type": member["resource_type"], "resource_id": member["resource_id"]}
            if action == "Confirm Arrived":
                confirmed.append(ref)
            elif action == "Substitute…":
                substitutions.append({"original": ref, "substitute": self._substitutes[row]})
            elif action == "Omit (not coming)":
                omitted.append(ref)
            # "Pending" rows are left out entirely -- never auto-checked-in.
        return {"confirmed": confirmed, "substitutions": substitutions, "omitted": omitted}


def offer_package_activation(
    resource_type: str, resource_id: int, parent: Optional[QWidget] = None, *, activated_by: str = ""
) -> None:
    """Call right after a resource checks in. Looks up standing packages
    involving it and, for any with un-checked-in members, offers the
    operator a chance to confirm/substitute/omit before checking anyone
    else in. No-op (returns immediately) if the resource is in no package
    or every package member is already checked in."""
    from modules.logistics.checkin import repository as checkin_repo

    suggestions = checkin_repo.fetch_package_suggestions(resource_type, resource_id)
    for package in suggestions:
        if package.get("checked_in_count") == package.get("total_count"):
            continue  # everyone is already here -- nothing to confirm
        dialog = PackageActivationDialog(package, parent)
        if dialog.exec() != QDialog.Accepted:
            continue
        payload = dialog.result_payload()
        if not (payload["confirmed"] or payload["substitutions"] or payload["omitted"]):
            continue
        checkin_repo.activate_package(
            package["package_id"],
            confirmed=payload["confirmed"],
            substitutions=payload["substitutions"],
            omitted=payload["omitted"],
            activated_by=activated_by,
        )
