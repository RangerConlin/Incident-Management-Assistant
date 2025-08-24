"""Helpers for team/role to channel assignments."""

from sqlmodel import Session, select

from .repository import get_mission_engine
from .models.comms_models import ChannelAssignment
from .models.schemas import ChannelAssignment as ChannelAssignmentSchema


def set_assignment(data: ChannelAssignmentSchema) -> ChannelAssignment:
    engine = get_mission_engine(data.mission_id)
    assignment = ChannelAssignment.model_validate(data)
    with Session(engine) as session:
        session.add(assignment)
        session.commit()
        session.refresh(assignment)
    return assignment


def list_assignments(mission_id: str) -> list[ChannelAssignment]:
    engine = get_mission_engine(mission_id)
    with Session(engine) as session:
        return session.exec(select(ChannelAssignment)).all()
