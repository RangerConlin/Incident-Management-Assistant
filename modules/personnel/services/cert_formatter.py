"""Certification level formatter and badge renderer.

This module centralises mapping between certification levels and human-
readable labels, and provides a simple rule-based badge renderer used
throughout the UI.

Levels (fixed):
0 None, 1 Trainee, 2 Qualified, 3 Evaluator

Badge render rule (global):
- Level 0: hidden (empty string)
- Level 1: "<CODE>-T"
- Level 2: "<CODE>"
- Level 3: "<CODE>-SET"
"""

from __future__ import annotations

from typing import Dict


_LEVEL_TO_LABEL: Dict[int, str] = {
    0: "None",
    1: "Trainee",
    2: "Qualified",
    3: "Evaluator",
}

_LABEL_TO_LEVEL: Dict[str, int] = {v.lower(): k for k, v in _LEVEL_TO_LABEL.items()}


def level_to_label(level: int) -> str:
    """Return the descriptive label for a level int.

    Unknown levels fall back to "None".
    """
    return _LEVEL_TO_LABEL.get(int(level), "None")


def label_to_level(label: str) -> int:
    """Return the integer level for a label (case-insensitive).

    Unknown labels map to 0 (None).
    """
    if label is None:
        return 0
    return _LABEL_TO_LEVEL.get(str(label).strip().lower(), 0)


def render_badge(code: str, level: int) -> str:
    """Render a badge per global rule for a given cert code and level.

    If `level` is 0 or invalid, returns an empty string.
    """
    try:
        lvl = int(level)
    except Exception:
        return ""
    if lvl <= 0:
        return ""
    base = (code or "").strip()
    if not base:
        return ""
    if lvl == 1:
        return f"{base}-T"
    if lvl == 2:
        return base
    return f"{base}-SET"


__all__ = [
    "level_to_label",
    "label_to_level",
    "render_badge",
]

