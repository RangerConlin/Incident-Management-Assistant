from __future__ import annotations

from datetime import date, datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, model_validator


FuelType = Literal["Gasoline", "Diesel", "Jet-A", "100LL"]
ForecastStatus = Literal["Draft", "Submitted", "Approved", "Rejected", "Returned for Information", "Archived"]
ExpenseStatus = Literal["Draft", "Submitted", "Approved", "Denied", "Returned for Information", "Paid/Reimbursed", "Closed", "Cancelled"]


class FuelPriceProfileCreate(BaseModel):
    operational_period_id: Optional[str] = None
    gasoline_price: float = Field(ge=0)
    diesel_price: float = Field(ge=0)
    jet_a_price: float = Field(ge=0)
    aviation_100ll_price: float = Field(ge=0)
    location_note: Optional[str] = None
    source_note: Optional[str] = None
    entered_by: Optional[str] = None
    effective_at: datetime
    is_active: bool = False


class FuelPriceProfileRead(FuelPriceProfileCreate):
    id: int
    entered_at: datetime


class FinanceForecastCreate(BaseModel):
    operational_period_id: Optional[str] = None
    forecast_name: str
    forecast_type: str = "Fuel"
    category: str = "Fuel"
    notes: Optional[str] = None
    created_by: Optional[str] = None


class FinanceForecastRead(FinanceForecastCreate):
    id: int
    status: ForecastStatus
    total_estimated_cost: float
    total_estimated_gallons: float
    created_at: datetime
    submitted_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None


class FuelForecastLineCreate(BaseModel):
    resource_type: Literal["Vehicle", "Aircraft", "Generator", "Equipment", "Other"]
    resource_id: Optional[str] = None
    resource_name: str
    fuel_type: FuelType
    quantity: int = Field(ge=1, default=1)
    estimated_miles_per_resource: Optional[float] = Field(default=None, ge=0)
    estimated_mpg: Optional[float] = Field(default=None, gt=0)
    estimated_hours: Optional[float] = Field(default=None, ge=0)
    gallons_per_hour: Optional[float] = Field(default=None, gt=0)
    fuel_price: float = Field(ge=0)
    linked_task_id: Optional[str] = None
    notes: Optional[str] = None

    @model_validator(mode="after")
    def validate_usage_inputs(self) -> "FuelForecastLineCreate":
        has_miles = self.estimated_miles_per_resource is not None and self.estimated_mpg is not None
        has_hours = self.estimated_hours is not None and self.gallons_per_hour is not None
        if not has_miles and not has_hours:
            raise ValueError("Provide either miles + MPG or hours + gallons/hour.")
        return self


class FuelForecastLineRead(FuelForecastLineCreate):
    id: int
    forecast_id: int
    estimated_total_miles: float
    estimated_gallons: float
    estimated_cost: float


class FundingSourceCreate(BaseModel):
    name: str
    code: Optional[str] = None
    type: str = "Unknown"
    agency: Optional[str] = None
    starting_balance: Optional[float] = None
    current_balance: Optional[float] = None
    notes: Optional[str] = None
    is_active: bool = True


class FundingSourceRead(FundingSourceCreate):
    id: int


class FinanceExpenseCreate(BaseModel):
    operational_period_id: Optional[str] = None
    category: str
    subcategory: Optional[str] = None
    description: str
    vendor: Optional[str] = None
    expense_datetime: datetime
    amount_subtotal: float = Field(ge=0)
    amount_tax: float = Field(default=0, ge=0)
    amount_tip: float = Field(default=0, ge=0)
    payment_method: Optional[str] = None
    funding_source_id: Optional[int] = None
    entered_by: Optional[str] = None
    notes: Optional[str] = None
    linked_forecast_id: Optional[int] = None
    receipt_attached: bool = False


class FinanceExpenseUpdate(BaseModel):
    status: Optional[ExpenseStatus] = None
    approved_by: Optional[str] = None
    notes: Optional[str] = None
    receipt_attached: Optional[bool] = None


class FinanceExpenseRead(FinanceExpenseCreate):
    id: int
    expense_number: str
    amount_total: float
    status: ExpenseStatus
    entered_at: datetime
    submitted_at: Optional[datetime] = None
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    paid_at: Optional[datetime] = None


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
    total_forecast_cost: float
    total_actual_cost: float
    fuel_forecast_cost: float
    fuel_actual_cost: float
    pending_approvals: int
    missing_receipts: int
    forecast_count: int
    expense_count: int


class FuelReportRow(BaseModel):
    forecast_name: str
    resource_name: str
    fuel_type: str
    estimated_gallons: float
    estimated_cost: float
    actual_cost: float
    variance: float


class PendingApprovalRow(BaseModel):
    record_type: str
    record_id: int
    description: str
    amount: float
    submitted_at: Optional[datetime] = None
    status: str
