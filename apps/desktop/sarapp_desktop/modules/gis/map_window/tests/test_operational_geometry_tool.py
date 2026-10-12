from dataclasses import replace

import pytest

from modules.gis.map_window.operational_geometry_types import (
    OPERATIONAL_AREA_TYPES,
    OPERATIONAL_GEOMETRY_TYPES,
    OPERATIONAL_LINE_TYPES,
    primary_area_types,
    primary_line_types,
)
from modules.gis.map_window.tools.feature_builder import centroid_lonlat
from modules.gis.map_window.tools.operational_geometry_tool import OperationalGeometryController
from modules.gis.models.feature_types import FeatureType
from modules.gis.models.geometry_types import GeometryType
from modules.gis.services.feature_registry import get_default_feature_registry

SQUARE = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]


class RecordingRepository:
    incident_id = "INC-GEOM"

    def __init__(self) -> None:
        self.created = []

    def create_feature(self, feature):
        self.created.append(feature)
        return replace(feature, id=7)


def _controller(repository=None) -> OperationalGeometryController:
    return OperationalGeometryController(repository or RecordingRepository(), get_default_feature_registry())


def test_every_catalog_entry_is_allowed_by_the_registry():
    registry = get_default_feature_registry()
    for definition in OPERATIONAL_GEOMETRY_TYPES:
        assert registry.can_use_geometry(definition.feature_type, definition.geometry_type)


def test_catalog_geometry_matches_its_list():
    assert all(d.geometry_type is GeometryType.LINE for d in OPERATIONAL_LINE_TYPES)
    assert all(d.geometry_type is GeometryType.POLYGON for d in OPERATIONAL_AREA_TYPES)
    assert primary_line_types() and primary_area_types()


def test_generated_and_live_feed_types_are_excluded():
    values = {d.feature_type for d in OPERATIONAL_GEOMETRY_TYPES}
    for excluded in (FeatureType.SEARCH_GRID, FeatureType.TEAM_TRACK, FeatureType.AIRCRAFT_TRACK):
        assert excluded not in values


def test_complete_persists_typed_line():
    repository = RecordingRepository()
    controller = _controller(repository)
    controller.arm("containment_line", GeometryType.LINE)
    assert controller.draw_tool_key == "draw_line"

    created = controller.complete([(-84.0, 39.0), (-84.1, 39.1)])

    assert created is not None
    assert created.feature_type is FeatureType.CONTAINMENT_LINE
    assert created.geometry_type is GeometryType.LINE
    assert created.geometry_wkt == "LINESTRING(-84.0000000 39.0000000, -84.1000000 39.1000000)"
    assert created.layer_key == "planning_overlays"
    assert created.style_key == "containment"
    assert created.is_planning_only is False
    assert controller.armed_type is None


def test_complete_persists_typed_area_with_closed_ring_and_bounds():
    controller = _controller()
    controller.arm("closure_area", GeometryType.POLYGON)
    assert controller.draw_tool_key == "draw_polygon"

    created = controller.complete(SQUARE)

    assert created.feature_type is FeatureType.CLOSURE_AREA
    assert created.geometry_type is GeometryType.POLYGON
    assert created.geometry_wkt.startswith("POLYGON((0.0000000 0.0000000")
    assert created.geometry_wkt.endswith("0.0000000 0.0000000))")
    assert (created.bbox_min_lon, created.bbox_max_lon) == (0.0, 2.0)
    assert (created.centroid_lon, created.centroid_lat) == pytest.approx((1.0, 1.0))
    assert created.layer_key == "hazards"


def test_callback_fires_and_controller_disarms():
    seen = []
    controller = _controller()
    controller.arm("route", GeometryType.LINE, on_created=seen.append)
    controller.complete([(0.0, 0.0), (1.0, 1.0)])
    assert len(seen) == 1
    assert controller.complete([(0.0, 0.0), (1.0, 1.0)]) is None


def test_too_few_vertices_raises_and_stays_armed():
    controller = _controller()
    controller.arm("task_area", GeometryType.POLYGON)
    with pytest.raises(ValueError):
        controller.complete([(0.0, 0.0), (1.0, 1.0)])
    assert controller.armed_type is not None


def test_failed_save_stays_armed_for_retry():
    class FailingRepository(RecordingRepository):
        def create_feature(self, feature):
            raise RuntimeError("offline")

    controller = _controller(FailingRepository())
    controller.arm("route", GeometryType.LINE)
    with pytest.raises(RuntimeError, match="offline"):
        controller.complete([(0.0, 0.0), (1.0, 1.0)])
    assert controller.armed_type is not None


def test_uncataloged_or_wrong_geometry_cannot_be_armed():
    controller = _controller()
    with pytest.raises(KeyError):
        controller.arm("team_track", GeometryType.LINE)
    with pytest.raises(KeyError):
        controller.arm("containment_line", GeometryType.POLYGON)


def test_line_centroid_is_length_weighted():
    lon, lat = centroid_lonlat(GeometryType.LINE, [(0.0, 0.0), (4.0, 0.0), (4.0, 1.0)])
    assert lon == pytest.approx((2.0 * 4 + 4.0 * 1) / 5)
    assert lat == pytest.approx((0.0 * 4 + 0.5 * 1) / 5)
