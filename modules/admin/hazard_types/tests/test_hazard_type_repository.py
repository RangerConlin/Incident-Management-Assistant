from __future__ import annotations

import sqlite3

import pytest

from modules.admin.hazard_types.data.hazard_type_repository import HazardTypeRepository
from modules.admin.hazard_types.models.hazard_type_models import (
    HazardMitigation,
    HazardPpeItem,
    HazardReference,
    HazardType,
    HazardTypeResourceDefault,
)
from modules.admin.resource_types.data.resource_type_repository import ResourceTypeRepository
from modules.admin.resource_types.models.resource_type_models import ResourceType


def test_hazard_type_crud_search_and_resource_defaults(tmp_path):
    master_db = tmp_path / "master.db"
    hazard_repo = HazardTypeRepository(master_db)
    resource_repo = ResourceTypeRepository(master_db)
    team_id = resource_repo.save_resource_type(ResourceType(name="Ground SAR Team", category="Team"))

    hazard_id = hazard_repo.create_hazard_type(
        HazardType(
            name="Heat Stress",
            display_name="Heat Stress",
            category="Environmental",
            source="AHJ Custom",
            owner_agency="County SAR",
            description="High temperature exposure during field operations.",
            default_risk_level="Moderate",
            default_likelihood="Possible",
            default_severity="Serious",
            default_control_measure="Hydration plan and work/rest cycles.",
            default_ppe="Sun protection",
            default_safety_message="Monitor personnel for symptoms.",
            aliases=["Heat", "Hot Weather"],
            mitigations=[
                HazardMitigation(hazard_type_id=0, mitigation_text="Hydration plan", mitigation_category="Medical", is_default=True, sort_order=1),
                HazardMitigation(hazard_type_id=0, mitigation_text="Shade or cooling area", mitigation_category="Environmental", sort_order=2),
            ],
            ppe_items=[
                HazardPpeItem(hazard_type_id=0, ppe_text="Sun protection", is_default=True, sort_order=1),
                HazardPpeItem(hazard_type_id=0, ppe_text="Helmet", sort_order=2),
            ],
            references=[
                HazardReference(hazard_type_id=0, title="Heat SOP", url_or_path="https://example.invalid/heat"),
            ],
            resource_defaults=[
                HazardTypeResourceDefault(hazard_type_id=0, resource_type_id=team_id, notes="Common field exposure"),
            ],
        )
    )

    saved = hazard_repo.get_hazard_type(hazard_id)

    assert saved is not None
    assert saved.name == "Heat Stress"
    assert saved.aliases == ["Heat", "Hot Weather"]
    assert len(saved.mitigations) == 2
    assert len(saved.ppe_items) == 2
    assert saved.resource_defaults[0].resource_type_name == "Ground SAR Team"
    assert hazard_repo.search_hazard_types("hot weather")[0].hazard_type_id == hazard_id
    assert hazard_repo.search_hazard_types("hydration")[0].matched_on == "mitigation"
    assert hazard_repo.search_hazard_types("sun protection")[0].matched_on == "PPE"

    rows = hazard_repo.list_hazard_types(
        {
            "category": "Environmental",
            "source": "AHJ Custom",
            "risk_level": "Moderate",
        }
    )
    assert rows[0]["mitigation_count"] == 2
    assert "Sun protection" in rows[0]["ppe_preview"]

    defaults = hazard_repo.get_default_hazards_for_resource_type(team_id)
    assert defaults[0].name == "Heat Stress"


def test_hazard_type_schema_migrates_existing_tables_and_clone_copies_children(tmp_path):
    db_path = tmp_path / "master.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """
        CREATE TABLE hazard_types (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            category TEXT NOT NULL DEFAULT 'Other',
            source TEXT NOT NULL DEFAULT 'AHJ Custom',
            owner_agency TEXT NOT NULL DEFAULT '',
            description TEXT NOT NULL DEFAULT '',
            default_risk_level TEXT NOT NULL DEFAULT 'Unknown',
            is_active INTEGER NOT NULL DEFAULT 1,
            notes TEXT NOT NULL DEFAULT '',
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()

    repo = HazardTypeRepository(db_path)
    hazard_id = repo.create_hazard_type(
        HazardType(
            name="Lightning",
            category="Weather",
            source="Agency Policy",
            default_risk_level="High",
            default_likelihood="Possible",
            default_severity="Critical",
            aliases=["Thunderstorm"],
            mitigations=[HazardMitigation(hazard_type_id=0, mitigation_text="Suspend exposed operations")],
            ppe_items=[HazardPpeItem(hazard_type_id=0, ppe_text="Rain gear")],
            references=[HazardReference(hazard_type_id=0, title="Weather SOP")],
        )
    )

    clone_id = repo.clone_hazard_type(hazard_id)
    clone = repo.get_hazard_type(clone_id)

    assert clone is not None
    assert clone.name == "Lightning Copy"
    assert clone.aliases == ["Thunderstorm"]
    assert clone.mitigations[0].mitigation_text == "Suspend exposed operations"
    assert clone.ppe_items[0].ppe_text == "Rain gear"


def test_hazard_resource_defaults_work_without_resource_type_library_tables(tmp_path):
    repo = HazardTypeRepository(tmp_path / "master.db")
    hazard_id = repo.create_hazard_type(
        HazardType(
            name="Fatigue",
            category="Human Factors",
            source="AHJ Custom",
            default_risk_level="Moderate",
            default_likelihood="Likely",
            default_severity="Moderate",
        )
    )

    repo.add_resource_default(hazard_id, 42, notes="Fallback ID only")
    rows = repo.list_resource_defaults(hazard_id)

    assert rows[0]["resource_type_id"] == 42
    assert rows[0]["resource_type_name"] == "42"


def test_hazard_validation_rejects_unsupported_dropdown_values(tmp_path):
    repo = HazardTypeRepository(tmp_path / "master.db")

    with pytest.raises(ValueError, match="supported value"):
        repo.create_hazard_type(
            HazardType(
                name="Poor Visibility",
                category="Other",
                source="AHJ Custom",
                default_risk_level="Severe",
                default_likelihood="Unknown",
                default_severity="Unknown",
            )
        )
