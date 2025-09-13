"""Utilities shared by theme adapters."""
from __future__ import annotations

from math import sqrt
from PySide6.QtGui import QColor, QBrush


def qcolor_to_hex(c: QColor) -> str:
    """Convert ``QColor`` to ``#RRGGBB`` hex string."""
    return f"#{c.red():02X}{c.green():02X}{c.blue():02X}"


def qbrush_to_hex(b: QBrush) -> str:
    """Convert ``QBrush`` (solid) to hex string."""
    color = b.color() if hasattr(b, "color") else QColor(0, 0, 0)
    return qcolor_to_hex(color)


def _linearize(value: float) -> float:
    value /= 255.0
    return value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4


def contrast_ratio(fg_hex: str, bg_hex: str) -> float:
    """Return WCAG contrast ratio for two hex colors."""
    fr = int(fg_hex[1:3], 16)
    fg = int(fg_hex[3:5], 16)
    fb = int(fg_hex[5:7], 16)
    br = int(bg_hex[1:3], 16)
    bg = int(bg_hex[3:5], 16)
    bb = int(bg_hex[5:7], 16)
    l1 = 0.2126 * _linearize(fr) + 0.7152 * _linearize(fg) + 0.0722 * _linearize(fb)
    l2 = 0.2126 * _linearize(br) + 0.7152 * _linearize(bg) + 0.0722 * _linearize(bb)
    lighter, darker = max(l1, l2), min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def ensure_contrast(fg_hex: str, bg_hex: str, base_fg_hex: str) -> str:
    """Return a foreground color with at least AA contrast against ``bg_hex``.

    If ``fg_hex`` fails, ``base_fg_hex`` is tried. When that also fails,
    the function falls back to either black or white depending on which
    provides better contrast.
    """
    if contrast_ratio(fg_hex, bg_hex) >= 4.5:
        return fg_hex
    if contrast_ratio(base_fg_hex, bg_hex) >= 4.5:
        return base_fg_hex
    return '#FFFFFF' if contrast_ratio('#FFFFFF', bg_hex) >= contrast_ratio('#000000', bg_hex) else '#000000'


__all__ = [
    "qcolor_to_hex",
    "qbrush_to_hex",
    "contrast_ratio",
    "ensure_contrast",
]
