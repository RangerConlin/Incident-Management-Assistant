from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Optional, Dict, Any, Type

from PySide6.QtWidgets import QWidget


@dataclass(frozen=True)
class Size:
    w: int  # grid columns (of 12)
    h: int  # grid rows (arbitrary row height units)


@dataclass(frozen=True)
class WidgetSpec:
    id: str
    title: str
    default_size: Size
    min_size: Size
    component: Type[QWidget]
    data_hooks: Optional[Dict[str, Callable[..., Any]]] = None


# Allowed snap sizes for width in a 12-column grid
ALLOWED_WIDTHS = {3, 4, 6, 8, 9, 12}


def snap_width(w: int) -> int:
    """Snap width to the nearest allowed size."""
    if w in ALLOWED_WIDTHS:
        return w
    # choose closest by absolute difference, prefer larger on ties
    best = min(ALLOWED_WIDTHS, key=lambda x: (abs(x - w), -x))
    return best

