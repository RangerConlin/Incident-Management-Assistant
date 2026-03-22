from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle


class RowOutlineSelectionDelegate(QStyledItemDelegate):
    """Paint selection as an outline across the entire row.

    Removes the default filled selection so per-row background colors remain
    visible, then draws a high-contrast rounded rectangle around the selected
    row. Attach to a QTableView/QTableWidget via ``setItemDelegate``.
    """

    def __init__(self, view, color: QColor, width: int = 2, radius: int = 3):
        super().__init__(view)
        self._view = view
        self._pen = QPen(color)
        self._pen.setWidth(width)
        self._radius = radius

    def setColor(self, color: QColor) -> None:
        self._pen.setColor(color)

    def paint(self, painter, option: QStyleOptionViewItem, index):  # type: ignore[override]
        # Suppress the default filled selection and focus rect so cell-level
        # highlights don't fight the row outline.
        selected = bool(option.state & QStyle.State_Selected)
        opt = QStyleOptionViewItem(option)
        if selected:
            opt.state &= ~QStyle.State_Selected
            opt.state &= ~QStyle.State_HasFocus
        super().paint(painter, opt, index)

        if not selected:
            return

        try:
            model = self._view.model()
            last_col = max(0, model.columnCount() - 1) if model is not None else index.column()
            first_rect = self._view.visualRect(index.sibling(index.row(), 0))
            last_rect = self._view.visualRect(index.sibling(index.row(), last_col))
            row_rect = first_rect.united(last_rect)
            # Clamp to the viewport
            row_rect = row_rect.intersected(self._view.viewport().rect())
            # Inset so the stroke is fully visible
            row_rect = row_rect.adjusted(1, 1, -1, -1)

            painter.save()
            painter.setPen(self._pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            try:
                painter.drawRoundedRect(row_rect, self._radius, self._radius)
            except Exception:
                painter.drawRect(row_rect)
            painter.restore()
        except Exception:
            # Never let painting errors break the view
            pass


class IconWithOutlineDelegate(QStyledItemDelegate):
    """Wrapper that renders an inner delegate (e.g., an icon) and then draws
    a row outline for selections. Ensures the outline appears even when only
    the special column repaints.
    """

    def __init__(self, inner: QStyledItemDelegate, view, color: QColor, width: int = 2, radius: int = 3):
        super().__init__(view)
        self._inner = inner
        self._view = view
        self._pen = QPen(color)
        self._pen.setWidth(width)
        self._radius = radius

    def setColor(self, color: QColor) -> None:
        self._pen.setColor(color)

    def paint(self, painter, option: QStyleOptionViewItem, index):  # type: ignore[override]
        selected = bool(option.state & QStyle.State_Selected)
        # Suppress cell-level selection/focus for the inner delegate
        opt = QStyleOptionViewItem(option)
        if selected:
            opt.state &= ~QStyle.State_Selected
            opt.state &= ~QStyle.State_HasFocus
        try:
            self._inner.paint(painter, opt, index)
        except Exception:
            super().paint(painter, opt, index)

        if not selected:
            return

        try:
            model = self._view.model()
            last_col = max(0, model.columnCount() - 1) if model is not None else index.column()
            first_rect = self._view.visualRect(index.sibling(index.row(), 0))
            last_rect = self._view.visualRect(index.sibling(index.row(), last_col))
            row_rect = first_rect.united(last_rect)
            row_rect = row_rect.intersected(self._view.viewport().rect())
            row_rect = row_rect.adjusted(1, 1, -1, -1)
            painter.save()
            painter.setPen(self._pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)
            try:
                painter.drawRoundedRect(row_rect, self._radius, self._radius)
            except Exception:
                painter.drawRect(row_rect)
            painter.restore()
        except Exception:
            pass
