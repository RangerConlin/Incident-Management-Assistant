from __future__ import annotations

from modules.gis.services.team_symbols import team_symbol_spec
from utils import styles as style_palette


def test_team_symbol_uses_status_alias_for_border() -> None:
    original_theme = style_palette.THEME_NAME
    try:
        style_palette.set_theme("light")

        spec = team_symbol_spec("GT", "Returning to Base")

        assert spec.status_key == "returning"
        assert spec.border_color == style_palette.team_status_colors()["returning"]["bg"].color().name()
    finally:
        style_palette.set_theme(original_theme)


def test_combined_team_type_uses_base_fill_without_modifier_badge() -> None:
    original_theme = style_palette.THEME_NAME
    try:
        style_palette.set_theme("light")

        combined = team_symbol_spec("GT/UAS", "Available")
        ground = team_symbol_spec("GT", "Available")

        assert combined.center_text == "GT"
        assert combined.fill_color == ground.fill_color
        assert combined.icon_url == ground.icon_url
        assert combined.team_type == "GT/UAS"
    finally:
        style_palette.set_theme(original_theme)


def test_unknown_team_type_still_builds_symbol_spec() -> None:
    spec = team_symbol_spec("MOUNTED", "Available")

    assert spec.team_type == "MOUNTED"
    assert spec.label == "MOUNTED"
    assert spec.center_text == "MOU"
    assert spec.icon_url is None
    assert spec.fill_color
    assert spec.border_color


def test_known_team_type_includes_png_icon_url() -> None:
    spec = team_symbol_spec("K9", "Available")

    assert spec.icon_url is not None
    assert spec.icon_url.endswith("/k9.png")


def test_symbol_spec_includes_frame_shading_colors() -> None:
    spec = team_symbol_spec("UAS", "Arrival")

    assert spec.fill_highlight_color
    assert spec.fill_shadow_color
    assert spec.border_shadow_color
    assert spec.inner_ring_color
    assert spec.fill_highlight_color != spec.fill_shadow_color
