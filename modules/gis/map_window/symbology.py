"""Map symbology: pattern/weight rules for style keys (colors live in styles/profiles).

A ``SymbolStyle`` describes everything about a symbol except its hue. The hue
comes from ``MAP_SYMBOL_COLORS[style_key]`` in the style profiles, so themes
stay in one place. Every style also carries a pattern (dash, decoration or
fill pattern) so symbols stay distinguishable in grayscale and for
colorblind users, per the planned-event symbology chart.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from styles.styles import map_symbol_colors

# Repeating marks placed along a line by the canvas.
DECORATIONS = frozenset({"arrow", "cross", "tick", "square"})
# SVG fill patterns for polygons; None means a plain translucent fill.
FILL_PATTERNS = frozenset({"hatch", "crosshatch", "dots"})


@dataclass(frozen=True, slots=True)
class SymbolStyle:
    weight: float = 3.0
    dash: str | None = None
    round_caps: bool = False
    decoration: str | None = None
    fill_pattern: str | None = None
    fill_opacity: float = 0.30


SYMBOL_STYLES: dict[str, SymbolStyle] = {
    # -- Planned-event lines --------------------------------------------------
    "primary_event_route": SymbolStyle(weight=5),
    "alternate_event_route": SymbolStyle(weight=4, dash="12 8"),
    "pedestrian_flow": SymbolStyle(weight=3, decoration="arrow"),
    "vehicle_flow": SymbolStyle(weight=5, decoration="arrow"),
    "shuttle_route": SymbolStyle(weight=3, dash="10 7", decoration="arrow"),
    "emergency_access_route": SymbolStyle(weight=3, dash="10 7", decoration="arrow"),
    "detour_route": SymbolStyle(weight=3, dash="10 7", decoration="arrow"),
    "evacuation_route": SymbolStyle(weight=3, decoration="arrow"),
    "staff_service_route": SymbolStyle(weight=3, dash="14 6 3 6"),
    "road_closure": SymbolStyle(weight=4, decoration="tick"),
    "soft_closure": SymbolStyle(weight=4, dash="14 10"),
    "barricade_line": SymbolStyle(weight=2, decoration="cross"),
    "queue_divider": SymbolStyle(weight=4, dash="1 9", round_caps=True),
    "temporary_barrier": SymbolStyle(weight=3, decoration="square"),
    "course_edge": SymbolStyle(weight=3, dash="10 5 3 5"),
    "no_cross_line": SymbolStyle(weight=3, dash="10 8", decoration="cross"),
    "crossing_control_zone": SymbolStyle(weight=3, dash="8 6", decoration="square"),
    # -- Planned-event polygons ----------------------------------------------
    "ceremony_area": SymbolStyle(weight=2),
    "spectator_area": SymbolStyle(weight=2),
    "vendor_area": SymbolStyle(weight=2),
    "volunteer_area": SymbolStyle(weight=2),
    "staff_area": SymbolStyle(weight=2),
    "logistics_area": SymbolStyle(weight=2),
    "general_parking": SymbolStyle(weight=2),
    "accessible_parking": SymbolStyle(weight=2, fill_pattern="hatch"),
    "overflow_parking": SymbolStyle(weight=2, dash="8 5"),
    "queue_area": SymbolStyle(weight=2, fill_pattern="hatch"),
    "restricted_area": SymbolStyle(weight=2, fill_pattern="crosshatch"),
    "emergency_keep_clear": SymbolStyle(weight=2, fill_pattern="hatch"),
    "hazard_area": SymbolStyle(weight=2, fill_pattern="dots"),
    "rehab_area": SymbolStyle(weight=2),
    "command_area": SymbolStyle(weight=2),
}


def resolve_symbol_style(style_key: str | None) -> dict[str, Any] | None:
    """JSON-ready style payload for the canvas, or None for un-symbolized keys."""
    if not style_key:
        return None
    style = SYMBOL_STYLES.get(style_key)
    color = map_symbol_colors().get(style_key)
    if style is None or color is None:
        return None
    return {
        "color": color.name(),
        "weight": style.weight,
        "dashArray": style.dash,
        "roundCaps": style.round_caps,
        "decoration": style.decoration,
        "fillPattern": style.fill_pattern,
        "fillOpacity": style.fill_opacity,
    }
