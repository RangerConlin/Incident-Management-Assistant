import sys, pathlib
sys.path.append(str(pathlib.Path(__file__).resolve().parents[2]))

from pathlib import Path

from modules.logistics import services
from modules.logistics.models import (
    ResourceRequestCreate,
    RequestApprovalCreate,
    RequestAssignmentCreate,
    EquipmentItemCreate,
)

TEST_MISSION = "test_mission"


def setup_module(module):
    db_path = Path("data") / "missions" / f"{TEST_MISSION}.db"
    if db_path.exists():
        db_path.unlink()


def test_request_workflow():
    req = services.create_request(
        TEST_MISSION,
        ResourceRequestCreate(
            requestor_id=1,
            item_code="ITM-1",
            quantity=2,
            priority="Urgent",
        ),
    )
    assert req.id
    services.approve_request(
        TEST_MISSION, req.id, RequestApprovalCreate(approver_id=2, action="Approve")
    )
    services.assign_request(
        TEST_MISSION, req.id, RequestAssignmentCreate(resource_id=1, assigned_to_id=5)
    )
    services.update_request_status(TEST_MISSION, req.id, "Complete", actor_id=1)
    with services.with_mission_session(TEST_MISSION) as session:
        refreshed = session.get(services.LogisticsResourceRequest, req.id)
        assert refreshed.status == "Complete"


def test_equipment_checkout_in():
    item = services.add_equipment(TEST_MISSION, EquipmentItemCreate(name="Radio"))
    services.checkout_equipment(TEST_MISSION, item.id, actor_id=1)
    services.checkin_equipment(TEST_MISSION, item.id, actor_id=1)
    with services.with_mission_session(TEST_MISSION) as session:
        refreshed = session.get(services.EquipmentItem, item.id)
        assert refreshed.status == "available"


def test_mission_db_path():
    engine = services.get_mission_engine("xyz")
    assert str(engine.url).endswith("xyz.db")
