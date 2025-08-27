import sys
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parents[2]))

from modules.logistics import services
from modules.logistics.models import (
    ResourceRequestCreate,
    RequestApprovalCreate,
    RequestAssignmentCreate,
    EquipmentItemCreate,
)

TEST_INCIDENT = "test_incident"


def setup_module(module):
    db_path = Path("data") / "incidents" / f"{TEST_INCIDENT}.db"
    if db_path.exists():
        db_path.unlink()


def test_request_workflow():
    req = services.create_request(
        TEST_INCIDENT,
        ResourceRequestCreate(
            requestor_id=1,
            item_code="ITM-1",
            quantity=2,
            priority="Urgent",
        ),
    )
    assert req.id
    services.approve_request(
        TEST_INCIDENT, req.id, RequestApprovalCreate(approver_id=2, action="Approve")
    )
    services.assign_request(
        TEST_INCIDENT, req.id, RequestAssignmentCreate(resource_id=1, assigned_to_id=5)
    )
    services.update_request_status(TEST_INCIDENT, req.id, "Complete", actor_id=1)
    with services.with_incident_session(TEST_INCIDENT) as session:
        refreshed = session.get(services.LogisticsResourceRequest, req.id)
        assert refreshed.status == "Complete"


def test_equipment_checkout_in():
    item = services.add_equipment(TEST_INCIDENT, EquipmentItemCreate(name="Radio"))
    services.checkout_equipment(TEST_INCIDENT, item.id, actor_id=1)
    services.checkin_equipment(TEST_INCIDENT, item.id, actor_id=1)
    with services.with_incident_session(TEST_INCIDENT) as session:
        refreshed = session.get(services.EquipmentItem, item.id)
        assert refreshed.status == "available"


def test_incident_db_path():
    engine = services.get_incident_engine("xyz")
    assert str(engine.url).endswith("xyz.db")
