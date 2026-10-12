"""Team map symbol composition helpers.

This module owns the base team icon recipe used by the incident map. Capability
modifier badges are intentionally out of scope for this first pass.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping

from PySide6.QtGui import QColor

from utils.constants import TEAM_TYPE_DETAILS
from utils import styles as style_palette


@dataclass(frozen=True)
class TeamTypeSymbol:
    code: str
    label: str
    center_text: str
    icon_name: str | None = None
    base_type: str | None = None


@dataclass(frozen=True)
class TeamSymbolSpec:
    team_type: str
    label: str
    center_text: str
    fill_color: str
    fill_highlight_color: str
    fill_shadow_color: str
    border_color: str
    border_shadow_color: str
    inner_ring_color: str
    text_color: str
    status_key: str
    icon_url: str | None = None


TEAM_TYPE_SYMBOLS: Mapping[str, TeamTypeSymbol] = {
    "GT": TeamTypeSymbol("GT", "Ground Team", "GT", "team.png"),
    "UDF": TeamTypeSymbol("UDF", "Urban DF Team", "DF", "df.png"),
    "LSAR": TeamTypeSymbol("LSAR", "Land SAR", "SAR", "team.png"),
    "DF": TeamTypeSymbol("DF", "Direction Finding Team", "DF", "df.png"),
    "GT/UAS": TeamTypeSymbol("GT/UAS", "Ground/UAS Team", "GT", "team.png", base_type="GT"),
    "UDF/UAS": TeamTypeSymbol("UDF/UAS", "UDF/UAS Team", "DF", "df.png", base_type="UDF"),
    "UAS": TeamTypeSymbol("UAS", "UAS Team", "UAS", "uas.png"),
    "AIR": TeamTypeSymbol("AIR", "Aircraft", "AIR", "fixed_wing.png"),
    "HELO": TeamTypeSymbol("HELO", "Helicopter Team", "HEL", "helo.png", base_type="AIR"),
    "K9": TeamTypeSymbol("K9", "K9 Team", "K9", "k9.png"),
    "UTIL": TeamTypeSymbol("UTIL", "Utility/Support", "SUP", "util.png"),
}

_ASSET_ROOT = Path(__file__).resolve().parent.parent / "assets" / "team_symbols"

_STATUS_ALIASES: Mapping[str, str] = {
    "rest": "crew rest",
    "returning to base": "returning",
    "to other location": "tol",
    "at other location": "aol",
    "post incident management": "post incident",
}


def _normalize_team_type(team_type: object) -> str:
    return str(team_type or "GT").strip().upper() or "GT"


def _normalize_status(status: object) -> str:
    key = str(status or "available").strip().lower() or "available"
    return _STATUS_ALIASES.get(key, key)


def _qcolor_hex(color: QColor) -> str:
    return color.name(QColor.NameFormat.HexRgb)


def _shade(color: QColor, factor: int) -> str:
    if factor >= 100:
        return _qcolor_hex(color.lighter(factor))
    return _qcolor_hex(color.darker(max(100, int(10000 / max(1, factor)))))


def _brush_hex(mapping: Mapping[str, object], key: str, fallback: QColor) -> str:
    entry = mapping.get(key)
    if isinstance(entry, dict):
        brush = entry.get("bg")
        if brush is not None and hasattr(brush, "color"):
            return _qcolor_hex(brush.color())
    return _qcolor_hex(fallback)


def _icon_url(icon_name: str | None) -> str | None:
    if not icon_name:
        return None
    path = _ASSET_ROOT / "light" / icon_name
    if not path.exists():
        return None
    return path.as_uri()


def _contrast_text_color(fill: QColor) -> str:
    palette = style_palette.get_palette()
    dark_text = QColor(palette["fg"])
    light_text = QColor(palette["bg"])
    return _qcolor_hex(dark_text if fill.lightness() > 145 else light_text)


def team_symbol_spec(team_type: object, status: object) -> TeamSymbolSpec:
    """Return the display recipe for one team's base map icon."""

    requested_type = _normalize_team_type(team_type)
    team_type_colors = style_palette.TEAM_TYPE_COLORS
    symbol = TEAM_TYPE_SYMBOLS.get(requested_type)
    if symbol is None:
        label = TEAM_TYPE_DETAILS.get(requested_type, {}).get("label") or requested_type or "Team"
        symbol = TeamTypeSymbol(requested_type, label, requested_type[:3] or "T")

    fill_type = symbol.base_type or symbol.code
    palette = style_palette.get_palette()
    fill = QColor(team_type_colors.get(fill_type) or team_type_colors.get(symbol.code) or palette["accent"])
    status_key = _normalize_status(status)
    status_colors = style_palette.team_status_light_colors()
    border_hex = _brush_hex(status_colors, status_key, palette["accent"])
    border_color = QColor(border_hex)
    text = _contrast_text_color(fill)
    return TeamSymbolSpec(
        team_type=symbol.code,
        label=symbol.label,
        center_text=symbol.center_text,
        fill_color=_qcolor_hex(fill),
        fill_highlight_color=_shade(fill, 126),
        fill_shadow_color=_shade(fill, 78),
        border_color=border_hex,
        border_shadow_color=_shade(border_color, 72),
        inner_ring_color=_shade(fill, 145),
        text_color=text,
        status_key=status_key,
        icon_url=_icon_url(symbol.icon_name),
    )
