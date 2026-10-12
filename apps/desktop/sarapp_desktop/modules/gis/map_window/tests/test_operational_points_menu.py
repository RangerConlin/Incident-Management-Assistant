"""Operational-point catalog coverage and registry compatibility."""

from modules.gis.models.geometry_types import GeometryType
from modules.gis.map_window.operational_point_types import OPERATIONAL_POINT_TYPES
from modules.gis.services.feature_registry import get_default_feature_registry


def _point_feature_type_values() -> set[str]:
    return {definition.feature_type.value for definition in OPERATIONAL_POINT_TYPES}


def test_point_feature_types_include_expected_primaries():
    values = _point_feature_type_values()
    for expected in ("landing_zone", "check_in_point", "roadblock", "med_unit_location", "repeater_site"):
        assert expected in values


def test_polygon_only_feature_types_are_excluded():
    values = _point_feature_type_values()
    assert "task_area" not in values
    assert "no_entry_zone" not in values


def test_point_or_polygon_types_are_included():
    values = _point_feature_type_values()
    assert "hazard_zone" in values
    assert "clue" in values


def test_all_catalog_types_are_registered_for_point_geometry():
    registry = get_default_feature_registry()
    for definition in OPERATIONAL_POINT_TYPES:
        registration = registry.get(definition.feature_type)
        assert GeometryType.POINT in registration.allowed_geometry_types
