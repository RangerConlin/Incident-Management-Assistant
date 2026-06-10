from __future__ import annotations

from dataclasses import dataclass

from .geometry_types import GeometryType


@dataclass(frozen=True, slots=True)
class LayerDefinition:
    layer_key: str
    name: str
    category: str
    description: str
    geometry_type: GeometryType | None
    is_system_layer: bool
    is_user_toggleable: bool
    default_visible: bool
    display_order: int
