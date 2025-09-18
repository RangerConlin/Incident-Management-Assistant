"""Graphics items representing template fields on the design canvas."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Type

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QPainter, QPen, QPolygonF
from PySide6.QtWidgets import QGraphicsItem, QGraphicsRectItem

HANDLE_SIZE = 8.0
MIN_FIELD_SIZE = 12.0


class FieldItem(QGraphicsRectItem):
    """Base graphics item providing selection, movement and resizing."""

    type_name = "field"

    def __init__(self, field: dict[str, Any], *, page: int = 1, parent: QGraphicsItem | None = None) -> None:
        rect = QRectF(0.0, 0.0, float(field.get("width", 100.0)), float(field.get("height", 24.0)))
        super().__init__(rect, parent)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable, True)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges, True)
        self.setAcceptHoverEvents(True)

        self.field: dict[str, Any] = field
        self.field.setdefault("page", page)
        self._resizing = False
        self._drag_origin = QPointF()
        self._resize_origin = QPointF()
        self._original_rect = QRectF(rect)
        self.setPos(float(field.get("x", 0.0)), float(field.get("y", 0.0)))

    # ------------------------------------------------------------------
    # Geometry helpers
    # ------------------------------------------------------------------
    def _handle_rect(self) -> QRectF:
        rect = self.rect()
        return QRectF(rect.right() - HANDLE_SIZE, rect.bottom() - HANDLE_SIZE, HANDLE_SIZE, HANDLE_SIZE)

    def _sync_field_geometry(self) -> None:
        rect = self.rect()
        pos = self.pos()
        self.field.update(
            {
                "x": round(pos.x(), 2),
                "y": round(pos.y(), 2),
                "width": round(rect.width(), 2),
                "height": round(rect.height(), 2),
            }
        )

    # ------------------------------------------------------------------
    # Event overrides
    # ------------------------------------------------------------------
    def hoverMoveEvent(self, event) -> None:  # noqa: N802 - Qt naming convention
        if self._handle_rect().contains(event.pos()):
            self.setCursor(Qt.SizeFDiagCursor)
        else:
            self.setCursor(Qt.ArrowCursor)
        super().hoverMoveEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.LeftButton and self._handle_rect().contains(event.pos()):
            self._resizing = True
            self._resize_origin = event.pos()
            self._original_rect = QRectF(self.rect())
            event.accept()
            return
        self._drag_origin = event.pos()
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._resizing:
            delta = event.pos() - self._resize_origin
            new_rect = QRectF(self._original_rect)
            new_rect.setWidth(max(MIN_FIELD_SIZE, new_rect.width() + delta.x()))
            new_rect.setHeight(max(MIN_FIELD_SIZE, new_rect.height() + delta.y()))
            self.prepareGeometryChange()
            self.setRect(new_rect)
            self._sync_field_geometry()
            self.update()
            event.accept()
            return
        super().mouseMoveEvent(event)
        self._sync_field_geometry()

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._resizing:
            self._resizing = False
            self._sync_field_geometry()
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self._sync_field_geometry()

    def itemChange(self, change: QGraphicsItem.GraphicsItemChange, value):  # noqa: N802
        result = super().itemChange(change, value)
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged:
            self._sync_field_geometry()
        return result

    # ------------------------------------------------------------------
    # Painting helpers
    # ------------------------------------------------------------------
    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: N802 - Qt API
        pen = QPen(QColor(0, 120, 215), 1.2, Qt.SolidLine)
        if self.isSelected():
            pen.setStyle(Qt.DashLine)
        painter.setPen(pen)
        painter.setBrush(Qt.transparent)
        painter.drawRect(self.rect())
        self._draw_preview(painter)
        painter.setBrush(Qt.white)
        painter.drawRect(self._handle_rect())

    def _draw_preview(self, painter: QPainter) -> None:
        font = QFont()
        if self.field.get("font_family"):
            font.setFamily(str(self.field["font_family"]))
        if self.field.get("font_size"):
            try:
                font.setPointSizeF(float(self.field["font_size"]))
            except (TypeError, ValueError):
                pass
        painter.setFont(font)
        painter.setPen(Qt.black)
        painter.drawText(self.rect().adjusted(2, 0, -2, 0), Qt.AlignVCenter | Qt.AlignLeft, self.field.get("name", ""))

    # ------------------------------------------------------------------
    # API helpers
    # ------------------------------------------------------------------
    def to_field_dict(self) -> dict[str, Any]:
        self._sync_field_geometry()
        return self.field


class CheckboxFieldItem(FieldItem):
    type_name = "checkbox"

    def _draw_preview(self, painter: QPainter) -> None:
        rect = self.rect()
        box_size = min(rect.width(), rect.height()) * 0.7
        box_rect = QRectF(rect.left() + 4, rect.center().y() - box_size / 2, box_size, box_size)
        painter.setPen(QPen(Qt.black, 1.0))
        painter.drawRect(box_rect)
        painter.drawText(rect.adjusted(box_size + 8, 0, -2, 0), Qt.AlignVCenter | Qt.AlignLeft, self.field.get("name", "Checkbox"))


class RadioFieldItem(FieldItem):
    type_name = "radio"

    def _draw_preview(self, painter: QPainter) -> None:
        rect = self.rect()
        radius = min(rect.width(), rect.height()) * 0.35
        center = QPointF(rect.left() + radius + 6, rect.center().y())
        painter.setPen(QPen(Qt.black, 1.0))
        painter.drawEllipse(center, radius, radius)
        painter.drawText(rect.adjusted(radius * 2 + 12, 0, -2, 0), Qt.AlignVCenter | Qt.AlignLeft, self.field.get("name", "Radio"))


class DropdownFieldItem(FieldItem):
    type_name = "dropdown"

    def _draw_preview(self, painter: QPainter) -> None:
        rect = self.rect()
        painter.setPen(QPen(Qt.black, 1.0))
        painter.drawRect(rect.adjusted(0, rect.height() * 0.2, 0, -rect.height() * 0.2))
        painter.drawText(rect.adjusted(4, 0, -20, 0), Qt.AlignVCenter | Qt.AlignLeft, self.field.get("name", "Dropdown"))
        triangle = QPolygonF(
            [
                QPointF(rect.right() - 14, rect.center().y() - 4),
                QPointF(rect.right() - 6, rect.center().y() - 4),
                QPointF(rect.right() - 10, rect.center().y() + 2),
            ]
        )
        painter.setBrush(Qt.black)
        painter.drawPolygon(triangle)


class MultilineFieldItem(FieldItem):
    type_name = "multiline"

    def _draw_preview(self, painter: QPainter) -> None:
        rect = self.rect()
        painter.setPen(QPen(Qt.darkGray, 0.6, Qt.DashLine))
        line_y = rect.top() + rect.height() / 3
        for _ in range(2):
            painter.drawLine(rect.left() + 4, line_y, rect.right() - 4, line_y)
            line_y += rect.height() / 3


class SignatureFieldItem(FieldItem):
    type_name = "signature"

    def _draw_preview(self, painter: QPainter) -> None:
        rect = self.rect()
        painter.setPen(QPen(Qt.darkBlue, 1.2, Qt.SolidLine))
        painter.drawLine(rect.left() + 4, rect.bottom() - 6, rect.right() - 4, rect.bottom() - 6)
        painter.drawText(rect.adjusted(4, 0, -4, 0), Qt.AlignLeft | Qt.AlignVCenter, "Signature")


class DateFieldItem(FieldItem):
    type_name = "date"


class TimeFieldItem(FieldItem):
    type_name = "time"


class ImageFieldItem(FieldItem):
    type_name = "image"

    def _draw_preview(self, painter: QPainter) -> None:
        rect = self.rect()
        painter.setPen(QPen(Qt.darkGray, 1.0))
        painter.drawRect(rect.adjusted(4, 4, -4, -4))
        painter.drawText(rect, Qt.AlignCenter, "IMG")


class TableFieldItem(FieldItem):
    type_name = "table"

    def _draw_preview(self, painter: QPainter) -> None:
        rect = self.rect()
        painter.setPen(QPen(Qt.darkGray, 0.8))
        rows = int(max(1, rect.height() // 24))
        row_height = rect.height() / max(1, rows)
        y = rect.top()
        for _ in range(rows):
            painter.drawRect(rect.left(), y, rect.width(), row_height)
            y += row_height


FIELD_ITEM_TYPES: Dict[str, Type[FieldItem]] = {
    "text": FieldItem,
    "multiline": MultilineFieldItem,
    "date": DateFieldItem,
    "time": TimeFieldItem,
    "checkbox": CheckboxFieldItem,
    "radio": RadioFieldItem,
    "dropdown": DropdownFieldItem,
    "signature": SignatureFieldItem,
    "image": ImageFieldItem,
    "table": TableFieldItem,
}


def create_field_item(field: dict[str, Any]) -> FieldItem:
    """Factory helper that instantiates the correct graphics item."""

    cls = FIELD_ITEM_TYPES.get(field.get("type", "text"), FieldItem)
    return cls(field, page=int(field.get("page", 1)))


__all__ = ["FieldItem", "FIELD_ITEM_TYPES", "create_field_item"]

