"""QGraphicsItem subclasses representing form fields."""

from __future__ import annotations

from PySide6.QtCore import QRectF
from PySide6.QtGui import QColor, QPainter
from PySide6.QtWidgets import QGraphicsRectItem


class FieldItem(QGraphicsRectItem):
    """Base graphics item carrying field metadata."""

    def __init__(self, field: dict, parent=None) -> None:
        rect = QRectF(0, 0, float(field.get("width", 0)), float(field.get("height", 0)))
        super().__init__(rect, parent)
        self.field = field
        self.setFlags(
            QGraphicsRectItem.GraphicsItemFlag.ItemIsSelectable
            | QGraphicsRectItem.GraphicsItemFlag.ItemIsMovable
            | QGraphicsRectItem.GraphicsItemFlag.ItemSendsGeometryChanges
        )
        self.setBrush(QColor(0, 120, 215, 40))
        self.setPen(QColor(0, 120, 215))
        self.setPos(float(field.get("x", 0)), float(field.get("y", 0)))

    def itemChange(self, change, value):  # noqa: N802 - Qt API
        if change == QGraphicsRectItem.GraphicsItemChange.ItemPositionChange:
            pos = value
            self.field["x"] = pos.x()
            self.field["y"] = pos.y()
        elif change == QGraphicsRectItem.GraphicsItemChange.ItemPositionHasChanged:
            pos = self.pos()
            self.field["x"] = pos.x()
            self.field["y"] = pos.y()
        return super().itemChange(change, value)

    def paint(self, painter: QPainter, option, widget=None) -> None:  # noqa: D401,N802
        painter.save()
        painter.setPen(self.pen())
        painter.setBrush(self.brush())
        painter.drawRect(self.rect())
        painter.restore()


class TextFieldItem(FieldItem):
    """Text entry field."""


class CheckboxFieldItem(FieldItem):
    """Checkbox field representation."""


class DropdownFieldItem(FieldItem):
    """Dropdown field representation."""
