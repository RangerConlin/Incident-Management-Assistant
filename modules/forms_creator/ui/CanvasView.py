"""Graphics view used as the form designer canvas."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QContextMenuEvent, QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView, QMenu

from .FieldItems import FieldItem


class CanvasView(QGraphicsView):
    """A QGraphicsView with handy zoom and pan controls."""

    fieldDrawn = Signal(QRectF)
    fieldCreationAborted = Signal()
    fieldDeleteRequested = Signal(int)

    def __init__(self, scene: QGraphicsScene | None = None, parent=None) -> None:
        super().__init__(parent)
        scene = scene or QGraphicsScene(self)
        self.setScene(scene)
        self._scene = scene
        self.setRenderHints(self.renderHints() | QPainter.RenderHint.Antialiasing)
        self.setDragMode(QGraphicsView.DragMode.RubberBandDrag)
        self.setTransformationAnchor(QGraphicsView.ViewportAnchor.AnchorUnderMouse)
        self.setViewportUpdateMode(QGraphicsView.ViewportUpdateMode.FullViewportUpdate)
        self._panning = False
        self._pan_start = QPoint()
        self._zoom = 1.0
        self._draw_enabled = False
        self._drawing = False
        self._draw_start = QPointF()
        self._draw_rect: QGraphicsRectItem | None = None
        self._space_pressed = False

    # ------------------------------------------------------------------
    def wheelEvent(self, event: QWheelEvent) -> None:  # noqa: N802 (Qt naming convention)
        if event.modifiers() & Qt.KeyboardModifier.ControlModifier:
            delta = event.angleDelta().y()
            factor = 1.2 if delta > 0 else 0.8
            self._apply_zoom(factor)
            event.accept()
        else:
            super().wheelEvent(event)

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.MiddleButton or (
            event.button() == Qt.MouseButton.LeftButton and self._space_pressed
        ):
            self._panning = True
            self._pan_start = event.pos()
            self._update_idle_cursor()
            event.accept()
            return
        if self._draw_enabled and event.button() == Qt.MouseButton.LeftButton:
            self._drawing = True
            self._draw_start = self.mapToScene(event.position().toPoint())
            if self._draw_rect is not None:
                self._scene.removeItem(self._draw_rect)
            initial_rect = QRectF(self._draw_start, self._draw_start)
            self._draw_rect = self._scene.addRect(initial_rect)
            pen = QPen(self._draw_rect.pen())
            pen.setStyle(Qt.PenStyle.DashLine)
            pen.setWidthF(1.0)
            self._draw_rect.setPen(pen)
            self._draw_rect.setBrush(Qt.BrushStyle.NoBrush)
            event.accept()
            return
        if event.button() == Qt.MouseButton.LeftButton and not self._draw_enabled:
            item = self.itemAt(event.position().toPoint())
            field_item = self._field_item_from_graphics_item(item)
            if field_item is not None:
                modifiers = event.modifiers()
                extend_selection = bool(
                    modifiers
                    & (
                        Qt.KeyboardModifier.ControlModifier
                        | Qt.KeyboardModifier.ShiftModifier
                    )
                )
                scene = self.scene()
                if scene is not None and not extend_selection:
                    scene.clearSelection()
                if modifiers & Qt.KeyboardModifier.ControlModifier:
                    field_item.setSelected(not field_item.isSelected())
                else:
                    field_item.setSelected(True)
                if scene is not None:
                    scene.setFocusItem(field_item)
                self.setFocus()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._panning:
            delta = event.pos() - self._pan_start
            self._pan_start = event.pos()
            self.horizontalScrollBar().setValue(self.horizontalScrollBar().value() - delta.x())
            self.verticalScrollBar().setValue(self.verticalScrollBar().value() - delta.y())
            event.accept()
            return
        if self._draw_enabled and self._drawing and self._draw_rect is not None:
            scene_pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._draw_start, scene_pos).normalized()
            self._draw_rect.setRect(rect)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if self._panning and event.button() in {
            Qt.MouseButton.MiddleButton,
            Qt.MouseButton.LeftButton,
        }:
            self._panning = False
            self._update_idle_cursor()
            event.accept()
            return
        if self._draw_enabled and self._drawing and event.button() == Qt.MouseButton.LeftButton:
            self._drawing = False
            scene_pos = self.mapToScene(event.position().toPoint())
            rect = QRectF(self._draw_start, scene_pos).normalized()
            if self._draw_rect is not None:
                self._scene.removeItem(self._draw_rect)
                self._draw_rect = None
            if rect.width() < 1.0 and rect.height() < 1.0:
                rect = QRectF(self._draw_start.x(), self._draw_start.y(), 150.0, 24.0)
            rect = rect.normalized()
            self.fieldDrawn.emit(rect)
            self._update_idle_cursor()
            event.accept()
            return
        super().mouseReleaseEvent(event)

    def contextMenuEvent(self, event: QContextMenuEvent) -> None:  # noqa: N802
        item = self.itemAt(event.pos())
        field_item = self._field_item_from_graphics_item(item)
        menu = QMenu(self)
        delete_action = menu.addAction("Delete Field")
        delete_action.setEnabled(field_item is not None)
        event.accept()
        chosen = menu.exec(event.globalPos())
        if chosen == delete_action and field_item is not None:
            field_id = field_item.field.get("id")
            try:
                field_key = int(field_id)
            except (TypeError, ValueError):
                return
            self.fieldDeleteRequested.emit(field_key)

    # ------------------------------------------------------------------
    def begin_field_creation(self, _field_type: str | None = None) -> None:
        """Enable drawing mode so a new field can be sketched on the canvas."""

        self._draw_enabled = True
        self._drawing = False
        self._draw_start = QPointF()
        self._update_idle_cursor()

    def cancel_field_creation(self) -> None:
        """Leave drawing mode and clean up any preview artefacts."""

        self._draw_enabled = False
        self._drawing = False
        self._draw_start = QPointF()
        if self._draw_rect is not None:
            self._scene.removeItem(self._draw_rect)
            self._draw_rect = None
        self._update_idle_cursor()

    # ------------------------------------------------------------------
    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Space:
            if not self._space_pressed:
                self._space_pressed = True
                self._update_idle_cursor()
            event.accept()
            return
        if event.key() == Qt.Key.Escape and self._draw_enabled:
            self.cancel_field_creation()
            self.fieldCreationAborted.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    def keyReleaseEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Space:
            self._space_pressed = False
            self._update_idle_cursor()
            event.accept()
            return
        super().keyReleaseEvent(event)

    # ------------------------------------------------------------------
    def reset_zoom(self) -> None:
        """Reset the view transformation to 100%."""

        self._zoom = 1.0
        self.resetTransform()

    def _apply_zoom(self, factor: float) -> None:
        self._zoom *= factor
        self.scale(factor, factor)

    # ------------------------------------------------------------------
    def _field_item_from_graphics_item(self, item) -> FieldItem | None:
        """Return the FieldItem for ``item`` or its parent chain."""

        while item is not None and not isinstance(item, FieldItem):
            item = item.parentItem()
        return item if isinstance(item, FieldItem) else None

    def _update_idle_cursor(self) -> None:
        """Set the cursor based on the current interaction state."""

        if self._panning:
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
        elif self._space_pressed:
            self.setCursor(Qt.CursorShape.OpenHandCursor)
        elif self._draw_enabled:
            self.setCursor(Qt.CursorShape.CrossCursor)
        else:
            self.setCursor(Qt.CursorShape.ArrowCursor)
