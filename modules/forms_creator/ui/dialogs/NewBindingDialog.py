"""Dialog for adding or editing a binding catalog entry."""

from __future__ import annotations

import json
import re
from pathlib import Path

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QFrame,
    QLabel,
    QLineEdit,
    QMessageBox,
    QSpinBox,
    QStackedWidget,
    QTextBrowser,
    QVBoxLayout,
    QWidget,
)

_BINDING_CATALOG_PATH = Path(__file__).resolve().parents[4] / "forms" / "binding_catalog.json"

_HELP_TEXTS = {
    "data_path": (
        "<b>Data Path</b><br><br>"
        "Pulls a live value from the incident at export time. "
        "Select the <i>data group</i> (what kind of data), then the specific <i>field</i> "
        "within that group.<br><br>"
        "For groups that contain lists (channels, teams, aircraft, personnel), "
        "also set <i>Which item</i>: 0 = first, 1 = second, and so on.<br><br>"
        "<b>Example:</b> Group <i>Aircraft</i> → Item <i>0</i> → Field <i>Tail Number</i><br>"
        "→ path: <code>aircraft.0.tail_number</code>"
    ),
    "static": (
        "<b>Static Value</b><br><br>"
        "A static value always outputs the same text regardless of the incident. "
        "Use this for agency names, required labels, or standing instructions "
        "that never change.<br><br>"
        "<b>Examples:</b> <i>Acme County Sheriff SAR</i>, "
        "<i>See Safety Message ICS 208</i>"
    ),
    "prompted": (
        "<b>Prompted</b><br><br>"
        "The user is asked to type this value each time the form is exported. "
        "Use for fields that change per export but aren't stored in the system "
        "(e.g. a specific message subject line).<br><br>"
        "Set a prompt question the user will see at export time, "
        "and optionally a default answer."
    ),
    "computed": (
        "<b>Computed</b><br><br>"
        "Combines or reformats other values at generation time. "
        "This type requires a developer to wire it up — flag it here so it "
        "appears in the catalog with the correct path, then implement it in "
        "<code>modules/forms/context.py</code>.<br><br>"
        "<b>Example:</b> joining first name + last name, or reformatting a datetime."
    ),
}


def _load_catalog() -> list[dict]:
    try:
        return json.loads(_BINDING_CATALOG_PATH.read_text(encoding="utf-8"))
    except Exception:
        return []


def _build_group_map(entries: list[dict]) -> dict[str, dict]:
    """
    Build a nested map from the catalog:
      group_name → {
        "label":    human-readable group label,
        "indexed":  bool,
        "fields":   { field_suffix → label }   (suffix = everything after group[.index].)
      }

    For indexed groups (channels.0.name) the suffix is the part after the index.
    For non-indexed groups (incident.name) the suffix is the part after the group.
    """
    groups: dict[str, dict] = {}

    for entry in entries:
        path = entry.get("path", "")
        label = entry.get("label", path)
        source_type = entry.get("source_type", "")

        # Only data-path entries go in the group map
        if source_type not in ("incident_db", "master_db", "computed"):
            continue

        parts = path.split(".")
        if len(parts) < 2:
            continue

        group = parts[0]

        # Detect indexed group: second segment is a digit
        if len(parts) >= 3 and parts[1].isdigit():
            indexed = True
            field_suffix = ".".join(parts[2:])
        else:
            indexed = False
            field_suffix = ".".join(parts[1:])

        if not field_suffix:
            continue

        if group not in groups:
            # Human-readable group name: use the prefix of the first label up to " —" or capitalise
            group_label = group.replace("_", " ").title()
            groups[group] = {"label": group_label, "indexed": indexed, "fields": {}}

        # Only record the field once (first index's label stripped of "N (Nth) — " prefix)
        if field_suffix not in groups[group]["fields"]:
            # Strip leading "Channel 1 (1st) — " / "Aircraft 3 (3rd) — " etc.
            clean_label = re.sub(r"^.*? — ", "", label, count=1)
            # Also strip "Prepared By — " style prefixes for non-indexed groups
            if not indexed:
                clean_label = re.sub(r"^[^—]*— ", "", label, count=1) or label
            groups[group]["fields"][field_suffix] = clean_label

    return groups


class NewBindingDialog(QDialog):
    """Add or edit a single entry in binding_catalog.json."""

    def __init__(
        self,
        existing: dict | None = None,
        existing_paths: set[str] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Edit Binding" if existing else "New Binding")
        self.setMinimumWidth(500)
        self._existing_paths = existing_paths or set()
        self._edit_original_path = existing.get("path") if existing else None

        # Build group map from catalog
        self._group_map = _build_group_map(_load_catalog())

        outer = QVBoxLayout(self)

        # Type selector
        type_form = QFormLayout()
        self.type_combo = QComboBox()
        self.type_combo.addItem("Data Path", "data_path")
        self.type_combo.addItem("Static Value", "static")
        self.type_combo.addItem("Prompted", "prompted")
        self.type_combo.addItem("Computed", "computed")
        type_form.addRow("Binding Type", self.type_combo)
        outer.addLayout(type_form)

        # Help text panel
        self.help_label = QTextBrowser()
        self.help_label.setMaximumHeight(100)
        self.help_label.setFrameShape(QFrame.Shape.StyledPanel)
        outer.addWidget(self.help_label)

        # Stacked pages
        self.stack = QStackedWidget()
        self.stack.addWidget(self._make_data_path_page())   # 0
        self.stack.addWidget(self._make_static_page())       # 1
        self.stack.addWidget(self._make_prompted_page())     # 2
        self.stack.addWidget(self._make_computed_page())     # 3
        outer.addWidget(self.stack)

        # Common fields
        common_form = QFormLayout()
        self.label_edit = QLineEdit()
        self.label_edit.setPlaceholderText("Human-readable label shown in the mapper dropdown")
        common_form.addRow("Label", self.label_edit)

        self.category_edit = QLineEdit()
        self.category_edit.setPlaceholderText("e.g. Incident, Aviation, Radio Channels")
        common_form.addRow("Category", self.category_edit)
        outer.addLayout(common_form)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)

        self.type_combo.currentIndexChanged.connect(self._on_type_changed)
        self._on_type_changed(0)

        if existing:
            self._populate(existing)

    # ------------------------------------------------------------------
    # Page builders
    # ------------------------------------------------------------------

    def _make_data_path_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)

        self.group_combo = QComboBox()
        for group_key, meta in self._group_map.items():
            self.group_combo.addItem(meta["label"], group_key)
        form.addRow("Data Group", self.group_combo)

        self.index_label = QLabel("Which item (0 = first)")
        self.index_spin = QSpinBox()
        self.index_spin.setMinimum(0)
        self.index_spin.setMaximum(99)
        self.index_spin.setValue(0)
        form.addRow(self.index_label, self.index_spin)

        self.field_combo = QComboBox()
        form.addRow("Field", self.field_combo)

        self.path_preview = QLabel()
        self.path_preview.setStyleSheet("font-family: monospace; color: #4a9eff;")
        form.addRow("Path preview", self.path_preview)

        self.group_combo.currentIndexChanged.connect(self._refresh_field_combo)
        self.field_combo.currentIndexChanged.connect(self._refresh_path_preview)
        self.index_spin.valueChanged.connect(self._refresh_path_preview)
        self._refresh_field_combo(0)

        return page

    def _make_static_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.static_value_edit = QLineEdit()
        self.static_value_edit.setPlaceholderText("The exact text to insert into the PDF field")
        form.addRow("Value", self.static_value_edit)
        return page

    def _make_prompted_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.prompt_question_edit = QLineEdit()
        self.prompt_question_edit.setPlaceholderText("e.g. Enter message subject:")
        form.addRow("Prompt Text", self.prompt_question_edit)
        self.prompt_default_edit = QLineEdit()
        self.prompt_default_edit.setPlaceholderText("Optional default answer")
        form.addRow("Default", self.prompt_default_edit)
        return page

    def _make_computed_page(self) -> QWidget:
        page = QWidget()
        form = QFormLayout(page)
        self.computed_path_edit = QLineEdit()
        self.computed_path_edit.setPlaceholderText("Dot-notation path (must be implemented in context.py)")
        form.addRow("Path", self.computed_path_edit)
        note = QLabel("Computed bindings require a developer to wire them up in context.py.")
        note.setWordWrap(True)
        note.setStyleSheet("color: gray; font-size: 11px;")
        form.addRow(note)
        return page

    # ------------------------------------------------------------------
    # Interactions
    # ------------------------------------------------------------------

    def _on_type_changed(self, index: int) -> None:
        type_key = self.type_combo.itemData(index)
        self.stack.setCurrentIndex(index)
        self.help_label.setHtml(_HELP_TEXTS.get(type_key, ""))

    def _refresh_field_combo(self, _=None) -> None:
        group_key = self.group_combo.currentData()
        meta = self._group_map.get(group_key, {})
        indexed = meta.get("indexed", False)
        fields = meta.get("fields", {})

        self.field_combo.clear()
        for suffix, label in fields.items():
            self.field_combo.addItem(label, suffix)

        self.index_spin.setVisible(indexed)
        self.index_label.setVisible(indexed)
        self._refresh_path_preview()

    def _refresh_path_preview(self, _=None) -> None:
        group_key = self.group_combo.currentData() or ""
        field_suffix = self.field_combo.currentData() or ""
        meta = self._group_map.get(group_key, {})
        indexed = meta.get("indexed", False)

        if indexed:
            idx = self.index_spin.value()
            path = f"{group_key}.{idx}.{field_suffix}" if field_suffix else f"{group_key}.{idx}"
        else:
            path = f"{group_key}.{field_suffix}" if field_suffix else group_key

        self.path_preview.setText(path)

    def _build_path(self) -> str:
        type_key = self.type_combo.currentData()
        if type_key == "data_path":
            return self.path_preview.text()
        elif type_key == "static":
            return ""
        elif type_key == "prompted":
            label = self.label_edit.text().strip()
            return "prompted." + re.sub(r"\s+", "_", label).lower() if label else "prompted.value"
        else:
            return self.computed_path_edit.text().strip()

    # ------------------------------------------------------------------
    # Accept / populate
    # ------------------------------------------------------------------

    def _on_accept(self) -> None:
        label = self.label_edit.text().strip()
        category = self.category_edit.text().strip()
        if not label or not category:
            QMessageBox.warning(self, "New Binding", "Label and Category are required.")
            return

        type_key = self.type_combo.currentData()
        path = self._build_path()

        if type_key in ("data_path", "computed") and not path:
            QMessageBox.warning(self, "New Binding", "Path is required for this binding type.")
            return

        if path and path != self._edit_original_path and path in self._existing_paths:
            QMessageBox.warning(self, "New Binding", f"Path '{path}' already exists in the catalog.")
            return

        entry: dict = {"path": path, "label": label, "category": category, "source_type": type_key}

        if type_key == "static":
            entry["static_value"] = self.static_value_edit.text()
        elif type_key == "prompted":
            entry["prompt_text"] = self.prompt_question_edit.text().strip()
            entry["prompt_default"] = self.prompt_default_edit.text().strip()

        self._result = entry
        self.accept()

    def _populate(self, entry: dict) -> None:
        self.label_edit.setText(entry.get("label", ""))
        self.category_edit.setText(entry.get("category", ""))

        source_type = entry.get("source_type", "data_path")
        idx = self.type_combo.findData(source_type)
        if idx >= 0:
            self.type_combo.setCurrentIndex(idx)

        path = entry.get("path", "")
        if source_type == "data_path" and path:
            parts = path.split(".")
            group = parts[0]
            gi = self.group_combo.findData(group)
            if gi >= 0:
                self.group_combo.setCurrentIndex(gi)

            meta = self._group_map.get(group, {})
            if meta.get("indexed") and len(parts) >= 3:
                try:
                    self.index_spin.setValue(int(parts[1]))
                    suffix = ".".join(parts[2:])
                except ValueError:
                    suffix = ".".join(parts[1:])
            else:
                suffix = ".".join(parts[1:])

            fi = self.field_combo.findData(suffix)
            if fi >= 0:
                self.field_combo.setCurrentIndex(fi)

        elif source_type == "static":
            self.static_value_edit.setText(entry.get("static_value", ""))
        elif source_type == "prompted":
            self.prompt_question_edit.setText(entry.get("prompt_text", ""))
            self.prompt_default_edit.setText(entry.get("prompt_default", ""))
        elif source_type == "computed":
            self.computed_path_edit.setText(path)

    def result_data(self) -> dict | None:
        return getattr(self, "_result", None)
