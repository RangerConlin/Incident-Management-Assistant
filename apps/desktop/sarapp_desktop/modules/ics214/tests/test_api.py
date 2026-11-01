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
