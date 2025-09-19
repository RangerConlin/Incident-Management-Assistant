"""Graphics view used as the form designer canvas."""

from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRectF, Qt, Signal
from PySide6.QtGui import QMouseEvent, QPainter, QPen, QWheelEvent
from PySide6.QtWidgets import QGraphicsRectItem, QGraphicsScene, QGraphicsView


class CanvasView(QGraphicsView):
    """A QGraphicsView with handy zoom and pan controls."""

    fieldDrawn = Signal(QRectF)
    fieldCreationAborted = Signal()

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
            event.button() == Qt.MouseButton.LeftButton and event.modifiers() & Qt.KeyboardModifier.SpaceModifier
        ):
            self._panning = True
            self._pan_start = event.pos()
            self.setCursor(Qt.CursorShape.ClosedHandCursor)
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
            self.setCursor(Qt.CursorShape.ArrowCursor)
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
            event.accept()
            return
        super().mouseReleaseEvent(event)

    # ------------------------------------------------------------------
    def begin_field_creation(self, _field_type: str | None = None) -> None:
        """Enable drawing mode so a new field can be sketched on the canvas."""

        self._draw_enabled = True
        self._drawing = False
        self._draw_start = QPointF()
        self.setCursor(Qt.CursorShape.CrossCursor)

    def cancel_field_creation(self) -> None:
        """Leave drawing mode and clean up any preview artefacts."""

        self._draw_enabled = False
        self._drawing = False
        self._draw_start = QPointF()
        if self._draw_rect is not None:
            self._scene.removeItem(self._draw_rect)
            self._draw_rect = None
        self.setCursor(Qt.CursorShape.ArrowCursor)

    # ------------------------------------------------------------------
    def keyPressEvent(self, event):  # noqa: N802
        if event.key() == Qt.Key.Escape and self._draw_enabled:
            self.cancel_field_creation()
            self.fieldCreationAborted.emit()
            event.accept()
            return
        super().keyPressEvent(event)

    # ------------------------------------------------------------------
    def reset_zoom(self) -> None:
        """Reset the view transformation to 100%."""

        self._zoom = 1.0
        self.resetTransform()

    def _apply_zoom(self, factor: float) -> None:
        self._zoom *= factor
        self.scale(factor, factor)
