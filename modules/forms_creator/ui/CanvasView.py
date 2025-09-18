"""Graphics view widget hosting the form designer canvas."""
from __future__ import annotations

from typing import Any, Iterable

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPen, QPixmap, QWheelEvent
from PySide6.QtWidgets import QGraphicsPixmapItem, QGraphicsScene, QGraphicsView

from .FieldItems import FieldItem, create_field_item


class CanvasView(QGraphicsView):
    """Designer surface with background pages and field items."""

    fieldSelected = Signal(object)
    pageChanged = Signal(int)

    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        scene = QGraphicsScene(self)
        scene.setSceneRect(QRectF(0, 0, 2000, 2000))
        self.setScene(scene)
        self.setRenderHints(QPainter.Antialiasing | QPainter.SmoothPixmapTransform)
        self.setViewportUpdateMode(QGraphicsView.FullViewportUpdate)
        self.setDragMode(QGraphicsView.RubberBandDrag)

        self._zoom = 1.0
        self._snap_enabled = True
        self._grid_visible = True
        self._grid_size = 10
        self._background_items: list[QGraphicsPixmapItem] = []
        self._field_items: list[FieldItem] = []
        self._current_page_index = 0
        self._panning = False
        self._space_pressed = False
        self._last_pan_point = QPoint()

        scene.selectionChanged.connect(self._on_selection_changed)

    # ------------------------------------------------------------------
    # Background management
    # ------------------------------------------------------------------
    def set_backgrounds(self, pixmaps: Iterable[str | QPixmap]) -> None:
        """Load background images for the canvas."""

        for item in self._background_items:
            self.scene().removeItem(item)
        self._background_items.clear()
        for index, path in enumerate(pixmaps):
            if isinstance(path, QPixmap):
                pixmap = path
            else:
                pixmap = QPixmap(str(path))
            pixmap_item = QGraphicsPixmapItem(pixmap)
            pixmap_item.setZValue(-100)
            pixmap_item.setVisible(index == 0)
            self.scene().addItem(pixmap_item)
            self._background_items.append(pixmap_item)
            if index == 0 and not pixmap.isNull():
                self.scene().setSceneRect(pixmap.rect())
        self._current_page_index = 0
        self.pageChanged.emit(1)

    def set_page(self, page_index: int) -> None:
        if page_index < 0 or page_index >= len(self._background_items):
            return
        self._current_page_index = page_index
        for index, item in enumerate(self._background_items):
            item.setVisible(index == page_index)
        for item in self._field_items:
            item.setVisible(int(item.field.get("page", 1)) - 1 == page_index)
        self.pageChanged.emit(page_index + 1)

    # ------------------------------------------------------------------
    # Field management
    # ------------------------------------------------------------------
    def clear_fields(self) -> None:
        for item in list(self._field_items):
            self.scene().removeItem(item)
        self._field_items.clear()

    def set_fields(self, fields: list[dict[str, Any]]) -> None:
        self.clear_fields()
        for field in fields:
            self.add_field(field)

    def add_field(self, field: dict[str, Any]) -> FieldItem:
        item = create_field_item(field)
        item.setZValue(50)
        self.scene().addItem(item)
        self._field_items.append(item)
        item.setVisible(int(field.get("page", 1)) - 1 == self._current_page_index)
        return item

    def selected_field(self) -> FieldItem | None:
        items = [item for item in self.scene().selectedItems() if isinstance(item, FieldItem)]
        return items[0] if items else None

    def delete_selected_fields(self) -> list[dict[str, Any]]:
        removed: list[dict[str, Any]] = []
        for item in list(self.scene().selectedItems()):
            if isinstance(item, FieldItem):
                removed.append(item.to_field_dict())
                self.scene().removeItem(item)
                if item in self._field_items:
                    self._field_items.remove(item)
        self.fieldSelected.emit(None)
        return removed

    def fields_as_dict(self) -> list[dict[str, Any]]:
        return [item.to_field_dict() for item in self._field_items]

    # ------------------------------------------------------------------
    # Interaction helpers
    # ------------------------------------------------------------------
    def toggle_snap(self, enabled: bool) -> None:
        self._snap_enabled = enabled

    def toggle_grid(self, visible: bool) -> None:
        self._grid_visible = visible
        self.viewport().update()

    def zoom_to(self, factor: float) -> None:
        self.resetTransform()
        self.scale(factor, factor)
        self._zoom = factor

    def zoom_in(self) -> None:
        self.zoom_to(min(self._zoom * 1.2, 6.0))

    def zoom_out(self) -> None:
        self.zoom_to(max(self._zoom / 1.2, 0.2))

    def fit_to_window(self) -> None:
        if self._background_items:
            rect = self._background_items[self._current_page_index].boundingRect()
            self.fitInView(rect, Qt.KeepAspectRatio)
            self._zoom = self.transform().m11()

    # ------------------------------------------------------------------
    # Qt overrides
    # ------------------------------------------------------------------
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802
        if event.modifiers() & Qt.ControlModifier:
            delta = 1.2 if event.angleDelta().y() > 0 else 1 / 1.2
            self.zoom_to(min(max(self._zoom * delta, 0.2), 6.0))
            event.accept()
            return
        super().wheelEvent(event)

    def keyPressEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Space:
            self._space_pressed = True
            self.setCursor(Qt.OpenHandCursor)
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event) -> None:  # noqa: N802
        if event.key() == Qt.Key_Space:
            self._space_pressed = False
            self.setCursor(Qt.ArrowCursor)
            event.accept()
            return
        super().keyReleaseEvent(event)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MiddleButton or (event.button() == Qt.LeftButton and self._space_pressed):
            self._panning = True
            self._last_pan_point = event.pos()
            self.setCursor(Qt.ClosedHandCursor)
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # noqa: N802
        if self._panning:
            delta = event.pos() - self._last_pan_point
            self._last_pan_point = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if self._panning:
            self._panning = False
            self.setCursor(Qt.OpenHandCursor if self._space_pressed else Qt.ArrowCursor)
            event.accept()
            return
        super().mouseReleaseEvent(event)
        self._apply_snap_to_selected()

    def drawForeground(self, painter: QPainter, rect: QRectF) -> None:  # noqa: N802
        super().drawForeground(painter, rect)
        if not self._grid_visible:
            return
        pen = QPen(QColor(225, 225, 225))
        painter.setPen(pen)
        grid = self._grid_size
        left = int(rect.left()) - (int(rect.left()) % grid)
        top = int(rect.top()) - (int(rect.top()) % grid)
        x = left
        while x < rect.right():
            painter.drawLine(x, rect.top(), x, rect.bottom())
            x += grid
        y = top
        while y < rect.bottom():
            painter.drawLine(rect.left(), y, rect.right(), y)
            y += grid

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _apply_snap_to_selected(self) -> None:
        if not self._snap_enabled:
            return
        for item in self.scene().selectedItems():
            if isinstance(item, FieldItem):
                pos = item.pos()
                snapped = self._snap_point(pos)
                if snapped != pos:
                    item.setPos(snapped)
                    item.to_field_dict()

    def _snap_point(self, point: QPointF) -> QPointF:
        grid = self._grid_size
        x = round(point.x() / grid) * grid
        y = round(point.y() / grid) * grid
        return QPointF(x, y)

    def _on_selection_changed(self) -> None:
        self.fieldSelected.emit(self.selected_field())

