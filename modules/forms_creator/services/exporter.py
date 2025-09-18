"""PDF export utilities for form instances."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

try:  # pragma: no cover - optional Qt dependency
    from PySide6.QtCore import QRectF, QSizeF, Qt
    from PySide6.QtGui import QFont, QGuiApplication, QImage, QPainter, QPageSize
    from PySide6.QtPdf import QPdfWriter
    QT_AVAILABLE = True
    QT_IMPORT_ERROR: Exception | None = None
except Exception as exc:  # pragma: no cover - fallback when Qt not available
    QT_AVAILABLE = False
    QT_IMPORT_ERROR = exc
    QRectF = QSizeF = Qt = QFont = QGuiApplication = QImage = QPainter = QPageSize = QPdfWriter = None  # type: ignore


class ExportError(RuntimeError):
    """Raised when the exporter cannot produce a PDF."""


def _ensure_app() -> None:
    if not QT_AVAILABLE:
        raise ExportError(f"PySide6 runtime is unavailable: {QT_IMPORT_ERROR}")
    if QGuiApplication.instance() is None:
        QGuiApplication(sys.argv or ["forms_creator_exporter"])


@dataclass(slots=True)
class PDFExporter:
    """Render form instances to PDF files."""

    default_dpi: int = 150

    def export(
        self,
        *,
        background_paths: Iterable[Path],
        fields: list[dict[str, Any]],
        values: dict[int, Any],
        output_path: Path,
    ) -> Path:
        """Render the PDF and return the resulting path."""

        background_paths = list(background_paths)
        if not background_paths:
            raise ExportError("No background pages were supplied")
        if not QT_AVAILABLE:
            raise ExportError(f"PySide6 runtime is unavailable: {QT_IMPORT_ERROR}")

        _ensure_app()
        output_path = output_path.expanduser().resolve()
        output_path.parent.mkdir(parents=True, exist_ok=True)

        writer = QPdfWriter(str(output_path))
        writer.setResolution(self.default_dpi)

        painter = QPainter(writer)
        try:
            for page_index, background_path in enumerate(background_paths):
                image = QImage(str(background_path))
                if image.isNull():
                    raise ExportError(f"Failed to load background image: {background_path}")

                dpi = self._image_dpi(image)
                page_size = self._page_size_from_image(image, dpi)
                writer.setPageSize(page_size)

                page_rect = QRectF(0, 0, writer.width(), writer.height())
                painter.save()
                painter.drawImage(page_rect, image)
                self._draw_fields(
                    painter,
                    image=image,
                    page_rect=page_rect,
                    page_index=page_index,
                    fields=fields,
                    values=values,
                )
                painter.restore()

                if page_index < len(background_paths) - 1:
                    writer.newPage()
        finally:
            painter.end()

        return output_path

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------
    def _image_dpi(self, image: QImage) -> int:
        x = image.dotsPerMeterX()
        if x > 0:
            return max(72, int(round(x * 0.0254)))
        return self.default_dpi

    def _page_size_from_image(self, image: QImage, dpi: int) -> 'QPageSize':
        width_mm = image.width() / dpi * 25.4
        height_mm = image.height() / dpi * 25.4
        return QPageSize(QSizeF(width_mm, height_mm), QPageSize.Unit.Millimeter)

    def _draw_fields(
        self,
        painter: QPainter,
        *,
        image: QImage,
        page_rect: QRectF,
        page_index: int,
        fields: list[dict[str, Any]],
        values: dict[int, Any],
    ) -> None:
        scale_x = page_rect.width() / image.width()
        scale_y = page_rect.height() / image.height()
        for field in fields:
            if int(field.get("page", 1)) - 1 != page_index:
                continue
            rect = QRectF(
                float(field.get("x", 0)) * scale_x,
                float(field.get("y", 0)) * scale_y,
                float(field.get("width", 0)) * scale_x,
                float(field.get("height", 0)) * scale_y,
            )
            value = values.get(int(field.get("id", -1)))
            self._draw_field(painter, rect, field, value)

    def _draw_field(self, painter: QPainter, rect: QRectF, field: dict[str, Any], value: Any) -> None:
        field_type = field.get("type", "text")
        if field_type in {"checkbox", "radio"}:
            self._draw_checkbox(painter, rect, field, value, radio=(field_type == "radio"))
            return
        if field_type in {"image", "signature"}:
            self._draw_image(painter, rect, value)
            return
        if field_type == "table":
            self._draw_table(painter, rect, value)
            return
        self._draw_text(painter, rect, field, value)

    def _draw_text(self, painter: QPainter, rect: QRectF, field: dict[str, Any], value: Any) -> None:
        text = "" if value is None else str(value)
        font = painter.font()
        font_family = field.get("font_family")
        if font_family:
            font.setFamily(str(font_family))
        font_size = field.get("font_size")
        if font_size:
            try:
                font.setPointSizeF(float(font_size))
            except (TypeError, ValueError):  # pragma: no cover - defensive
                pass
        painter.setFont(font)
        alignment = {
            "left": Qt.AlignLeft | Qt.AlignVCenter,
            "center": Qt.AlignHCenter | Qt.AlignVCenter,
            "right": Qt.AlignRight | Qt.AlignVCenter,
        }.get(field.get("align", "left"), Qt.AlignLeft | Qt.AlignVCenter)
        painter.setPen(Qt.black)
        painter.drawText(rect, alignment, text)

    def _draw_checkbox(
        self,
        painter: QPainter,
        rect: QRectF,
        field: dict[str, Any],
        value: Any,
        *,
        radio: bool = False,
    ) -> None:
        painter.setPen(Qt.black)
        painter.setBrush(Qt.NoBrush)
        if radio:
            painter.drawEllipse(rect)
        else:
            painter.drawRect(rect)
        if self._is_truthy(value):
            painter.save()
            painter.setPen(Qt.black)
            if radio:
                center = rect.center()
                radius = min(rect.width(), rect.height()) / 3
                painter.setBrush(Qt.black)
                painter.drawEllipse(center, radius, radius)
            else:
                painter.drawLine(rect.topLeft(), rect.bottomRight())
                painter.drawLine(rect.topRight(), rect.bottomLeft())
            painter.restore()

    def _draw_image(self, painter: QPainter, rect: QRectF, value: Any) -> None:
        if not value:
            return
        path = Path(str(value))
        if not path.exists():
            return
        image = QImage(str(path))
        if image.isNull():
            return
        painter.drawImage(rect, image)

    def _draw_table(self, painter: QPainter, rect: QRectF, value: Any) -> None:
        if not value:
            return
        if isinstance(value, dict):
            rows = value.get("rows", [])
        else:
            rows = value
        lines = []
        if isinstance(rows, list):
            for row in rows:
                if isinstance(row, dict):
                    lines.append(", ".join(f"{k}: {v}" for k, v in row.items()))
                else:
                    lines.append(str(row))
        text = "\n".join(lines)
        painter.drawText(rect, Qt.AlignLeft | Qt.AlignTop, text)

    def _is_truthy(self, value: Any) -> bool:
        if isinstance(value, str):
            return value.strip().lower() in {"1", "true", "yes", "y", "checked"}
        return bool(value)


