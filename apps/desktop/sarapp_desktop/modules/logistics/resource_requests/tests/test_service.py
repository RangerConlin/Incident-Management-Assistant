from __future__ import annotations

import os
from pathlib import Path

import pytest

os.environ.setdefault("SARAPP_MONGO_URI", "mongodb://localhost:27017")

from modules.logistics.resource_requests.api import printers
from modules.logistics.resource_requests.api.service import ResourceRequestService
from modules.logistics.resource_requests.api.validators import ValidationError, available_approval_actions
from modules.logistics.resource_requests.models.enums import (
    ApprovalAction,
    ApprovalSection,
    FulfillmentStatus,
    Priority,
    RequestStatus,
)

INCIDENT_ID = "resource-request-test"


@pytest.fixture()
def resource_request_app_client():
    """Points api_client at the real sarapp_db app in-process — resource
    request reads/writes go through MongoDB via the API, not local SQLite."""
    from sarapp_db.api.app import create_app
    from sarapp_db.mongo.collection_names import IncidentCollections
    from sarapp_db.mongo.database_manager import get_incident_db
    from utils.api_client import api_client, DEFAULT_BASE_URL

    db = get_incident_db(INCIDENT_ID)
    db[IncidentCollections.RESOURCE_REQUESTS].delete_many({})
    db["logistics_resource_requests"].delete_many({})

    app = create_app()
    api_client.configure_test_transport(app)
    try:
        yield api_client
    finally:
        api_client.configure(DEFAULT_BASE_URL)
        db[IncidentCollections.RESOURCE_REQUESTS].delete_many({})
        db["logistics_resource_requests"].delete_many({})


@pytest.fixture
def service(resource_request_app_client) -> ResourceRequestService:
    return ResourceRequestService(INCIDENT_ID)


def _base_header(priority: Priority = Priority.ROUTINE) -> dict[str, object]:
    return {
        "title": "Test Request",
        "requesting_section": "Logistics",
        "priority": priority.value,
        "created_by_id": "tester",
        "needed_by_utc": "2023-01-01T12:00:00Z",
        "justification": "Unit test",
        "delivery_location": "Cache",
        "delivery_facility_id": "fac-cache",
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
    assert record["delivery_facility_id"] == "fac-cache"


def test_create_writes_canonical_resource_requests_collection(
    service: ResourceRequestService,
):
    from sarapp_db.mongo.collection_names import IncidentCollections
    from sarapp_db.mongo.database_manager import get_incident_db

    request_id = service.create_request(_base_header(), _single_item())
    db = get_incident_db(INCIDENT_ID)

    assert db[IncidentCollections.RESOURCE_REQUESTS].find_one({"id": request_id}) is not None
    assert db["logistics_resource_requests"].find_one({"id": request_id}) is None


def test_update_and_versioning(service: ResourceRequestService):
    request_id = service.create_request(_base_header(), _single_item())
    service.record_approval(request_id, ApprovalAction.SUBMIT.value, actor_id="ops")
    original = service.get_request(request_id)
    service.update_request(
        request_id,
        {"delivery_location": "Forward Base", "delivery_facility_id": "fac-forward"},
    )
    updated = service.get_request(request_id)
    assert updated["delivery_location"] == "Forward Base"
    assert updated["delivery_facility_id"] == "fac-forward"
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
    fulfillment_id = service.assign_fulfillment(
        request_id,
        supplier_id="S1",
        team_id="T1",
        destination_location="Staging Alpha",
        destination_facility_id="fac-staging-alpha",
    )
    service.update_fulfillment(
        fulfillment_id,
        FulfillmentStatus.INTRANSIT.value,
        note="En route",
        request_id=request_id,
    )
    record = service.get_request(request_id)
    assert record["fulfillments"][-1]["status"] == FulfillmentStatus.INTRANSIT.value
    assert record["fulfillments"][-1]["destination_location"] == "Staging Alpha"
    assert record["fulfillments"][-1]["destination_facility_id"] == "fac-staging-alpha"


def test_fulfillment_defaults_to_request_delivery_target(service: ResourceRequestService):
    request_id = service.create_request(_base_header(Priority.HIGH), _single_item())
    fulfillment_id = service.assign_fulfillment(request_id, supplier_id="S1")
    record = service.get_request(request_id)
    fulfillment = next(f for f in record["fulfillments"] if f["id"] == fulfillment_id)
    assert fulfillment["destination_location"] == "Cache"
    assert fulfillment["destination_facility_id"] == "fac-cache"


def test_printers_generate_summary_pdf(tmp_path: Path, service: ResourceRequestService, monkeypatch):
    request_id = service.create_request(_base_header(), _single_item())
    service.record_approval(request_id, ApprovalAction.SUBMIT.value, actor_id="ops")
    output_dir = tmp_path / "pdfs"
    output_dir.mkdir()

    monkeypatch.setattr(printers, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(printers, "get_service", lambda: service)

    path = printers.render_summary_sheet(request_id)
    assert path.exists()
    assert path.read_bytes().startswith(b"%PDF")


def test_list_filters(service: ResourceRequestService):
    request_id = service.create_request(_base_header(Priority.HIGH), _single_item())
    service.record_approval(request_id, ApprovalAction.SUBMIT.value, actor_id="ops")
    immediate_id = service.create_request(_base_header(Priority.IMMEDIATE), _single_item())

    filtered = service.list_requests({"priority": Priority.IMMEDIATE.value})
    assert len(filtered) == 1 and filtered[0]["id"] == immediate_id

    filtered_status = service.list_requests({"status": [RequestStatus.SUBMITTED.value]})
    assert filtered_status and filtered_status[0]["status"] == RequestStatus.SUBMITTED.value


def test_record_approval_defaults_section_from_action(service: ResourceRequestService):
    request_id = service.create_request(_base_header(), _single_item())
    service.record_approval(request_id, ApprovalAction.SUBMIT.value, actor_id="ops")
    record = service.get_request(request_id)
    assert record["approvals"][-1]["section"] == ApprovalSection.REQUESTING.value

    service.record_approval(request_id, ApprovalAction.REVIEW.value, actor_id="logs")
    record = service.get_request(request_id)
    assert record["approvals"][-1]["section"] == ApprovalSection.LOGISTICS.value


def test_record_approval_accepts_explicit_section_override(service: ResourceRequestService):
    request_id = service.create_request(_base_header(), _single_item())
    service.record_approval(
        request_id,
        ApprovalAction.SUBMIT.value,
        actor_id="ops",
        section=ApprovalSection.LOGISTICS.value,
    )
    record = service.get_request(request_id)
    assert record["approvals"][-1]["section"] == ApprovalSection.LOGISTICS.value


def test_finance_approval_does_not_change_request_status(service: ResourceRequestService):
    request_id = service.create_request(_base_header(), _single_item())
    service.record_approval(request_id, ApprovalAction.SUBMIT.value, actor_id="ops")
    before = service.get_request(request_id)

    service.record_approval(request_id, ApprovalAction.FINANCE_APPROVE.value, actor_id="finance")
    after = service.get_request(request_id)

    assert after["status"] == before["status"]
    assert after["approvals"][-1]["action"] == ApprovalAction.FINANCE_APPROVE.value
    assert after["approvals"][-1]["section"] == ApprovalSection.FINANCE.value


def test_finance_deny_requires_note(service: ResourceRequestService):
    request_id = service.create_request(_base_header(), _single_item())
    service.record_approval(request_id, ApprovalAction.SUBMIT.value, actor_id="ops")
    with pytest.raises(ValidationError):
        service.record_approval(request_id, ApprovalAction.FINANCE_DENY.value, actor_id="finance")


def test_available_approval_actions_by_status():
    assert set(available_approval_actions(RequestStatus.DRAFT)) == {
        ApprovalAction.SUBMIT,
        ApprovalAction.CANCEL,
    }
    submitted_actions = set(available_approval_actions(RequestStatus.SUBMITTED))
    assert submitted_actions == {
        ApprovalAction.REVIEW,
        ApprovalAction.APPROVE,
        ApprovalAction.DENY,
        ApprovalAction.CANCEL,
    }
    # Reopen only becomes available once denied/cancelled; Review never
    # does, since there's nothing left to re-review from those statuses.
    denied_actions = set(available_approval_actions(RequestStatus.DENIED))
    assert denied_actions == {ApprovalAction.REOPEN}
    # Finance actions are never status-gated — they're independent of the
    # request's lifecycle, so they never show up here.
    assert ApprovalAction.FINANCE_APPROVE not in submitted_actions
    assert ApprovalAction.FINANCE_DENY not in submitted_actions
