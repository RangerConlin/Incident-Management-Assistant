"""FeatureRegistry-driven Operational Points 'More' menu population.

Mirrors the filter used by IncidentTab._build_operational_points_group:
list feature types whose allowed geometry types include POINT.
"""

from modules.gis.models.geometry_types import GeometryType
from modules.gis.services.feature_registry import get_default_feature_registry


def _point_feature_type_values() -> set[str]:
    registry = get_default_feature_registry()
    return {
        ft.value
        for ft in registry.list_feature_types()
        if GeometryType.POINT in registry.get(ft).allowed_geometry_types
    }


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
