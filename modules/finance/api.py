from __future__ import annotations

from fastapi import APIRouter

from modules.finance import services
from modules.finance.models.schemas import (
    AttachmentCreate,
    AttachmentRead,
    FinanceDashboardSnapshot,
    FinanceExpenseCreate,
    FinanceExpenseRead,
    FinanceExpenseUpdate,
    FinanceForecastCreate,
    FinanceForecastRead,
    FuelForecastLineCreate,
    FuelForecastLineRead,
    FuelPriceProfileCreate,
    FuelPriceProfileRead,
    FuelReportRow,
    FundingSourceCreate,
    FundingSourceRead,
    PendingApprovalRow,
)

router = APIRouter(prefix="/api/finance", tags=["finance"])


@router.get("/dashboard", response_model=FinanceDashboardSnapshot)
def get_dashboard(incident_id: str):
    return services.get_dashboard_snapshot(incident_id)


@router.get("/fuel-prices", response_model=list[FuelPriceProfileRead])
def list_fuel_prices(incident_id: str):
    return services.list_fuel_price_profiles(incident_id)


@router.get("/fuel-prices/active", response_model=FuelPriceProfileRead | None)
def get_active_fuel_price(incident_id: str):
    return services.get_active_fuel_price_profile(incident_id)


@router.post("/fuel-prices", response_model=FuelPriceProfileRead)
def create_fuel_price(incident_id: str, data: FuelPriceProfileCreate):
    return services.create_fuel_price_profile(incident_id, data)


@router.post("/fuel-prices/{profile_id}/set-active")
def set_active_fuel_price(incident_id: str, profile_id: int):
    services.set_active_fuel_price_profile(incident_id, profile_id)
    return {"status": "ok"}


@router.get("/forecasts", response_model=list[FinanceForecastRead])
def list_forecasts(incident_id: str):
    return services.list_forecasts(incident_id)


@router.post("/forecasts", response_model=FinanceForecastRead)
def create_forecast(incident_id: str, data: FinanceForecastCreate):
    return services.create_forecast(incident_id, data)


@router.post("/forecasts/{forecast_id}/fuel-lines", response_model=FuelForecastLineRead)
def add_fuel_line(incident_id: str, forecast_id: int, data: FuelForecastLineCreate):
    return services.add_fuel_forecast_line(incident_id, forecast_id, data)


@router.get("/forecasts/{forecast_id}/fuel-lines", response_model=list[FuelForecastLineRead])
def list_fuel_lines(incident_id: str, forecast_id: int):
    return services.list_fuel_forecast_lines(incident_id, forecast_id)


@router.post("/forecasts/{forecast_id}/submit")
def submit_forecast(incident_id: str, forecast_id: int):
    services.submit_forecast(incident_id, forecast_id, "Finance/Admin")
    return {"status": "ok"}


@router.post("/forecasts/{forecast_id}/approve")
def approve_forecast(incident_id: str, forecast_id: int):
    services.approve_forecast(incident_id, forecast_id, "Finance/Admin")
    return {"status": "ok"}


@router.get("/expenses", response_model=list[FinanceExpenseRead])
def list_expenses(incident_id: str):
    return services.list_expenses(incident_id)


@router.post("/expenses", response_model=FinanceExpenseRead)
def create_expense(incident_id: str, data: FinanceExpenseCreate):
    return services.create_expense(incident_id, data)


@router.get("/expenses/{expense_id}", response_model=FinanceExpenseRead)
def get_expense(incident_id: str, expense_id: int):
    return services.get_expense(incident_id, expense_id)


@router.put("/expenses/{expense_id}")
def update_expense(incident_id: str, expense_id: int, data: FinanceExpenseUpdate):
    services.update_expense(incident_id, expense_id, data)
    return {"status": "ok"}


@router.post("/expenses/{expense_id}/submit")
def submit_expense(incident_id: str, expense_id: int):
    services.submit_expense(incident_id, expense_id, "Finance/Admin")
    return {"status": "ok"}


@router.post("/expenses/{expense_id}/approve")
def approve_expense(incident_id: str, expense_id: int):
    services.approve_expense(incident_id, expense_id, "Finance/Admin")
    return {"status": "ok"}


@router.get("/funding-sources", response_model=list[FundingSourceRead])
def list_funding_sources(incident_id: str):
    return services.list_funding_sources(incident_id)


@router.post("/funding-sources", response_model=FundingSourceRead)
def create_funding_source(incident_id: str, data: FundingSourceCreate):
    return services.create_funding_source(incident_id, data)


@router.get("/{record_type}/{record_id}/attachments", response_model=list[AttachmentRead])
def list_attachments(incident_id: str, record_type: str, record_id: int):
    return services.list_attachments(incident_id, record_type, record_id)


@router.post("/{record_type}/{record_id}/attachments", response_model=AttachmentRead)
def create_attachment(incident_id: str, record_type: str, record_id: int, data: AttachmentCreate):
    payload = data.model_copy(update={"record_type": record_type, "record_id": record_id})
    return services.create_attachment(incident_id, payload)


@router.get("/reports/fuel", response_model=list[FuelReportRow])
def fuel_report(incident_id: str):
    return services.get_fuel_report(incident_id)


@router.get("/approvals/pending", response_model=list[PendingApprovalRow])
def pending_approvals(incident_id: str):
    return services.list_pending_approvals(incident_id)
