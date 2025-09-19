"""Main window for the SARApp form creator workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QFormLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QPushButton,
    QSplitter,
    QSpinBox,
    QDoubleSpinBox,
    QToolBar,
    QVBoxLayout,
    QWidget,
)

from ..assets import get_asset_path
from ..services.templates import FormService
from .CanvasView import CanvasView
from .FieldItems import CheckboxFieldItem, DropdownFieldItem, FieldItem, TextFieldItem
from .dialogs.BindingDialog import BindingDialog
from .dialogs.NewTemplateWizard import NewTemplateWizard
from .dialogs.PreviewDialog import PreviewDialog
from .dialogs.ValidationDialog import ValidationDialog


FIELD_CLASSES = {
    "text": TextFieldItem,
    "multiline": TextFieldItem,
    "date": TextFieldItem,
    "time": TextFieldItem,
    "checkbox": CheckboxFieldItem,
    "radio": CheckboxFieldItem,
    "dropdown": DropdownFieldItem,
    "signature": FieldItem,
    "image": FieldItem,
    "table": FieldItem,
}


class MainWindow(QMainWindow):
    """Three-pane designer workspace."""

    def __init__(self, form_service: FormService | None = None, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Form Creator")
        self.resize(1280, 720)
        self.form_service = form_service or FormService()
        self.current_template: dict[str, Any] | None = None
        self.background_item = None
        self.current_field_item: FieldItem | None = None
        self.next_field_id = 1

        self._build_menu()
        self._build_central_widget()
        self._build_toolbar()
        self.statusBar().showMessage("Ready")

    # ------------------------------------------------------------------
    def _build_menu(self) -> None:
        menu_reference = self.menuBar().addMenu("Reference Library")
        forms_menu = menu_reference.addMenu("Forms")

        action_template_library = QAction("Template Library", self)
        action_template_library.triggered.connect(self.open_template)
        forms_menu.addAction(action_template_library)

        action_form_creator = QAction("Form Creator", self)
        action_form_creator.setEnabled(False)
        forms_menu.addAction(action_form_creator)

    def _build_toolbar(self) -> None:
        toolbar = QToolBar("Main", self)
        toolbar.setMovable(False)
        self.addToolBar(toolbar)

        toolbar.addAction(self._make_toolbar_action("New", "new.svg", self.new_template))
        toolbar.addAction(self._make_toolbar_action("Open", "open.svg", self.open_template))
        toolbar.addAction(self._make_toolbar_action("Save", "save.svg", self.save_template))
        toolbar.addAction(self._make_toolbar_action("Preview", "preview.svg", self.preview_template))
        toolbar.addAction(self._make_toolbar_action("Export", "export.svg", self.export_current_instance))

        toolbar.addSeparator()

        toolbar.addAction(
            self._make_toolbar_action("Zoom +", "zoom_in.svg", lambda: self.canvas._apply_zoom(1.2))
        )
        toolbar.addAction(
            self._make_toolbar_action("Zoom -", "zoom_out.svg", lambda: self.canvas._apply_zoom(0.8))
        )
        toolbar.addAction(self._make_toolbar_action("Reset Zoom", "zoom_reset.svg", self.canvas.reset_zoom))

    def _build_central_widget(self) -> None:
        splitter = QSplitter(Qt.Orientation.Horizontal, self)

        # Palette
        palette_container = QWidget()
        palette_layout = QVBoxLayout()
        palette_container.setLayout(palette_layout)
        palette_layout.addWidget(QLabel("Field Palette"))
        self.palette_list = QListWidget()
        for key in FIELD_CLASSES.keys():
            item = QListWidgetItem(key.title())
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.palette_list.addItem(item)
        self.palette_list.itemDoubleClicked.connect(self._handle_palette_double_click)
        palette_layout.addWidget(self.palette_list)
        splitter.addWidget(palette_container)

        # Canvas
        self.canvas = CanvasView()
        self.scene = self.canvas.scene()
        self.scene.selectionChanged.connect(self._on_selection_changed)
        splitter.addWidget(self.canvas)

        # Properties panel
        properties_container = QWidget()
        self.properties_layout = QFormLayout()
        properties_container.setLayout(self.properties_layout)
        self._build_properties_panel()
        splitter.addWidget(properties_container)

        splitter.setSizes([200, 800, 280])
        self.setCentralWidget(splitter)

    def _build_properties_panel(self) -> None:
        self.field_name_edit = QLineEdit()
        self.field_name_edit.editingFinished.connect(self._apply_properties_changes)
        self.properties_layout.addRow("Name", self.field_name_edit)

        self.field_type_edit = QLineEdit()
        self.field_type_edit.setReadOnly(True)
        self.properties_layout.addRow("Type", self.field_type_edit)

        self.field_x_spin = QDoubleSpinBox()
        self.field_x_spin.setRange(0, 10000)
        self.field_x_spin.valueChanged.connect(self._apply_properties_changes)
        self.properties_layout.addRow("X", self.field_x_spin)

        self.field_y_spin = QDoubleSpinBox()
        self.field_y_spin.setRange(0, 10000)
        self.field_y_spin.valueChanged.connect(self._apply_properties_changes)
        self.properties_layout.addRow("Y", self.field_y_spin)

        self.field_w_spin = QDoubleSpinBox()
        self.field_w_spin.setRange(0, 10000)
        self.field_w_spin.valueChanged.connect(self._apply_properties_changes)
        self.properties_layout.addRow("Width", self.field_w_spin)

        self.field_h_spin = QDoubleSpinBox()
        self.field_h_spin.setRange(0, 10000)
        self.field_h_spin.valueChanged.connect(self._apply_properties_changes)
        self.properties_layout.addRow("Height", self.field_h_spin)

        self.font_size_spin = QSpinBox()
        self.font_size_spin.setRange(6, 72)
        self.font_size_spin.valueChanged.connect(self._apply_properties_changes)
        self.properties_layout.addRow("Font Size", self.font_size_spin)

        self.binding_button = QPushButton("Bindings...")
        self.binding_button.clicked.connect(self._open_binding_dialog)
        self.binding_button.setEnabled(False)
        self.properties_layout.addRow(self.binding_button)

        self.validation_button = QPushButton("Validations...")
        self.validation_button.clicked.connect(self._open_validation_dialog)
        self.validation_button.setEnabled(False)
        self.properties_layout.addRow(self.validation_button)

        self.properties_layout.addRow(QLabel(""))

    # ------------------------------------------------------------------
    def _make_toolbar_action(self, text: str, icon_name: str, slot: Callable[[], None]) -> QAction:
        """Create a toolbar action with a themed icon if available."""

        icon_path = get_asset_path(icon_name)
        icon = QIcon(str(icon_path)) if icon_path.exists() else QIcon()
        action = QAction(icon, text, self)
        action.triggered.connect(slot)
        return action

    # ------------------------------------------------------------------
    def new_template(self) -> None:
        wizard = NewTemplateWizard(self.form_service, self)
        if wizard.exec() == wizard.DialogCode.Accepted:
            template_id = wizard.created_template_id
            if template_id:
                self.load_template(template_id)
                self.statusBar().showMessage("Template created", 5000)

    def open_template(self) -> None:
        templates = self.form_service.list_templates()
        if not templates:
            QMessageBox.information(self, "Templates", "No templates available yet.")
            return
        items = [f"{t['id']}: {t['name']} v{t['version']}" for t in templates]
        from PySide6.QtWidgets import QInputDialog

        selected, ok = QInputDialog.getItem(self, "Open Template", "Template", items, 0, False)
        if ok and selected:
            template_id = int(selected.split(":", 1)[0])
            self.load_template(template_id)

    def load_template(self, template_id: int) -> None:
        template = self.form_service.get_template(template_id)
        self.current_template = template
        self.next_field_id = max((f.get("id", 0) for f in template.get("fields", [])), default=0) + 1
        self.scene.clear()
        self.background_item = None
        self.canvas.reset_zoom()
        self._load_background(template)
        for field in template.get("fields", []):
            self._add_field_item(field)
        self.statusBar().showMessage(f"Loaded template {template['name']} v{template['version']}", 5000)

    def save_template(self) -> None:
        if not self.current_template:
            QMessageBox.warning(self, "Save Template", "No template is currently loaded.")
            return
        fields = self.current_template.get("fields", [])
        template_id = self.current_template.get("id")
        self.form_service.save_template(
            name=self.current_template.get("name", "Untitled"),
            category=self.current_template.get("category"),
            subcategory=self.current_template.get("subcategory"),
            background_path=self.current_template.get("background_path"),
            page_count=self.current_template.get("page_count", 1),
            fields=fields,
            template_id=template_id,
        )
        self.load_template(template_id)
        self.statusBar().showMessage("Template saved", 3000)

    def preview_template(self) -> None:
        if not self.current_template:
            QMessageBox.information(self, "Preview", "Load a template first.")
            return
        dialog = PreviewDialog(self.current_template, parent=self)
        dialog.exec()

    def export_current_instance(self) -> None:
        if not self.current_template:
            QMessageBox.warning(self, "Export", "Load a template first.")
            return
        path, _ = QFileDialog.getSaveFileName(self, "Export Template PDF", "", "PDF Files (*.pdf)")
        if not path:
            return
        temp_values = {field.get("id"): field.get("default_value") for field in self.current_template.get("fields", [])}
        export_template = dict(self.current_template)
        self.form_service.exporter.export_instance(export_template, temp_values, Path(path))
        self.statusBar().showMessage(f"Exported preview to {path}", 5000)

    # ------------------------------------------------------------------
    def _handle_palette_double_click(self, item: QListWidgetItem) -> None:
        field_type = item.data(Qt.ItemDataRole.UserRole)
        if not self.current_template:
            QMessageBox.warning(self, "Add Field", "Create or open a template first.")
            return
        field = {
            "id": self.next_field_id,
            "page": 1,
            "name": f"field_{self.next_field_id}",
            "type": field_type,
            "x": 50.0,
            "y": 50.0,
            "width": 150.0,
            "height": 24.0,
            "font_family": "",
            "font_size": 10,
            "align": "left",
            "required": False,
            "placeholder": "",
            "mask": "",
            "default_value": "",
            "config": {"bindings": [], "validations": [], "dropdown": None, "table": None},
        }
        self.next_field_id += 1
        self.current_template.setdefault("fields", []).append(field)
        self._add_field_item(field)

    def _add_field_item(self, field: dict[str, Any]) -> None:
        cls = FIELD_CLASSES.get(field.get("type"), FieldItem)
        item = cls(field)
        self.scene.addItem(item)
        item.setZValue(5)

    def _on_selection_changed(self) -> None:
        items = self.scene.selectedItems()
        self.current_field_item = items[0] if items else None
        if self.current_field_item is None:
            self._clear_properties()
            return
        field = self.current_field_item.field
        self.field_name_edit.setText(field.get("name", ""))
        self.field_type_edit.setText(field.get("type", ""))
        self.field_x_spin.blockSignals(True)
        self.field_y_spin.blockSignals(True)
        self.field_w_spin.blockSignals(True)
        self.field_h_spin.blockSignals(True)
        self.font_size_spin.blockSignals(True)
        self.field_x_spin.setValue(float(field.get("x", 0)))
        self.field_y_spin.setValue(float(field.get("y", 0)))
        self.field_w_spin.setValue(float(field.get("width", 0)))
        self.field_h_spin.setValue(float(field.get("height", 0)))
        self.font_size_spin.setValue(int(field.get("font_size", 10)))
        self.field_x_spin.blockSignals(False)
        self.field_y_spin.blockSignals(False)
        self.field_w_spin.blockSignals(False)
        self.field_h_spin.blockSignals(False)
        self.font_size_spin.blockSignals(False)
        self.binding_button.setEnabled(True)
        self.validation_button.setEnabled(True)

    def _clear_properties(self) -> None:
        self.field_name_edit.clear()
        self.field_type_edit.clear()
        self.field_x_spin.setValue(0)
        self.field_y_spin.setValue(0)
        self.field_w_spin.setValue(0)
        self.field_h_spin.setValue(0)
        self.font_size_spin.setValue(10)
        self.binding_button.setEnabled(False)
        self.validation_button.setEnabled(False)

    def _apply_properties_changes(self) -> None:
        if not self.current_field_item:
            return
        field = self.current_field_item.field
        field["name"] = self.field_name_edit.text()
        field["x"] = self.field_x_spin.value()
        field["y"] = self.field_y_spin.value()
        field["width"] = self.field_w_spin.value()
        field["height"] = self.field_h_spin.value()
        field["font_size"] = self.font_size_spin.value()
        self.current_field_item.setPos(field["x"], field["y"])
        self.current_field_item.setRect(0, 0, field["width"], field["height"])

    def _open_binding_dialog(self) -> None:
        if not self.current_field_item:
            return
        field = self.current_field_item.field
        dialog = BindingDialog(field.get("config", {}), self.form_service.binder, self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            field.setdefault("config", {})["bindings"] = dialog.bindings

    def _open_validation_dialog(self) -> None:
        if not self.current_field_item:
            return
        field = self.current_field_item.field
        dialog = ValidationDialog(field.get("config", {}), self)
        if dialog.exec() == dialog.DialogCode.Accepted:
            field.setdefault("config", {})["validations"] = dialog.validations

    def _load_background(self, template: dict[str, Any]) -> None:
        background_path = Path(template.get("background_path", ""))
        if not background_path.is_absolute():
            background_path = self.form_service.data_dir / background_path
        image_path = background_path / "background_page_001.png"
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            return
        self.background_item = self.scene.addPixmap(pixmap)
        self.background_item.setZValue(-10)
        self.background_item.setEnabled(False)
        self.scene.setSceneRect(0, 0, pixmap.width(), pixmap.height())


if __name__ == "__main__":  # pragma: no cover - manual smoke test helper
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
