"""Design tokens for reusable styling primitives."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple

from PySide6.QtGui import QColor

# Alert levels -------------------------------------------------------------
ALERT_WARNING = "#F6C85B"  # 50-minute check-in threshold
ALERT_DANGER = "#F45B69"   # 60-minute overdue threshold

# Card surfaces ------------------------------------------------------------
CARD_BG = "#1f1f23"
CARD_BORDER = "#2a2a2e"
PILL_BG_MUTED = "#2d2d33"

# Icon sizing --------------------------------------------------------------
ICON_SIZE_SM = 16
ICON_SIZE_MD = 20

# Typography / layout helpers ---------------------------------------------
DEFAULT_PADDING = 12
SMALL_PADDING = 8
TINY_PADDING = 4
SECTION_SPACING = 10
CARD_RADIUS = 8


@dataclass(frozen=True)
class PaletteSwatch:
    """Utility swatch describing a foreground/background pairing."""

    fg: QColor
    bg: QColor

    def as_tuple(self) -> Tuple[QColor, QColor]:
        return self.fg, self.bg


__all__ = [
    "ALERT_WARNING",
    "ALERT_DANGER",
    "CARD_BG",
    "CARD_BORDER",
    "PILL_BG_MUTED",
    "ICON_SIZE_SM",
    "ICON_SIZE_MD",
    "DEFAULT_PADDING",
    "SMALL_PADDING",
    "TINY_PADDING",
    "SECTION_SPACING",
    "CARD_RADIUS",
    "PaletteSwatch",
]
