"""PDF export utilities for the form creator module."""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any


class PDFExporter:
    """Render form instances to PDF using QPainter."""

    def __init__(self, *, base_data_dir: Path | str = Path("data")) -> None:
        self.base_data_dir = Path(base_data_dir)
        self._qt = None

    # ------------------------------------------------------------------
    def export_instance(self, template: dict[str, Any], values: dict[int, Any], out_path: Path) -> Path:
        """Composite background pages with field overlays."""

        out_path = Path(out_path)
        out_path.parent.mkdir(parents=True, exist_ok=True)

        qt = self._require_qt()

        writer = qt.QPdfWriter(str(out_path))
        writer.setResolution(300)

        painter = qt.QPainter(writer)
        try:
            for index in range(template.get("page_count", 1)):
                page_number = index + 1
                background = self._page_background(template, page_number)
                image = qt.QImage(str(background))
                if image.isNull():
                    raise FileNotFoundError(f"Background image missing: {background}")

                if index == 0:
                    page_size = qt.QPageSize(qt.QSizeF(image.width(), image.height()), qt.QPageSize.Unit.Point)
                    layout = qt.QPageLayout(
                        page_size, qt.QPageLayout.Orientation.Portrait, qt.QMarginsF(0, 0, 0, 0)
                    )
                    writer.setPageLayout(layout)
                else:
                    writer.newPage()

                painter.drawImage(qt.QRectF(0, 0, image.width(), image.height()), image)
                self._paint_fields(painter, template.get("fields", []), values, page_number)
        finally:
            painter.end()

        return out_path

    # ------------------------------------------------------------------
    def _page_background(self, template: dict[str, Any], page_number: int) -> Path:
        base = Path(template.get("background_path", ""))
        if not base.is_absolute():
            base = self.base_data_dir / base
        file_name = f"background_page_{page_number:03d}.png"
        return base / file_name

    def _paint_fields(
        self,
        painter,
        fields: list[dict[str, Any]],
        values: dict[int, Any],
        page_number: int,
    ) -> None:
        qt = self._require_qt()
        for field in fields:
            if int(field.get("page", 1)) != page_number:
                continue
            rect = qt.QRectF(
                float(field.get("x", 0)),
                float(field.get("y", 0)),
                float(field.get("width", 0)),
                float(field.get("height", 0)),
            )
            value = values.get(field.get("id"))
            if value is None:
                value = field.get("default_value")
            field_type = field.get("type", "text")
            if field_type in {"text", "multiline", "date", "time", "dropdown"}:
                self._draw_text_field(painter, field, rect, value)
            elif field_type in {"checkbox", "radio"}:
                self._draw_checkbox(painter, field, rect, value, is_radio=field_type == "radio")
            elif field_type == "signature":
                self._draw_placeholder(painter, rect, "Signature")
            elif field_type == "image":
                self._draw_placeholder(painter, rect, "Image")
            elif field_type == "table":
                self._draw_placeholder(painter, rect, "Table rows")
            else:
                self._draw_text_field(painter, field, rect, value)

    def _draw_text_field(self, painter, field: dict[str, Any], rect, value: Any) -> None:
        qt = self._require_qt()
        font = qt.QFont()
        if field.get("font_family"):
            font.setFamily(field["font_family"])
        font.setPointSize(int(field.get("font_size", 10)))
        painter.save()
        painter.setFont(font)
        painter.setPen(qt.QColor(0, 0, 0))

        alignment = field.get("align", "left")
        flags = qt.Qt.AlignmentFlag.AlignLeft | qt.Qt.AlignmentFlag.AlignVCenter
        if alignment == "center":
            flags = qt.Qt.AlignmentFlag.AlignHCenter | qt.Qt.AlignmentFlag.AlignVCenter
        elif alignment == "right":
            flags = qt.Qt.AlignmentFlag.AlignRight | qt.Qt.AlignmentFlag.AlignVCenter
        if field.get("type") == "multiline":
            flags = flags | qt.Qt.TextFlag.TextWordWrap

        text = "" if value is None else str(value)
        painter.drawText(rect, flags, text)
        painter.restore()

    def _draw_checkbox(self, painter, field: dict[str, Any], rect, value: Any, *, is_radio: bool = False) -> None:
        qt = self._require_qt()
        painter.save()
        painter.setPen(qt.QColor(0, 0, 0))
        painter.drawRect(rect)
        if self._is_checked(value):
            if is_radio:
                painter.setBrush(qt.QColor(0, 0, 0))
                painter.drawEllipse(rect.center(), rect.width() / 4, rect.height() / 4)
            else:
                painter.drawLine(rect.topLeft(), rect.bottomRight())
                painter.drawLine(rect.bottomLeft(), rect.topRight())
        painter.restore()

    def _draw_placeholder(self, painter, rect, text: str) -> None:
        qt = self._require_qt()
        painter.save()
        painter.setPen(qt.QColor(80, 80, 80))
        painter.drawRect(rect)
        painter.drawText(rect, qt.Qt.AlignmentFlag.AlignCenter, text)
        painter.restore()

    def _is_checked(self, value: Any) -> bool:
        if value is None:
            return False
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value != 0
        value_str = str(value).strip().lower()
        return value_str in {"true", "yes", "1", "x", "checked"}

    def _require_qt(self) -> SimpleNamespace:
        if self._qt is not None:
            return self._qt
        try:
            from PySide6.QtCore import QMarginsF, QRectF, QSizeF, Qt  # type: ignore
            from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPageLayout, QPageSize, QPdfWriter  # type: ignore
        except ImportError as exc:  # pragma: no cover - dependency guard
            raise RuntimeError(
                "PySide6 is required for PDF export. Install the Qt bindings or provide a custom exporter."
            ) from exc
        self._qt = SimpleNamespace(
            QMarginsF=QMarginsF,
            QRectF=QRectF,
            QSizeF=QSizeF,
            Qt=Qt,
            QColor=QColor,
            QFont=QFont,
            QImage=QImage,
            QPainter=QPainter,
            QPageLayout=QPageLayout,
            QPageSize=QPageSize,
            QPdfWriter=QPdfWriter,
        )
        return self._qt
