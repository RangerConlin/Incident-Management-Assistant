"""Canonical ICS-214 client/API integration tests."""
from modules.ics214 import services
from modules.ics214.schemas import EntryCreate, EntryFilter


def test_create_and_filter_entry(ics214_app_client):
    created = services.create_entry(
        "m1", EntryCreate(text="hello", task_ids=[12], incident_wide=True)
    )
    assert created["task_ids"] == [12]
    rows = services.list_entries("m1", EntryFilter(task_ids=[12]))
    assert [row["text"] for row in rows] == ["hello"]


def test_empty_associations_are_unassigned(ics214_app_client):
    created = services.create_entry("m1", EntryCreate(text="needs review"))
    assert created["unassigned"] is True
    assert services.list_entries("m1", EntryFilter(unassigned=True))[0]["id"] == created["id"]


def test_builtin_log_exists_without_incident_organization(ics214_app_client):
    definitions = services.list_log_definitions("m1")
    medical = next(item for item in definitions if item["id"] == "builtin:medical_unit")

    assert medical["builtin"] is True
    assert medical["name"] == "Medical Unit"
    assert medical["filters"] == {"log_keys": ["medical_unit"]}


def test_entry_is_filtered_by_builtin_log_identity(ics214_app_client):
    medical = services.create_entry(
        "m1", EntryCreate(text="Patient transported", log_keys=["medical_unit"])
    )
    services.create_entry(
        "m1", EntryCreate(text="Radio cache assigned", log_keys=["communications_unit"])
    )

    rows = services.list_entries("m1", EntryFilter(log_keys=["medical_unit"]))

    assert [row["id"] for row in rows] == [medical["id"]]
    assert medical["unassigned"] is False
