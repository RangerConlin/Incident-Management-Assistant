"""Main window for the SARApp form creator workspace."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import Qt, QRectF, Signal
from PySide6.QtGui import QAction, QIcon, QKeySequence, QPixmap, QShortcut
from PySide6.QtWidgets import (
    QAbstractItemView,
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
from .PreviewWidget import TemplatePreview
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


class FieldListWidget(QListWidget):
    """List widget that emits the new order when items are moved."""

    orderChanged = Signal(list)

    def dropEvent(self, event):  # noqa: D401,N802 - Qt override
        super().dropEvent(event)
        ordered_ids: list[int] = []
        for row in range(self.count()):
            item = self.item(row)
            field_id = item.data(Qt.ItemDataRole.UserRole)
            try:
                ordered_ids.append(int(field_id))
            except (TypeError, ValueError):
                continue
        self.orderChanged.emit(ordered_ids)


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
        self.active_field_type: str | None = None
        self.field_items: dict[int, FieldItem] = {}
        self.field_list_items: dict[int, QListWidgetItem] = {}
        self.field_list: QListWidget | None = None
        self._syncing_field_list = False

        self._build_menu()
        self._build_central_widget()
        self._build_toolbar()
        self.statusBar().showMessage("Ready")

        QShortcut(QKeySequence(Qt.Key.Key_Delete), self, activated=self.delete_selected_field)
        QShortcut(QKeySequence(Qt.Key.Key_Backspace), self, activated=self.delete_selected_field)

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
        self.palette_list.setEnabled(False)
        for key in FIELD_CLASSES.keys():
            item = QListWidgetItem(key.title())
            item.setData(Qt.ItemDataRole.UserRole, key)
            self.palette_list.addItem(item)
        self.palette_list.itemDoubleClicked.connect(self._handle_palette_double_click)
        self.palette_list.currentItemChanged.connect(self._handle_palette_selection)
        palette_layout.addWidget(self.palette_list)

        palette_layout.addWidget(QLabel("Fields"))
        self.field_list = FieldListWidget()
        self.field_list.setEnabled(False)
        self.field_list.currentItemChanged.connect(self._handle_field_list_selection)
        self.field_list.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.field_list.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.field_list.orderChanged.connect(self._on_field_order_changed)
        palette_layout.addWidget(self.field_list)

        self.delete_field_button = QPushButton("Delete Field")
        self.delete_field_button.setEnabled(False)
        self.delete_field_button.clicked.connect(self.delete_selected_field)
        palette_layout.addWidget(self.delete_field_button)

        self.preview_widget = TemplatePreview()
        self.preview_widget.fieldClicked.connect(self._handle_preview_click)
        palette_layout.addWidget(self.preview_widget)

        splitter.addWidget(palette_container)

        # Canvas
        self.canvas = CanvasView()
        self.canvas.fieldDrawn.connect(self._on_canvas_field_drawn)
        self.canvas.fieldCreationAborted.connect(self._on_canvas_field_aborted)
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
        def _coerce_field_id(value: Any) -> int:
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
        self.next_field_id = max((
            _coerce_field_id(f.get("id")) for f in template.get("fields", [])
        ), default=0) + 1
        self._reset_palette_tool()
        self.scene.clear()
        self.field_items.clear()
        self.field_list_items.clear()
        if self.field_list is not None:
            self.field_list.blockSignals(True)
            self.field_list.clear()
            self.field_list.blockSignals(False)
            self.field_list.setEnabled(True)
        self.background_item = None
        self.canvas.reset_zoom()
        self._load_background(template)
        self.preview_widget.set_template(template, self.form_service.data_dir)
        for field in template.get("fields", []):
            self._add_field_item(field)
        self._refresh_field_list()
        self.palette_list.setEnabled(True)
        if self.field_list is not None:
            self.field_list.setEnabled(True)
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
        highlight_id = None
        if self.current_field_item is not None:
            highlight_id = self._safe_int(self.current_field_item.field.get("id"))
        dialog = PreviewDialog(
            self.current_template,
            parent=self,
            highlight_field_id=highlight_id,
        )
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
        self._create_field_from_rect(field_type, QRectF(50.0, 50.0, 150.0, 24.0), select=True)
        self._reset_palette_tool()

    def _handle_palette_selection(self, current: QListWidgetItem | None, previous: QListWidgetItem | None) -> None:
        if current is None:
            if previous is not None:
                self._reset_palette_tool()
            return
        if not self.current_template:
            self.statusBar().showMessage("Open or create a template before adding fields.", 5000)
            self._reset_palette_tool()
            return
        field_type = current.data(Qt.ItemDataRole.UserRole)
        if not field_type:
            return
        self.active_field_type = str(field_type)
        self.canvas.begin_field_creation(self.active_field_type)
        self.statusBar().showMessage(
            f"Click and drag on the canvas to draw a {current.text()} field.", 5000
        )

    def _handle_field_list_selection(
        self, current: QListWidgetItem | None, previous: QListWidgetItem | None
    ) -> None:
        """Sync canvas selection when a field is chosen from the list."""
        if self._syncing_field_list:
            return
        if current is None:
            self._update_delete_button_state()
            return
        field_id = current.data(Qt.ItemDataRole.UserRole)
        try:
            field_key = int(field_id)
        except (TypeError, ValueError):
            return
        field_item = self.field_items.get(field_key)
        if not field_item:
            self._update_delete_button_state()
            return
        self.scene.clearSelection()
        field_item.setSelected(True)
        self.canvas.centerOn(field_item)
        self._update_delete_button_state()

    def _refresh_field_list(self) -> None:
        """Populate the field list widget to match the template fields."""
        if self.field_list is None:
            return
        self.field_list_items.clear()
        self.field_list.blockSignals(True)
        self.field_list.clear()
        if not self.current_template:
            self.field_list.blockSignals(False)
            self.preview_widget.clear()
            return
        fields = list(self.current_template.get("fields", []))
        for field in fields:
            field_id = field.get("id")
            try:
                field_key = int(field_id)
            except (TypeError, ValueError):
                continue
            item = QListWidgetItem(self._format_field_list_label(field))
            item.setData(Qt.ItemDataRole.UserRole, field_key)
            self.field_list.addItem(item)
            self.field_list_items[field_key] = item
        self.field_list.blockSignals(False)
        self.preview_widget.update_fields(fields)
        self._update_delete_button_state()

    def _format_field_list_label(self, field: dict[str, Any]) -> str:
        """Return the human readable label for a field entry."""
        name = field.get("name") or f"Field {field.get('id')}"
        field_type = str(field.get("type") or "unknown").title()
        page = field.get("page", 1)
        return f"{name} • {field_type} (p{page})"

    def _get_field_by_id(self, field_id: int) -> dict[str, Any] | None:
        """Locate a field dictionary by its identifier."""
        if not self.current_template:
            return None
        for field in self.current_template.get("fields", []):
            try:
                candidate = int(field.get("id"))
            except (TypeError, ValueError):
                continue
            if candidate == field_id:
                return field
        return None

    def _sync_field_list_selection(self, field_id: int | None) -> None:
        """Reflect the active canvas selection in the field list widget."""
        if self.field_list is None:
            return
        self._syncing_field_list = True
        try:
            self.field_list.blockSignals(True)
            if field_id is None:
                self.field_list.clearSelection()
            else:
                try:
                    field_key = int(field_id)
                except (TypeError, ValueError):
                    self.field_list.clearSelection()
                else:
                    item = self.field_list_items.get(field_key)
                    if item:
                        self.field_list.setCurrentItem(item)
                    else:
                        self.field_list.clearSelection()
        finally:
            self.field_list.blockSignals(False)
            self._syncing_field_list = False

    def _update_field_list_item(self, field_id: Any) -> None:
        """Refresh the label for a single field entry when its data changes."""
        if field_id is None or self.field_list is None:
            return
        try:
            field_key = int(field_id)
        except (TypeError, ValueError):
            return
        field = self._get_field_by_id(field_key)
        item = self.field_list_items.get(field_key)
        if field and item:
            item.setText(self._format_field_list_label(field))

    def _add_field_item(self, field: dict[str, Any], *, select: bool = False) -> FieldItem:
        cls = FIELD_CLASSES.get(field.get("type"), FieldItem)
        item = cls(field, geometry_changed=self._handle_field_geometry_changed)
        self.scene.addItem(item)
        item.setZValue(5)
        field_id = field.get("id")
        try:
            field_key = int(field_id)
        except (TypeError, ValueError):
            field_key = None
        if field_key is not None:
            self.field_items[field_key] = item
        if select:
            self.scene.clearSelection()
            item.setSelected(True)
        return item

    def _on_canvas_field_drawn(self, rect: QRectF) -> None:
        if not self.current_template or not self.active_field_type:
            self._reset_palette_tool()
            return
        self._create_field_from_rect(self.active_field_type, rect, select=True)
        self._reset_palette_tool()

    def _on_canvas_field_aborted(self) -> None:
        self.statusBar().showMessage("Field placement canceled", 3000)
        self._reset_palette_tool()

    def _create_field_from_rect(self, field_type: str, rect: QRectF, *, select: bool = False) -> None:
        if not self.current_template:
            return
        width = rect.width() if rect.width() > 0 else 150.0
        height = rect.height() if rect.height() > 0 else 24.0
        field = {
            "id": self.next_field_id,
            "page": 1,
            "name": f"field_{self.next_field_id}",
            "type": field_type,
            "x": float(rect.x()),
            "y": float(rect.y()),
            "width": float(width),
            "height": float(height),
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
        self._add_field_item(field, select=select)
        if self.field_list is not None:
            self.field_list.setEnabled(True)
        self._refresh_field_list()
        self._sync_field_list_selection(field.get("id"))
        self.preview_widget.update_fields(self.current_template.get("fields", []))
        self.statusBar().showMessage(f"Added {field_type.title()} field", 4000)

    def _reset_palette_tool(self) -> None:
        self.active_field_type = None
        if hasattr(self, "canvas"):
            self.canvas.cancel_field_creation()
        if hasattr(self, "palette_list"):
            self.palette_list.blockSignals(True)
            self.palette_list.clearSelection()
            self.palette_list.blockSignals(False)

    def _on_selection_changed(self) -> None:
        items = self.scene.selectedItems()
        self.current_field_item = items[0] if items else None
        if self.current_field_item is None:
            self._clear_properties()
            self._sync_field_list_selection(None)
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
        self.preview_widget.set_highlight(field.get("id"))
        self._update_delete_button_state()
        self._sync_field_list_selection(field.get("id"))

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
        self.preview_widget.set_highlight(None)
        self._update_delete_button_state()
        self._sync_field_list_selection(None)

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
        self._update_field_list_item(field.get("id"))
        self.preview_widget.update_fields(self.current_template.get("fields", []))

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

    def _handle_field_geometry_changed(self, field: dict[str, Any]) -> None:
        """Update UI elements when a field is moved on the canvas."""

        if self.current_template is None:
            return
        self.preview_widget.update_fields(self.current_template.get("fields", []))
        self._update_field_list_item(field.get("id"))
        if self.current_field_item and self.current_field_item.field is field:
            self.field_x_spin.blockSignals(True)
            self.field_y_spin.blockSignals(True)
            self.field_x_spin.setValue(float(field.get("x", 0)))
            self.field_y_spin.setValue(float(field.get("y", 0)))
            self.field_x_spin.blockSignals(False)
            self.field_y_spin.blockSignals(False)

    def _on_field_order_changed(self, ordered_ids: list[int]) -> None:
        """Persist the drag-and-drop order back to the template list."""

        if not self.current_template:
            return
        id_to_field: dict[int, dict[str, Any]] = {}
        for field in self.current_template.get("fields", []):
            try:
                field_id = int(field.get("id"))
            except (TypeError, ValueError):
                continue
            id_to_field[field_id] = field
        ordered_fields: list[dict[str, Any]] = []
        for field_id in ordered_ids:
            field = id_to_field.pop(field_id, None)
            if field:
                ordered_fields.append(field)
        # Append any remaining fields that may have been filtered out from the list widget.
        ordered_fields.extend(id_to_field.values())
        self.current_template["fields"] = ordered_fields
        self.preview_widget.update_fields(self.current_template.get("fields", []))

    def delete_selected_field(self) -> None:
        """Remove the active field from the template and canvas."""

        if not self.current_template:
            return
        field_item: FieldItem | None = self.current_field_item
        if field_item is None and self.field_list is not None:
            current = self.field_list.currentItem()
            if current is not None:
                field_id = current.data(Qt.ItemDataRole.UserRole)
                try:
                    field_item = self.field_items.get(int(field_id))
                except (TypeError, ValueError):
                    field_item = None
        if field_item is None:
            return
        field = field_item.field
        try:
            field_id = int(field.get("id"))
        except (TypeError, ValueError):
            field_id = None
        self.scene.removeItem(field_item)
        if field_id is not None:
            self.field_items.pop(field_id, None)
            list_item = self.field_list_items.pop(field_id, None)
            if list_item and self.field_list is not None:
                row = self.field_list.row(list_item)
                self.field_list.takeItem(row)
        fields = self.current_template.get("fields", [])
        if field_id is not None:
            self.current_template["fields"] = [
                f for f in fields if self._safe_int(f.get("id")) != field_id
            ]
        else:
            self.current_template["fields"] = [f for f in fields if f is not field]
        self.current_field_item = None
        self._clear_properties()
        self.preview_widget.update_fields(self.current_template.get("fields", []))
        self._update_delete_button_state()
        self.statusBar().showMessage("Field deleted", 4000)

    def _handle_preview_click(self, field_id: int) -> None:
        """Select the field on the canvas when clicked in the preview."""

        field_item = self.field_items.get(field_id)
        if not field_item:
            return
        self.scene.clearSelection()
        field_item.setSelected(True)
        self.canvas.centerOn(field_item)

    def _update_delete_button_state(self) -> None:
        """Enable or disable the delete field button based on selection."""

        if not hasattr(self, "delete_field_button"):
            return
        has_selection = bool(self.current_field_item)
        if not has_selection and self.field_list is not None:
            has_selection = self.field_list.currentItem() is not None
        self.delete_field_button.setEnabled(has_selection)

    @staticmethod
    def _safe_int(value: Any, default: int | None = None) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return default


if __name__ == "__main__":  # pragma: no cover - manual smoke test helper
    app = QApplication([])
    window = MainWindow()
    window.show()
    app.exec()
