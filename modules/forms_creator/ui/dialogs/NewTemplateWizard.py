"""Dialog guiding the user through creating a new template."""
from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
)

from ...services import db
from ...services.rasterizer import Rasterizer, RasterizerError


class NewTemplateWizard(QDialog):
    """Import a PDF or set of images and produce template assets."""

    def __init__(self, parent=None, *, rasterizer: Rasterizer | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("New Template Wizard")
        self._rasterizer = rasterizer or Rasterizer()
        self._selected_files: list[Path] = []
        self._result: dict[str, str | int | None] | None = None

        self._name_edit = QLineEdit()
        self._category_edit = QLineEdit()
        self._subcategory_edit = QLineEdit()
        self._import_type_combo = QComboBox()
        self._import_type_combo.addItems(["PDF", "Images"])
        self._path_edit = QLineEdit()
        self._path_edit.setReadOnly(True)
        browse_button = QPushButton("Browse…")
        browse_button.clicked.connect(self._browse)

        form = QFormLayout()
        form.addRow("Template Name", self._name_edit)
        form.addRow("Category", self._category_edit)
        form.addRow("Subcategory", self._subcategory_edit)
        form.addRow("Source Type", self._import_type_combo)

        path_row = QHBoxLayout()
        path_row.addWidget(self._path_edit)
        path_row.addWidget(browse_button)
        form.addRow("Source File(s)", path_row)

        info_label = QLabel(
            "Select a PDF or image files to use as the background for the template. "
            "Files are copied into the local data directory so the tool works offline."
        )
        info_label.setWordWrap(True)

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel, Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)

        layout = QVBoxLayout(self)
        layout.addLayout(form)
        layout.addWidget(info_label)
        layout.addWidget(buttons)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @property
    def result(self) -> dict[str, str | int | None] | None:
        return self._result

    # ------------------------------------------------------------------
    # Qt slots
    # ------------------------------------------------------------------
    def accept(self) -> None:  # noqa: N802 - Qt naming
        if not self._name_edit.text().strip():
            QMessageBox.warning(self, "Missing information", "Please provide a template name.")
            return
        if not self._selected_files:
            QMessageBox.warning(self, "Missing file", "Please select a PDF or image file to import.")
            return
        try:
            data = self._process_files()
        except RasterizerError as exc:  # pragma: no cover - UI feedback
            QMessageBox.critical(self, "Import failed", str(exc))
            return
        except Exception as exc:  # pragma: no cover - defensive
            QMessageBox.critical(self, "Unexpected error", str(exc))
            return
        self._result = data
        super().accept()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _browse(self) -> None:
        if self._import_type_combo.currentText() == "PDF":
            filename, _ = QFileDialog.getOpenFileName(self, "Select PDF", filter="PDF Files (*.pdf)")
            if filename:
                self._selected_files = [Path(filename)]
                self._path_edit.setText(filename)
        else:
            files, _ = QFileDialog.getOpenFileNames(self, "Select images", filter="Images (*.png *.jpg *.jpeg *.bmp)")
            if files:
                self._selected_files = [Path(f) for f in files]
                self._path_edit.setText("; ".join(files))

    def _process_files(self) -> dict[str, str | int | None]:
        db.ensure_data_directories()
        template_uuid = uuid4().hex
        target_dir = db.TEMPLATES_ROOT / template_uuid
        target_dir.mkdir(parents=True, exist_ok=True)

        if self._import_type_combo.currentText() == "PDF":
            pages = self._rasterizer.rasterize_pdf(self._selected_files[0], target_dir)
        else:
            pages = self._rasterizer.rasterize_images(self._selected_files, target_dir)

        relative_background = target_dir.relative_to(db.DATA_DIR)
        return {
            "name": self._name_edit.text().strip(),
            "category": self._category_edit.text().strip() or None,
            "subcategory": self._subcategory_edit.text().strip() or None,
            "background_path": str(relative_background).replace("\\", "/"),
            "page_count": len(pages),
        }

