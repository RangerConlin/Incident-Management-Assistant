from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle, QTableWidget


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
            if index.column() != self._first_visible_column():
                return

            row_rect = self._row_rect_for(index.row())
            if row_rect.isNull():
                return

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

    def _first_visible_column(self) -> int:
        model = self._view.model()
        if model is None:
            return 0
        for col in range(model.columnCount()):
            try:
                if not self._view.isColumnHidden(col):
                    return col
            except Exception:
                return col
        return 0

    def _row_rect_for(self, row: int):
        model = self._view.model()
        if model is None or model.columnCount() <= 0:
            return self._view.visualRect(self._view.model().index(row, 0)) if model is not None else None
        first_col = self._first_visible_column()
        last_col = first_col
        for col in range(model.columnCount() - 1, -1, -1):
            try:
                if not self._view.isColumnHidden(col):
                    last_col = col
                    break
            except Exception:
                last_col = col
                break
        first_rect = self._view.visualRect(model.index(row, first_col))
        last_rect = self._view.visualRect(model.index(row, last_col))
        row_rect = first_rect.united(last_rect)
        row_rect = row_rect.intersected(self._view.viewport().rect())
        return row_rect.adjusted(1, 1, -1, -1)


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
            if index.column() != self._first_visible_column():
                return

            row_rect = self._row_rect_for(index.row())
            if row_rect.isNull():
                return
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

    def _first_visible_column(self) -> int:
        model = self._view.model()
        if model is None:
            return 0
        for col in range(model.columnCount()):
            try:
                if not self._view.isColumnHidden(col):
                    return col
            except Exception:
                return col
        return 0

    def _row_rect_for(self, row: int):
        model = self._view.model()
        if model is None or model.columnCount() <= 0:
            return self._view.visualRect(self._view.model().index(row, 0)) if model is not None else None
        first_col = self._first_visible_column()
        last_col = first_col
        for col in range(model.columnCount() - 1, -1, -1):
            try:
                if not self._view.isColumnHidden(col):
                    last_col = col
                    break
            except Exception:
                last_col = col
                break
        first_rect = self._view.visualRect(model.index(row, first_col))
        last_rect = self._view.visualRect(model.index(row, last_col))
        row_rect = first_rect.united(last_rect)
        row_rect = row_rect.intersected(self._view.viewport().rect())
        return row_rect.adjusted(1, 1, -1, -1)


class RowOutlineTableWidget(QTableWidget):
    """QTableWidget that paints a row outline after the normal cells render."""

    def __init__(self, *args, outline_color: QColor | None = None, outline_width: int = 2, outline_radius: int = 3):
        super().__init__(*args)
        self._outline_color = outline_color or QColor("#3b82f6")
        self._outline_width = outline_width
        self._outline_radius = outline_radius

    def setOutlineColor(self, color: QColor) -> None:
        self._outline_color = QColor(color)
        self.viewport().update()

    def paintEvent(self, event):  # type: ignore[override]
        super().paintEvent(event)
        try:
            selection_model = self.selectionModel()
            if selection_model is None:
                return
            rows = selection_model.selectedRows()
            if not rows:
                return

            painter = QPainter(self.viewport())
            painter.setRenderHint(QPainter.Antialiasing)
            pen = QPen(self._outline_color)
            pen.setWidth(self._outline_width)
            painter.setPen(pen)
            painter.setBrush(Qt.BrushStyle.NoBrush)

            model = self.model()
            if model is None:
                return

            for index in rows:
                row = index.row()
                first_col = None
                last_col = None
                for col in range(model.columnCount()):
                    if not self.isColumnHidden(col):
                        first_col = col
                        break
                for col in range(model.columnCount() - 1, -1, -1):
                    if not self.isColumnHidden(col):
                        last_col = col
                        break
                if first_col is None or last_col is None:
                    continue
                first_rect = self.visualRect(model.index(row, first_col))
                last_rect = self.visualRect(model.index(row, last_col))
                row_rect = first_rect.united(last_rect).intersected(self.viewport().rect()).adjusted(1, 1, -1, -1)
                if row_rect.isNull():
                    continue
                try:
                    painter.drawRoundedRect(row_rect, self._outline_radius, self._outline_radius)
                except Exception:
                    painter.drawRect(row_rect)
            painter.end()
        except Exception:
            pass
