from __future__ import annotations

import json
import re
from typing import List, Optional, Sequence

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication, QFont
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
    QHeaderView,
)

from ..services.binding_library import (
    BindingOption,
    load_binding_library,
    save_binding_option,
    delete_binding_option,
)
from utils.profile_manager import profile_manager


_DEFAULT_SOURCES = [
    "constants",
    "incident",
    "operations",
    "planning",
    "logistics",
    "finance",
    "personnel",
    "mission",
    "computed",
    "form",
]


def _collect_lines(widget: QPlainTextEdit) -> List[str]:
    return [line.strip() for line in widget.toPlainText().splitlines() if line.strip()]


def _slugify(value: str) -> str:
    value = value.strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return value.strip("_")


def _pattern_from_phrase(phrase: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", ".*", phrase.lower())
    normalized = normalized.strip(".*")
    if not normalized:
        return ""
    return f"^{normalized}$"


def _pattern_from_key(key: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", ".?", key.lower())
    normalized = normalized.strip(".?")
    if not normalized:
        return ""
    return f"^{normalized}$"


class BindingEditorDialog(QDialog):
    """Interactive helper for creating or editing a binding entry."""

    def __init__(
        self,
        parent: Optional[QWidget] = None,
        option: Optional[BindingOption] = None,
        namespaces: Sequence[str] = (),
        active_profile: Optional[str] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Binding Editor")
        self._option = option
        self._active_profile = active_profile
        self._original_key = option.key if option else None
        self._extra = dict(option.extra) if option else {}

        layout = QVBoxLayout(self)

        intro = QLabel(
            "Bindings map PDF fields to canonical keys used across the incident. "
            "Provide a descriptive key, optional synonyms for search, and "
            "regex patterns that help the auto-mapper spot the field."
        )
        intro.setWordWrap(True)
        layout.addWidget(intro)

        if option and not option.is_defined_in_active:
            inherit_note = QLabel(
                "This binding is inherited from profile "
                f"<b>{option.origin_profile or 'unknown'}</b>. "
                "Saving will create an override in the active profile."
            )
            inherit_note.setWordWrap(True)
            layout.addWidget(inherit_note)

        form = QFormLayout()

        self.txt_key = QLineEdit(option.key if option else "")
        self.txt_key.setPlaceholderText("e.g., incident.name")
        form.addRow("Key", self.txt_key)

        self.cbo_source = QComboBox()
        self.cbo_source.setEditable(True)
        for src in _DEFAULT_SOURCES:
            self.cbo_source.addItem(src)
        if option:
            self.cbo_source.setCurrentText(option.source or "constants")
        else:
            self.cbo_source.setCurrentText("constants")
        form.addRow("Source", self.cbo_source)

        self.txt_desc = QLineEdit(option.description if option else "")
        self.txt_desc.setPlaceholderText("Short description shown to authors")
        form.addRow("Description", self.txt_desc)

        self.txt_synonyms = QPlainTextEdit()
        self.txt_synonyms.setPlaceholderText("One synonym per line")
        if option and option.synonyms:
            self.txt_synonyms.setPlainText("\n".join(option.synonyms))
        form.addRow("Synonyms", self.txt_synonyms)

        self.txt_patterns = QPlainTextEdit()
        self.txt_patterns.setPlaceholderText("One regex pattern per line")
        if option and option.patterns:
            self.txt_patterns.setPlainText("\n".join(option.patterns))
        form.addRow("Patterns", self.txt_patterns)

        layout.addLayout(form)

        helper_box = QGroupBox("Binding Helper")
        helper_layout = QVBoxLayout(helper_box)

        helper_form = QFormLayout()
        self.cbo_namespace = QComboBox()
        self.cbo_namespace.setEditable(True)
        unique_namespaces = sorted({ns for ns in namespaces if ns})
        for ns in unique_namespaces:
            self.cbo_namespace.addItem(ns)
        if option and option.key:
            ns_guess = option.key.split(".")[0]
            self.cbo_namespace.setCurrentText(ns_guess)
        helper_form.addRow("Namespace", self.cbo_namespace)

        self.txt_helper_label = QLineEdit()
        self.txt_helper_label.setPlaceholderText("Label on the PDF (e.g., Incident Name)")
        helper_form.addRow("Field label", self.txt_helper_label)
        helper_layout.addLayout(helper_form)

        helper_actions = QHBoxLayout()
        self.btn_generate = QPushButton("Build key & synonyms")
        self.btn_generate.clicked.connect(self._apply_helper)
        helper_actions.addWidget(self.btn_generate)

        self.btn_patterns = QPushButton("Generate patterns from synonyms")
        self.btn_patterns.clicked.connect(self._generate_patterns_from_synonyms)
        helper_actions.addWidget(self.btn_patterns)

        helper_actions.addStretch(1)
        helper_layout.addLayout(helper_actions)

        helper_hint = QLabel(
            "Use the helper to convert a plain-language label into a canonical key. "
            "Synonyms feed the search experience and patterns help auto-mapping."
        )
        helper_hint.setWordWrap(True)
        helper_layout.addWidget(helper_hint)

        layout.addWidget(helper_box)

        self.preview = QPlainTextEdit()
        self.preview.setReadOnly(True)
        self.preview.setPlaceholderText("Binding preview")
        layout.addWidget(self.preview)

        self.buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        self.buttons.accepted.connect(self._on_accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)

        self.txt_key.textChanged.connect(self._update_state)
        self.cbo_source.editTextChanged.connect(self._update_state)
        self.txt_desc.textChanged.connect(self._update_state)
        self.txt_synonyms.textChanged.connect(self._update_state)
        self.txt_patterns.textChanged.connect(self._update_state)

        self._update_state()

    # ------------------------------------------------------------------
    def _apply_helper(self) -> None:
        namespace = self.cbo_namespace.currentText().strip()
        label = self.txt_helper_label.text().strip()
        if not label:
            QMessageBox.information(self, "Binding Helper", "Enter a field label to build from.")
            return

        slug = _slugify(label)
        key_parts = [namespace, slug] if namespace else [slug]
        key = ".".join(part for part in key_parts if part)
        if key:
            self.txt_key.setText(key)

        if not self.txt_desc.text().strip():
            self.txt_desc.setText(label)

        synonyms = set(_collect_lines(self.txt_synonyms))
        synonyms.add(label)
        synonyms.add(label.title())
        synonyms.add(label.lower())
        self.txt_synonyms.setPlainText("\n".join(sorted(s.strip() for s in synonyms if s.strip())))

        if namespace and namespace in _DEFAULT_SOURCES:
            self.cbo_source.setCurrentText(namespace)

        self._generate_patterns_from_synonyms()

    def _generate_patterns_from_synonyms(self) -> None:
        patterns = set(_collect_lines(self.txt_patterns))
        key_pattern = _pattern_from_key(self.txt_key.text())
        if key_pattern:
            patterns.add(key_pattern)
        for synonym in _collect_lines(self.txt_synonyms):
            pat = _pattern_from_phrase(synonym)
            if pat:
                patterns.add(pat)
        self.txt_patterns.setPlainText("\n".join(sorted(patterns)))

    def _update_state(self) -> None:
        option = self._build_option()
        payload = option.to_payload()
        preview_data = {"key": option.key, **payload}
        try:
            preview_text = json.dumps(preview_data, indent=2, ensure_ascii=False)
        except Exception:
            preview_text = str(preview_data)
        self.preview.setPlainText(preview_text)

        error = self._validate()
        ok_button = self.buttons.button(QDialogButtonBox.Ok)
        if ok_button is not None:
            ok_button.setEnabled(error is None)

    def _validate(self) -> Optional[str]:
        key = self.txt_key.text().strip()
        if not key:
            return "Key is required."
        if any(ch.isspace() for ch in key):
            return "Key cannot contain whitespace."
        return None

    def _build_option(self) -> BindingOption:
        key = self.txt_key.text().strip()
        source = self.cbo_source.currentText().strip() or "constants"
        description = self.txt_desc.text().strip()
        synonyms = _collect_lines(self.txt_synonyms)
        patterns = _collect_lines(self.txt_patterns)
        origin = self._active_profile or (self._option.origin_profile if self._option else None)
        return BindingOption(
            key=key,
            source=source,
            description=description,
            synonyms=synonyms,
            patterns=patterns,
            origin_profile=origin,
            is_defined_in_active=True,
            extra=dict(self._extra),
        )

    def _on_accept(self) -> None:
        error = self._validate()
        if error:
            QMessageBox.warning(self, "Binding Editor", error)
            return
        self.accept()

    def result_option(self) -> BindingOption:
        return self._build_option()

    @property
    def original_key(self) -> Optional[str]:
        return self._original_key


class BindingLibraryPanel(QWidget):
    """Display and edit the centralized catalog of bindings."""

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Binding Library")

        self._bindings: List[BindingOption] = []
        self._active_profile: Optional[str] = None
        self._catalog_path: Optional[str] = None

        layout = QVBoxLayout(self)

        header = QHBoxLayout()
        self.lbl_profile = QLabel("")
        header.addWidget(self.lbl_profile)
        header.addStretch(1)

        self.btn_add = QPushButton("Add Binding")
        self.btn_add.clicked.connect(self._add_binding)
        header.addWidget(self.btn_add)

        self.btn_edit = QPushButton("Edit…")
        self.btn_edit.clicked.connect(self._edit_selected_binding)
        header.addWidget(self.btn_edit)

        self.btn_delete = QPushButton("Delete")
        self.btn_delete.clicked.connect(self._delete_selected_binding)
        header.addWidget(self.btn_delete)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        header.addWidget(self.btn_refresh)

        layout.addLayout(header)

        self.lbl_catalog = QLabel("")
        self.lbl_catalog.setTextInteractionFlags(Qt.TextSelectableByMouse)
        layout.addWidget(self.lbl_catalog)

        self.txt_filter = QLineEdit()
        self.txt_filter.setPlaceholderText("Filter bindings…")
        self.txt_filter.textChanged.connect(self._apply_filter)
        layout.addWidget(self.txt_filter)

        self.tbl = QTableWidget(0, 4, self)
        self.tbl.setHorizontalHeaderLabels(["Key", "Source", "Description", "Synonyms"])
        self.tbl.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.tbl.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.tbl.horizontalHeader().setSectionResizeMode(3, QHeaderView.Stretch)
        self.tbl.verticalHeader().setVisible(False)
        self.tbl.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.tbl.setSelectionMode(QAbstractItemView.SingleSelection)
        self.tbl.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.tbl.itemSelectionChanged.connect(self._update_actions)
        self.tbl.itemDoubleClicked.connect(lambda *_: self._edit_selected_binding())
        layout.addWidget(self.tbl, 1)

        footer = QHBoxLayout()
        self.lbl_count = QLabel("")
        footer.addWidget(self.lbl_count)
        footer.addStretch(1)
        self.btn_copy = QPushButton("Copy Key")
        self.btn_copy.clicked.connect(self._copy_selected_key)
        footer.addWidget(self.btn_copy)
        layout.addLayout(footer)

        self.btn_copy.setEnabled(False)
        self.btn_edit.setEnabled(False)
        self.btn_delete.setEnabled(False)

        self.refresh()

    # ------------------------------------------------------------------
    def refresh(self) -> None:
        """Reload bindings from the active profile catalog."""

        active = profile_manager.get_active_profile_id() or "(no active profile)"
        self.lbl_profile.setText(f"Active profile: {active}")
        try:
            result = load_binding_library()
            bindings = result.options
            self._active_profile = result.active_profile_id
            self._catalog_path = result.catalog_path.as_posix() if result.catalog_path else None
        except Exception as exc:  # pragma: no cover - defensive UI path
            QMessageBox.warning(self, "Binding Library", f"Failed to load bindings: {exc}")
            bindings = []
            self._active_profile = None
            self._catalog_path = None

        if self._catalog_path:
            self.lbl_catalog.setText(f"Catalog file: {self._catalog_path}")
        else:
            self.lbl_catalog.setText("Catalog file: (not found)")

        self._bindings = bindings
        self._rebuild_table()

    def _rebuild_table(self) -> None:
        self.tbl.setRowCount(0)
        for row, binding in enumerate(self._bindings):
            self.tbl.insertRow(row)
            key_item = QTableWidgetItem(binding.key)
            key_item.setData(Qt.UserRole, binding.key)
            if not binding.is_defined_in_active:
                font = QFont(key_item.font())
                font.setItalic(True)
                key_item.setFont(font)
                key_item.setToolTip("Inherited from another profile")
            self.tbl.setItem(row, 0, key_item)

            source_item = QTableWidgetItem(binding.source)
            self.tbl.setItem(row, 1, source_item)

            desc_item = QTableWidgetItem(binding.description)
            desc_tooltip = binding.description
            if binding.patterns:
                desc_tooltip = f"{binding.description}\nPatterns: {', '.join(binding.patterns)}".strip()
            desc_item.setToolTip(desc_tooltip)
            self.tbl.setItem(row, 2, desc_item)

            synonyms_text = ", ".join(binding.synonyms)
            syn_item = QTableWidgetItem(synonyms_text)
            syn_item.setToolTip("\n".join(binding.synonyms))
            self.tbl.setItem(row, 3, syn_item)

        self.lbl_count.setText(f"{len(self._bindings)} bindings")
        self._apply_filter(self.txt_filter.text())
        if self.tbl.rowCount() > 0:
            # select first visible row
            for idx in range(self.tbl.rowCount()):
                if not self.tbl.isRowHidden(idx):
                    self.tbl.selectRow(idx)
                    break
        else:
            self.tbl.clearSelection()
        self._update_actions()

    def _apply_filter(self, text: str) -> None:
        query = (text or "").strip().lower()
        for row, binding in enumerate(self._bindings):
            if not query:
                self.tbl.setRowHidden(row, False)
                continue
            haystack = " ".join(
                [
                    binding.key,
                    binding.source,
                    binding.description,
                    " ".join(binding.synonyms),
                    " ".join(binding.patterns),
                ]
            ).lower()
            self.tbl.setRowHidden(row, query not in haystack)
        self._update_actions()

    def _selected_binding(self) -> Optional[BindingOption]:
        row = self.tbl.currentRow()
        if row < 0 or row >= len(self._bindings):
            return None
        if self.tbl.isRowHidden(row):
            return None
        return self._bindings[row]

    def _copy_selected_key(self) -> None:
        binding = self._selected_binding()
        if not binding:
            QMessageBox.information(self, "Copy Key", "Select a binding to copy.")
            return
        QGuiApplication.clipboard().setText(binding.key)
        QMessageBox.information(self, "Copy Key", f"Copied {binding.key} to clipboard.")

    def _add_binding(self) -> None:
        namespaces = self._collect_namespaces()
        dlg = BindingEditorDialog(self, option=None, namespaces=namespaces, active_profile=self._active_profile)
        if dlg.exec() == QDialog.Accepted:
            try:
                save_binding_option(dlg.result_option())
            except Exception as exc:
                QMessageBox.warning(self, "Binding Library", f"Failed to save binding: {exc}")
                return
            self.refresh()

    def _edit_selected_binding(self) -> None:
        binding = self._selected_binding()
        if not binding:
            QMessageBox.information(self, "Edit Binding", "Select a binding to edit.")
            return
        namespaces = self._collect_namespaces()
        dlg = BindingEditorDialog(self, option=binding, namespaces=namespaces, active_profile=self._active_profile)
        if dlg.exec() == QDialog.Accepted:
            try:
                save_binding_option(dlg.result_option(), original_key=binding.key)
            except Exception as exc:
                QMessageBox.warning(self, "Binding Library", f"Failed to save binding: {exc}")
                return
            self.refresh()

    def _delete_selected_binding(self) -> None:
        binding = self._selected_binding()
        if not binding:
            QMessageBox.information(self, "Delete Binding", "Select a binding to delete.")
            return
        if not binding.is_defined_in_active:
            QMessageBox.information(
                self,
                "Delete Binding",
                "This key is inherited. Override it instead of deleting, or remove it from the parent profile.",
            )
            return
        confirm = QMessageBox.question(
            self,
            "Delete Binding",
            f"Remove binding <b>{binding.key}</b>?",
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            removed = delete_binding_option(binding.key)
        except Exception as exc:
            QMessageBox.warning(self, "Binding Library", f"Failed to delete binding: {exc}")
            return
        if not removed:
            QMessageBox.information(self, "Delete Binding", "Binding was not found in the active profile catalog.")
            return
        self.refresh()

    def _collect_namespaces(self) -> List[str]:
        namespaces = sorted({binding.key.split(".")[0] for binding in self._bindings if "." in binding.key})
        if self._active_profile:
            namespaces.insert(0, "")
        return namespaces

    def _update_actions(self) -> None:
        binding = self._selected_binding()
        has_binding = binding is not None
        self.btn_copy.setEnabled(has_binding)
        self.btn_edit.setEnabled(has_binding)
        self.btn_delete.setEnabled(bool(binding and binding.is_defined_in_active))


__all__ = ["BindingLibraryPanel"]
