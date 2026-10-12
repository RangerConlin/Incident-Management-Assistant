import pytest

from modules.gis.map_window.operational_geometry_types import (
    OPERATIONAL_EVENT_AREA_TYPES,
    OPERATIONAL_EVENT_LINE_TYPES,
    OPERATIONAL_GEOMETRY_TYPES,
    operational_geometry_type,
)
from modules.gis.map_window.symbology import (
    DECORATIONS,
    FILL_PATTERNS,
    SYMBOL_STYLES,
    resolve_symbol_style,
)
from modules.gis.map_window.tools.operational_geometry_tool import OperationalGeometryController
from modules.gis.models.geometry_types import GeometryType
from modules.gis.services.feature_registry import get_default_feature_registry
from styles.profiles import load_profile

EVENT_TYPES = OPERATIONAL_EVENT_LINE_TYPES + OPERATIONAL_EVENT_AREA_TYPES


def test_chart_entry_counts():
    assert len(OPERATIONAL_EVENT_LINE_TYPES) == 17
    assert len(OPERATIONAL_EVENT_AREA_TYPES) == 15


def test_every_event_entry_has_subtype_style_and_section():
    for definition in EVENT_TYPES:
        assert definition.subtype and definition.style_key == definition.subtype
        assert definition.menu_section


def test_subtypes_are_unique_and_styles_match_exactly():
    subtypes = [d.subtype for d in EVENT_TYPES]
    assert len(subtypes) == len(set(subtypes))
    assert set(subtypes) == set(SYMBOL_STYLES)


@pytest.mark.parametrize("profile", ["light", "dark"])
def test_every_style_has_a_color_in_each_profile(profile):
    colors = load_profile(profile).MAP_SYMBOL_COLORS
    assert set(colors) == set(SYMBOL_STYLES)


def test_style_pattern_values_are_known():
    for style in SYMBOL_STYLES.values():
        assert style.decoration is None or style.decoration in DECORATIONS
        assert style.fill_pattern is None or style.fill_pattern in FILL_PATTERNS


def test_lines_never_use_fill_patterns_and_areas_never_decorate():
    for definition in OPERATIONAL_EVENT_LINE_TYPES:
        assert SYMBOL_STYLES[definition.style_key].fill_pattern is None
    for definition in OPERATIONAL_EVENT_AREA_TYPES:
        assert SYMBOL_STYLES[definition.style_key].decoration is None


def test_event_entries_are_allowed_by_registry():
    registry = get_default_feature_registry()
    for definition in EVENT_TYPES:
        assert registry.can_use_geometry(definition.feature_type, definition.geometry_type)


def test_lookup_distinguishes_subtypes_of_the_same_feature_type():
    generic = operational_geometry_type("route", GeometryType.LINE)
    event = operational_geometry_type("route", GeometryType.LINE, "evacuation_route")
    assert generic.subtype is None and event.subtype == "evacuation_route"
    with pytest.raises(KeyError):
        operational_geometry_type("route", GeometryType.LINE, "road_closure")


def test_resolve_symbol_style_payload():
    payload = resolve_symbol_style("road_closure")
    assert payload["color"] == "#c1121f"
    assert payload["decoration"] == "tick"
    assert payload["fillPattern"] is None
    assert resolve_symbol_style("hazard_area")["fillPattern"] == "dots"


def test_unsymbolized_keys_resolve_to_none():
    assert resolve_symbol_style(None) is None
    assert resolve_symbol_style("containment") is None


class _Repo:
    incident_id = "INC-SYM"

    def create_feature(self, feature):
        return feature


def test_controller_stores_subtype_and_style_key():
    controller = OperationalGeometryController(_Repo(), get_default_feature_registry())
    controller.arm("route", GeometryType.LINE, subtype="pedestrian_flow")
    created = controller.complete([(0.0, 0.0), (1.0, 1.0)])
    assert created.feature_type.value == "route"
    assert created.feature_subtype == "pedestrian_flow"
    assert created.style_key == "pedestrian_flow"
    assert created.label == "Pedestrian Flow"


def test_generic_types_keep_registry_style_key():
    controller = OperationalGeometryController(_Repo(), get_default_feature_registry())
    controller.arm("containment_line", GeometryType.LINE)
    created = controller.complete([(0.0, 0.0), (1.0, 1.0)])
    assert created.feature_subtype is None
    assert created.style_key == "containment"


def test_catalog_has_no_duplicate_type_geometry_subtype_triples():
    triples = [(d.feature_type, d.geometry_type, d.subtype) for d in OPERATIONAL_GEOMETRY_TYPES]
    assert len(triples) == len(set(triples))
