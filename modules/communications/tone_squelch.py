"""Helpers for tone and squelch parsing."""

import re
from typing import Optional


def parse_ctcss(value: Optional[str]) -> Optional[float]:
    """Parse a CTCSS tone value to float Hz."""
    if not value:
        return None
    try:
        return float(value)
    except ValueError:
        return None


def parse_nac(value: Optional[str]) -> Optional[str]:
    """Parse a P25 Network Access Code (NAC)."""
    if not value:
        return None
    value = value.strip().lstrip("0x").upper()
    if re.fullmatch(r"[0-9A-F]{3}", value):
        return value
    return None


def parse_tone(value: Optional[str]) -> Optional[str]:
    """Attempt to parse tone as CTCSS or NAC."""
    nac = parse_nac(value)
    if nac:
        return nac
    ctcss = parse_ctcss(value)
    return f"{ctcss:.1f}" if ctcss is not None else None
