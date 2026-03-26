from __future__ import annotations

from functools import lru_cache

from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.layer_definition import LayerDefinition


class LayerRegistry:
    """Registry of logical layers available to spatial features."""

    def __init__(self, definitions: list[LayerDefinition]) -> None:
        self._definitions = {item.layer_key: item for item in definitions}

    def get(self, layer_key: str) -> LayerDefinition:
        return self._definitions[layer_key]

    def list_layers(self) -> list[LayerDefinition]:
        return sorted(self._definitions.values(), key=lambda item: item.display_order)

    def has_layer(self, layer_key: str) -> bool:
        return layer_key in self._definitions


@lru_cache(maxsize=1)
def get_default_layer_registry() -> LayerRegistry:
    return LayerRegistry(
        [
            LayerDefinition("teams", "Teams", "operations", "Current team positions", GeometryType.POINT, True, True, True, 10),
            LayerDefinition("tracks", "Tracks", "operations", "Movement tracks for teams and vehicles", GeometryType.LINE, True, True, True, 20),
            LayerDefinition("tasks", "Tasks", "operations", "Task points, routes, and areas", None, True, True, True, 30),
            LayerDefinition("assignments", "Assignments", "operations", "Assignment and control areas", GeometryType.POLYGON, True, True, True, 40),
            LayerDefinition("clues", "intel", "Clues and sightings", None, True, True, True, 50),
            LayerDefinition("subjects", "intel", "Subject planning and event locations", None, True, True, True, 60),
            LayerDefinition("hazards", "safety", "Hazards and closures", None, True, True, True, 70),
            LayerDefinition("comm_sites", "communications", "Radio and communications sites", None, True, True, True, 80),
            LayerDefinition("logistics_sites", "logistics", "Logistics and support locations", None, True, True, True, 90),
            LayerDefinition("planning_overlays", "planning", "Planning overlays and sketches", None, True, True, True, 100),
            LayerDefinition("imported_overlays", "planning", "Imported external overlay references", None, True, True, True, 110),
        ]
    )
