"""Dialog for creating or editing a form set (manifest.json under forms/sets/)."""

from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QVBoxLayout,
)

_SETS_ROOT = Path(__file__).resolve().parents[4] / "forms" / "sets"


def _to_set_id(name: str) -> str:
    s = name.lower().strip()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


class NewFormSetDialog(QDialog):
    """Create or edit a form set (manifest.json)."""

    def __init__(
        self,
        existing_set_ids: set[str],
        existing_set_ids_with_names: list[tuple[str, str]],
        existing: dict | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self._edit_mode = existing is not None
        self.setWindowTitle("Edit Form Set" if self._edit_mode else "New Form Set")
        self.setMinimumWidth(400)
        self._existing_ids = existing_set_ids - ({existing["id"]} if existing else set())

        layout = QVBoxLayout(self)
        form = QFormLayout()
        layout.addLayout(form)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("e.g. USCG ICS Forms")
        if not self._edit_mode:
            self.name_edit.textChanged.connect(self._auto_id)
        form.addRow("Display Name", self.name_edit)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("auto-generated — edit if needed")
        if self._edit_mode:
            self.id_edit.setEnabled(False)
        form.addRow("Set ID", self.id_edit)

        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("e.g. 2023")
        form.addRow("Version", self.version_edit)

        self.fallback_combo = QComboBox()
        self.fallback_combo.addItem("None (no fallback)", "")
        for set_id, display_name in existing_set_ids_with_names:
            if not self._edit_mode or set_id != (existing or {}).get("id"):
                self.fallback_combo.addItem(display_name, set_id)
        form.addRow("Fallback Set", self.fallback_combo)

        info = QLabel(
            "The fallback set is used when this set doesn't have a version of a requested form. "
            "Most sets should fall back to FEMA."
        )
        info.setWordWrap(True)
        info.setStyleSheet("color: gray; font-size: 11px;")
        layout.addWidget(info)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        if existing:
            self._populate(existing)

    def _populate(self, entry: dict) -> None:
        self.name_edit.setText(entry.get("display_name", ""))
        self.id_edit.setText(entry.get("id", ""))
        self.version_edit.setText(entry.get("version", ""))
        fallback = entry.get("fallback") or ""
        idx = self.fallback_combo.findData(fallback)
        if idx >= 0:
            self.fallback_combo.setCurrentIndex(idx)

    def _auto_id(self, text: str) -> None:
        self.id_edit.setText(_to_set_id(text))

    def _on_accept(self) -> None:
        display_name = self.name_edit.text().strip()
        set_id = self.id_edit.text().strip()
        version = self.version_edit.text().strip()
        fallback = self.fallback_combo.currentData() or None

        if not display_name or not set_id:
            QMessageBox.warning(self, "Form Set", "Display name and Set ID are required.")
            return
        if set_id in self._existing_ids:
            QMessageBox.warning(self, "Form Set", f"Set ID '{set_id}' already exists.")
            return

        if not self._edit_mode:
            # Create directory and manifest for new sets
            set_dir = _SETS_ROOT / set_id
            try:
                set_dir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                QMessageBox.warning(self, "Form Set", f"Directory '{set_id}' already exists.")
                return
            except Exception as exc:
                QMessageBox.critical(self, "Form Set", f"Could not create directory:\n{exc}")
                return

            manifest = {
                "id": set_id,
                "display_name": display_name,
                "version": version,
                "fallback": fallback,
            }
            try:
                (set_dir / "manifest.json").write_text(
                    json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8"
                )
            except Exception as exc:
                QMessageBox.critical(self, "Form Set", f"Could not write manifest.json:\n{exc}")
                return

        self._result = {
            "id": set_id,
            "display_name": display_name,
            "version": version,
            "fallback": fallback,
        }
        self.accept()

    def result_data(self) -> dict | None:
        return getattr(self, "_result", None)
