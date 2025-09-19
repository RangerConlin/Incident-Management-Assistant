"""Dialogs used by the resource request detail panel."""

from __future__ import annotations

from PySide6 import QtCore, QtWidgets


class NoteDialog(QtWidgets.QDialog):
    """Collects a textual note from the operator."""

    def __init__(self, title: str, label: str, require_note: bool = False, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle(title)
        self._require_note = require_note
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel(label))
        self.note_edit = QtWidgets.QPlainTextEdit(self)
        layout.addWidget(self.note_edit)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def accept(self) -> None:  # pragma: no cover - exercised via UI tests
        if self._require_note and not self.note_edit.toPlainText().strip():
            QtWidgets.QMessageBox.warning(self, "Validation", "A note is required for this action.")
            return
        super().accept()

    @property
    def note(self) -> str:
        return self.note_edit.toPlainText().strip()


class AssignDialog(QtWidgets.QDialog):
    """Dialog allowing the user to assign fulfillment resources."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Assign Resources")
        layout = QtWidgets.QFormLayout(self)
        self.supplier_edit = QtWidgets.QLineEdit(self)
        self.team_edit = QtWidgets.QLineEdit(self)
        self.vehicle_edit = QtWidgets.QLineEdit(self)
        self.eta_edit = QtWidgets.QDateTimeEdit(self)
        self.eta_edit.setCalendarPopup(True)
        self.note_edit = QtWidgets.QPlainTextEdit(self)

        layout.addRow("Supplier ID", self.supplier_edit)
        layout.addRow("Team ID", self.team_edit)
        layout.addRow("Vehicle ID", self.vehicle_edit)
        layout.addRow("ETA", self.eta_edit)
        layout.addRow("Note", self.note_edit)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addRow(button_box)

    def values(self) -> dict[str, object]:
        return {
            "supplier_id": self.supplier_edit.text().strip() or None,
            "team_id": self.team_edit.text().strip() or None,
            "vehicle_id": self.vehicle_edit.text().strip() or None,
            "eta_utc": self.eta_edit.dateTime().toString(QtCore.Qt.ISODate) if self.eta_edit.dateTime().isValid() else None,
            "note": self.note_edit.toPlainText().strip() or None,
        }


class EtaDialog(QtWidgets.QDialog):
    """Dialog for updating the estimated arrival time."""

    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Set ETA")
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel("Set a revised ETA:"))
        self.eta_edit = QtWidgets.QDateTimeEdit(self)
        self.eta_edit.setCalendarPopup(True)
        layout.addWidget(self.eta_edit)
        self.note_edit = QtWidgets.QPlainTextEdit(self)
        self.note_edit.setPlaceholderText("Optional note")
        layout.addWidget(self.note_edit)

        button_box = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal,
            self,
        )
        button_box.accepted.connect(self.accept)
        button_box.rejected.connect(self.reject)
        layout.addWidget(button_box)

    def values(self) -> dict[str, object]:
        return {
            "eta_utc": self.eta_edit.dateTime().toString(QtCore.Qt.ISODate) if self.eta_edit.dateTime().isValid() else None,
            "note": self.note_edit.toPlainText().strip() or None,
        }
