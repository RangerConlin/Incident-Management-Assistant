"""Stage 1: Resource Kind + composition-requirement fields round-trip."""
from __future__ import annotations

from modules.admin.resource_types.data.resource_type_repository import (
    ApiResourceTypeRepository,
    _api_doc_to_resource_type,
    _resource_type_to_api_doc,
)
from modules.admin.resource_types.models.resource_type_models import (
    ResourceType,
    ResourceTypeSpec,
)
from utils.api_client import api_client
from utils.catalog_cache import catalog_cache


def test_api_doc_round_trip_carries_kind_and_requirements():
    doc = {
        "resource_type_id": "42",
        "name": "Engine 1",
        "resource_name": "Fire Engine",
        "category": "Vehicle",
        "source": "AHJ Custom",
        "kind": "Fire Engine",
        "technical_specs": [
            {"name": "Pump Capacity", "value": "1250", "unit": "GPM", "notes": ""},
        ],
        "min_personnel": 4,
        "required_qualifications": ["Firefighter I", "Driver/Operator"],
        "required_equipment_ids": [10, 11],
        "recommended_equipment_ids": [12],
        "composition_notes": "Must carry a full complement of SCBA.",
    }
    rt = _api_doc_to_resource_type(doc)
    assert rt.kind == "Fire Engine"
    assert rt.min_personnel == 4
    assert rt.required_qualifications == ["Firefighter I", "Driver/Operator"]
    assert rt.required_equipment_ids == [10, 11]
    assert rt.recommended_equipment_ids == [12]
    assert rt.composition_notes == "Must carry a full complement of SCBA."
    assert rt.technical_specs == [ResourceTypeSpec(name="Pump Capacity", value="1250", unit="GPM")]

    payload = _resource_type_to_api_doc(rt)
    assert payload["kind"] == "Fire Engine"
    assert payload["min_personnel"] == 4
    assert payload["required_qualifications"] == ["Firefighter I", "Driver/Operator"]
    assert payload["required_equipment_ids"] == [10, 11]
    assert payload["recommended_equipment_ids"] == [12]
    assert payload["technical_specs"] == [
        {"name": "Pump Capacity", "value": "1250", "unit": "GPM", "notes": ""}
    ]


def test_api_doc_defaults_when_legacy_fields_absent():
    """A pre-Stage-1 resource_type document (no kind/requirements at all)
    must load without error and without inventing data."""
    doc = {"resource_type_id": "7", "name": "Legacy Type", "category": "Equipment"}
    rt = _api_doc_to_resource_type(doc)
    assert rt.kind == ""
    assert rt.min_personnel is None
    assert rt.required_qualifications == []
    assert rt.required_equipment_ids == []
    assert rt.recommended_equipment_ids == []
    assert rt.technical_specs == []
    assert rt.composition_notes == ""


def test_save_resource_type_sends_requirement_fields(monkeypatch):
    sent: dict = {}

    def fake_post(path, json=None):
        sent["path"] = path
        sent["json"] = json
        return {"resource_type_id": "99"}

    monkeypatch.setattr(api_client, "post", fake_post)
    catalog_cache.invalidate()

    rt = ResourceType(
        name="Ground Search Team",
        category="Team",
        kind="Ground Search Team",
        min_personnel=4,
        required_qualifications=["Ground Team Member"],
        required_equipment_ids=[5],
        recommended_equipment_ids=[6],
        technical_specs=[ResourceTypeSpec(name="Max Terrain Grade", value="35", unit="%")],
        composition_notes="One member must be a qualified navigator.",
    )
    repo = ApiResourceTypeRepository()
    new_id = repo.save_resource_type(rt)

    assert new_id == 99
    assert sent["json"]["kind"] == "Ground Search Team"
    assert sent["json"]["min_personnel"] == 4
    assert sent["json"]["required_qualifications"] == ["Ground Team Member"]
    assert sent["json"]["required_equipment_ids"] == [5]
    assert sent["json"]["recommended_equipment_ids"] == [6]
    assert sent["json"]["technical_specs"] == [
        {"name": "Max Terrain Grade", "value": "35", "unit": "%", "notes": ""}
    ]
