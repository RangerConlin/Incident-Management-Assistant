from __future__ import annotations

"""Helpers for importing fillable PDFs into form templates."""

import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Sequence

from PySide6.QtGui import QImage

from .pdf_fields import (
    DetectedPDFField,
    PDFFieldExtractionError,
    PDFFormFieldExtractor,
)
from .rasterizer import Rasterizer, RasterizerError
from .templates import FormService


class TemplateImportError(RuntimeError):
    """Raised when a PDF template cannot be imported."""


@dataclass(slots=True)
class TemplateImportResult:
    template: Dict[str, Any]
    template_id: int
    field_count: int
    warnings: List[str]
    pdf_path: Path


def import_pdf_template(
    form_service: FormService,
    pdf_path: Path,
    *,
    name: str,
    category: str | None = None,
    subcategory: str | None = None,
    rasterizer: Rasterizer | None = None,
    extractor: PDFFormFieldExtractor | None = None,
) -> TemplateImportResult:
    """Rasterise ``pdf_path`` and create a template entry with detected fields."""

    if not pdf_path.exists():
        raise TemplateImportError(f"PDF not found: {pdf_path}")

    rasterizer = rasterizer or Rasterizer()
    extractor = extractor or PDFFormFieldExtractor()

    template_uuid = uuid.uuid4().hex
    template_dir = form_service.templates_dir / template_uuid
    template_dir.mkdir(parents=True, exist_ok=True)

    try:
        background_images = rasterizer.rasterize_pdf(pdf_path, template_dir)
    except RasterizerError as exc:
        raise TemplateImportError(str(exc)) from exc

    if not background_images:
        raise TemplateImportError(f"No pages were rendered from {pdf_path.name}.")

    warnings: List[str] = []
    detected: Sequence[DetectedPDFField] = []
    try:
        detected = extractor.extract(pdf_path)
    except PDFFieldExtractionError as exc:
        warnings.append(str(exc))
        detected = []

    fields = _convert_detected_fields(detected, background_images)

    template_name = name.strip() or pdf_path.stem
    background_rel = Path("forms") / "templates" / template_uuid
    template_id = form_service.save_template(
        name=template_name,
        category=category,
        subcategory=subcategory,
        background_path=str(background_rel),
        page_count=len(background_images),
        fields=fields,
    )
    template = form_service.get_template(template_id)

    return TemplateImportResult(
        template=template,
        template_id=template_id,
        field_count=len(fields),
        warnings=warnings,
        pdf_path=pdf_path,
    )


def _convert_detected_fields(
    detected_fields: Sequence[DetectedPDFField],
    background_images: Sequence[Path],
) -> List[Dict[str, Any]]:
    page_images: Dict[int, QImage] = {}
    for index, image_path in enumerate(background_images):
        image = QImage(str(image_path))
        if not image.isNull():
            page_images[index] = image

    fields: List[Dict[str, Any]] = []
    name_counts: Dict[str, int] = {}
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
        base_name = _sanitise_field_name(base_name)
        suffix = ""
        if detected.template_type == "radio" and detected.export_value:
            export_value = detected.export_value
            if export_value.lower() != "off":
                suffix = f"_{_sanitise_field_name(export_value)}"

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

        field_dict: Dict[str, Any] = {
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


def _sanitise_field_name(name: str) -> str:
    text = name.strip() or "field"
    cleaned = [
        ch if ("a" <= ch.lower() <= "z" or ch.isdigit() or ch in {"_", "-"}) else "_"
        for ch in text
    ]
    result = "".join(cleaned).strip("_")
    return result or "field"


__all__ = [
    "TemplateImportError",
    "TemplateImportResult",
    "import_pdf_template",
]
