from __future__ import annotations

from typing import Any

from .models.schemas import (
    ApprovalRecordCreate,
    ApprovalRecordRead,
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


def _client():
    from utils.api_client import api_client

    return api_client


def _base(incident_id: str) -> str:
    return f"/api/incidents/{incident_id}/finance"


def _post(path: str, *, json: Any = None, params: dict[str, Any] | None = None) -> Any:
    from utils.api_client import APIError

    try:
        return _client().post(path, json=json, params=params)
    except APIError as exc:
        raise ValueError(str(exc)) from exc


def _patch(path: str, *, json: Any = None) -> Any:
    from utils.api_client import APIError

    try:
        return _client().patch(path, json=json)
    except APIError as exc:
        raise ValueError(str(exc)) from exc


def list_fuel_price_profiles(incident_id: str) -> list[FuelPriceProfileRead]:
    rows = _client().get(f"{_base(incident_id)}/fuel-price-profiles") or []
    return [FuelPriceProfileRead(**row) for row in rows]


def create_fuel_price_profile(incident_id: str, data: FuelPriceProfileCreate) -> FuelPriceProfileRead:
    row = _post(f"{_base(incident_id)}/fuel-price-profiles", json=_jsonable(data))
    return FuelPriceProfileRead(**row)


def get_fuel_price_profile(incident_id: str, profile_id: int) -> FuelPriceProfileRead:
    row = _client().get(f"{_base(incident_id)}/fuel-price-profiles/{profile_id}")
    return FuelPriceProfileRead(**row)


def get_active_fuel_price_profile(incident_id: str) -> FuelPriceProfileRead | None:
    row = _client().get(f"{_base(incident_id)}/fuel-price-profiles/active")
    return FuelPriceProfileRead(**row) if row else None


def get_fuel_unit_price(incident_id: str, fuel_type: str) -> float | None:
    profile = get_active_fuel_price_profile(incident_id)
    if profile is None:
        return None
    mapping = {
        "Gasoline": profile.gasoline_price,
        "Diesel": profile.diesel_price,
        "Jet-A": profile.jet_a_price,
        "100LL": profile.aviation_100ll_price,
    }
    return mapping.get(fuel_type)


def set_active_fuel_price_profile(incident_id: str, profile_id: int) -> None:
    _post(f"{_base(incident_id)}/fuel-price-profiles/{profile_id}/activate")


def list_forecasts(incident_id: str) -> list[FinanceForecastRead]:
    rows = _client().get(f"{_base(incident_id)}/forecasts") or []
    return [FinanceForecastRead(**row) for row in rows]


def create_forecast(incident_id: str, data: FinanceForecastCreate) -> FinanceForecastRead:
    row = _post(f"{_base(incident_id)}/forecasts", json=_jsonable(data))
    return FinanceForecastRead(**row)


def get_forecast(incident_id: str, forecast_id: int) -> FinanceForecastRead:
    row = _client().get(f"{_base(incident_id)}/forecasts/{forecast_id}")
    return FinanceForecastRead(**row)


def add_fuel_forecast_line(incident_id: str, forecast_id: int, data: FuelForecastLineCreate) -> FuelForecastLineRead:
    row = _post(f"{_base(incident_id)}/forecasts/{forecast_id}/fuel-lines", json=_jsonable(data))
    return FuelForecastLineRead(**row)


def list_fuel_forecast_lines(incident_id: str, forecast_id: int) -> list[FuelForecastLineRead]:
    rows = _client().get(f"{_base(incident_id)}/forecasts/{forecast_id}/fuel-lines") or []
    return [FuelForecastLineRead(**row) for row in rows]


def submit_forecast(incident_id: str, forecast_id: int, approver_role: str | None = None) -> None:
    _post(
        f"{_base(incident_id)}/forecasts/{forecast_id}/submit",
        params={"approver_role": approver_role} if approver_role else None,
    )


def approve_forecast(
    incident_id: str,
    forecast_id: int,
    approved_by: str | None = None,
    comments: str | None = None,
) -> None:
    params = {k: v for k, v in {"approved_by": approved_by, "comments": comments}.items() if v is not None}
    _post(f"{_base(incident_id)}/forecasts/{forecast_id}/approve", params=params or None)


def list_funding_sources(incident_id: str) -> list[FundingSourceRead]:
    rows = _client().get(f"{_base(incident_id)}/funding-sources") or []
    return [FundingSourceRead(**row) for row in rows]


def create_funding_source(incident_id: str, data: FundingSourceCreate) -> FundingSourceRead:
    row = _post(f"{_base(incident_id)}/funding-sources", json=_jsonable(data))
    return FundingSourceRead(**row)


def list_expenses(incident_id: str) -> list[FinanceExpenseRead]:
    rows = _client().get(f"{_base(incident_id)}/expenses") or []
    return [FinanceExpenseRead(**row) for row in rows]


def create_expense(incident_id: str, data: FinanceExpenseCreate) -> FinanceExpenseRead:
    row = _post(f"{_base(incident_id)}/expenses", json=_jsonable(data))
    return FinanceExpenseRead(**row)


def get_expense(incident_id: str, expense_id: int) -> FinanceExpenseRead:
    row = _client().get(f"{_base(incident_id)}/expenses/{expense_id}")
    return FinanceExpenseRead(**row)


def update_expense(incident_id: str, expense_id: int, data: FinanceExpenseUpdate) -> None:
    fields = _jsonable(data, exclude_none=True)
    if not fields:
        return
    _patch(f"{_base(incident_id)}/expenses/{expense_id}", json=fields)


def submit_expense(incident_id: str, expense_id: int, approver_role: str | None = None) -> None:
    _post(
        f"{_base(incident_id)}/expenses/{expense_id}/submit",
        params={"approver_role": approver_role} if approver_role else None,
    )


def approve_expense(
    incident_id: str,
    expense_id: int,
    approved_by: str | None = None,
    comments: str | None = None,
) -> None:
    params = {k: v for k, v in {"approved_by": approved_by, "comments": comments}.items() if v is not None}
    _post(f"{_base(incident_id)}/expenses/{expense_id}/approve", params=params or None)


def mark_expense_status(
    incident_id: str,
    expense_id: int,
    status: str,
    actor: str | None = None,
    comments: str | None = None,
) -> None:
    _post(
        f"{_base(incident_id)}/expenses/{expense_id}/status",
        json={"status": status, "actor": actor, "comments": comments},
    )


def create_attachment(incident_id: str, data: AttachmentCreate) -> AttachmentRead:
    row = _post(f"{_base(incident_id)}/attachments", json=_jsonable(data))
    return AttachmentRead(**row)


def list_attachments(incident_id: str, record_type: str, record_id: int) -> list[AttachmentRead]:
    rows = _client().get(
        f"{_base(incident_id)}/attachments",
        params={"record_type": record_type, "record_id": record_id},
    ) or []
    return [AttachmentRead(**row) for row in rows]


def list_approvals(incident_id: str, record_type: str, record_id: int) -> list[ApprovalRecordRead]:
    rows = _client().get(
        f"{_base(incident_id)}/approvals",
        params={"record_type": record_type, "record_id": record_id},
    ) or []
    return [ApprovalRecordRead(**row) for row in rows]


def create_approval(incident_id: str, data: ApprovalRecordCreate) -> ApprovalRecordRead:
    row = _post(f"{_base(incident_id)}/approvals", json=_jsonable(data))
    return ApprovalRecordRead(**row)


def get_dashboard_snapshot(incident_id: str) -> FinanceDashboardSnapshot:
    row = _client().get(f"{_base(incident_id)}/dashboard")
    return FinanceDashboardSnapshot(**row)


def get_fuel_report(incident_id: str) -> list[FuelReportRow]:
    rows = _client().get(f"{_base(incident_id)}/fuel-report") or []
    return [FuelReportRow(**row) for row in rows]


def list_pending_approvals(incident_id: str) -> list[PendingApprovalRow]:
    rows = _client().get(f"{_base(incident_id)}/pending-approvals") or []
    return [PendingApprovalRow(**row) for row in rows]


def _jsonable(data: Any, *, exclude_none: bool = False) -> dict[str, Any]:
    """Serialize a pydantic model to a JSON-safe dict (datetimes -> ISO strings)."""

    return data.model_dump(mode="json", exclude_none=exclude_none)
