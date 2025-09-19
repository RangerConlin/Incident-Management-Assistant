"""Wizard that helps users import a document and create a template."""

from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Any

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

from ...services.pdf_fields import (
    PDFFieldExtractionError,
    PDFFormFieldExtractor,
    DetectedPDFField,
)
from ...services.rasterizer import Rasterizer, RasterizerError
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
        except RasterizerError as exc:  # pragma: no cover - Qt dialog path
            QMessageBox.critical(self, "Rasterizer", str(exc))
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
        template_uuid = uuid.uuid4().hex
        template_dir = self.form_service.templates_dir / template_uuid
        template_dir.mkdir(parents=True, exist_ok=True)

        fields: list[dict[str, Any]] = []
        if source.suffix.lower() == ".pdf":
            images = self.rasterizer.rasterize_pdf(source, template_dir)
            fields = self._auto_detect_pdf_fields(source, images)
        else:
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
            fields=fields,
        )

        self.imported_field_count = len(fields)

        # Persist metadata for future reference
        meta_path = template_dir / "meta.json"
        meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
        return template_id

    def _copy_image(self, source: Path, target_dir: Path) -> list[Path]:
        image_path = target_dir / "background_page_001.png"
        image = QImage(str(source))
        if image.isNull():
            raise RuntimeError(f"Unable to load image {source}")
        image.save(str(image_path))
        return [image_path]

    def _auto_detect_pdf_fields(self, pdf_path: Path, background_images: list[Path]) -> list[dict[str, Any]]:
        if not background_images:
            return []
        try:
            detected = self.field_extractor.extract(pdf_path)
        except PDFFieldExtractionError as exc:
            QMessageBox.warning(
                self,
                "PDF Fields",
                f"Unable to import fillable fields automatically:\n{exc}",
            )
            return []
        if not detected:
            return []
        return self._convert_detected_fields(detected, background_images)

    def _convert_detected_fields(
        self,
        detected_fields: list[DetectedPDFField],
        background_images: list[Path],
    ) -> list[dict[str, Any]]:
        page_images: dict[int, QImage] = {}
        for index, image_path in enumerate(background_images):
            image = QImage(str(image_path))
            if not image.isNull():
                page_images[index] = image

        fields: list[dict[str, Any]] = []
        name_counts: dict[str, int] = {}
        field_id = 1
        for detected in detected_fields:
            image = page_images.get(detected.page_index)
            if image is None or image.isNull():
                continue

            scale_x = image.width() / detected.page_width if detected.page_width else 1.0
            scale_y = image.height() / detected.page_height if detected.page_height else 1.0
            llx, lly, urx, ury = detected.rect
            width = max(1.0, (urx - llx) * scale_x)
            height = max(1.0, (ury - lly) * scale_y)
            x = max(0.0, llx * scale_x)
            y = max(0.0, image.height() - ury * scale_y)
            if width < 4 or height < 4:
                continue

            base_name = detected.name or f"field_{field_id}"
            base_name = self._sanitise_field_name(base_name)
            suffix = ""
            if detected.template_type == "radio" and detected.export_value:
                export_value = detected.export_value
                if export_value.lower() != "off":
                    suffix = f"_{self._sanitise_field_name(export_value)}"

            candidate = f"{base_name}{suffix}"
            count = name_counts.get(candidate, 0)
            final_name = candidate if count == 0 else f"{candidate}_{count + 1}"
            name_counts[candidate] = count + 1

            height_pt = detected.rect[3] - detected.rect[1]
            font_size = int(round(height_pt * 0.75)) if height_pt > 0 else 10
            font_size = max(8, min(18, font_size))

            dropdown_config = None
            if detected.template_type == "dropdown":
                dropdown_config = {
                    "options": detected.options or [],
                    "editable": detected.choice_editable,
                    "multi": detected.choice_multi_select,
                }

            field_dict = {
                "id": field_id,
                "page": detected.page_index + 1,
                "name": final_name,
                "type": detected.template_type,
                "x": float(round(x, 2)),
                "y": float(round(y, 2)),
                "width": float(round(width, 2)),
                "height": float(round(height, 2)),
                "font_family": "",
                "font_size": font_size,
                "align": "left",
                "required": detected.required,
                "placeholder": "",
                "mask": "",
                "default_value": detected.default_value or "",
                "config": {
                    "bindings": [],
                    "validations": [],
                    "dropdown": dropdown_config,
                    "table": None,
                },
            }
            fields.append(field_dict)
            field_id += 1

        return fields

    def _sanitise_field_name(self, name: str) -> str:
        text = name.strip() or "field"
        cleaned = [
            ch if ("a" <= ch.lower() <= "z" or ch.isdigit() or ch in {"_", "-"}) else "_"
            for ch in text
        ]
        result = "".join(cleaned).strip("_")
        return result or "field"
