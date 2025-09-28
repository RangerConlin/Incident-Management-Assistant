"""Generic custom filter dialog for building per-field rules.

Used by Team and Task status boards. Accepts a field schema and returns a
list of rules and a match mode (All/Any). Presets are managed inside the
dialog and persisted via SettingsManager when a context_key is provided.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import List

from PySide6 import QtWidgets, QtCore


@dataclass(frozen=True)
class FieldSpec:
    key: str
    label: str
    # string | number | date
    type: str = "string"


class _RuleRow(QtWidgets.QWidget):
    def __init__(self, fields: List[FieldSpec], parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.fields = fields
        layout = QtWidgets.QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(6)

        self.field_combo = QtWidgets.QComboBox(self)
        for f in fields:
            self.field_combo.addItem(f.label, f.key)
        layout.addWidget(self.field_combo)

        self.op_combo = QtWidgets.QComboBox(self)
        self.op_combo.addItems([
            "=",
            "!=",
            ">",
            ">=",
            "<",
            "<=",
            "contains",
            "not contains",
            "starts with",
            "ends with",
        ])
        layout.addWidget(self.op_combo)

        self.value_edit = QtWidgets.QLineEdit(self)
        self.value_edit.setPlaceholderText("Value")
        layout.addWidget(self.value_edit, stretch=1)

        self.remove_btn = QtWidgets.QToolButton(self)
        self.remove_btn.setText("x")
        layout.addWidget(self.remove_btn)

    def set_rule(self, field: str, op: str, value: str) -> None:
        idx = self.field_combo.findData(field)
        if idx >= 0:
            self.field_combo.setCurrentIndex(idx)
        idx = self.op_combo.findText(op)
        if idx >= 0:
            self.op_combo.setCurrentIndex(idx)
        self.value_edit.setText(str(value))

    def rule(self) -> dict:
        return {
            "field": self.field_combo.currentData(),
            "op": self.op_combo.currentText(),
            "value": self.value_edit.text(),
        }


class CustomFilterDialog(QtWidgets.QDialog):
    def __init__(
        self,
        fields: List[FieldSpec],
        *,
        rules: List[dict] | None = None,
        match_all: bool = True,
        context_key: str | None = None,
        seed_presets: dict | None = None,
        parent: QtWidgets.QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Custom Filters")
        self.resize(560, 360)
        self._fields = fields
        self._context_key = context_key

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.setSpacing(6)

        # Presets bar (managed internally; optional)
        preset_bar = QtWidgets.QHBoxLayout()
        self._preset_combo = QtWidgets.QComboBox(self)
        self._preset_combo.setMinimumWidth(180)
        self._preset_combo.currentTextChanged.connect(self._on_preset_selected)
        preset_bar.addWidget(QtWidgets.QLabel("Preset:", self))
        preset_bar.addWidget(self._preset_combo)
        save_btn = QtWidgets.QPushButton("Save")
        save_btn.clicked.connect(self._on_save_preset)
        del_btn = QtWidgets.QPushButton("Delete")
        del_btn.clicked.connect(self._on_delete_preset)
        preset_bar.addWidget(save_btn)
        preset_bar.addWidget(del_btn)
        preset_bar.addStretch(1)
        layout.addLayout(preset_bar)

        # Match mode
        mode_box = QtWidgets.QGroupBox("Match Mode", self)
        mode_layout = QtWidgets.QHBoxLayout(mode_box)
        self._and_radio = QtWidgets.QRadioButton("All rules (AND)", mode_box)
        self._or_radio = QtWidgets.QRadioButton("Any rule (OR)", mode_box)
        mode_layout.addWidget(self._and_radio)
        mode_layout.addWidget(self._or_radio)
        layout.addWidget(mode_box)
        if match_all:
            self._and_radio.setChecked(True)
        else:
            self._or_radio.setChecked(True)

        # Rules list
        rules_container = QtWidgets.QWidget(self)
        self._rules_layout = QtWidgets.QVBoxLayout(rules_container)
        self._rules_layout.setContentsMargins(0, 0, 0, 0)
        self._rules_layout.setSpacing(4)
        layout.addWidget(rules_container, stretch=1)

        btn_row = QtWidgets.QHBoxLayout()
        add_btn = QtWidgets.QPushButton("Add Rule", self)
        add_btn.clicked.connect(self._add_rule_row)
        btn_row.addWidget(add_btn)
        btn_row.addStretch(1)
        layout.addLayout(btn_row)

        # Buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            parent=self,
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Load presets and initial rules
        self._load_presets(seed_presets or {})
        for r in (rules or []):
            self._add_rule_row(preset=r)
        if not (rules or []):
            # Try to load last-used filters from settings if context provided
            default_loaded = self._load_last_filters_into_rows()
            if not default_loaded:
                self._add_rule_row()

    # ------------------------------------------------------------------ API
    def rules(self) -> List[dict]:
        out: List[dict] = []
        for i in range(self._rules_layout.count()):
            item = self._rules_layout.itemAt(i)
            w = item.widget()
            if isinstance(w, _RuleRow):
                out.append(w.rule())
        return out

    def match_all(self) -> bool:
        return self._and_radio.isChecked()

    # ---------------------------------------------------------------- handlers
    def _add_rule_row(self, preset: dict | None = None) -> None:
        row = _RuleRow(self._fields, self)
        if preset:
            row.set_rule(str(preset.get("field", "")), str(preset.get("op", "")), str(preset.get("value", "")))
        row.remove_btn.clicked.connect(lambda: self._remove_rule_row(row))
        self._rules_layout.addWidget(row)

    def _remove_rule_row(self, row: _RuleRow) -> None:
        row.setParent(None)
        row.deleteLater()

    # ------------------------------ presets/storage --------------------------
    def _settings(self):
        if not self._context_key:
            return None
        try:
            from utils.settingsmanager import SettingsManager
            return SettingsManager()
        except Exception:
            return None

    def _load_presets(self, seed: dict) -> None:
        s = self._settings()
        presets = {}
        if s and self._context_key:
            presets = s.get(f"{self._context_key}.presets", {}) or {}
            if not presets and seed:
                presets = seed
                s.set(f"{self._context_key}.presets", presets)
        self._preset_combo.blockSignals(True)
        self._preset_combo.clear()
        for name in sorted(presets.keys()):
            self._preset_combo.addItem(name)
        self._preset_combo.blockSignals(False)
        if s and self._context_key:
            sel = s.get(f"{self._context_key}.preset_selected", None)
            if sel and self._preset_combo.findText(sel) >= 0:
                self._preset_combo.setCurrentText(sel)

    def _load_last_filters_into_rows(self) -> bool:
        s = self._settings()
        if not (s and self._context_key):
            return False
        payload = s.get(f"{self._context_key}.filters", None)
        if not isinstance(payload, dict):
            return False
        rules = list(payload.get("rules", []))
        match_all = bool(payload.get("matchAll", True))
        self._and_radio.setChecked(match_all)
        self._or_radio.setChecked(not match_all)
        for r in rules:
            self._add_rule_row(preset=r)
        return bool(rules)

    @QtCore.Slot()
    def accept(self) -> None:  # persist last-used on OK
        s = self._settings()
        if s and self._context_key:
            s.set(f"{self._context_key}.filters", {"rules": self.rules(), "matchAll": self.match_all()})
        super().accept()

    def _on_preset_selected(self, name: str) -> None:
        s = self._settings()
        if not (s and self._context_key and name):
            return
        presets = s.get(f"{self._context_key}.presets", {}) or {}
        payload = presets.get(name)
        if not isinstance(payload, dict):
            return
        # Clear existing rule rows
        while self._rules_layout.count():
            item = self._rules_layout.takeAt(0)
            if item and item.widget():
                item.widget().deleteLater()
        # Apply preset
        for r in payload.get("rules", []):
            self._add_rule_row(preset=r)
        self._and_radio.setChecked(bool(payload.get("matchAll", True)))
        self._or_radio.setChecked(not bool(payload.get("matchAll", True)))
        s.set(f"{self._context_key}.preset_selected", name)

    def _on_save_preset(self) -> None:
        s = self._settings()
        if not (s and self._context_key):
            return
        name, ok = QtWidgets.QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not str(name).strip():
            return
        name = str(name).strip()
        presets = s.get(f"{self._context_key}.presets", {}) or {}
        presets[name] = {"rules": self.rules(), "matchAll": self.match_all()}
        s.set(f"{self._context_key}.presets", presets)
        if self._preset_combo.findText(name) < 0:
            self._preset_combo.addItem(name)
        self._preset_combo.setCurrentText(name)
        s.set(f"{self._context_key}.preset_selected", name)

    def _on_delete_preset(self) -> None:
        s = self._settings()
        if not (s and self._context_key):
            return
        name = self._preset_combo.currentText()
        if not name:
            return
        presets = s.get(f"{self._context_key}.presets", {}) or {}
        if name in presets:
            del presets[name]
            s.set(f"{self._context_key}.presets", presets)
            idx = self._preset_combo.findText(name)
            if idx >= 0:
                self._preset_combo.removeItem(idx)
            if s.get(f"{self._context_key}.preset_selected", None) == name:
                s.set(f"{self._context_key}.preset_selected", None)

