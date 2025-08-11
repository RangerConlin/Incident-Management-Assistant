from __future__ import annotations

import datetime as dt
from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, Boolean
from sqlalchemy.orm import declarative_base, relationship

MasterBase = declarative_base()
EventBase = declarative_base()


class EventTemplate(MasterBase):
    __tablename__ = "event_templates"
    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False)
    category = Column(String)
    description = Column(Text)
    default_ops_period_hours = Column(Integer, default=12)
    default_objectives_json = Column(JSON)
    default_roles_json = Column(JSON)
    default_checklists_json = Column(JSON)
    created_by = Column(String)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)
    version = Column(Integer, default=1)

    routes = relationship("TemplateRoute", cascade="all, delete-orphan")
    sites = relationship("TemplateSite", cascade="all, delete-orphan")
    comms = relationship("TemplateComms", cascade="all, delete-orphan")
    medical = relationship("TemplateMedical", cascade="all, delete-orphan")
    safety = relationship("TemplateSafety", cascade="all, delete-orphan")
    permits = relationship("TemplatePermits", cascade="all, delete-orphan")
    vendors = relationship("TemplateVendors", cascade="all, delete-orphan")
    contacts = relationship("TemplateContacts", cascade="all, delete-orphan")


class TemplateRoute(MasterBase):
    __tablename__ = "template_routes"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("event_templates.id"))
    name = Column(String, nullable=False)
    geometry_json = Column(JSON)
    notes = Column(Text)


class TemplateSite(MasterBase):
    __tablename__ = "template_sites"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("event_templates.id"))
    name = Column(String, nullable=False)
    site_type = Column(String)
    geometry_json = Column(JSON)
    capacity = Column(Integer)
    notes = Column(Text)


class TemplateComms(MasterBase):
    __tablename__ = "template_comms"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("event_templates.id"))
    channels_json = Column(JSON)


class TemplateMedical(MasterBase):
    __tablename__ = "template_medical"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("event_templates.id"))
    hospitals_json = Column(JSON)
    ems_contacts_json = Column(JSON)
    aid_stations_json = Column(JSON)


class TemplateSafety(MasterBase):
    __tablename__ = "template_safety"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("event_templates.id"))
    hazards_json = Column(JSON)
    mitigations_json = Column(JSON)
    safety_messages_json = Column(JSON)


class TemplatePermits(MasterBase):
    __tablename__ = "template_permits"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("event_templates.id"))
    requirements_json = Column(JSON)


class TemplateVendors(MasterBase):
    __tablename__ = "template_vendors"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("event_templates.id"))
    vendors_json = Column(JSON)


class TemplateContacts(MasterBase):
    __tablename__ = "template_contacts"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer, ForeignKey("event_templates.id"))
    contacts_json = Column(JSON)


# Event instance models


class Event(EventBase):
    __tablename__ = "events"
    id = Column(Integer, primary_key=True)
    template_id = Column(Integer)
    name = Column(String, nullable=False)
    start_datetime = Column(DateTime)
    end_datetime = Column(DateTime)
    status = Column(String, default="planning")
    objectives_json = Column(JSON)
    created_by = Column(String)
    created_at = Column(DateTime, default=dt.datetime.utcnow)
    updated_at = Column(DateTime, default=dt.datetime.utcnow, onupdate=dt.datetime.utcnow)


class EventSite(EventBase):
    __tablename__ = "event_sites"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String, nullable=False)
    site_type = Column(String)
    geometry_json = Column(JSON)
    capacity = Column(Integer)
    notes = Column(Text)


class EventRoute(EventBase):
    __tablename__ = "event_routes"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String, nullable=False)
    geometry_json = Column(JSON)
    segments_json = Column(JSON)
    notes = Column(Text)


class OpsPeriod(EventBase):
    __tablename__ = "ops_periods"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    op_number = Column(Integer, nullable=False)
    start_datetime = Column(DateTime)
    end_datetime = Column(DateTime)
    notes = Column(Text)


class StaffingRow(EventBase):
    __tablename__ = "staffing_matrix"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    op_number = Column(Integer)
    location_ref = Column(String)
    position = Column(String)
    required = Column(Integer, default=0)
    assigned = Column(Integer, default=0)
    notes = Column(Text)


class CommsPlan(EventBase):
    __tablename__ = "comms_plan"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    op_number = Column(Integer)
    channels_json = Column(JSON)
    notes = Column(Text)


class MedicalPlan(EventBase):
    __tablename__ = "medical_plan"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    op_number = Column(Integer)
    hospitals_json = Column(JSON)
    ems_contacts_json = Column(JSON)
    aid_stations_json = Column(JSON)
    notes = Column(Text)


class SafetyPlan(EventBase):
    __tablename__ = "safety_plan"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    op_number = Column(Integer)
    hazards_json = Column(JSON)
    mitigations_json = Column(JSON)
    safety_messages_json = Column(JSON)
    notes = Column(Text)


class Permit(EventBase):
    __tablename__ = "permits"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String)
    issuer = Column(String)
    number = Column(String)
    expires_on = Column(DateTime)
    status = Column(String)
    file_path = Column(String)
    notes = Column(Text)


class Vendor(EventBase):
    __tablename__ = "vendors"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String)
    contact_json = Column(JSON)
    approved = Column(Boolean, default=False)
    notes = Column(Text)


class Contact(EventBase):
    __tablename__ = "contacts"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    name = Column(String)
    agency = Column(String)
    role = Column(String)
    phones_json = Column(JSON)
    emails_json = Column(JSON)
    notes = Column(Text)


class Attachment(EventBase):
    __tablename__ = "attachments"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    file_path = Column(String)
    title = Column(String)
    category = Column(String)
    tags_json = Column(JSON)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class ExportArtifact(EventBase):
    __tablename__ = "exports"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer, ForeignKey("events.id"))
    op_number = Column(Integer)
    type = Column(String)
    file_path = Column(String)
    created_at = Column(DateTime, default=dt.datetime.utcnow)


class AuditLog(EventBase):
    __tablename__ = "audit_log"
    id = Column(Integer, primary_key=True)
    event_id = Column(Integer)
    entity = Column(String)
    entity_id = Column(Integer)
    action = Column(String)
    who = Column(String)
    when = Column(DateTime, default=dt.datetime.utcnow)
    details_json = Column(JSON)
