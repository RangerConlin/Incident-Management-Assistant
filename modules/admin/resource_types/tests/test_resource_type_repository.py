from __future__ import annotations

import sqlite3

import pytest

from modules.admin.resource_types.data.resource_type_io import (
    export_capabilities_csv,
    import_capabilities_csv,
)
from modules.admin.resource_types.data.resource_assignment_repository import ResourceAssignmentRepository
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


def test_capability_csv_round_trip_updates_existing_rows(tmp_path):
    repo = ResourceTypeRepository(tmp_path / "master.db")
    repo.save_capability(
        ResourceCapability(
            name="Portable communications",
            category="Communications",
            description="Initial description",
            aliases=["radio comms"],
            notes="Seed note",
        )
    )
    repo.save_capability(
        ResourceCapability(
            name="Shelter support",
            category="Logistics",
            description="Inactive seed",
            is_active=False,
        )
    )

    export_path = tmp_path / "capabilities.csv"
    exported = export_capabilities_csv(repo, export_path)

    assert exported == 2
    text = export_path.read_text(encoding="utf-8")
    assert "Portable communications" in text
    assert "Shelter support" in text

    export_path.write_text(
        "\n".join(
            [
                "name,category,description,aliases,is_active,notes",
                "Portable communications,Communications,Updated description,radio comms; vhf,0,Updated note",
                "Medical support,Medical,Field care,ems; first aid,1,New capability",
                ",Operations,Missing name,ops,1,Should be skipped",
            ]
        ),
        encoding="utf-8",
    )

    result = import_capabilities_csv(repo, export_path)

    assert result["inserted"] == 1
    assert result["updated"] == 1
    assert len(result["errors"]) == 1
    updated = repo.get_capability_by_name("Portable communications")
    inserted = repo.get_capability_by_name("Medical support")
    assert updated is not None
    assert updated["description"] == "Updated description"
    assert updated["aliases"] == "radio comms; vhf"
    assert updated["is_active"] == 0
    assert updated["notes"] == "Updated note"
    assert inserted is not None


def test_resource_assignments_and_availability_queries(tmp_path):
    master_db = tmp_path / "master.db"
    incident_db = tmp_path / "incident.db"

    resource_repo = ResourceTypeRepository(master_db)
    assignment_repo = ResourceAssignmentRepository(master_db, incident_db)

    with sqlite3.connect(master_db) as conn:
        conn.execute("CREATE TABLE personnel (id TEXT PRIMARY KEY, name TEXT)")
        conn.execute("CREATE TABLE vehicles (id TEXT PRIMARY KEY, vin TEXT, license_plate TEXT, make TEXT, model TEXT, status_id TEXT)")
        conn.execute("CREATE TABLE equipment (id INTEGER PRIMARY KEY, name TEXT, type TEXT, condition TEXT)")
        conn.commit()
    assignment_repo.ensure_schema()

    gtm_id = resource_repo.save_resource_type(ResourceType(name="Ground Team Member", category="Personnel"))
    truck_id = resource_repo.save_resource_type(ResourceType(name="4x4 Truck", category="Vehicle"))
    cache_id = resource_repo.save_resource_type(ResourceType(name="Radio Cache", category="Equipment Kit / Cache", is_kit_cache=True))
    team_type_id = resource_repo.save_resource_type(ResourceType(name="Ground SAR Team", category="Team"))

    with sqlite3.connect(master_db) as conn:
        conn.execute("INSERT INTO personnel (id, name) VALUES (?, ?)", ("1", "Alex"))
        conn.execute(
            """
            INSERT INTO vehicles (id, vin, license_plate, make, model, status_id, resource_type_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            ("10", "VIN10", "ABC123", "Ford", "F150", "Available", truck_id),
        )
        conn.execute(
            """
            INSERT INTO equipment (id, name, type, condition, condition_status, resource_type_id, contents_verified)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (20, "Radio Cache #2", "Communications", "Serviceable", "Serviceable", cache_id, 1),
        )
        conn.commit()

    with sqlite3.connect(incident_db) as conn:
        conn.execute("CREATE TABLE personnel (id TEXT PRIMARY KEY, name TEXT, team_id INTEGER)")
        conn.execute("CREATE TABLE vehicles (id TEXT PRIMARY KEY, vin TEXT, license_plate TEXT, make TEXT, model TEXT, status_id TEXT, team_id INTEGER)")
        conn.execute("CREATE TABLE equipment (id INTEGER PRIMARY KEY, name TEXT, type TEXT, condition TEXT, team_id INTEGER)")
        conn.execute("CREATE TABLE teams (id INTEGER PRIMARY KEY, name TEXT, status TEXT, current_task_id INTEGER)")
        conn.execute("CREATE TABLE checkins (person_id TEXT, ci_status TEXT, personnel_status TEXT)")
        assignment_repo.ensure_incident_schema(conn)
        conn.execute("INSERT INTO personnel (id, name, team_id) VALUES (?, ?, ?)", ("1", "Alex", None))
        conn.execute(
            """
            INSERT INTO checkins (person_id, ci_status, personnel_status)
            VALUES (?, ?, ?)
            """,
            ("1", "Checked In", "Available"),
        )
        conn.execute(
            """
            INSERT INTO vehicles (id, vin, license_plate, make, model, status_id, resource_type_id, team_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            ("10", "VIN10", "ABC123", "Ford", "F150", "Available", truck_id, None),
        )
        conn.execute(
            """
            INSERT INTO equipment (id, name, type, condition, condition_status, resource_type_id, contents_verified, team_id)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (20, "Radio Cache #2", "Communications", "Serviceable", "Serviceable", cache_id, 1, None),
        )
        conn.execute(
            """
            INSERT INTO teams (id, name, status, current_task_id, resource_type_id, readiness_status)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (30, "Team Alpha", "available", None, team_type_id, "Ready"),
        )
        conn.commit()

    assignment_repo.set_personnel_resource_types("1", [gtm_id], primary_resource_type_id=gtm_id)

    personnel_links = assignment_repo.get_personnel_resource_types("1")
    available_personnel = assignment_repo.get_available_personnel_by_resource_type(gtm_id)
    available_vehicles = assignment_repo.get_available_vehicles_by_resource_type(truck_id)
    available_equipment = assignment_repo.get_available_equipment_by_resource_type(cache_id)
    available_teams = assignment_repo.get_available_teams_by_resource_type(team_type_id)

    assert personnel_links[0]["resource_type_id"] == gtm_id
    assert available_personnel[0]["name"] == "Alex"
    assert available_vehicles[0]["license_plate"] == "ABC123"
    assert available_equipment[0]["name"] == "Radio Cache #2"
    assert available_teams[0]["name"] == "Team Alpha"
