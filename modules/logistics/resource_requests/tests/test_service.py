from __future__ import annotations

from pathlib import Path

import pytest

from modules.logistics.resource_requests.api import printers
from modules.logistics.resource_requests.api.service import ResourceRequestService
from modules.logistics.resource_requests.api.validators import ValidationError
from modules.logistics.resource_requests.models.enums import ApprovalAction, FulfillmentStatus, Priority, RequestStatus


@pytest.fixture
def service(tmp_path: Path) -> ResourceRequestService:
    db_path = tmp_path / "incident.db"
    return ResourceRequestService("TEST-INC", db_path)


def _base_header(priority: Priority = Priority.ROUTINE) -> dict[str, object]:
    return {
        "title": "Test Request",
        "requesting_section": "Logistics",
        "priority": priority.value,
        "created_by_id": "tester",
        "needed_by_utc": "2023-01-01T12:00:00Z",
        "justification": "Unit test",
        "delivery_location": "Cache",
    }


def _single_item() -> list[dict[str, object]]:
    return [
        {
            "kind": "SUPPLY",
            "description": "Tarps",
            "quantity": 5,
            "unit": "roll",
        }
    ]


def test_create_and_fetch_request(service: ResourceRequestService):
    request_id = service.create_request(_base_header(), _single_item())
    record = service.get_request(request_id)
    assert record["title"] == "Test Request"
    assert len(record["items"]) == 1
    assert record["status"] == RequestStatus.DRAFT.value


def test_update_and_versioning(service: ResourceRequestService):
    request_id = service.create_request(_base_header(), _single_item())
    service.record_approval(request_id, ApprovalAction.SUBMIT.value, actor_id="ops")
    original = service.get_request(request_id)
    service.update_request(request_id, {"delivery_location": "Forward Base"})
    updated = service.get_request(request_id)
    assert updated["delivery_location"] == "Forward Base"
    assert updated["version"] == original["version"] + 1


def test_illegal_transition_raises(service: ResourceRequestService):
    request_id = service.create_request(_base_header(), _single_item())
    with pytest.raises(ValidationError):
        service.change_status(request_id, RequestStatus.DELIVERED.value, actor_id="ops")


def test_replace_items(service: ResourceRequestService):
    request_id = service.create_request(_base_header(), _single_item())
    new_items = [
        {
            "kind": "equipment",
            "description": "Generators",
            "quantity": 2,
            "unit": "ea",
        }
    ]
    service.replace_items(request_id, new_items)
    record = service.get_request(request_id)
    assert record["items"][0]["description"] == "Generators"


def test_fulfillment_flow(service: ResourceRequestService):
    request_id = service.create_request(_base_header(Priority.IMMEDIATE), _single_item())
    fulfillment_id = service.assign_fulfillment(request_id, supplier_id="S1", team_id="T1")
    service.update_fulfillment(fulfillment_id, FulfillmentStatus.INTRANSIT.value, note="En route")
    record = service.get_request(request_id)
    assert record["fulfillments"][-1]["status"] == FulfillmentStatus.INTRANSIT.value


def test_printers_generate_pdfs(tmp_path: Path, service: ResourceRequestService, monkeypatch):
    request_id = service.create_request(_base_header(), _single_item())
    service.record_approval(request_id, ApprovalAction.SUBMIT.value, actor_id="ops")
    output_dir = tmp_path / "pdfs"
    output_dir.mkdir()

    monkeypatch.setattr(printers, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(printers, "get_service", lambda: service)

    path1 = printers.render_ics_213rr(request_id)
    path2 = printers.render_summary_sheet(request_id)
    assert path1.exists()
    assert path2.exists()
    assert path1.read_bytes().startswith(b"%PDF")


def test_list_filters(service: ResourceRequestService):
    request_id = service.create_request(_base_header(Priority.HIGH), _single_item())
    service.record_approval(request_id, ApprovalAction.SUBMIT.value, actor_id="ops")
    immediate_id = service.create_request(_base_header(Priority.IMMEDIATE), _single_item())

    filtered = service.list_requests({"priority": Priority.IMMEDIATE.value})
    assert len(filtered) == 1 and filtered[0]["id"] == immediate_id

    filtered_status = service.list_requests({"status": [RequestStatus.SUBMITTED.value]})
    assert filtered_status and filtered_status[0]["status"] == RequestStatus.SUBMITTED.value
