"""Dialog for importing an incident export package as a new incident."""
from __future__ import annotations

import json
import zipfile
from dataclasses import dataclass

from PySide6.QtCore import Signal
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from utils.styles import form_dialog_stylesheet, subscribe_theme


@dataclass(slots=True)
class ImportedIncident:
    """Result of a successful import: the new incident's registry fields."""

    incident_id: str
    number: str
    name: str


def _peek_source(file_path: str) -> dict:
    """Read manifest.json out of the package without uploading it, so the
    dialog can pre-fill number/name from the source incident."""
    with zipfile.ZipFile(file_path, "r") as archive:
        manifest = json.loads(archive.read("manifest.json").decode("utf-8"))
    return manifest.get("source", {})


class ImportIncidentDialog(QDialog):
    """Confirm (and optionally rename) a new incident before importing it."""

    imported = Signal(ImportedIncident)
    cancelled = Signal()

    def __init__(self, file_path: str, parent: None | QWidget = None) -> None:
        super().__init__(parent)
        self.setObjectName("ImportIncidentDialog")
        self.setWindowTitle("Import Incident")
        self.setModal(True)
        self.setMinimumWidth(420)
        self._file_path = file_path

        try:
            source = _peek_source(file_path)
        except Exception as exc:
            source = {}
            self._peek_error = str(exc)
        else:
            self._peek_error = None

        self._number = QLineEdit(str(source.get("number", "")))
        self._name = QLineEdit(str(source.get("name", "")))

        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.setObjectName("secondaryButton")
        self.btn_import = QPushButton("Import Incident")
        self.btn_import.setObjectName("primaryButton")
        self.btn_import.setDefault(True)

        title = QLabel("Import Incident")
        title.setObjectName("dialogTitle")
        subtitle = QLabel(
            "This creates a brand-new incident on this server from the selected file. "
            "Rename it below if the number would collide with an existing incident here."
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(28, 24, 28, 24)
        layout.setSpacing(14)
        layout.addWidget(title)
        layout.addWidget(subtitle)
        layout.addSpacing(6)
        layout.addWidget(self._labeled_field("Number", self._number))
        layout.addWidget(self._labeled_field("Name", self._name))

        layout.addSpacing(6)
        button_row = QHBoxLayout()
        button_row.addStretch(1)
        button_row.addWidget(self.btn_cancel)
        button_row.addWidget(self.btn_import)
        layout.addLayout(button_row)

        self.btn_import.clicked.connect(self._handle_accept)
        self.btn_cancel.clicked.connect(self._handle_reject)

        self._apply_styles()
        subscribe_theme(self, lambda *_: self._apply_styles())

        if self._peek_error:
            QMessageBox.warning(
                self,
                "Invalid File",
                f"Could not read this file as an incident export:\n{self._peek_error}",
            )

    def _labeled_field(self, label_text: str, field: QWidget) -> QWidget:
        wrap = QWidget()
        layout = QVBoxLayout(wrap)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)
        label = QLabel(label_text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        layout.addWidget(field)
        return wrap

    def _apply_styles(self) -> None:
        self.setStyleSheet(form_dialog_stylesheet("ImportIncidentDialog"))

    def _handle_accept(self) -> None:
        number = self._number.text().strip()
        name = self._name.text().strip()
        if not number or not name:
            QMessageBox.warning(self, "Missing Data", "Name and Number are required.")
            return

        try:
            from utils.api_client import api_client

            result = api_client.post_file(
                "/api/incidents/import",
                file_path=self._file_path,
                data={"number": number, "name": name},
            )
            if result is None:
                QMessageBox.critical(self, "Error", "Failed to import incident: no response from server.")
                return
            incident_id = result.get("incident_id") or result.get("id", "")
        except Exception as e:
            err = str(e)
            if "409" in err or "already exists" in err.lower():
                QMessageBox.warning(
                    self,
                    "Duplicate Incident",
                    f"An incident with number '{number}' already exists on this server. Choose a different number.",
                )
            else:
                QMessageBox.critical(self, "Incident Import Error", err)
            return

        self.imported.emit(ImportedIncident(incident_id=incident_id, number=number, name=name))
        self.accept()

    def _handle_reject(self) -> None:
        self.cancelled.emit()
        self.reject()


__all__ = ["ImportedIncident", "ImportIncidentDialog"]
