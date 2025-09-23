from __future__ import annotations

from modules.ui_customization.models import LayoutTemplate, ThemeProfile
from modules.ui_customization.repository import UICustomizationRepository


def test_repository_roundtrip(tmp_path):
    storage = tmp_path / "custom.json"
    repo = UICustomizationRepository(storage)

    layout = LayoutTemplate(
        id="",
        name="Ops Layout",
        perspective_name="",
        description="",
        ads_state="c3RhdGU=",
        dashboard_widgets=["incidentinfo", "teamstatusboard"],
    )
    layout = repo.upsert_layout(layout)
    assert layout.id
    repo.set_active_layout(layout.id)

    theme = ThemeProfile(
        id="",
        name="Mission Dark",
        base_theme="dark",
        description="Night ops palette",
        tokens={"bg_window": "#101010", "fg_primary": "#fafafa"},
    )
    theme = repo.upsert_theme(theme)
    repo.set_active_theme(theme.id)

    bundle = repo.export_bundle()
    assert bundle.active_layout_id == layout.id
    assert bundle.active_theme_id == theme.id

    storage_2 = tmp_path / "imported.json"
    repo_imported = UICustomizationRepository(storage_2)
    repo_imported.import_bundle(bundle, replace=True)

    assert repo_imported.active_layout_id() == layout.id
    assert repo_imported.active_theme_id() == theme.id
    imported_layout = repo_imported.get_layout(layout.id)
    assert imported_layout and imported_layout.dashboard_widgets == ["incidentinfo", "teamstatusboard"]


def test_import_generates_unique_ids(tmp_path):
    storage = tmp_path / "custom.json"
    repo = UICustomizationRepository(storage)

    layout = LayoutTemplate(
        id="",
        name="Layout A",
        perspective_name="",
        description="",
        ads_state="abc",
        dashboard_widgets=[],
    )
    layout = repo.upsert_layout(layout)

    bundle = repo.export_bundle()

    # Import again without replace to trigger id remapping
    repo.import_bundle(bundle, replace=False)
    layouts = repo.list_layouts()
    ids = {l.id for l in layouts}
    assert len(ids) == len(layouts)
