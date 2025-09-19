from __future__ import annotations

import json
from pathlib import Path
from typing import Dict

import pytest

from modules.devtools.services.binding_library import load_binding_library
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
            "mission.id": {"source": "mission", "desc": "Mission identifier"},
        },
    }
    child_catalog = {
        "version": 1,
        "keys": {
            "incident.name": {"desc": "Child incident name"},
            "planning.chief": {"source": "personnel", "desc": "Planning Section Chief"},
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

    options = load_binding_library()
    direct_options = load_binding_library(child_id)

    assert [opt.key for opt in options] == [opt.key for opt in direct_options]

    opt_map = {opt.key: opt for opt in options}
    assert opt_map["incident.name"].source == "constants"
    assert opt_map["incident.name"].description == "Child incident name"
    assert opt_map["mission.id"].source == "mission"
    assert opt_map["planning.chief"].source == "personnel"
    assert len(opt_map) == 3
