"""Wizard that helps users import a document and create a template."""

from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtGui import QImage
from PySide6.QtWidgets import (
    QFileDialog,
    QGridLayout,
    QLabel,
    QLineEdit,
    QMessageBox,
    QPushButton,
    QVBoxLayout,
    QWizard,
    QWizardPage,
)

from ...services.pdf_fields import PDFFormFieldExtractor
from ...services.rasterizer import Rasterizer
from ...services.template_importer import TemplateImportError, import_pdf_template
from ...services.templates import FormService


class _FileSelectionPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Select Source Document")
        layout = QGridLayout(self)
        layout.addWidget(QLabel("PDF or image"), 0, 0)
        self.path_edit = QLineEdit()
        layout.addWidget(self.path_edit, 0, 1)
        browse_btn = QPushButton("Browse…")
        layout.addWidget(browse_btn, 0, 2)
        browse_btn.clicked.connect(self._browse)

    def _browse(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Select PDF or image",
            "",
            "PDF Files (*.pdf);;Images (*.png *.jpg *.jpeg)",
        )
        if path:
            self.path_edit.setText(path)

    def selected_path(self) -> Path:
        return Path(self.path_edit.text())


class _MetadataPage(QWizardPage):
    def __init__(self) -> None:
        super().__init__()
        self.setTitle("Template Details")
        layout = QVBoxLayout(self)
        form_layout = QGridLayout()
        layout.addLayout(form_layout)

        form_layout.addWidget(QLabel("Name"), 0, 0)
        self.name_edit = QLineEdit()
        form_layout.addWidget(self.name_edit, 0, 1)

        form_layout.addWidget(QLabel("Category"), 1, 0)
        self.category_edit = QLineEdit()
        form_layout.addWidget(self.category_edit, 1, 1)

        form_layout.addWidget(QLabel("Subcategory"), 2, 0)
        self.subcategory_edit = QLineEdit()
        form_layout.addWidget(self.subcategory_edit, 2, 1)

    def metadata(self) -> dict[str, str | None]:
        return {
            "name": self.name_edit.text().strip() or "Untitled Template",
            "category": self.category_edit.text().strip() or None,
            "subcategory": self.subcategory_edit.text().strip() or None,
        }


class NewTemplateWizard(QWizard):
    """Walks the user through importing a PDF/image into a template."""

    def __init__(self, form_service: FormService, parent=None, *, rasterizer: Rasterizer | None = None):
        super().__init__(parent)
        self.form_service = form_service
        self.rasterizer = rasterizer or Rasterizer()
        self.field_extractor = PDFFormFieldExtractor()
        self.setWindowTitle("New Form Template")
        self.created_template_id: int | None = None
        self.imported_field_count: int = 0

        self.file_page = _FileSelectionPage()
        self.meta_page = _MetadataPage()
        self.addPage(self.file_page)
        self.addPage(self.meta_page)

    def accept(self) -> None:  # noqa: D401
        try:
            self.created_template_id = self._create_template()
        except TemplateImportError as exc:  # pragma: no cover - Qt dialog path
            QMessageBox.critical(self, "PDF Import", str(exc))
            return
        except Exception as exc:  # pragma: no cover - Qt dialog path
            QMessageBox.critical(self, "Template", f"Failed to create template: {exc}")
            return
        super().accept()

    # ------------------------------------------------------------------
    def _create_template(self) -> int:
        source = self.file_page.selected_path()
        if not source.exists():
            raise FileNotFoundError("Selected source file does not exist")

        meta = self.meta_page.metadata()
        if source.suffix.lower() == ".pdf":
            result = import_pdf_template(
                self.form_service,
                source,
                name=meta["name"],
                category=meta["category"],
                subcategory=meta["subcategory"],
                rasterizer=self.rasterizer,
                extractor=self.field_extractor,
            )
            self.imported_field_count = result.field_count
            if result.warnings:
                QMessageBox.warning(
                    self,
                    "PDF Fields",
                    "\n\n".join(result.warnings),
                )
            return result.template_id

        template_uuid = uuid.uuid4().hex
        template_dir = self.form_service.templates_dir / template_uuid
        template_dir.mkdir(parents=True, exist_ok=True)
        images = self._copy_image(source, template_dir)

        if not images:
            raise RuntimeError("Rasteriser returned no images")

        background_rel = Path("forms") / "templates" / template_uuid
        template_id = self.form_service.save_template(
            name=meta["name"],
            category=meta["category"],
            subcategory=meta["subcategory"],
            background_path=str(background_rel),
            page_count=len(images),
            fields=[],
        )

        self.imported_field_count = 0

        return template_id

    def _copy_image(self, source: Path, target_dir: Path) -> list[Path]:
        image_path = target_dir / "background_page_001.png"
        image = QImage(str(source))
        if image.isNull():
            raise RuntimeError(f"Unable to load image {source}")
        image.save(str(image_path))
        return [image_path]

