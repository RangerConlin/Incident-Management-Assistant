"""Main workspace for the SARApp Form Creator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QCloseEvent, QKeySequence, QPixmap
from PySide6.QtWidgets import (
    QCheckBox,
    QComboBox,
    QDialog,
    QFileDialog,
    QFormLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QShortcut,
    QSpinBox,
    QSplitter,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..services import db
from ..services.templates import FormService
from .CanvasView import CanvasView
from .FieldItems import FieldItem
from .dialogs.BindingDialog import BindingDialog
from .dialogs.NewTemplateWizard import NewTemplateWizard
from .dialogs.PreviewDialog import PreviewDialog
from .dialogs.TableEditorDialog import TableEditorDialog
from .dialogs.ValidationDialog import ValidationDialog


FIELD_TYPES = [
    ("Text", "text"),
    ("Multiline", "multiline"),
    ("Date", "date"),
    ("Time", "time"),
    ("Checkbox", "checkbox"),
    ("Radio", "radio"),
    ("Dropdown", "dropdown"),
    ("Signature", "signature"),
    ("Image", "image"),
    ("Table", "table"),
]


@dataclass
class TemplateContext:
    id: int | None = None
    version: int = 1
    name: str = ""
    category: str | None = None
    subcategory: str | None = None
    background_path: str | None = None
    page_count: int = 1


class MainWindow(QMainWindow):
    """Main workspace window providing a three-pane layout."""

    def __init__(self) -> None:
        super().__init__()
        self.setWindowTitle("Form Creator")
        self.resize(1400, 900)
        self.service = FormService()
        self.template = TemplateContext()
        self._field_id_counter = 1
        self._current_field_item: FieldItem | None = None
        self._updating_properties = False

        self._build_ui()
        self.new_template()

    # ------------------------------------------------------------------
    # UI construction
    # ------------------------------------------------------------------
    def _build_ui(self) -> None:
        self._create_actions()
        self._create_menus()
        self._create_toolbar()
        self.statusBar()

        splitter = QSplitter(Qt.Horizontal)
        self.setCentralWidget(splitter)

        self.palette_panel = self._build_palette_panel()
        splitter.addWidget(self.palette_panel)

        self.canvas = CanvasView()
        splitter.addWidget(self.canvas)

        self.properties_panel = self._build_properties_panel()
        splitter.addWidget(self.properties_panel)

        splitter.setSizes([220, 900, 280])

        self.canvas.fieldSelected.connect(self._on_field_selected)
        self.canvas.pageChanged.connect(self._on_canvas_page_changed)

        QShortcut(QKeySequence.Delete, self, activated=self._delete_selected)
        QShortcut(QKeySequence("Ctrl+D"), self, activated=self._duplicate_field)
        QShortcut(QKeySequence("Ctrl+0"), self, activated=self.canvas.fit_to_window)
        QShortcut(QKeySequence("Ctrl+;"), self, activated=self._toggle_snap_shortcut)

    def _create_actions(self) -> None:
        self.new_action = QAction("New Template", self)
        self.new_action.setShortcut(QKeySequence.New)
        self.new_action.triggered.connect(self.new_template)

        self.open_action = QAction("Open Template", self)
        self.open_action.setShortcut(QKeySequence.Open)
        self.open_action.triggered.connect(self.open_template)

        self.save_action = QAction("Save", self)
        self.save_action.setShortcut(QKeySequence.Save)
        self.save_action.triggered.connect(self.save_template)

        self.preview_action = QAction("Preview", self)
        self.preview_action.setShortcut(QKeySequence("Ctrl+P"))
        self.preview_action.triggered.connect(self.preview_template)

        self.export_action = QAction("Export PDF", self)
        self.export_action.setShortcut(QKeySequence("Ctrl+E"))
        self.export_action.triggered.connect(self.export_template_pdf)

        self.zoom_in_action = QAction("Zoom In", self)
        self.zoom_in_action.setShortcut(QKeySequence.ZoomIn)
        self.zoom_in_action.triggered.connect(self.canvas.zoom_in)

        self.zoom_out_action = QAction("Zoom Out", self)
        self.zoom_out_action.setShortcut(QKeySequence.ZoomOut)
        self.zoom_out_action.triggered.connect(self.canvas.zoom_out)

        self.zoom_fit_action = QAction("Fit", self)
        self.zoom_fit_action.setShortcut(QKeySequence("Ctrl+Shift+F"))
        self.zoom_fit_action.triggered.connect(self.canvas.fit_to_window)

        self.snap_action = QAction("Snap to Grid", self, checkable=True)
        self.snap_action.setChecked(True)
        self.snap_action.triggered.connect(self.canvas.toggle_snap)

        self.grid_action = QAction("Show Grid", self, checkable=True)
        self.grid_action.setChecked(True)
        self.grid_action.triggered.connect(self.canvas.toggle_grid)

        self.align_left_action = QAction("Align Left", self)
        self.align_left_action.setShortcut(QKeySequence("Ctrl+Alt+Left"))
        self.align_left_action.triggered.connect(lambda: self._align_selected("left"))

        self.align_right_action = QAction("Align Right", self)
        self.align_right_action.setShortcut(QKeySequence("Ctrl+Alt+Right"))
        self.align_right_action.triggered.connect(lambda: self._align_selected("right"))

        self.align_top_action = QAction("Align Top", self)
        self.align_top_action.setShortcut(QKeySequence("Ctrl+Alt+Up"))
        self.align_top_action.triggered.connect(lambda: self._align_selected("top"))

        self.align_bottom_action = QAction("Align Bottom", self)
        self.align_bottom_action.setShortcut(QKeySequence("Ctrl+Alt+Down"))
        self.align_bottom_action.triggered.connect(lambda: self._align_selected("bottom"))

        self.add_field_action = QAction("Add Field", self)
        self.add_field_action.setShortcut(QKeySequence("F"))
        self.add_field_action.triggered.connect(self._add_selected_field_type)

        self.template_library_action = QAction("Template Library", self)
        self.template_library_action.triggered.connect(self._show_template_library_placeholder)

        self.form_creator_action = QAction("Form Creator", self)
        self.form_creator_action.setEnabled(False)

    def _create_toolbar(self) -> None:
        toolbar = QToolBar("Tools", self)
        toolbar.addAction(self.new_action)
        toolbar.addAction(self.open_action)
        toolbar.addAction(self.save_action)
        toolbar.addSeparator()
        toolbar.addAction(self.preview_action)
        toolbar.addAction(self.export_action)
        toolbar.addSeparator()
        toolbar.addAction(self.zoom_out_action)
        toolbar.addAction(self.zoom_in_action)
        toolbar.addAction(self.zoom_fit_action)
        toolbar.addSeparator()
        toolbar.addAction(self.snap_action)
        toolbar.addAction(self.grid_action)
        toolbar.addSeparator()
        toolbar.addAction(self.align_left_action)
        toolbar.addAction(self.align_right_action)
        toolbar.addAction(self.align_top_action)
        toolbar.addAction(self.align_bottom_action)
        self.addToolBar(toolbar)

    def _create_menus(self) -> None:
        reference_menu = self.menuBar().addMenu("Reference Library")
        forms_menu = reference_menu.addMenu("Forms")
        forms_menu.addAction(self.template_library_action)
        forms_menu.addAction(self.form_creator_action)

    def _build_palette_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        self.template_name_edit = QLineEdit()
        self.category_edit = QLineEdit()
        self.subcategory_edit = QLineEdit()
        self.page_selector = QSpinBox()
        self.page_selector.setRange(1, 1)
        self.page_selector.valueChanged.connect(self._on_page_selected)

        form = QFormLayout()
        form.addRow("Name", self.template_name_edit)
        form.addRow("Category", self.category_edit)
        form.addRow("Subcategory", self.subcategory_edit)
        form.addRow("Page", self.page_selector)
        layout.addLayout(form)

        layout.addWidget(QLabel("Field Palette"))
        self.field_list = QListWidget()
        for label, field_type in FIELD_TYPES:
            item = QListWidgetItem(label)
            item.setData(Qt.UserRole, field_type)
            self.field_list.addItem(item)
        self.field_list.itemDoubleClicked.connect(lambda _: self._add_selected_field_type())
        layout.addWidget(self.field_list)

        add_button = QPushButton("Add Field")
        add_button.clicked.connect(self._add_selected_field_type)
        layout.addWidget(add_button)
        layout.addStretch(1)
        return widget

    def _build_properties_panel(self) -> QWidget:
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(6, 6, 6, 6)

        form = QFormLayout()
        self.prop_name_edit = QLineEdit()
        self.prop_name_edit.textChanged.connect(lambda _: self._update_current_field("name", self.prop_name_edit.text()))

        self.prop_type_combo = QComboBox()
        self.prop_type_combo.addItems([label for label, _ in FIELD_TYPES])
        self.prop_type_combo.setEnabled(False)

        self.prop_page_spin = QSpinBox()
        self.prop_page_spin.setRange(1, 1)
        self.prop_page_spin.valueChanged.connect(lambda value: self._update_current_field("page", value))

        self.prop_x_spin = QSpinBox()
        self.prop_x_spin.setRange(0, 10000)
        self.prop_x_spin.valueChanged.connect(lambda value: self._update_current_geometry("x", value))

        self.prop_y_spin = QSpinBox()
        self.prop_y_spin.setRange(0, 10000)
        self.prop_y_spin.valueChanged.connect(lambda value: self._update_current_geometry("y", value))

        self.prop_width_spin = QSpinBox()
        self.prop_width_spin.setRange(10, 3000)
        self.prop_width_spin.valueChanged.connect(lambda value: self._update_current_geometry("width", value))

        self.prop_height_spin = QSpinBox()
        self.prop_height_spin.setRange(10, 3000)
        self.prop_height_spin.valueChanged.connect(lambda value: self._update_current_geometry("height", value))

        self.prop_font_family_edit = QLineEdit()
        self.prop_font_family_edit.textChanged.connect(lambda _: self._update_current_field("font_family", self.prop_font_family_edit.text()))

        self.prop_font_size_spin = QSpinBox()
        self.prop_font_size_spin.setRange(6, 72)
        self.prop_font_size_spin.setValue(10)
        self.prop_font_size_spin.valueChanged.connect(lambda value: self._update_current_field("font_size", value))

        self.prop_align_combo = QComboBox()
        self.prop_align_combo.addItems(["left", "center", "right"])
        self.prop_align_combo.currentTextChanged.connect(lambda text: self._update_current_field("align", text))

        self.prop_default_edit = QLineEdit()
        self.prop_default_edit.textChanged.connect(lambda _: self._update_current_field("default_value", self.prop_default_edit.text()))

        self.prop_required_checkbox = QCheckBox("Required")
        self.prop_required_checkbox.toggled.connect(lambda state: self._update_current_field("required", state))

        self.prop_placeholder_edit = QLineEdit()
        self.prop_placeholder_edit.textChanged.connect(lambda _: self._update_current_field("placeholder", self.prop_placeholder_edit.text()))

        self.prop_mask_edit = QLineEdit()
        self.prop_mask_edit.textChanged.connect(lambda _: self._update_current_field("mask", self.prop_mask_edit.text()))

        form.addRow("Name", self.prop_name_edit)
        form.addRow("Type", self.prop_type_combo)
        form.addRow("Page", self.prop_page_spin)
        form.addRow("X", self.prop_x_spin)
        form.addRow("Y", self.prop_y_spin)
        form.addRow("Width", self.prop_width_spin)
        form.addRow("Height", self.prop_height_spin)
        form.addRow("Font", self.prop_font_family_edit)
        form.addRow("Font Size", self.prop_font_size_spin)
        form.addRow("Align", self.prop_align_combo)
        form.addRow("Default", self.prop_default_edit)
        form.addRow("Placeholder", self.prop_placeholder_edit)
        form.addRow("Input Mask", self.prop_mask_edit)
        form.addRow(self.prop_required_checkbox)

        layout.addLayout(form)

        binding_button = QPushButton("Bindings…")
        binding_button.clicked.connect(self._open_binding_dialog)
        validation_button = QPushButton("Validation…")
        validation_button.clicked.connect(self._open_validation_dialog)
        table_button = QPushButton("Table Setup…")
        table_button.clicked.connect(self._open_table_dialog)

        layout.addWidget(binding_button)
        layout.addWidget(validation_button)
        layout.addWidget(table_button)
        layout.addStretch(1)
        return widget

    # ------------------------------------------------------------------
    # Action handlers
    # ------------------------------------------------------------------
    def new_template(self) -> None:
        wizard = NewTemplateWizard(self)
        if wizard.exec() != QDialog.Accepted or not wizard.result:
            return
        data = wizard.result
        self.template = TemplateContext(
            id=None,
            version=1,
            name=str(data["name"]),
            category=data["category"],
            subcategory=data["subcategory"],
            background_path=str(data["background_path"]),
            page_count=int(data["page_count"]),
        )
        self.template_name_edit.setText(self.template.name)
        self.category_edit.setText(self.template.category or "")
        self.subcategory_edit.setText(self.template.subcategory or "")
        self.page_selector.setMaximum(max(1, self.template.page_count))
        self.prop_page_spin.setMaximum(max(1, self.template.page_count))
        backgrounds = self._background_pixmaps()
        self.canvas.set_backgrounds(backgrounds)
        self.canvas.clear_fields()
        self._field_id_counter = 1
        self.statusBar().showMessage("Template imported. Place fields and press Save.", 5000)

    def open_template(self) -> None:
        templates = self.service.list_templates()
        if not templates:
            QMessageBox.information(self, "No templates", "There are no saved templates yet.")
            return
        items = [f"#{row['id']} — {row['name']} (v{row['version']})" for row in templates]
        item, ok = QInputDialog.getItem(self, "Open Template", "Select template", items, editable=False)
        if not ok:
            return
        selected_index = items.index(item)
        record = templates[selected_index]
        template = self.service.get_template(int(record["id"]))
        self.template = TemplateContext(
            id=int(template["id"]),
            version=int(template["version"]),
            name=template["name"],
            category=template.get("category"),
            subcategory=template.get("subcategory"),
            background_path=template.get("background_path"),
            page_count=int(template.get("page_count", 1)),
        )
        self.template_name_edit.setText(self.template.name)
        self.category_edit.setText(self.template.category or "")
        self.subcategory_edit.setText(self.template.subcategory or "")
        self.page_selector.setMaximum(max(1, self.template.page_count))
        self.prop_page_spin.setMaximum(max(1, self.template.page_count))
        backgrounds = self._background_pixmaps()
        self.canvas.set_backgrounds(backgrounds)
        self.canvas.set_fields(template.get("fields", []))
        self._field_id_counter = max((int(field.get("id", 0)) for field in template.get("fields", []) if field.get("id")), default=0) + 1
        self.statusBar().showMessage(f"Loaded template #{self.template.id}", 5000)

    def save_template(self) -> None:
        if not self.template.background_path:
            QMessageBox.warning(self, "Missing background", "Import a template background first.")
            return
        name = self.template_name_edit.text().strip()
        if not name:
            QMessageBox.warning(self, "Missing name", "Template name cannot be empty.")
            return
        fields = self.canvas.fields_as_dict()
        for field in fields:
            field.setdefault("config", {})
            field["config"].setdefault("bindings", [])
            field["config"].setdefault("validations", [])
            field["config"].setdefault("dropdown", None)
            field["config"].setdefault("table", None)
        template_id = self.service.save_template(
            name=name,
            category=self.category_edit.text().strip() or None,
            subcategory=self.subcategory_edit.text().strip() or None,
            background_path=self.template.background_path,
            page_count=self.template.page_count,
            fields=fields,
            template_id=self.template.id,
        )
        self.template.id = template_id
        saved = self.service.get_template(template_id)
        self.template.version = int(saved.get("version", self.template.version))
        self.statusBar().showMessage("Template saved", 3000)

    def preview_template(self) -> None:
        backgrounds = self._background_paths()
        if not backgrounds:
            QMessageBox.warning(self, "No background", "Import or open a template before previewing.")
            return
        fields = self.canvas.fields_as_dict()
        dialog = PreviewDialog(backgrounds, fields, parent=self)
        dialog.exec()

    def export_template_pdf(self) -> None:
        backgrounds = self._background_paths()
        if not backgrounds:
            QMessageBox.warning(self, "No background", "Import or open a template before exporting.")
            return
        filename, _ = QFileDialog.getSaveFileName(self, "Export PDF", filter="PDF Files (*.pdf)")
        if not filename:
            return
        values = {int(field.get("id", index)): field.get("default_value", "") for index, field in enumerate(self.canvas.fields_as_dict(), start=1)}
        try:
            self.service.exporter.export(
                background_paths=backgrounds,
                fields=self.canvas.fields_as_dict(),
                values=values,
                output_path=Path(filename),
            )
        except Exception as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "Export failed", str(exc))
            return
        self.statusBar().showMessage(f"Exported PDF to {filename}", 5000)

    def _show_template_library_placeholder(self) -> None:
        QMessageBox.information(
            self,
            "Template Library",
            "The Template Library UI is handled elsewhere in the application."
        )

    # ------------------------------------------------------------------
    # Field helpers
    # ------------------------------------------------------------------
    def _add_selected_field_type(self) -> None:
        current_item = self.field_list.currentItem()
        if not current_item:
            current_item = self.field_list.item(0)
        if not current_item:
            return
        field_type = current_item.data(Qt.UserRole)
        field_data = self._create_field_data(field_type)
        item = self.canvas.add_field(field_data)
        item.setSelected(True)
        self._on_field_selected(item)

    def _create_field_data(self, field_type: str) -> Dict[str, Any]:
        field_id = self._field_id_counter
        self._field_id_counter += 1
        return {
            "id": field_id,
            "page": self.page_selector.value(),
            "name": f"{field_type}_{field_id}",
            "type": field_type,
            "x": 100.0,
            "y": 120.0,
            "width": 160.0,
            "height": 32.0,
            "font_family": "",
            "font_size": 10,
            "align": "left",
            "required": False,
            "placeholder": "",
            "mask": "",
            "default_value": "",
            "config": {"bindings": [], "validations": [], "dropdown": None, "table": None},
        }

    def _delete_selected(self) -> None:
        removed = self.canvas.delete_selected_fields()
        if removed:
            self.statusBar().showMessage(f"Deleted {len(removed)} field(s)", 3000)

    def _duplicate_field(self) -> None:
        item = self.canvas.selected_field()
        if not item:
            return
        data = item.to_field_dict().copy()
        data["id"] = self._field_id_counter
        self._field_id_counter += 1
        data["x"] = float(data.get("x", 0)) + 24
        data["y"] = float(data.get("y", 0)) + 24
        new_item = self.canvas.add_field(data)
        new_item.setSelected(True)
        self.statusBar().showMessage("Field duplicated", 2000)

    def _align_selected(self, mode: str) -> None:
        selected_items = [item for item in self.canvas.scene().selectedItems() if isinstance(item, FieldItem)]
        if len(selected_items) < 2:
            return
        reference = selected_items[0]
        for item in selected_items[1:]:
            pos = item.pos()
            rect = item.rect()
            ref_pos = reference.pos()
            ref_rect = reference.rect()
            if mode == "left":
                item.setPos(ref_pos.x(), pos.y())
            elif mode == "right":
                item.setPos(ref_pos.x() + ref_rect.width() - rect.width(), pos.y())
            elif mode == "top":
                item.setPos(pos.x(), ref_pos.y())
            elif mode == "bottom":
                item.setPos(pos.x(), ref_pos.y() + ref_rect.height() - rect.height())
            item.to_field_dict()
        self.statusBar().showMessage("Fields aligned", 2000)

    # ------------------------------------------------------------------
    # Property handling
    # ------------------------------------------------------------------
    def _on_field_selected(self, item: FieldItem | None) -> None:
        self._current_field_item = item
        self._updating_properties = True
        try:
            if not item:
                for widget in [
                    self.prop_name_edit,
                    self.prop_font_family_edit,
                    self.prop_default_edit,
                    self.prop_placeholder_edit,
                    self.prop_mask_edit,
                ]:
                    widget.clear()
                self.prop_required_checkbox.setChecked(False)
                return
            field = item.field
            self.prop_name_edit.setText(field.get("name", ""))
            index = next((i for i, (_, ftype) in enumerate(FIELD_TYPES) if ftype == field.get("type")), 0)
            self.prop_type_combo.setCurrentIndex(index)
            self.prop_page_spin.setValue(int(field.get("page", 1)))
            self.prop_x_spin.setValue(int(field.get("x", 0)))
            self.prop_y_spin.setValue(int(field.get("y", 0)))
            self.prop_width_spin.setValue(int(field.get("width", 0)))
            self.prop_height_spin.setValue(int(field.get("height", 0)))
            self.prop_font_family_edit.setText(field.get("font_family", ""))
            self.prop_font_size_spin.setValue(int(field.get("font_size", 10)))
            align_index = self.prop_align_combo.findText(field.get("align", "left"))
            self.prop_align_combo.setCurrentIndex(max(0, align_index))
            self.prop_default_edit.setText(field.get("default_value", ""))
            self.prop_placeholder_edit.setText(field.get("placeholder", ""))
            self.prop_mask_edit.setText(field.get("mask", ""))
            self.prop_required_checkbox.setChecked(bool(field.get("required")))
        finally:
            self._updating_properties = False

    def _update_current_field(self, key: str, value: Any) -> None:
        if self._updating_properties or not self._current_field_item:
            return
        field = self._current_field_item.field
        field[key] = value
        self._current_field_item.to_field_dict()
        if key == "page":
            self._current_field_item.setVisible(int(value) - 1 == self.page_selector.value() - 1)

    def _update_current_geometry(self, key: str, value: int) -> None:
        if self._updating_properties or not self._current_field_item:
            return
        if key in {"x", "y"}:
            pos = self._current_field_item.pos()
            if key == "x":
                self._current_field_item.setPos(float(value), pos.y())
            else:
                self._current_field_item.setPos(pos.x(), float(value))
        else:
            rect = self._current_field_item.rect()
            if key == "width":
                rect.setWidth(float(value))
            else:
                rect.setHeight(float(value))
            self._current_field_item.setRect(rect)
        self._current_field_item.to_field_dict()

    def _open_binding_dialog(self) -> None:
        if not self._current_field_item:
            return
        config = self._current_field_item.field.setdefault("config", {})
        current_bindings = config.get("bindings", [])
        dialog = BindingDialog(self.service.binder, current_bindings, self)
        if dialog.exec() == QDialog.Accepted:
            config["bindings"] = dialog.bindings

    def _open_validation_dialog(self) -> None:
        if not self._current_field_item:
            return
        config = self._current_field_item.field.setdefault("config", {})
        current_rules = config.get("validations", [])
        dialog = ValidationDialog(current_rules, self)
        if dialog.exec() == QDialog.Accepted:
            config["validations"] = dialog.rules
            self._current_field_item.field["required"] = any(rule.get("rule_type") == "required" for rule in dialog.rules)
            self.prop_required_checkbox.setChecked(self._current_field_item.field["required"])

    def _open_table_dialog(self) -> None:
        if not self._current_field_item:
            return
        config = self._current_field_item.field.setdefault("config", {})
        dialog = TableEditorDialog(config.get("table"), self)
        if dialog.exec() == QDialog.Accepted:
            config["table"] = dialog.table_config

    # ------------------------------------------------------------------
    # Page handling
    # ------------------------------------------------------------------
    def _on_page_selected(self, page: int) -> None:
        self.canvas.set_page(page - 1)

    def _on_canvas_page_changed(self, page: int) -> None:
        if self.page_selector.value() != page:
            self.page_selector.blockSignals(True)
            self.page_selector.setValue(page)
            self.page_selector.blockSignals(False)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _background_folder(self) -> Path | None:
        if not self.template.background_path:
            return None
        path = Path(self.template.background_path)
        if not path.is_absolute():
            path = db.DATA_DIR / path
        return path

    def _background_paths(self) -> list[Path]:
        folder = self._background_folder()
        if not folder:
            return []
        return [folder / f"background_page_{index:03d}.png" for index in range(1, self.template.page_count + 1)]

    def _background_pixmaps(self) -> list[QPixmap]:
        return [QPixmap(str(path)) for path in self._background_paths()]

    def _toggle_snap_shortcut(self) -> None:
        self.snap_action.setChecked(not self.snap_action.isChecked())
        self.canvas.toggle_snap(self.snap_action.isChecked())

    # ------------------------------------------------------------------
    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        event.accept()


__all__ = ["MainWindow"]

