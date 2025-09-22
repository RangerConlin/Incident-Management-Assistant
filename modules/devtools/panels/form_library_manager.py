from __future__ import annotations

import json
import re
import shutil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QHeaderView,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPushButton,
    QTableWidget,
    QTableWidgetItem,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from ..services.form_catalog import FormCatalog, FormEntry, TemplateEntry
from ..services.fema_fetch import FORM_IDS, fetch_latest
from ..services.binding_library import (
    BindingOption,
    delete_binding_option,
    load_binding_library,
    save_binding_option,
)
from .binding_library_panel import BindingEditorDialog
from modules.forms_creator.ui.MainWindow import MainWindow, ProfileTemplateContext
from utils.profile_manager import ProfileMeta, profile_manager


def _sanitize_component(value: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z._-]+", "_", value.strip())
    return cleaned or "default"


def _relative_template_dir(form_id: str, version: str) -> Path:
    return Path("templates") / _sanitize_component(form_id) / _sanitize_component(version)


def _default_pdf_relative_path(form_id: str, version: str) -> Path:
    directory = _relative_template_dir(form_id, version)
    filename = f"{_sanitize_component(form_id)}_{_sanitize_component(version)}.pdf"
    return directory / filename


def _default_mapping_relative_path(form_id: str, version: str) -> Path:
    return _relative_template_dir(form_id, version) / "bindings.json"


def _to_posix(path: Path) -> str:
    return path.as_posix()


class NewFormDialog(QDialog):
    """Collect the metadata required to register a new form."""

    def __init__(self, existing_ids: Iterable[str], parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Form")
        self._existing = {str(fid).strip().lower() for fid in existing_ids}
        self._result: Optional[Tuple[str, str]] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        layout.addLayout(form)

        self.id_edit = QLineEdit()
        self.id_edit.setPlaceholderText("e.g. ICS_205")
        form.addRow("Form ID", self.id_edit)

        self.title_edit = QLineEdit()
        self.title_edit.setPlaceholderText("Human-readable title")
        form.addRow("Title", self.title_edit)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _on_accept(self) -> None:
        form_id = self.id_edit.text().strip()
        if not form_id:
            QMessageBox.warning(self, "New Form", "Form ID is required.")
            return
        if form_id.lower() in self._existing:
            QMessageBox.warning(self, "New Form", "A form with that ID already exists.")
            return
        title = self.title_edit.text().strip() or form_id
        self._result = (form_id, title)
        self.accept()

    def result(self) -> Optional[Tuple[str, str]]:
        return self._result


class AddVersionDialog(QDialog):
    """Dialog used to capture version metadata and select a PDF."""

    def __init__(
        self,
        form_id: str,
        existing_versions: Iterable[str],
        profiles: Sequence[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Add Version — {form_id}")
        self._existing = {str(v).strip().lower() for v in existing_versions}
        self._pdf_path: Optional[Path] = None
        self._result: Optional[Tuple[str, str, Path]] = None

        layout = QVBoxLayout(self)

        form = QFormLayout()
        layout.addLayout(form)

        self.version_edit = QLineEdit()
        self.version_edit.setPlaceholderText("e.g. 2025.09")
        form.addRow("Version", self.version_edit)

        self.profile_combo = QComboBox()
        for pid in profiles:
            self.profile_combo.addItem(pid)
        form.addRow("Profile", self.profile_combo)

        file_row = QHBoxLayout()
        self.pdf_label = QLabel("No file selected")
        self.pdf_label.setMinimumWidth(260)
        file_row.addWidget(self.pdf_label, 1)
        browse = QPushButton("Choose PDF…")
        browse.clicked.connect(self._choose_pdf)
        file_row.addWidget(browse)
        layout.addLayout(file_row)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._on_accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def _choose_pdf(self) -> None:
        filename, _ = QFileDialog.getOpenFileName(self, "Select PDF", "", "PDF Files (*.pdf)")
        if not filename:
            return
        path = Path(filename)
        if path.suffix.lower() != ".pdf":
            QMessageBox.warning(self, "Add Version", "Please choose a PDF file.")
            return
        self._pdf_path = path
        self.pdf_label.setText(path.name)

    def _on_accept(self) -> None:
        version = self.version_edit.text().strip()
        if not version:
            QMessageBox.warning(self, "Add Version", "Version is required.")
            return
        if version.lower() in self._existing:
            QMessageBox.warning(self, "Add Version", "A template for that version already exists.")
            return
        profile_id = self.profile_combo.currentText().strip()
        if not profile_id:
            QMessageBox.warning(self, "Add Version", "Select a profile to store the template.")
            return
        if self._pdf_path is None:
            QMessageBox.warning(self, "Add Version", "Choose a PDF to continue.")
            return
        self._result = (version, profile_id, self._pdf_path)
        self.accept()

    def result(self) -> Optional[Tuple[str, str, Path]]:
        return self._result


class ProfileSelectionDialog(QDialog):
    """Multi-select helper for assigning template versions to profiles."""

    def __init__(
        self,
        form_id: str,
        version: str,
        profiles: Sequence[str],
        selected: Sequence[str],
        parent: Optional[QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle(f"Profiles — {form_id} {version}")

        layout = QVBoxLayout(self)

        intro = QLabel("Select incident profiles that should use this form version.")
        intro.setWordWrap(True)
        layout.addWidget(intro)

        self.list_widget = QListWidget(self)
        self.list_widget.setSelectionMode(QAbstractItemView.MultiSelection)
        selected_set = {s for s in selected}
        for pid in profiles:
            item = QListWidgetItem(pid)
            if pid in selected_set:
                item.setSelected(True)
            self.list_widget.addItem(item)
        layout.addWidget(self.list_widget)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    def selected_profiles(self) -> List[str]:
        return [item.text() for item in self.list_widget.selectedItems()]


class BindingLibraryEditorDialog(QDialog):
    """Compact editor surface for the binding library."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Binding Library")
        self.resize(720, 420)

        self._result = None
        self._options: List[BindingOption] = []

        layout = QVBoxLayout(self)

        self.table = QTableWidget(0, 4, self)
        self.table.setHorizontalHeaderLabels(["Key", "Source", "Description", "Origin Profile"])
        self.table.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeToContents)
        self.table.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.table.horizontalHeader().setSectionResizeMode(3, QHeaderView.ResizeToContents)
        self.table.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.table.itemSelectionChanged.connect(self._update_buttons)
        layout.addWidget(self.table)

        button_row = QHBoxLayout()
        self.btn_add = QPushButton("Add")
        self.btn_edit = QPushButton("Edit")
        self.btn_delete = QPushButton("Delete")
        button_row.addWidget(self.btn_add)
        button_row.addWidget(self.btn_edit)
        button_row.addWidget(self.btn_delete)
        button_row.addStretch(1)
        layout.addLayout(button_row)

        close_box = QDialogButtonBox(QDialogButtonBox.Close)
        close_box.rejected.connect(self.reject)
        close_box.accepted.connect(self.reject)
        layout.addWidget(close_box)

        self.btn_add.clicked.connect(self._add_option)
        self.btn_edit.clicked.connect(self._edit_option)
        self.btn_delete.clicked.connect(self._delete_option)

        self._reload()
        self._update_buttons()

    def _namespaces(self) -> List[str]:
        namespaces = set()
        for opt in self._options:
            if opt.key and "." in opt.key:
                namespaces.add(opt.key.split(".", 1)[0])
        return sorted(namespaces)

    def _active_profile(self) -> Optional[str]:
        try:
            result = load_binding_library()
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Binding Library", f"Unable to load bindings:\n{exc}")
            return None
        self._options = list(result.options)
        active = result.active_profile_id
        self.table.setRowCount(0)
        for opt in self._options:
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QTableWidgetItem(opt.key))
            self.table.setItem(row, 1, QTableWidgetItem(opt.source or ""))
            self.table.setItem(row, 2, QTableWidgetItem(opt.description or ""))
            origin = opt.origin_profile or (active if opt.is_defined_in_active else "")
            self.table.setItem(row, 3, QTableWidgetItem(origin or ""))
            self.table.item(row, 0).setData(Qt.UserRole, opt)
        return active

    def _reload(self) -> None:
        self._active = self._active_profile()

    def _selected_option(self) -> Optional[BindingOption]:
        row = self.table.currentRow()
        if row < 0:
            return None
        item = self.table.item(row, 0)
        if item is None:
            return None
        opt = item.data(Qt.UserRole)
        return opt if isinstance(opt, BindingOption) else None

    def _add_option(self) -> None:
        active = getattr(self, "_active", None)
        dialog = BindingEditorDialog(self, option=None, namespaces=self._namespaces(), active_profile=active)
        if dialog.exec() != QDialog.Accepted:
            return
        option = dialog.result_option()
        try:
            save_binding_option(option)
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Binding Library", f"Failed to save binding:\n{exc}")
            return
        self._reload()

    def _edit_option(self) -> None:
        option = self._selected_option()
        if option is None:
            return
        active = getattr(self, "_active", None)
        dialog = BindingEditorDialog(self, option=option, namespaces=self._namespaces(), active_profile=active)
        if dialog.exec() != QDialog.Accepted:
            return
        try:
            save_binding_option(dialog.result_option(), original_key=option.key)
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Binding Library", f"Failed to update binding:\n{exc}")
            return
        self._reload()

    def _delete_option(self) -> None:
        option = self._selected_option()
        if option is None:
            return
        if QMessageBox.question(
            self,
            "Binding Library",
            f"Remove binding '{option.key}'?",
        ) != QMessageBox.Yes:
            return
        try:
            delete_binding_option(option.key)
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Binding Library", f"Failed to delete binding:\n{exc}")
            return
        self._reload()

    def _update_buttons(self) -> None:
        has_selection = self.table.currentRow() >= 0
        self.btn_edit.setEnabled(has_selection)
        self.btn_delete.setEnabled(has_selection)


class FormLibraryManager(QWidget):
    """Unified panel for managing form templates, versions, and bindings."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Form Library Manager")

        self.catalog = FormCatalog()
        self._forms_cache: Dict[str, FormEntry] = {}
        self._open_editors: List[MainWindow] = []

        layout = QHBoxLayout(self)

        self.tree = QTreeWidget(self)
        self.tree.setColumnCount(4)
        self.tree.setHeaderLabels(["Form ID", "Title", "Version", "Profiles"])
        self.tree.itemSelectionChanged.connect(self._update_details)
        layout.addWidget(self.tree, 2)

        sidebar = QVBoxLayout()
        layout.addLayout(sidebar, 1)

        form_group = QGroupBox("Form Details", self)
        form_layout = QFormLayout(form_group)
        self.form_id_label = QLabel("—")
        form_layout.addRow("Form ID", self.form_id_label)
        self.form_title_edit = QLineEdit()
        self.form_title_edit.setPlaceholderText("Title shown in menus")
        form_layout.addRow("Title", self.form_title_edit)
        self.form_save_button = QPushButton("Save Form Details")
        self.form_save_button.clicked.connect(self._save_form_details)
        form_layout.addRow(self.form_save_button)
        sidebar.addWidget(form_group)

        version_group = QGroupBox("Selected Version", self)
        version_layout = QFormLayout(version_group)
        self.version_label = QLabel("—")
        version_layout.addRow("Version", self.version_label)
        self.version_profiles_label = QLabel("—")
        version_layout.addRow("Profiles", self.version_profiles_label)
        self.version_pdf_label = QLabel("—")
        self.version_pdf_label.setWordWrap(True)
        version_layout.addRow("PDF", self.version_pdf_label)
        self.version_mapping_label = QLabel("—")
        self.version_mapping_label.setWordWrap(True)
        version_layout.addRow("Mapping", self.version_mapping_label)
        sidebar.addWidget(version_group)

        actions_group = QGroupBox("Actions", self)
        actions_layout = QVBoxLayout(actions_group)
        self.btn_new_form = QPushButton("New Form")
        self.btn_new_form.clicked.connect(self._handle_new_form)
        actions_layout.addWidget(self.btn_new_form)

        self.btn_add_version = QPushButton("Add Version…")
        self.btn_add_version.clicked.connect(self._handle_add_version)
        actions_layout.addWidget(self.btn_add_version)

        self.btn_assign_profiles = QPushButton("Profiles…")
        self.btn_assign_profiles.clicked.connect(self._handle_assign_profiles)
        actions_layout.addWidget(self.btn_assign_profiles)

        self.btn_edit_template = QPushButton("Edit Template…")
        self.btn_edit_template.clicked.connect(self._handle_edit_template)
        actions_layout.addWidget(self.btn_edit_template)

        self.btn_binding_library = QPushButton("Edit Binding Library…")
        self.btn_binding_library.clicked.connect(self._handle_binding_library)
        actions_layout.addWidget(self.btn_binding_library)

        self.btn_import_fema = QPushButton("Import FEMA/ICS forms…")
        self.btn_import_fema.clicked.connect(self._handle_import_forms)
        actions_layout.addWidget(self.btn_import_fema)

        self.btn_refresh = QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self._refresh_tree)
        actions_layout.addWidget(self.btn_refresh)

        sidebar.addWidget(actions_group)
        sidebar.addStretch(1)

        self._refresh_tree()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _profile_meta_map(self) -> Dict[str, ProfileMeta]:
        return {meta.id: meta for meta in profile_manager.list_profiles()}

    def _is_custom_form(self, form: FormEntry) -> bool:
        category = (form.category or "").strip().lower()
        return category == "custom"

    def _ensure_entry_paths(self, form_id: str, entry: TemplateEntry) -> TemplateEntry:
        pdf_rel = Path(entry.pdf) if entry.pdf else _default_pdf_relative_path(form_id, entry.version)
        mapping_rel = (
            Path(entry.mapping)
            if entry.mapping
            else _default_mapping_relative_path(form_id, entry.version)
        )
        return TemplateEntry(
            version=entry.version,
            pdf=_to_posix(pdf_rel),
            mapping=_to_posix(mapping_rel),
            schema=entry.schema,
            profiles=list(entry.profiles or []),
        )

    def _cleanup_closed_editors(self, *_args) -> None:
        alive: List[MainWindow] = []
        for window in self._open_editors:
            try:
                window.windowTitle()
            except RuntimeError:
                continue
            alive.append(window)
        self._open_editors = alive

    def _refresh_tree(self) -> None:
        self._cleanup_closed_editors()
        self.catalog.load()
        forms = self.catalog.list_forms()
        self._forms_cache = {f.id: f for f in forms}
        self.tree.blockSignals(True)
        self.tree.clear()
        for form in sorted(forms, key=lambda f: f.id):
            form_item = QTreeWidgetItem(self.tree, [form.id, form.title or form.id, "", ", ".join(form.profiles or [])])
            form_item.setData(0, Qt.UserRole, ("form", form.id))
            for tpl in sorted(form.templates, key=lambda t: t.version):
                tpl_norm = self._ensure_entry_paths(form.id, tpl)
                profiles = ", ".join(tpl_norm.profiles) if tpl_norm.profiles else "—"
                version_item = QTreeWidgetItem(form_item, ["", "", tpl_norm.version, profiles])
                version_item.setData(0, Qt.UserRole, ("version", form.id, tpl_norm.version))
                version_item.setData(0, Qt.UserRole + 1, tpl_norm)
                tooltip = f"PDF: {tpl_norm.pdf or '—'}\nMapping: {tpl_norm.mapping or '—'}"
                version_item.setToolTip(0, tooltip)
                version_item.setToolTip(2, tooltip)
            form_item.setExpanded(True)
        self.tree.blockSignals(False)
        self.tree.resizeColumnToContents(0)
        self.tree.resizeColumnToContents(2)
        self._update_details()

    def _current_form_context(self) -> Optional[Tuple[str, FormEntry]]:
        item = self.tree.currentItem()
        if not item:
            return None
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, tuple):
            return None
        if data[0] == "form":
            form_id = data[1]
        elif data[0] == "version":
            form_id = data[1]
        else:
            return None
        form = self._forms_cache.get(form_id)
        if not form:
            return None
        return form_id, form

    def _current_version_context(self) -> Optional[Tuple[FormEntry, TemplateEntry]]:
        item = self.tree.currentItem()
        if not item:
            return None
        data = item.data(0, Qt.UserRole)
        if not isinstance(data, tuple) or data[0] != "version":
            return None
        form_id, version = data[1], data[2]
        form = self._forms_cache.get(form_id)
        if not form:
            return None
        for tpl in form.templates:
            if tpl.version == version:
                return form, self._ensure_entry_paths(form.id, tpl)
        return None

    def _select_form(self, form_id: str) -> None:
        for row in range(self.tree.topLevelItemCount()):
            item = self.tree.topLevelItem(row)
            if item and item.text(0) == form_id:
                self.tree.setCurrentItem(item)
                break

    def _select_version(self, form_id: str, version: str) -> None:
        for row in range(self.tree.topLevelItemCount()):
            form_item = self.tree.topLevelItem(row)
            if form_item and form_item.text(0) == form_id:
                for child_idx in range(form_item.childCount()):
                    child = form_item.child(child_idx)
                    data = child.data(0, Qt.UserRole)
                    if isinstance(data, tuple) and data[0] == "version" and data[2] == version:
                        self.tree.setCurrentItem(child)
                        return
                break

    def _bind_form_details(self, form: Optional[FormEntry]) -> None:
        if form is None:
            self.form_id_label.setText("—")
            self.form_title_edit.blockSignals(True)
            self.form_title_edit.clear()
            self.form_title_edit.blockSignals(False)
            self.form_title_edit.setEnabled(False)
            self.form_save_button.setEnabled(False)
            return
        self.form_id_label.setText(form.id)
        self.form_title_edit.blockSignals(True)
        self.form_title_edit.setText(form.title or form.id)
        self.form_title_edit.blockSignals(False)
        self.form_title_edit.setEnabled(True)
        self.form_save_button.setEnabled(True)

    def _bind_version_details(self, tpl: Optional[TemplateEntry]) -> None:
        if tpl is None:
            self.version_label.setText("—")
            self.version_profiles_label.setText("—")
            self.version_pdf_label.setText("—")
            self.version_mapping_label.setText("—")
            return
        self.version_label.setText(tpl.version)
        self.version_profiles_label.setText(", ".join(tpl.profiles) if tpl.profiles else "—")
        self.version_pdf_label.setText(tpl.pdf or "—")
        self.version_mapping_label.setText(tpl.mapping or "—")

    def _update_button_states(self) -> None:
        item = self.tree.currentItem()
        data = item.data(0, Qt.UserRole) if item else None
        is_form = isinstance(data, tuple) and data[0] == "form"
        is_version = isinstance(data, tuple) and data[0] == "version"
        self.btn_add_version.setEnabled(is_form or is_version)
        self.btn_assign_profiles.setEnabled(is_version)
        self.btn_edit_template.setEnabled(is_version)
        self.form_title_edit.setEnabled(is_form)
        self.form_save_button.setEnabled(is_form)

    def _update_details(self) -> None:
        context = self._current_form_context()
        form = context[1] if context else None
        version_context = self._current_version_context()
        tpl = version_context[1] if version_context else None
        self._bind_form_details(form)
        self._bind_version_details(tpl)
        self._update_button_states()

    # ------------------------------------------------------------------
    # Actions
    # ------------------------------------------------------------------
    def _save_form_details(self) -> None:
        ctx = self._current_form_context()
        if not ctx:
            return
        form_id, form = ctx
        new_title = self.form_title_edit.text().strip() or form_id
        form.title = new_title
        self.catalog.upsert_form(form, custom=self._is_custom_form(form))
        QMessageBox.information(self, "Form Library", "Form details updated.")
        self._refresh_tree()
        self._select_form(form_id)

    def _handle_new_form(self) -> None:
        dialog = NewFormDialog(self._forms_cache.keys(), self)
        if dialog.exec() != QDialog.Accepted:
            return
        result = dialog.result()
        if not result:
            return
        form_id, title = result
        entry = FormEntry(id=form_id, title=title, category="Custom", profiles=[], templates=[])
        self.catalog.upsert_form(entry, custom=True)
        self._refresh_tree()
        self._select_form(form_id)

    def _handle_add_version(self) -> None:
        ctx = self._current_form_context()
        if not ctx:
            QMessageBox.warning(self, "Add Version", "Select a form first.")
            return
        form_id, form = ctx
        profiles = [meta.id for meta in profile_manager.list_profiles()]
        if not profiles:
            QMessageBox.warning(self, "Add Version", "No incident profiles are available. Create a profile first.")
            return
        dialog = AddVersionDialog(form_id, [tpl.version for tpl in form.templates], profiles, self)
        if dialog.exec() != QDialog.Accepted:
            return
        result = dialog.result()
        if not result:
            return
        version, profile_id, pdf_path = result
        try:
            self._create_template_version(form, version, profile_id, pdf_path)
        except Exception as exc:  # pragma: no cover - dialog feedback
            QMessageBox.critical(self, "Add Version", f"Failed to add version:\n{exc}")
            return
        self._refresh_tree()
        self._select_version(form_id, version)

    def _create_template_version(
        self,
        form: FormEntry,
        version: str,
        profile_id: str,
        source_pdf: Path,
    ) -> None:
        meta_map = self._profile_meta_map()
        profile = meta_map.get(profile_id)
        if profile is None:
            raise RuntimeError(f"Profile '{profile_id}' not found")
        rel_pdf = _default_pdf_relative_path(form.id, version)
        rel_mapping = _default_mapping_relative_path(form.id, version)
        dest_pdf = profile.path / rel_pdf
        dest_pdf.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source_pdf, dest_pdf)
        mapping_path = profile.path / rel_mapping
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        if not mapping_path.exists():
            placeholder = {
                "form_id": form.id,
                "version": version,
                "bindings": {},
            }
            mapping_path.write_text(json.dumps(placeholder, indent=2), encoding="utf-8")
        tpl = TemplateEntry(
            version=version,
            pdf=_to_posix(rel_pdf),
            mapping=_to_posix(rel_mapping),
            profiles=[profile_id],
        )
        self.catalog.add_template(form.id, tpl, custom=self._is_custom_form(form))
        profiles_union = sorted(set(form.profiles or []) | {profile_id})
        form.profiles = profiles_union
        self.catalog.upsert_form(form, custom=self._is_custom_form(form))

    def _handle_assign_profiles(self) -> None:
        ctx = self._current_version_context()
        if ctx is None:
            QMessageBox.warning(self, "Profiles", "Select a specific version first.")
            return
        form, tpl = ctx
        profiles = [meta.id for meta in profile_manager.list_profiles()]
        if not profiles:
            QMessageBox.warning(self, "Profiles", "No incident profiles are available.")
            return
        dlg = ProfileSelectionDialog(form.id, tpl.version, profiles, tpl.profiles, self)
        if dlg.exec() != QDialog.Accepted:
            return
        selected = dlg.selected_profiles()
        tpl.profiles = sorted({p for p in selected if p})
        if tpl.profiles:
            self._ensure_files_for_profiles(form.id, tpl, tpl.profiles[0], tpl.profiles)
        self.catalog.add_template(form.id, tpl, custom=self._is_custom_form(form))
        form.profiles = sorted(set(form.profiles or []) | set(tpl.profiles))
        self.catalog.upsert_form(form, custom=self._is_custom_form(form))
        self._refresh_tree()
        self._select_version(form.id, tpl.version)

    def _ensure_files_for_profiles(
        self,
        form_id: str,
        tpl: TemplateEntry,
        source_profile_id: str,
        targets: Iterable[str],
    ) -> None:
        meta_map = self._profile_meta_map()
        rel_pdf = Path(tpl.pdf) if tpl.pdf else _default_pdf_relative_path(form_id, tpl.version)
        rel_mapping = (
            Path(tpl.mapping)
            if tpl.mapping
            else _default_mapping_relative_path(form_id, tpl.version)
        )
        source_meta = meta_map.get(source_profile_id)
        if source_meta is None:
            return
        source_pdf = source_meta.path / rel_pdf
        source_mapping = source_meta.path / rel_mapping
        for profile_id in targets:
            meta = meta_map.get(profile_id)
            if meta is None:
                continue
            if source_pdf.exists():
                dest_pdf = meta.path / rel_pdf
                dest_pdf.parent.mkdir(parents=True, exist_ok=True)
                if not dest_pdf.exists():
                    try:
                        shutil.copy2(source_pdf, dest_pdf)
                    except Exception:
                        pass
            if source_mapping.exists():
                dest_map = meta.path / rel_mapping
                dest_map.parent.mkdir(parents=True, exist_ok=True)
                if profile_id == source_profile_id:
                    continue
                try:
                    shutil.copy2(source_mapping, dest_map)
                except Exception:
                    pass

    def _handle_edit_template(self) -> None:
        ctx = self._current_version_context()
        if ctx is None:
            QMessageBox.warning(self, "Edit Template", "Select a form version to edit.")
            return
        form, tpl = ctx
        profiles = tpl.profiles or []
        if not profiles:
            active = profile_manager.get_active_profile_id()
            if active:
                profiles = [active]
            else:
                QMessageBox.warning(
                    self,
                    "Edit Template",
                    "Assign the version to at least one profile before editing.",
                )
                return
        profile_id = profiles[0]
        if len(profiles) > 1:
            profile_id, ok = QInputDialog.getItem(
                self,
                "Choose Profile",
                "Edit template for profile:",
                profiles,
                0,
                False,
            )
            if not ok or not profile_id:
                return
        meta_map = self._profile_meta_map()
        profile_meta = meta_map.get(profile_id)
        if profile_meta is None:
            QMessageBox.warning(self, "Edit Template", f"Profile '{profile_id}' is unavailable.")
            return
        self._ensure_files_for_profiles(form.id, tpl, profile_id, [profile_id])
        context = ProfileTemplateContext(
            form_id=form.id,
            version=tpl.version,
            profile_id=profile_id,
            profile_path=profile_meta.path,
            pdf_rel=Path(tpl.pdf) if tpl.pdf else _default_pdf_relative_path(form.id, tpl.version),
            mapping_rel=Path(tpl.mapping)
            if tpl.mapping
            else _default_mapping_relative_path(form.id, tpl.version),
            assigned_profiles=list(tpl.profiles or []),
            custom=self._is_custom_form(form),
        )
        window = MainWindow(parent=self.window())
        window.apply_profile_context(context)
        window.templateSaved.connect(self._on_template_saved)
        window.destroyed.connect(self._cleanup_closed_editors)
        self._open_editors.append(window)
        window.show()

    def _on_template_saved(self, payload: Optional[dict]) -> None:
        self._refresh_tree()
        if not payload:
            return
        form_id = payload.get("form_id")
        version = payload.get("version")
        if form_id and version:
            self._select_version(str(form_id), str(version))

    def _handle_binding_library(self) -> None:
        dlg = BindingLibraryEditorDialog(self)
        dlg.exec()

    def _handle_import_forms(self) -> None:
        confirm = QMessageBox.question(
            self,
            "Import FEMA/ICS forms",
            "Fetch the latest FEMA/ICS form PDFs now?",
            QMessageBox.Yes | QMessageBox.No,
        )
        if confirm != QMessageBox.Yes:
            return
        try:
            results = fetch_latest(FORM_IDS)
        except Exception as exc:  # pragma: no cover - network path
            QMessageBox.critical(self, "Import FEMA/ICS forms", f"Import failed:\n{exc}")
            return
        if results:
            lines = [f"{fid} v{ver}" for fid, ver, _ in results]
            QMessageBox.information(
                self,
                "Import Complete",
                "Imported forms:\n" + "\n".join(lines),
            )
        else:
            QMessageBox.information(
                self,
                "Import Complete",
                "No new forms were imported. The catalog is already up to date.",
            )
        self._refresh_tree()


__all__ = ["FormLibraryManager"]
