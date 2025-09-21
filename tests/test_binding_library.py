from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pytest

from modules.devtools.services.binding_library import (
    BindingOption,
    delete_binding_option,
    load_binding_library,
    save_binding_option,
)

from utils.profile_manager import profile_manager


@pytest.fixture()
def temp_profile_catalog(tmp_path: Path):
    repo_root = Path(__file__).resolve().parents[1]

    base_dir = tmp_path / "base_profile"
    child_dir = tmp_path / "child_profile"
    for p in (base_dir, child_dir):
        (p / "templates").mkdir(parents=True, exist_ok=True)
        (p / "assets").mkdir(parents=True, exist_ok=True)
        (p / "computed.py").write_text("# test stub\n", encoding="utf-8")

    base_manifest: Dict[str, object] = {
        "id": "base",
        "name": "Base",
        "version": "1.0.0",
        "inherits": [],
        "locale": {"date_format": "YYYY-MM-DD"},
        "units": {"distance": "km"},
        "templates_dir": "templates",
        "catalog": "catalog.json",
        "computed_module": "computed.py",
        "assets": {},
    }
    child_manifest: Dict[str, object] = {
        "id": "child",
        "name": "Child",
        "version": "1.0.0",
        "inherits": ["base"],
        "locale": {"date_format": "YYYY-MM-DD"},
        "units": {"distance": "km"},
        "templates_dir": "templates",
        "catalog": "catalog.json",
        "computed_module": "computed.py",
        "assets": {},
    }

    base_catalog = {
        "version": 1,
        "keys": {
            "incident.name": {"source": "constants", "desc": "Base incident name"},
            "mission.id": {
                "source": "mission",
                "desc": "Mission identifier",
                "synonyms": ["mission number"],
                "patterns": ["^mission.*id$"]
            },
            "ops.chief": {"source": "personnel", "desc": "Operations Section Chief"},

        },
    }
    child_catalog = {
        "version": 1,
        "keys": {
            "incident.name": {"desc": "Child incident name"},
            "planning.chief": {
                "source": "personnel",
                "desc": "Planning Section Chief",
                "synonyms": ["psc"],
                "patterns": ["^planning.*chief$"]
            },
        },
    }

    (base_dir / "manifest.json").write_text(json.dumps(base_manifest, indent=2), encoding="utf-8")
    (base_dir / "catalog.json").write_text(json.dumps(base_catalog, indent=2), encoding="utf-8")
    (child_dir / "manifest.json").write_text(json.dumps(child_manifest, indent=2), encoding="utf-8")
    (child_dir / "catalog.json").write_text(json.dumps(child_catalog, indent=2), encoding="utf-8")

    try:
        profile_manager.load_all_profiles(tmp_path)
        yield "child"
    finally:
        profile_manager.load_all_profiles(repo_root / "profiles")


def test_binding_library_merges_catalogs(temp_profile_catalog: str):
    child_id = temp_profile_catalog
    # ensure default active profile resolves to child for this test
    profile_manager._active_id = child_id  # type: ignore[attr-defined]

    result = load_binding_library()
    direct_result = load_binding_library(child_id)

    assert result.active_profile_id == child_id
    assert [opt.key for opt in result.options] == [opt.key for opt in direct_result.options]

    opt_map = {opt.key: opt for opt in result.options}
    assert opt_map["incident.name"].source == "constants"
    assert opt_map["incident.name"].description == "Child incident name"
    assert opt_map["mission.id"].source == "mission"
    assert opt_map["planning.chief"].source == "personnel"
    assert opt_map["mission.id"].synonyms == ["mission number"]
    assert opt_map["mission.id"].patterns == ["^mission.*id$"]
    assert opt_map["ops.chief"].origin_profile == "base"
    assert not opt_map["ops.chief"].is_defined_in_active
    assert len(opt_map) == 4


def test_save_binding_option_creates_override(temp_profile_catalog: str):
    child_id = temp_profile_catalog
    profile_manager._active_id = child_id  # type: ignore[attr-defined]

    result = load_binding_library()
    assert result.catalog_path is not None
    active_path = Path(result.catalog_path)
    base_option = next(opt for opt in result.options if opt.key == "ops.chief")

    override = BindingOption(
        key="ops.chief",
        source=base_option.source,
        description="Operations Chief (Override)",
        synonyms=["osc"],
        patterns=["^operations.*chief$"],
        origin_profile=child_id,
        is_defined_in_active=True,
        extra=dict(base_option.extra),
    )

    save_binding_option(override, original_key=base_option.key)

    updated = load_binding_library()
    opt_map = {opt.key: opt for opt in updated.options}
    assert opt_map["ops.chief"].description == "Operations Chief (Override)"
    assert opt_map["ops.chief"].is_defined_in_active

    data = json.loads(active_path.read_text(encoding="utf-8"))
    assert data["keys"]["ops.chief"]["desc"] == "Operations Chief (Override)"
    assert "osc" in data["keys"]["ops.chief"]["synonyms"]


def test_save_and_delete_binding_option(temp_profile_catalog: str):
    child_id = temp_profile_catalog
    profile_manager._active_id = child_id  # type: ignore[attr-defined]

    result = load_binding_library()
    assert result.catalog_path is not None
    active_path = Path(result.catalog_path)

    new_binding = BindingOption(
        key="logistics.staging",
        source="logistics",
        description="Staging Area",
        synonyms=["staging area"],
        patterns=["^staging.*area$"],
        origin_profile=child_id,
        is_defined_in_active=True,
        extra={},
    )
    save_binding_option(new_binding)

    renamed = BindingOption(
        key="logistics.staging_area",
        source="logistics",
        description="Staging Area",
        synonyms=["staging area"],
        patterns=["^staging.*area$"],
        origin_profile=child_id,
        is_defined_in_active=True,
        extra={},
    )
    save_binding_option(renamed, original_key="logistics.staging")

    data = json.loads(active_path.read_text(encoding="utf-8"))
    assert "logistics.staging" not in data["keys"]
    assert "logistics.staging_area" in data["keys"]

    removed = delete_binding_option("logistics.staging_area")
    assert removed is True

    data = json.loads(active_path.read_text(encoding="utf-8"))
    assert "logistics.staging_area" not in data["keys"]

    # inherited keys cannot be removed from the parent via delete
    assert delete_binding_option("ops.chief") is False
