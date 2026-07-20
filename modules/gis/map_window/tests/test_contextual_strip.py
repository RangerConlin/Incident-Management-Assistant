"""Contextual strip show/hide logic.

Requires QT_QPA_PLATFORM=offscreen (see Design Documents/Instructions/
testing_and_qa.md) since it instantiates real Qt widgets.
"""

from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtWidgets import QApplication

from modules.gis.map_window.contextual_strip import ContextualStrip
from modules.gis.models.feature_types import FeatureType
from modules.gis.models.geometry_types import GeometryType
from modules.gis.models.spatial_feature import SpatialFeature


@pytest.fixture(scope="module")
def qapp():
    app = QApplication.instance() or QApplication([])
    yield app


def _feature(**overrides) -> SpatialFeature:
    base = dict(
        id=1,
        incident_id="TEST-INC",
        feature_type=FeatureType.CLUE,
        feature_subtype=None,
        geometry_type=GeometryType.POINT,
        label="Test Clue",
        description=None,
        status="active",
        source_module="gis.map_window",
        source_record_type="drawing",
        source_record_id="",
        geometry_wkt="POINT(-98.5 39.8)",
        centroid_lat=39.8,
        centroid_lon=-98.5,
        bbox_min_lat=39.8,
        bbox_min_lon=-98.5,
        bbox_max_lat=39.8,
        bbox_max_lon=-98.5,
        elevation_m=None,
        start_time=None,
        end_time=None,
        is_planning_only=False,
        is_visible=True,
        is_locked=False,
        is_archived=False,
        layer_key="clues",
        style_key="clue",
        created_at=None,
        updated_at=None,
        created_by=None,
        updated_by=None,
    )
    base.update(overrides)
    return SpatialFeature(**base)


def test_hidden_with_no_selection_and_default_tool(qapp):
    strip = ContextualStrip()
    strip.set_selection(None)
    assert strip.isVisible() is False


def test_visible_with_selection(qapp):
    strip = ContextualStrip()
    strip.set_selection(_feature())
    assert strip.isVisible() is True


def test_visible_for_non_default_tool(qapp):
    strip = ContextualStrip()
    strip.set_selection(None)
    strip.set_active_tool("draw_polygon")
    assert strip.isVisible() is True


def test_hidden_for_pan_and_select_tools(qapp):
    strip = ContextualStrip()
    strip.set_selection(None)
    strip.set_active_tool("draw_polygon")
    strip.set_active_tool("pan")
    assert strip.isVisible() is False


def test_selection_takes_priority_over_tool_state(qapp):
    strip = ContextualStrip()
    strip.set_selection(_feature())
    strip.set_active_tool("draw_polygon")
    assert strip.isVisible() is True
