from __future__ import annotations

import datetime as dt
from typing import List
from uuid import uuid4

from . import planned_models as models
from .models import schemas
from .repository import with_master_session, with_event_session


# Template services

def create_template(data: schemas.EventTemplateCreate) -> models.EventTemplate:
    with with_master_session() as session:
        obj = models.EventTemplate(**data.dict())
        session.add(obj)
        session.flush()
        return obj


def list_templates() -> List[models.EventTemplate]:
    with with_master_session() as session:
        return session.query(models.EventTemplate).all()


def clone_template(template_id: int, name: str | None = None) -> str:
    with with_master_session() as session:
        template = session.get(models.EventTemplate, template_id)
        if not template:
            raise ValueError("Template not found")
    event_id = uuid4().hex
    with with_event_session(event_id) as session:
        event = models.Event(
            template_id=template.id,
            name=name or template.name,
            status="planning",
            objectives_json=template.default_objectives_json,
            created_at=dt.datetime.utcnow(),
            updated_at=dt.datetime.utcnow(),
        )
        session.add(event)
    return event_id


# Event services

def create_event(event_id: str, data: schemas.EventCreate) -> models.Event:
    with with_event_session(event_id) as session:
        obj = models.Event(**data.dict())
        session.add(obj)
        session.flush()
        return obj


def get_event(event_id: str) -> models.Event | None:
    with with_event_session(event_id) as session:
        return session.query(models.Event).first()


def add_site(event_id: str, data: schemas.EventSiteCreate) -> models.EventSite:
    with with_event_session(event_id) as session:
        obj = models.EventSite(**data.dict())
        session.add(obj)
        session.flush()
        return obj


def list_sites(event_id: str) -> List[models.EventSite]:
    with with_event_session(event_id) as session:
        return session.query(models.EventSite).all()


def add_route(event_id: str, data: schemas.EventRouteCreate) -> models.EventRoute:
    with with_event_session(event_id) as session:
        obj = models.EventRoute(**data.dict())
        session.add(obj)
        session.flush()
        return obj


def list_routes(event_id: str) -> List[models.EventRoute]:
    with with_event_session(event_id) as session:
        return session.query(models.EventRoute).all()


# Placeholder functions for other planners

def add_staffing_row(event_id: str, data: schemas.StaffingRowCreate) -> models.StaffingRow:
    with with_event_session(event_id) as session:
        obj = models.StaffingRow(**data.dict())
        session.add(obj)
        session.flush()
        return obj


def add_comms_plan(event_id: str, data: schemas.CommsPlanCreate) -> models.CommsPlan:
    with with_event_session(event_id) as session:
        obj = models.CommsPlan(**data.dict())
        session.add(obj)
        session.flush()
        return obj


def add_medical_plan(event_id: str, data: schemas.MedicalPlanCreate) -> models.MedicalPlan:
    with with_event_session(event_id) as session:
        obj = models.MedicalPlan(**data.dict())
        session.add(obj)
        session.flush()
        return obj


def add_safety_plan(event_id: str, data: schemas.SafetyPlanCreate) -> models.SafetyPlan:
    with with_event_session(event_id) as session:
        obj = models.SafetyPlan(**data.dict())
        session.add(obj)
        session.flush()
        return obj

