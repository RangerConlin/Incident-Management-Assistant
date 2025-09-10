"""Helpers determining whether FCC Lines A or C apply.

Currently these functions return ``False`` for all inputs.  They serve as
placeholders until detailed boundary data is incorporated into the
project.  The interfaces are stable so calling code may rely on them and
later be extended with geographic logic without changes.
"""

from __future__ import annotations

from typing import Optional


def line_a_applies(lat: Optional[float], lon: Optional[float]) -> bool:
    """Return ``True`` if Line A coordination rules apply.

    The implementation is a stub and always returns ``False``.  Real logic
    will be added once boundary datasets are available.
    """

    return False


def line_c_applies(lat: Optional[float], lon: Optional[float]) -> bool:
    """Return ``True`` if Line C coordination rules apply.

    The implementation is a stub and always returns ``False``.  Real logic
    will be added once boundary datasets are available.
    """

    return False


__all__ = ["line_a_applies", "line_c_applies"]
