"""CardWidget — base styled container used throughout the Intel Module.

A CardWidget is a rounded, padded QFrame that groups related information.
It provides a consistent visual container without enforcing any specific layout.
Subclass it or instantiate it directly and add children to its layout.
"""

from __future__ import annotations

from PySide6.QtWidgets import QFrame, QVBoxLayout, QWidget
from PySide6.QtCore import Qt


class CardWidget(QFrame):
    """Rounded, padded card container with a raised background.

    Usage::

        card = CardWidget()
        card.layout().addWidget(QLabel("Content"))
        card.setFixedWidth(300)
    """

    def __init__(
        self,
        parent: QWidget | None = None,
        *,
        padding: int = 14,
        accent_left: str | None = None,   # Optional left-border accent color (CSS hex)
        clickable: bool = False,
    ) -> None:
        super().__init__(parent)
        self._accent_left = accent_left
        self._clickable = clickable

        self.setFrameShape(QFrame.StyledPanel)
        self.setFrameShadow(QFrame.Plain)
        self._apply_style()

        self._layout = QVBoxLayout(self)
        self._layout.setContentsMargins(padding, padding, padding, padding)
        self._layout.setSpacing(6)

        if clickable:
            self.setCursor(Qt.PointingHandCursor)

    def _apply_style(self) -> None:
        left_border = (
            f"border-left: 4px solid {self._accent_left}; border-radius: 0 8px 8px 0;"
            if self._accent_left
            else "border-radius: 8px;"
        )
        self.setStyleSheet(f"""
            CardWidget {{
                background: palette(base);
                {left_border}
                border: 1px solid palette(mid);
            }}
            CardWidget:hover {{
                border: 1px solid palette(highlight);
            }}
        """)

    def set_accent(self, color: str | None) -> None:
        """Change the left-border accent color and repaint."""
        self._accent_left = color
        self._apply_style()
        self.update()

    # Pass through layout() so callers can do card.layout().addWidget(...)
    def layout(self) -> QVBoxLayout:  # type: ignore[override]
        return self._layout
