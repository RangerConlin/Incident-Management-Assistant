"""ICS-214 immutability, associations, and correction behavior."""
from modules.ics214 import services
from modules.ics214.schemas import CorrectionCreate, EntryCreate, EntryFilter


def test_idempotency_does_not_duplicate_entry(ics214_app_client):
    first = services.create_entry(
        "ics214-test", EntryCreate(text="one", team_ids=[2], idempotency_hash="h")
    )
    second = services.create_entry(
        "ics214-test", EntryCreate(text="two", team_ids=[2], idempotency_hash="h")
    )
    assert second["id"] == first["id"]


def test_correction_voids_original_and_keeps_new_associations(ics214_app_client):
    original = services.create_entry(
        "ics214-test2", EntryCreate(text="Team A arrived", team_ids=[1])
    )
    replacement = services.correct_entry(
        "ics214-test2", original["id"],
        CorrectionCreate(text="Team B arrived", team_ids=[2], voided_by="ops",
                         void_reason="Wrong team selected", created_by="ops"),
    )
    assert replacement["corrects_entry_id"] == original["id"]
    assert services.list_entries("ics214-test2", EntryFilter(team_ids=[1])) == []
    assert services.list_entries("ics214-test2", EntryFilter(team_ids=[2]))[0]["id"] == replacement["id"]
