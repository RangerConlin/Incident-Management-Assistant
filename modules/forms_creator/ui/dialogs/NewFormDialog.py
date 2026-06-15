"""Dialog for adding or editing a form definition in catalog.json."""

from __future__ import annotations

import re

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)


def _to_form_id(number: str) -> str:
    """Convert a form number like 'ICS 204' → 'ics_204'."""
    s = number.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


class NewFormDialog(QDialog):
    """Collect metadata for a new or edited form definition."""

    KNOWN_CATEGORIES = [
        "Incident Command",
        "Planning",
        "Operations",
        "Logistics",
        "Communications",
        "Medical",
        "Finance/Admin",
        "Documentation",
        "Safety",
        "CAP",
        "SAR",
        "Other",
    ]

    def __init__(
        self,
        existing_ids: set[str],
        existing_categories: list[str],
        existing: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._edit_mode = existing is not None
        self.setWindowTitle("Edit Form Definition" if self._edit_mode else "New Form Definition")
        self.setMinimumWidth(380)
        # When editing, exclude the current form's own ID from duplicate check
        self._existing_ids = existing_ids - ({existing["id"]} if existing else set())

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.number_edit = QLineEdit()
        self.number_edit.setPlaceholderText("e.g. ICS 204 or CAPF 104")
        self.number_edit.textChanged.connect(self._auto_id)
        form.addRow("Form Number", self.number_edit)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("auto-generated — edit if needed")
        if self._edit_mode:
            self.id_edit.setEnabled(False)  # ID is immutable once created
        form.addRow("Form ID", self.id_edit)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("e.g. Assignment List")
        form.addRow("Title", self.title_edit)

        all_cats = list(dict.fromkeys(existing_categories + self.KNOWN_CATEGORIES))
        self.category_combo = QComboBox()
        for c in all_cats:
            self.category_combo.addItem(c)
        form.addRow("Category", self.category_combo)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if existing:
            self._populate(existing)

    def _populate(self, entry: dict) -> None:
        self.number_edit.setText(entry.get("number", ""))
        self.id_edit.setText(entry.get("id", ""))
        self.title_edit.setText(entry.get("title", ""))
        cat = entry.get("category", "")
        idx = self.category_combo.findText(cat)
        if idx >= 0:
            self.category_combo.setCurrentIndex(idx)
        else:
            self.category_combo.setCurrentText(cat)

    def _auto_id(self, text: str) -> None:
        if not self._edit_mode:
            self.id_edit.setText(_to_form_id(text))

    def _on_accept(self) -> None:
        number = self.number_edit.text().strip()
        form_id = self.id_edit.text().strip()
        title = self.title_edit.text().strip()
        category = self.category_combo.currentText().strip()

        if not number or not form_id or not title or not category:
            QMessageBox.warning(self, "Form Definition", "All fields are required.")
            return
        if form_id in self._existing_ids:
            QMessageBox.warning(self, "Form Definition", f"Form ID '{form_id}' already exists.")
            return

        self._result = {
            "number": number,
            "id": form_id,
            "title": title,
            "category": category,
        }
        self.accept()

    def result_data(self) -> dict | None:
        return getattr(self, "_result", None)
