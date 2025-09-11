"""Helpers for Line A / Line C applicability.

Currently return False (placeholders) until geographic boundary data is added.
"""

from typing import Any


def line_a_applies(lat: Any, lon: Any) -> bool:  # noqa: ARG001
    return False


def line_c_applies(lat: Any, lon: Any) -> bool:  # noqa: ARG001
    return False


__all__ = ["line_a_applies", "line_c_applies"]

