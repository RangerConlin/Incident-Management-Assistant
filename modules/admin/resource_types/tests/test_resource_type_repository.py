from __future__ import annotations

import sqlite3

import pytest

from modules.admin.resource_types.data.resource_type_repository import ResourceTypeRepository
from modules.admin.resource_types.models.resource_type_models import (
    FemaNimsMapping,
    ResourceCapability,
    ResourceType,
    ResourceTypeComponent,
)


def test_resource_type_crud_search_and_free_text_contract(tmp_path):
    repo = ResourceTypeRepository(tmp_path / "master.db")
    capability_id = repo.save_capability(
        ResourceCapability(
            name="Portable communications",
            category="Communications",
            description="Handheld radio support",
            aliases=["radio comms"],
            notes="Used by radio-heavy resources",
        )
    )
    resource_id = repo.save_resource_type(
        ResourceType(
            name="Radio Cache",
            planning_display_name="Radio Cache (6 radios)",
            category="Equipment Kit / Cache",
            source="AHJ Custom",
            owner_agency="County SAR",
            aliases=["radio kit"],
            is_kit_cache=True,
            is_consumable=False,
            capability_ids=[capability_id],
            fema_mappings=[
                FemaNimsMapping(
                    resource_type_id=0,
                    kind="Communications",
                    type_code="COMMS-CACHE",
                    nims_name="Radio Cache",
                    discipline="Communications",
                    reference_url="https://example.invalid/reference-note",
                )
            ],
        )
    )

    saved = repo.get_resource_type(resource_id)

    assert saved is not None
    assert saved.name == "Radio Cache"
    assert saved.aliases == ["radio kit"]
    assert saved.is_kit_cache is True
    assert saved.is_consumable is False
    assert saved.capability_ids == [capability_id]
    assert repo.search_resource_types("radio comms")[0].resource_type_id == resource_id
    assert repo.search_resource_types("County SAR")[0].resource_type_text == "Radio Cache (6 radios)"
    assert repo.search_resource_types("COMMS-CACHE")[0].matched_on == "FEMA/NIMS mapping"

    rows = repo.list_resource_types(category="Equipment Kit / Cache", source="AHJ Custom")
    assert rows[0]["capabilities"] == "Portable communications"
    assert rows[0]["is_kit_cache"] == 1


def test_components_allow_nested_kits_but_reject_cycles(tmp_path):
    repo = ResourceTypeRepository(tmp_path / "master.db")
    cache_id = repo.save_resource_type(ResourceType(name="Radio Cache", category="Equipment Kit / Cache", is_kit_cache=True))
    radio_id = repo.save_resource_type(ResourceType(name="Handheld Radio", category="Communications"))
    battery_id = repo.save_resource_type(ResourceType(name="Spare Battery", category="Supply", is_consumable=True))

    repo.add_component(
        ResourceTypeComponent(
            parent_resource_type_id=cache_id,
            component_resource_type_id=radio_id,
            quantity=6,
            unit="each",
            required=True,
        )
    )
    repo.add_component(
        ResourceTypeComponent(
            parent_resource_type_id=radio_id,
            component_resource_type_id=battery_id,
            quantity=2,
            unit="each",
            required=False,
        )
    )

    components = repo.list_components(cache_id)
    assert components[0]["component_name"] == "Handheld Radio"
    assert components[0]["required"] == 1
    assert repo.would_create_cycle(battery_id, cache_id) is True
    with pytest.raises(ValueError, match="circular"):
        repo.add_component(
            ResourceTypeComponent(
                parent_resource_type_id=battery_id,
                component_resource_type_id=cache_id,
            )
        )


def test_clone_copies_children_and_schema_migrates_existing_tables(tmp_path):
    db_path = tmp_path / "master.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE resource_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            planning_display_name TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'Other',
            source TEXT NOT NULL DEFAULT 'AHJ Custom',
            owner_agency TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            default_unit TEXT NOT NULL DEFAULT 'each',
            typical_quantity REAL NOT NULL DEFAULT 1,
            typical_team_size INTEGER,
            is_active INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    repo = ResourceTypeRepository(db_path)
    cache_id = repo.save_resource_type(ResourceType(name="Radio Cache", category="Equipment Kit / Cache", is_kit_cache=True))
    radio_id = repo.save_resource_type(ResourceType(name="Handheld Radio", category="Communications"))
    repo.replace_aliases(cache_id, ["radio kit"])
    repo.replace_components(
        cache_id,
        [
            ResourceTypeComponent(
                parent_resource_type_id=cache_id,
                component_resource_type_id=radio_id,
                quantity=6,
            )
        ],
    )

    clone_id = repo.clone_resource_type(cache_id)
    clone = repo.get_resource_type(clone_id)

    assert clone is not None
    assert clone.name == "Radio Cache Copy"
    assert clone.aliases == ["radio kit"]
    assert clone.components[0].component_resource_type_id == radio_id
