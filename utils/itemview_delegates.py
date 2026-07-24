from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QPen, QColor, QPainter
from PySide6.QtWidgets import QStyledItemDelegate, QStyleOptionViewItem, QStyle, QTableWidget


def _first_visible_column(view) -> int:
    model = view.model()
    if model is None:
        return 0
    for col in range(model.columnCount()):
        try:
            if not view.isColumnHidden(col):
                return col
        except Exception:
            return col
    return 0


def _last_visible_column(view) -> int:
    model = view.model()
    if model is None:
        return 0
    for col in range(model.columnCount() - 1, -1, -1):
        try:
            if not view.isColumnHidden(col):
                return col
        except Exception:
            return col
    return 0


def _paint_row_outline_segment(
    painter: QPainter,
    option: QStyleOptionViewItem,
    index,
    view,
    pen: QPen,
) -> None:
    rect = option.rect.adjusted(0, 1, 0, -1)
    if rect.isNull():
        return

    first_col = _first_visible_column(view)
    last_col = _last_visible_column(view)
    is_first = index.column() == first_col
    is_last = index.column() == last_col
    if is_first:
        rect.setLeft(rect.left() + 1)
    if is_last:
        rect.setRight(rect.right() - 1)

    painter.save()
    painter.setPen(pen)
    painter.setBrush(Qt.BrushStyle.NoBrush)
    painter.drawLine(rect.topLeft(), rect.topRight())
    painter.drawLine(rect.bottomLeft(), rect.bottomRight())
    if is_first:
        painter.drawLine(rect.topLeft(), rect.bottomLeft())
    if is_last:
        painter.drawLine(rect.topRight(), rect.bottomRight())
    painter.restore()


class RowOutlineSelectionDelegate(QStyledItemDelegate):
    """Paint selection as an outline across the entire row.

    Removes the default filled selection so per-row background colors remain
    visible, then draws a high-contrast outline segment around the selected
    row. Attach to a QTableView/QTableWidget via ``setItemDelegate``.
    """

    def __init__(self, view, color: QColor, width: int = 2, radius: int = 3):
        super().__init__(view)
        self._view = view
        self._pen = QPen(color)
        self._pen.setWidth(width)
        self._radius = radius
        self._wrap_column_delegate_setter()

    def setColor(self, color: QColor) -> None:
        self._pen.setColor(color)
        for delegate in getattr(self._view, "_row_outline_column_delegates", []):
            try:
                delegate.setColor(color)
            except Exception:
                pass

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
            _paint_row_outline_segment(painter, option, index, self._view, self._pen)
        except Exception:
            # Never let painting errors break the view
            pass

    def _wrap_column_delegate_setter(self) -> None:
        if getattr(self._view, "_row_outline_wraps_column_delegates", False):
            return
        try:
            original = self._view.setItemDelegateForColumn
        except Exception:
            return

        def set_item_delegate_for_column(column, delegate):
            if delegate is not None and not isinstance(delegate, IconWithOutlineDelegate):
                delegate = IconWithOutlineDelegate(
                    delegate,
                    self._view,
                    self._pen.color(),
                    self._pen.width(),
                    self._radius,
                )
                wrappers = getattr(self._view, "_row_outline_column_delegates", None)
                if wrappers is None:
                    wrappers = []
                    setattr(self._view, "_row_outline_column_delegates", wrappers)
                wrappers.append(delegate)
            return original(column, delegate)

        self._view.setItemDelegateForColumn = set_item_delegate_for_column
        self._view._row_outline_wraps_column_delegates = True  # type: ignore[attr-defined]


class IconWithOutlineDelegate(QStyledItemDelegate):
    """Wrapper that renders an inner delegate (e.g., an icon) and then draws
    a row outline segment for selections. Ensures the outline appears even
    when a special column delegate repaints the clicked/current cell.
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
            _paint_row_outline_segment(painter, option, index, self._view, self._pen)
        except Exception:
            pass


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
