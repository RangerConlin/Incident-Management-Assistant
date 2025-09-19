"""Preview dialog for templates."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from PySide6.QtGui import QColor, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QDialog, QDialogButtonBox, QLabel, QVBoxLayout


class PreviewDialog(QDialog):
    """Renders a lightweight preview of the first template page."""

    def __init__(self, template: dict[str, Any], *, data_dir: Path | str = Path("data"), parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Template Preview")
        layout = QVBoxLayout(self)

        pixmap = self._render_preview(template, Path(data_dir))
        label = QLabel()
        label.setPixmap(pixmap)
        layout.addWidget(label)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        buttons.accepted.connect(self.accept)
        layout.addWidget(buttons)

    def _render_preview(self, template: dict[str, Any], data_dir: Path) -> QPixmap:
        background = Path(template.get("background_path", ""))
        if not background.is_absolute():
            background = data_dir / background
        image_path = background / "background_page_001.png"
        base = QImage(str(image_path))
        if base.isNull():
            base = QImage(800, 600, QImage.Format.Format_ARGB32)
            base.fill(QColor("white"))
        painter = QPainter(base)
        painter.setPen(QColor(0, 0, 0))
        for field in template.get("fields", []):
            if int(field.get("page", 1)) != 1:
                continue
            rect = (field.get("x", 0), field.get("y", 0), field.get("width", 0), field.get("height", 0))
            painter.drawRect(*rect)
            value = field.get("default_value", "")
            painter.drawText(rect[0] + 2, rect[1] + rect[3] / 2, str(value))
        painter.end()
        return QPixmap.fromImage(base)
