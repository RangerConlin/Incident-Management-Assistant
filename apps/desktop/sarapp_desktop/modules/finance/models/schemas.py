from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, Field


RateCategory = Literal[
    "personnel", "aircraft", "vehicle", "equipment", "fuel",
    "lodging", "meals", "rentals", "contracted_services", "other",
]
EstimateStatus = Literal["estimated", "committed"]
CloseReason = Literal[
    "No longer needed", "Request cancelled", "Resource not used",
    "Replaced by another estimate", "Duplicate", "Entered in error",
    "Included in another cost", "Provided at no charge", "Actual cost received",
]
VerificationStatus = Literal["unverified", "verified", "disputed"]


class RateTableEntryCreate(BaseModel):
    name: str
    category: RateCategory
    applies_to_type: Optional[str] = None
    applies_to_id: Optional[str] = None
    amount: float = Field(ge=0)
    unit: str
    rate_kind: Optional[Literal["regular", "overtime"]] = None
    effective_start: Optional[str] = None
    effective_end: Optional[str] = None
    is_active: bool = True
    notes: Optional[str] = None
    template_id: Optional[int] = None


class RateTableEntryUpdate(BaseModel):
    name: Optional[str] = None
    applies_to_type: Optional[str] = None
    applies_to_id: Optional[str] = None
    amount: Optional[float] = None
    unit: Optional[str] = None
    rate_kind: Optional[str] = None
    effective_start: Optional[str] = None
    effective_end: Optional[str] = None
    is_active: Optional[bool] = None
    notes: Optional[str] = None
    changed_by: Optional[str] = None


class RateTableEntryRead(RateTableEntryCreate):
    id: int
    revision_history: List[Dict[str, Any]] = Field(default_factory=list)


class RateTableTemplateRead(BaseModel):
    id: int
    name: str
    category: RateCategory
    amount: float
    unit: str
    rate_kind: Optional[str] = None
    notes: Optional[str] = None


class BudgetCategoryLine(BaseModel):
    category: str
    amount: float
    notes: Optional[str] = None


class BudgetSet(BaseModel):
    total_budget: float = Field(ge=0)
    category_lines: List[BudgetCategoryLine] = Field(default_factory=list)
    notes: Optional[str] = None


class BudgetSummaryRead(BaseModel):
    total_budget: float
    open_estimated_cost: float
    open_committed_cost: float
    actual_cost: float
    projected_incident_cost: float
    remaining_budget: float
    projected_budget_variance: float
    category_lines: List[Dict[str, Any]] = Field(default_factory=list)
    notes: Optional[str] = None


class ManualEstimateCreate(BaseModel):
    description: str
    category: str
    source_type: Optional[str] = None
    source_id: Optional[str] = None
    task_id: Optional[str] = None
    resource_request_id: Optional[str] = None
    resource_request_item_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    operational_period_id: Optional[str] = None
    quantity: float = 1.0
    unit: Optional[str] = None
    amount: float = Field(ge=0)
    status: EstimateStatus = "estimated"
    notes: Optional[str] = None
    created_by: Optional[str] = None


class CalculatedEstimateCreate(BaseModel):
    description: str
    rate_table_entry_id: int
    task_id: Optional[str] = None
    resource_request_id: Optional[str] = None
    resource_request_item_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    operational_period_id: Optional[str] = None
    quantity: float = Field(gt=0)
    status: EstimateStatus = "estimated"
    notes: Optional[str] = None
    created_by: Optional[str] = None


class EstimateRead(BaseModel):
    id: int
    incident_id: str
    description: str
    category: str
    source_type: str
    source_id: Optional[str] = None
    task_id: Optional[str] = None
    resource_request_id: Optional[str] = None
    resource_request_item_id: Optional[str] = None
    resource_type: Optional[str] = None
    resource_id: Optional[str] = None
    operational_period_id: Optional[str] = None
    quantity: float
    unit: Optional[str] = None
    rate_snapshot: Optional[Dict[str, Any]] = None
    calc_method: str
    calc_inputs: Dict[str, Any] = Field(default_factory=dict)
    original_amount: float
    satisfied_amount: float
    remaining_amount: float
    status: EstimateStatus
    closed: bool
    satisfied: bool
    closed_reason: Optional[str] = None
    linked_actual_line_ids: List[str] = Field(default_factory=list)
    notes: Optional[str] = None
    created_by: Optional[str] = None
    audit_history: List[Dict[str, Any]] = Field(default_factory=list)
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class ActualCostDocumentCreate(BaseModel):
    vendor: str
    document_number: Optional[str] = None
    document_date: str
    subtotal: float = Field(ge=0)
    tax: float = Field(default=0, ge=0)
    shipping_fees: float = Field(default=0, ge=0)
    notes: Optional[str] = None
    entered_by: Optional[str] = None


class ActualCostDocumentRead(ActualCostDocumentCreate):
    id: int
    total: float
    verification_status: VerificationStatus
    paid: bool
    paid_date: Optional[str] = None
    paid_reference: Optional[str] = None
    audit_history: List[Dict[str, Any]] = Field(default_factory=list)


class ActualCostLineLink(BaseModel):
    estimate_id: int
    amount: float = Field(ge=0)


class ActualCostLineCreate(BaseModel):
    description: str
    category: str
    quantity: float = 1.0
    unit_price: float = Field(ge=0)
    attributable_tax: float = 0.0
    attributable_shipping: float = 0.0
    attributable_fees: float = 0.0
    linked_resource_request_item_id: Optional[str] = None
    notes: Optional[str] = None
    links: List[ActualCostLineLink] = Field(default_factory=list)


class ActualCostLineRead(BaseModel):
    id: int
    document_id: int
    description: str
    category: str
    quantity: float
    unit_price: float
    line_subtotal: float
    attributable_extra: float
    linked_estimate_ids: List[int] = Field(default_factory=list)
    linked_resource_request_item_id: Optional[str] = None
    notes: Optional[str] = None


class ApprovalRecordCreate(BaseModel):
    record_type: str
    record_id: int
    approver_id: Optional[str] = None
    approver_role: Optional[str] = None
    action: str
    comments: Optional[str] = None


class ApprovalRecordRead(ApprovalRecordCreate):
    id: int
    timestamp: datetime


class AttachmentCreate(BaseModel):
    record_type: str
    record_id: int
    filename: str
    file_path: str
    file_type: Optional[str] = None
    attachment_type: str = "Receipt"
    uploaded_by: Optional[str] = None
    notes: Optional[str] = None


class AttachmentRead(AttachmentCreate):
    id: int
    uploaded_at: datetime


class FinanceDashboardSnapshot(BaseModel):
    total_budget: float
    open_estimated_cost: float
    open_committed_cost: float
    actual_cost: float
    projected_incident_cost: float
    remaining_budget: float
    projected_budget_variance: float
    open_estimate_count: int
    committed_pending_documentation: int
    estimate_count: int


class TaskFinanceSummaryRead(BaseModel):
    task_id: str
    estimated_total: float
    committed_total: float
    remaining_open_estimate: float
    actual_total: float
    shared_actual_total: float
    estimates: List[Dict[str, Any]] = Field(default_factory=list)


class PendingApprovalRow(BaseModel):
    record_type: str
    record_id: int
    description: str
    amount: float
    status: str
