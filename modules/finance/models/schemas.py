from __future__ import annotations

from pydantic import BaseModel, Field
from datetime import date, datetime
from typing import Optional, List

# Master lookups -------------------------------------------------------------

class VendorRead(BaseModel):
    id: int
    name: str
    contacts_json: Optional[str] = None
    payment_terms: Optional[str] = None
    notes: Optional[str] = None


class LaborRateRead(BaseModel):
    id: int
    title: str
    rate_per_hour: float
    overtime_mult: float = 1.5
    effective_from: date
    effective_to: Optional[date] = None


class EquipmentRateRead(BaseModel):
    id: int
    type: str
    rate_per_hour: float
    rate_per_day: float
    effective_from: date
    effective_to: Optional[date] = None


class AccountRead(BaseModel):
    id: int
    code: str
    name: str
    category: str


# Time Unit -----------------------------------------------------------------

class TimeEntryBase(BaseModel):
    person_id: int
    role: str
    op_period: str
    date: date
    hours_worked: float
    overtime_hours: float = 0
    labor_rate_id: int
    equipment_id: Optional[int] = None
    notes: Optional[str] = None


class TimeEntryCreate(TimeEntryBase):
    pass


class TimeEntryUpdate(BaseModel):
    hours_worked: Optional[float] = None
    overtime_hours: Optional[float] = None
    labor_rate_id: Optional[int] = None
    equipment_id: Optional[int] = None
    notes: Optional[str] = None
    status: Optional[str] = None


class TimeEntryRead(TimeEntryBase):
    id: int
    status: str
    approved_by: Optional[int] = None
    approved_at: Optional[datetime] = None


# Procurement ---------------------------------------------------------------

class RequisitionCreate(BaseModel):
    req_number: str
    requestor_id: int
    date: date
    description: str
    amount_est: float
    approval_chain_id: Optional[int] = None


class RequisitionRead(RequisitionCreate):
    id: int
    status: str


class POCreate(BaseModel):
    po_number: str
    vendor_id: int
    req_id: int
    date: date
    amount_auth: float


class PORead(POCreate):
    id: int
    status: str


class ReceiptCreate(BaseModel):
    po_id: int
    date: date
    qty: float
    amount: float
    notes: Optional[str] = None


class ReceiptRead(ReceiptCreate):
    id: int


class InvoiceCreate(BaseModel):
    po_id: int
    vendor_invoice_no: str
    date: date
    amount: float


class InvoiceUpdate(BaseModel):
    status: Optional[str] = None
    amount: Optional[float] = None


class InvoiceRead(InvoiceCreate):
    id: int
    status: str


# Cost Unit -----------------------------------------------------------------

class CostEntryCreate(BaseModel):
    date: date
    account_id: int
    description: str
    amount: float
    source: str
    ref_table: Optional[str] = None
    ref_id: Optional[int] = None


class CostEntryRead(CostEntryCreate):
    id: int


class DailyCostFinalizeRequest(BaseModel):
    date: date
    notes: Optional[str] = None


class BudgetCreate(BaseModel):
    account_id: int
    amount_budgeted: float
    notes: Optional[str] = None


class BudgetRead(BudgetCreate):
    id: int


# Claims --------------------------------------------------------------------

class ClaimBase(BaseModel):
    claim_type: str
    claimant_id: int
    date_reported: date
    description: str
    amount_est: float
    attachments_json: Optional[str] = None


class ClaimCreate(ClaimBase):
    pass


class ClaimUpdate(BaseModel):
    description: Optional[str] = None
    amount_est: Optional[float] = None
    status: Optional[str] = None
    attachments_json: Optional[str] = None


class ClaimRead(ClaimBase):
    id: int
    status: str


# Approvals & Audit ---------------------------------------------------------

class ApprovalAction(BaseModel):
    step: str
    action: str
    comments: Optional[str] = None


class ApprovalRecordRead(BaseModel):
    id: int
    entity: str
    entity_id: int
    step: str
    actor_id: int
    action: str
    timestamp: datetime
    comments: Optional[str] = None


# Reports / Exports ---------------------------------------------------------

class ReportRequest(BaseModel):
    report_type: str
    date: Optional[date] = None


class ExportArtifactRead(BaseModel):
    path: str
    created_at: datetime


# Permissions ---------------------------------------------------------------

class PermissionOut(BaseModel):
    can_edit: bool = False
    can_approve: bool = False
    can_finalize: bool = False
    can_export: bool = False
