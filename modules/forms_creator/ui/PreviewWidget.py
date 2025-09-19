"""Lightweight preview widget for the form creator.

The widget renders the first page of the currently loaded template and overlays
field rectangles.  The active field is highlighted and the author can click a
rectangle to select it directly from the preview pane.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QMouseEvent, QPainter, QPaintEvent, QPixmap
from PySide6.QtWidgets import QWidget


class TemplatePreview(QWidget):
    """Embedded preview of a template page with clickable field overlays."""

    fieldClicked = Signal(int)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._background: QPixmap | None = None
        self._fields: list[tuple[int, QRectF]] = []
        self._highlight_id: int | None = None
        self._last_target = QRectF()
        self._last_scale = 1.0
        self.setMinimumHeight(220)
        self.setMouseTracking(True)

    # ------------------------------------------------------------------
    def clear(self) -> None:
        """Reset the widget to an empty state."""

        self._background = None
        self._fields.clear()
        self._highlight_id = None
        self._last_target = QRectF()
        self._last_scale = 1.0
        self.update()

    # ------------------------------------------------------------------
    def set_template(self, template: dict, data_dir: Path) -> None:
        """Load the preview background from ``template`` metadata."""

        background = Path(template.get("background_path", ""))
        if not background.is_absolute():
            background = data_dir / background
        image_path = background / "background_page_001.png"
        pixmap = QPixmap(str(image_path))
        if pixmap.isNull():
            self._background = None
        else:
            self._background = pixmap
        self.update_fields(template.get("fields", []))

    # ------------------------------------------------------------------
    def update_fields(self, fields: Iterable[dict]) -> None:
        """Refresh overlay rectangles from ``fields``."""

        self._fields.clear()
        for field in fields:
            try:
                field_id = int(field.get("id"))
            except (TypeError, ValueError):
                continue
            try:
                page = int(field.get("page", 1))
            except (TypeError, ValueError):
                page = 1
            if page != 1:
                continue
            rect = QRectF(
                float(field.get("x", 0.0)),
                float(field.get("y", 0.0)),
                float(field.get("width", 0.0)),
                float(field.get("height", 0.0)),
            )
            self._fields.append((field_id, rect))
        self.update()

    # ------------------------------------------------------------------
    def set_highlight(self, field_id: int | None) -> None:
        """Update the active highlight."""

        if field_id is None:
            self._highlight_id = None
        else:
            try:
                self._highlight_id = int(field_id)
            except (TypeError, ValueError):
                self._highlight_id = None
        self.update()

    # ------------------------------------------------------------------
    def paintEvent(self, event: QPaintEvent) -> None:  # noqa: D401,N802
        painter = QPainter(self)
        painter.fillRect(self.rect(), self.palette().window())

        if not self._background or self._background.isNull():
            self._last_target = QRectF()
            self._last_scale = 1.0
            painter.end()
            return

        scaled = self._background.scaled(
            self.size(), Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation
        )
        offset_x = (self.width() - scaled.width()) / 2
        offset_y = (self.height() - scaled.height()) / 2
        target_top_left = QPointF(offset_x, offset_y)
        painter.drawPixmap(target_top_left, scaled)

        # Cache geometry for hit-testing.
        self._last_target = QRectF(target_top_left, scaled.size())
        if self._background.width() > 0:
            self._last_scale = scaled.width() / float(self._background.width())
        else:
            self._last_scale = 1.0

        base_brush = QColor(0, 0, 0, 60)
        base_pen = QColor(0, 0, 0, 150)
        highlight_brush = QColor(255, 170, 0, 100)
        highlight_pen = QColor(255, 120, 0)

        for field_id, rect in self._fields:
            display_rect = QRectF(
                target_top_left.x() + rect.x() * self._last_scale,
                target_top_left.y() + rect.y() * self._last_scale,
                rect.width() * self._last_scale,
                rect.height() * self._last_scale,
            )
            if field_id == self._highlight_id:
                painter.setBrush(highlight_brush)
                painter.setPen(highlight_pen)
            else:
                painter.setBrush(base_brush)
                painter.setPen(base_pen)
            painter.drawRect(display_rect)

        painter.end()

    # ------------------------------------------------------------------
    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: D401,N802
        if not self._background or self._background.isNull():
            return
        if not self._last_target.contains(event.position()):
            return

        local_x = (event.position().x() - self._last_target.left()) / self._last_scale
        local_y = (event.position().y() - self._last_target.top()) / self._last_scale
        point = QPointF(local_x, local_y)

        # Iterate in reverse order so later entries (most recently added) win.
        for field_id, rect in reversed(self._fields):
            if rect.contains(point):
                self.fieldClicked.emit(field_id)
                break

        super().mousePressEvent(event)
