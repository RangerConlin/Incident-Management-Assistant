"""Generic form editor that can render simple schemas from ``ics_forms``."""

from __future__ import annotations

from typing import Dict, Optional

from PySide6 import QtCore, QtWidgets

from ..models.autofill import AutofillEngine
from ..models.iap_models import FormInstance
from .components.autofill_preview_panel import AutofillPreviewPanel
from .components.form_field_widget import FormFieldWidget


class IAPFormEditor(QtWidgets.QWidget):
    """Light-weight form editor used during the scaffolding milestone."""

    formSaved = QtCore.Signal(FormInstance)

    def __init__(
        self,
        form: FormInstance,
        autofill_engine: Optional[AutofillEngine] = None,
        parent: Optional[QtWidgets.QWidget] = None,
    ) -> None:
        super().__init__(parent)
        self._form = form
        self.autofill_engine = autofill_engine or AutofillEngine()
        self.setWindowTitle(form.title)

        self._build_ui()
        self._populate_fields(form.fields)
        self._refresh_autofill()

    # ------------------------------------------------------------------ UI helpers
    def _build_ui(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)

        header = QtWidgets.QHBoxLayout()
        self.title_label = QtWidgets.QLabel(f"{self._form.title} – OP {self._form.op_number}")
        header.addWidget(self.title_label)
        header.addStretch()
        self.save_button = QtWidgets.QPushButton("Save")
        self.preview_button = QtWidgets.QPushButton("Preview PDF")
        self.attach_button = QtWidgets.QPushButton("Attach File")
        header.addWidget(self.save_button)
        header.addWidget(self.preview_button)
        header.addWidget(self.attach_button)
        layout.addLayout(header)

        splitter = QtWidgets.QSplitter(self)
        splitter.setOrientation(QtCore.Qt.Horizontal)
        layout.addWidget(splitter, 1)

        # Left – navigation placeholder
        navigation = QtWidgets.QListWidget()
        navigation.addItem("Fields")
        navigation.setCurrentRow(0)
        splitter.addWidget(navigation)

        # Center – field editor panel
        editor_container = QtWidgets.QScrollArea()
        editor_container.setWidgetResizable(True)
        splitter.addWidget(editor_container)

        self._field_host = QtWidgets.QWidget()
        self._field_layout = QtWidgets.QVBoxLayout(self._field_host)
        self._field_layout.setContentsMargins(12, 12, 12, 12)
        self._field_layout.setSpacing(8)
        self._field_layout.addStretch()
        editor_container.setWidget(self._field_host)

        # Right – autofill preview
        self.autofill_panel = AutofillPreviewPanel(parent=self)
        splitter.addWidget(self.autofill_panel)
        splitter.setStretchFactor(0, 1)
        splitter.setStretchFactor(1, 3)
        splitter.setStretchFactor(2, 2)

        self.save_button.clicked.connect(self._on_save)
        self.preview_button.clicked.connect(self._on_preview)
        self.attach_button.clicked.connect(self._on_attach)

    def _populate_fields(self, fields: Dict[str, object]) -> None:
        # Remove existing field widgets while keeping the trailing stretch.
        while self._field_layout.count() > 1:
            item = self._field_layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.deleteLater()
        for field_id, value in fields.items():
            multiline = not isinstance(value, (str, int, float))
            label = field_id.replace("_", " ").title()
            widget = FormFieldWidget(field_id, label, value=value, multiline=multiline)
            widget.valueChanged.connect(self._on_field_changed)
            self._field_layout.insertWidget(self._field_layout.count() - 1, widget)

    def _refresh_autofill(self) -> None:
        preview = self.autofill_engine.preview_for_form(self._form)
        self.autofill_panel.set_preview(preview)

    # ------------------------------------------------------------------- callbacks
    def _on_field_changed(self, field_id: str, value: object) -> None:
        self._form.fields[field_id] = value
        self._form.mark_updated()
        self._refresh_autofill()

    def _on_save(self) -> None:
        self.formSaved.emit(self._form)
        QtWidgets.QMessageBox.information(self, "Saved", "Form changes saved (stub).")

    def _on_preview(self) -> None:
        QtWidgets.QMessageBox.information(self, "Preview", "PDF preview will be added in a later milestone.")

    def _on_attach(self) -> None:
        QtWidgets.QMessageBox.information(self, "Attachments", "Attachment management is not part of the scaffold.")

    # -------------------------------------------------------------------- API
    def update_form(self, form: FormInstance) -> None:
        """Load a new :class:`FormInstance` into the editor."""

        self._form = form
        self.setWindowTitle(form.title)
        self.title_label.setText(f"{form.title} – OP {form.op_number}")
        self._populate_fields(form.fields)
        self._refresh_autofill()
