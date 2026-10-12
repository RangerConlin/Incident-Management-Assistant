from dataclasses import replace

import pytest

from modules.gis.map_window.tools.operational_point_tool import OperationalPointController
from modules.gis.models.feature_types import FeatureType
from modules.gis.models.geometry_types import GeometryType
from modules.gis.services.feature_registry import get_default_feature_registry


class RecordingRepository:
    incident_id = "INC-POINTS"

    def __init__(self) -> None:
        self.created = []

    def create_feature(self, feature):
        self.created.append(feature)
        return replace(feature, id=41)


def test_place_at_persists_selected_type_and_point_geometry():
    repository = RecordingRepository()
    controller = OperationalPointController(repository, get_default_feature_registry())
    controller.arm("landing_zone")

    created = controller.place_at(39.12345678, -84.87654321)

    assert created is not None
    assert created.feature_type is FeatureType.LANDING_ZONE
    assert created.geometry_type is GeometryType.POINT
    assert created.geometry_wkt == "POINT(-84.8765432 39.1234568)"
    assert created.label == "Landing Zone"
    assert created.layer_key == "logistics_sites"
    assert controller.armed_type is None


def test_failed_create_remains_armed_for_retry():
    class FailingRepository(RecordingRepository):
        def create_feature(self, feature):
            raise RuntimeError("offline")

    controller = OperationalPointController(FailingRepository(), get_default_feature_registry())
    controller.arm("roadblock")

    with pytest.raises(RuntimeError, match="offline"):
        controller.place_at(39.0, -84.0)

    assert controller.armed_type is not None
    assert controller.armed_type.feature_type is FeatureType.ROADBLOCK


def test_non_catalog_feature_type_cannot_be_armed():
    controller = OperationalPointController(RecordingRepository(), get_default_feature_registry())

    with pytest.raises(KeyError):
        controller.arm("team_location")
