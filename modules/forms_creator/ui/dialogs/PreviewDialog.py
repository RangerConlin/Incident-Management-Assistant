"""Preview dialog that renders the template with sample data."""
from __future__ import annotations

from pathlib import Path
from typing import Any, Iterable

from PySide6.QtCore import Qt, QRectF
from PySide6.QtGui import QColor, QFont, QImage, QPainter, QPen, QPixmap
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
)


class PreviewDialog(QDialog):
    """Display each page of the template with overlayed field values."""

    def __init__(
        self,
        background_paths: Iterable[Path],
        fields: list[dict[str, Any]],
        values: dict[int, Any] | None = None,
        parent=None,
    ) -> None:
        super().__init__(parent)
        self.setWindowTitle("Template Preview")
        self._paths = list(background_paths)
        self._fields = fields
        self._values = values or {}

        self._stack = QStackedWidget()
        for index, path in enumerate(self._paths, start=1):
            pixmap = QPixmap(str(path))
            if pixmap.isNull():
                pixmap = QPixmap(850, 1100)
                pixmap.fill(Qt.white)
            composed = self._compose_page(pixmap, index)
            label = QLabel()
            label.setPixmap(composed)
            label.setAlignment(Qt.AlignCenter)
            self._stack.addWidget(label)

        self._page_label = QLabel(self._page_text(1))
        self._page_label.setAlignment(Qt.AlignCenter)

        previous_button = QPushButton("Previous")
        next_button = QPushButton("Next")
        previous_button.clicked.connect(self._previous_page)
        next_button.clicked.connect(self._next_page)

        controls = QHBoxLayout()
        controls.addWidget(previous_button)
        controls.addWidget(self._page_label)
        controls.addWidget(next_button)

        layout = QVBoxLayout(self)
        layout.addWidget(self._stack)
        layout.addLayout(controls)

    # ------------------------------------------------------------------
    def _compose_page(self, background: QPixmap, page_number: int) -> QPixmap:
        image = QImage(background.size(), QImage.Format_ARGB32)
        image.fill(Qt.white)
        painter = QPainter(image)
        painter.drawPixmap(0, 0, background)

        scale_x = image.width() / background.width()
        scale_y = image.height() / background.height()

        painter.setPen(QPen(QColor(0, 120, 215), 1, Qt.DashLine))
        for field in self._fields:
            if int(field.get("page", 1)) != page_number:
                continue
            rect = field
            x = float(rect.get("x", 0))
            y = float(rect.get("y", 0))
            w = float(rect.get("width", 0))
            h = float(rect.get("height", 0))
            draw_rect = QRectF(x * scale_x, y * scale_y, w * scale_x, h * scale_y)
            painter.drawRect(draw_rect)
            value = self._values.get(int(field.get("id", 0)))
            if value is None:
                value = field.get("default_value", "")
            font = QFont()
            if field.get("font_family"):
                font.setFamily(str(field["font_family"]))
            if field.get("font_size"):
                try:
                    font.setPointSizeF(float(field["font_size"]))
                except (TypeError, ValueError):
                    pass
            painter.setFont(font)
            painter.setPen(Qt.black)
            painter.drawText(draw_rect, Qt.AlignLeft | Qt.AlignVCenter, str(value)[:120])
        painter.end()
        return QPixmap.fromImage(image)

    def _page_text(self, page: int) -> str:
        return f"Page {page} of {max(1, len(self._paths))}"

    def _previous_page(self) -> None:
        index = max(0, self._stack.currentIndex() - 1)
        self._stack.setCurrentIndex(index)
        self._page_label.setText(self._page_text(index + 1))

    def _next_page(self) -> None:
        index = min(self._stack.count() - 1, self._stack.currentIndex() + 1)
        self._stack.setCurrentIndex(index)
        self._page_label.setText(self._page_text(index + 1))

