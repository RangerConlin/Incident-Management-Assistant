from __future__ import annotations

from typing import List, Optional, Dict, Any
from pydantic import BaseModel

# Template schemas


class EventTemplateBase(BaseModel):
    name: str
    category: Optional[str] = None
    description: Optional[str] = None
    default_ops_period_hours: Optional[int] = 12
    default_objectives_json: Optional[Dict[str, Any]] = None
    default_roles_json: Optional[Dict[str, Any]] = None
    default_checklists_json: Optional[Dict[str, Any]] = None


class EventTemplateCreate(EventTemplateBase):
    pass


class EventTemplateUpdate(EventTemplateBase):
    pass


class EventTemplateRead(EventTemplateBase):
    id: int

    class Config:
        orm_mode = True


class TemplateSiteBase(BaseModel):
    name: str
    site_type: Optional[str] = None
    geometry_json: Optional[Dict[str, Any]] = None
    capacity: Optional[int] = None
    notes: Optional[str] = None


class TemplateSiteCreate(TemplateSiteBase):
    template_id: int


class TemplateSiteRead(TemplateSiteBase):
    id: int
    template_id: int

    class Config:
        orm_mode = True


class TemplateRouteBase(BaseModel):
    name: str
    geometry_json: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class TemplateRouteCreate(TemplateRouteBase):
    template_id: int


class TemplateRouteRead(TemplateRouteBase):
    id: int
    template_id: int

    class Config:
        orm_mode = True


class TemplateCommsBase(BaseModel):
    channels_json: Optional[Dict[str, Any]] = None


class TemplateCommsCreate(TemplateCommsBase):
    template_id: int


class TemplateCommsRead(TemplateCommsBase):
    id: int
    template_id: int

    class Config:
        orm_mode = True


class TemplateMedicalBase(BaseModel):
    hospitals_json: Optional[Dict[str, Any]] = None
    ems_contacts_json: Optional[Dict[str, Any]] = None
    aid_stations_json: Optional[Dict[str, Any]] = None


class TemplateMedicalCreate(TemplateMedicalBase):
    template_id: int


class TemplateMedicalRead(TemplateMedicalBase):
    id: int
    template_id: int

    class Config:
        orm_mode = True


class TemplateSafetyBase(BaseModel):
    hazards_json: Optional[Dict[str, Any]] = None
    mitigations_json: Optional[Dict[str, Any]] = None
    safety_messages_json: Optional[Dict[str, Any]] = None


class TemplateSafetyCreate(TemplateSafetyBase):
    template_id: int


class TemplateSafetyRead(TemplateSafetyBase):
    id: int
    template_id: int

    class Config:
        orm_mode = True


class TemplatePermitsBase(BaseModel):
    requirements_json: Optional[Dict[str, Any]] = None


class TemplatePermitsCreate(TemplatePermitsBase):
    template_id: int


class TemplatePermitsRead(TemplatePermitsBase):
    id: int
    template_id: int

    class Config:
        orm_mode = True


class TemplateVendorsBase(BaseModel):
    vendors_json: Optional[Dict[str, Any]] = None


class TemplateVendorsCreate(TemplateVendorsBase):
    template_id: int


class TemplateVendorsRead(TemplateVendorsBase):
    id: int
    template_id: int

    class Config:
        orm_mode = True


class TemplateContactsBase(BaseModel):
    contacts_json: Optional[Dict[str, Any]] = None


class TemplateContactsCreate(TemplateContactsBase):
    template_id: int


class TemplateContactsRead(TemplateContactsBase):
    id: int
    template_id: int

    class Config:
        orm_mode = True


# Event instance schemas


class EventBaseModel(BaseModel):
    name: str
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    status: Optional[str] = "planning"
    objectives_json: Optional[Dict[str, Any]] = None


class EventCreate(EventBaseModel):
    template_id: Optional[int] = None


class EventRead(EventBaseModel):
    id: int
    template_id: Optional[int] = None

    class Config:
        orm_mode = True


class EventSiteBase(BaseModel):
    name: str
    site_type: Optional[str] = None
    geometry_json: Optional[Dict[str, Any]] = None
    capacity: Optional[int] = None
    notes: Optional[str] = None


class EventSiteCreate(EventSiteBase):
    event_id: int


class EventSiteRead(EventSiteBase):
    id: int
    event_id: int

    class Config:
        orm_mode = True


class EventRouteBase(BaseModel):
    name: str
    geometry_json: Optional[Dict[str, Any]] = None
    segments_json: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class EventRouteCreate(EventRouteBase):
    event_id: int


class EventRouteRead(EventRouteBase):
    id: int
    event_id: int

    class Config:
        orm_mode = True


class OpsPeriodBase(BaseModel):
    op_number: int
    start_datetime: Optional[str] = None
    end_datetime: Optional[str] = None
    notes: Optional[str] = None


class OpsPeriodCreate(OpsPeriodBase):
    event_id: int


class OpsPeriodRead(OpsPeriodBase):
    id: int
    event_id: int

    class Config:
        orm_mode = True


class StaffingRowBase(BaseModel):
    op_number: int
    location_ref: Optional[str] = None
    position: Optional[str] = None
    required: Optional[int] = 0
    assigned: Optional[int] = 0
    notes: Optional[str] = None


class StaffingRowCreate(StaffingRowBase):
    event_id: int


class StaffingRowRead(StaffingRowBase):
    id: int
    event_id: int

    class Config:
        orm_mode = True


class CommsPlanBase(BaseModel):
    op_number: int
    channels_json: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class CommsPlanCreate(CommsPlanBase):
    event_id: int


class CommsPlanRead(CommsPlanBase):
    id: int
    event_id: int

    class Config:
        orm_mode = True


class MedicalPlanBase(BaseModel):
    op_number: int
    hospitals_json: Optional[Dict[str, Any]] = None
    ems_contacts_json: Optional[Dict[str, Any]] = None
    aid_stations_json: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class MedicalPlanCreate(MedicalPlanBase):
    event_id: int


class MedicalPlanRead(MedicalPlanBase):
    id: int
    event_id: int

    class Config:
        orm_mode = True


class SafetyPlanBase(BaseModel):
    op_number: int
    hazards_json: Optional[Dict[str, Any]] = None
    mitigations_json: Optional[Dict[str, Any]] = None
    safety_messages_json: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class SafetyPlanCreate(SafetyPlanBase):
    event_id: int


class SafetyPlanRead(SafetyPlanBase):
    id: int
    event_id: int

    class Config:
        orm_mode = True


class PermitBase(BaseModel):
    name: str
    issuer: Optional[str] = None
    number: Optional[str] = None
    expires_on: Optional[str] = None
    status: Optional[str] = None
    file_path: Optional[str] = None
    notes: Optional[str] = None


class PermitCreate(PermitBase):
    event_id: int


class PermitRead(PermitBase):
    id: int
    event_id: int

    class Config:
        orm_mode = True


class VendorBase(BaseModel):
    name: str
    contact_json: Optional[Dict[str, Any]] = None
    approved: Optional[bool] = False
    notes: Optional[str] = None


class VendorCreate(VendorBase):
    event_id: int


class VendorRead(VendorBase):
    id: int
    event_id: int

    class Config:
        orm_mode = True


class ContactBase(BaseModel):
    name: str
    agency: Optional[str] = None
    role: Optional[str] = None
    phones_json: Optional[Dict[str, Any]] = None
    emails_json: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None


class ContactCreate(ContactBase):
    event_id: int


class ContactRead(ContactBase):
    id: int
    event_id: int

    class Config:
        orm_mode = True


class AttachmentBase(BaseModel):
    file_path: str
    title: Optional[str] = None
    category: Optional[str] = None
    tags_json: Optional[Dict[str, Any]] = None


class AttachmentCreate(AttachmentBase):
    event_id: int


class AttachmentRead(AttachmentBase):
    id: int
    event_id: int
    created_at: Optional[str]

    class Config:
        orm_mode = True


class ExportArtifactBase(BaseModel):
    op_number: Optional[int] = None
    type: str
    file_path: str


class ExportArtifactCreate(ExportArtifactBase):
    event_id: int


class ExportArtifactRead(ExportArtifactBase):
    id: int
    event_id: int
    created_at: Optional[str]

    class Config:
        orm_mode = True


# Helper schemas


class CloneFromTemplateRequest(BaseModel):
    template_id: int
    name: Optional[str] = None


class IapBuildRequest(BaseModel):
    forms: List[str]
    op_numbers: List[int]
    attachments: Optional[List[int]] = None


class SearchQuery(BaseModel):
    text: str
    filters: Optional[Dict[str, Any]] = None


class SearchResult(BaseModel):
    id: int
    type: str
    snippet: str


class PermissionOut(BaseModel):
    can_edit: bool = True
    can_finalize: bool = False
    can_export: bool = False
