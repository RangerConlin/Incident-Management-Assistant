from __future__ import annotations

from modules.logistics.resource_requests.models import request as request_model
from modules.logistics.resource_requests.models.approval import ApprovalRecord
from modules.logistics.resource_requests.models.audit import AuditRecord
from modules.logistics.resource_requests.models.enums import ApprovalAction, FulfillmentStatus, Priority
from modules.logistics.resource_requests.models.fulfillment import FulfillmentRecord
from modules.logistics.resource_requests.models.request_item import create_item


def test_request_round_trip():
    header = {
        "title": "Generators",
        "requesting_section": "Logistics",
        "priority": Priority.HIGH,
        "created_by_id": "tester",
        "justification": "Power backups",
    }
    request = request_model.create_from_header("req1", "INC-1", header)
    row = request.to_row()
    loaded = request_model.ResourceRequest.from_row(row)
    assert loaded == request


def test_item_factory_handles_strings():
    data = {
        "kind": "equipment",
        "description": "Portable radios",
        "quantity": "3",
        "unit": "each",
    }
    item = create_item("item1", "req1", data)
    assert item.kind.value == "EQUIPMENT"
    assert item.quantity == 3


def test_audit_and_approval_round_trip():
    approval = ApprovalRecord(
        id="a1",
        request_id="req1",
        action=ApprovalAction.APPROVE,
        actor_id="planner",
        note="Looks good",
        ts_utc="2023-01-01T00:00:00Z",
    )
    assert ApprovalRecord.from_row(approval.to_row()) == approval

    audit = AuditRecord(
        id="audit1",
        entity_type="resource_request",
        entity_id="req1",
        field="status",
        old_value="DRAFT",
        new_value="SUBMITTED",
        ts_utc="2023-01-01T00:00:00Z",
    )
    assert AuditRecord.from_row(audit.to_row()) == audit

    fulfillment = FulfillmentRecord(
        id="f1",
        request_id="req1",
        status=FulfillmentStatus.DELIVERED,
        ts_utc="2023-01-01T00:00:00Z",
    )
    assert FulfillmentRecord.from_row(fulfillment.to_row()) == fulfillment
