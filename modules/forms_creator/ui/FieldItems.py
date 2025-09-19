"""QGraphicsItem subclasses representing form fields."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QPainter, QPen
from PySide6.QtWidgets import QGraphicsRectItem, QStyle


class FieldItem(QGraphicsRectItem):
    """Base graphics item carrying field metadata."""

    def __init__(
        self,
        field: dict,
        *,
        geometry_changed: Callable[[dict], None] | None = None,
        parent=None,
    ) -> None:
        rect = QRectF(0, 0, float(field.get("width", 0)), float(field.get("height", 0)))
        super().__init__(rect, parent)
        self.field = field
        self._geometry_changed = geometry_changed
        self.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self._base_colour = QColor(0, 120, 215)
        self.setBrush(QColor(self._base_colour.red(), self._base_colour.green(), self._base_colour.blue(), 40))
        self.setPen(QPen(self._base_colour))
        self.setPos(float(field.get("x", 0)), float(field.get("y", 0)))
        self._refresh_tooltip()

    def itemChange(self, change, value):  # noqa: N802 - Qt API
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange:
            pos = value
            self.field["x"] = pos.x()
            self.field["y"] = pos.y()
        elif change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = self.pos()
            self.field["x"] = pos.x()
            self.field["y"] = pos.y()
            if self._geometry_changed:
                self._geometry_changed(self.field)
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            self._refresh_tooltip()
        return super().itemChange(change, value)

    def _refresh_tooltip(self) -> None:
        """Update the hover tooltip to reflect the current field metadata."""

        name = self.field.get("name") or f"Field {self.field.get('id')}"
        field_type = self.field.get("type", "")
        coords = f"({self.field.get('x', 0):.0f}, {self.field.get('y', 0):.0f})"
        self.setToolTip(f"{name}\nType: {field_type}\nOrigin: {coords}")

    # ------------------------------------------------------------------
    def update_field_metadata(self) -> None:
        """Refresh rendering after the backing dictionary has changed."""

        self._refresh_tooltip()
        self.update()

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: D401,N802
        painter.save()

        rect = self.rect()
        selected = bool(option.state & QStyle.StateFlag.State_Selected)

        pen = QPen(self._base_colour if not selected else QColor(20, 90, 180))
        pen.setWidthF(1.0 if not selected else 2.0)
        painter.setPen(pen)

        fill_alpha = 60 if not selected else 110
        painter.setBrush(QColor(self._base_colour.red(), self._base_colour.green(), self._base_colour.blue(), fill_alpha))
        painter.drawRect(rect)

        label = self.field.get("name") or f"Field {self.field.get('id')}"
        if label and rect.width() > 4 and rect.height() > 6:
            font = QFont(painter.font())
            font.setPointSizeF(max(8.0, min(float(self.field.get("font_size", 10)) * 0.8, 14.0)))
            painter.setFont(font)
            painter.setRenderHint(QPainter.RenderHint.TextAntialiasing, on=True)
            text_rect = rect.adjusted(3, 2, -3, -2)
            metrics = QFontMetricsF(font)
            available_width = max(0.0, text_rect.width())
            elided = metrics.elidedText(label, Qt.TextElideMode.ElideRight, int(available_width))
            text_colour = QColor(15, 15, 15) if selected else QColor(35, 35, 35)
            painter.setPen(text_colour)
            painter.drawText(
                text_rect,
                Qt.AlignmentFlag.AlignVCenter | Qt.AlignmentFlag.AlignLeft,
                elided,
            )

        painter.restore()


class TextFieldItem(FieldItem):
    """Text entry field."""


class CheckboxFieldItem(FieldItem):
    """Checkbox field representation."""


class DropdownFieldItem(FieldItem):
    """Dropdown field representation."""
