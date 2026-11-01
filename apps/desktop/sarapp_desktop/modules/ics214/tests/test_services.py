from __future__ import annotations

from modules.ics214 import services
from modules.ics214.schemas import EntryCreate, EntryFilter, VoidRequest


def test_ics214_export_assets_resolve_from_module_location():
    from json import loads
    from pathlib import Path
    from pypdf import PdfReader

    assets = Path(services.__file__).resolve().parent / "assets"
    mapping_path = assets / "ics214_mapping.json"
    page_one = assets / "ics214_page1.pdf"
    page_two = assets / "ics214_page2.pdf"
    assert mapping_path.is_file() and page_one.is_file() and page_two.is_file()
    mapping = loads(mapping_path.read_text(encoding="utf-8"))
    mapped_fields = {row["pdf_field"] for row in mapping["fields"]}
    assert mapped_fields <= set(PdfReader(page_one).get_fields() or {})


def test_filter_and_void(ics214_app_client):
    created = services.create_entry(
        "incident", EntryCreate(text="Team departed", team_ids=[7], idempotency_hash="event-1")
    )
    services.create_entry(
        "incident", EntryCreate(text="Duplicate", team_ids=[7], idempotency_hash="event-1")
    )
    assert len(services.list_entries("incident", EntryFilter(team_ids=[7]))) == 1
    services.void_entry(
        "incident", created["id"], VoidRequest(voided_by="tester", reason="wrong event")
    )
    assert services.list_entries("incident", EntryFilter(team_ids=[7])) == []
    assert services.list_entries(
        "incident", EntryFilter(team_ids=[7], include_voided=True)
    )[0]["voided"] is True
