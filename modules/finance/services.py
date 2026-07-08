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


def _cached_docs(incident_id: str, collection: str) -> list[dict[str, Any]] | None:
    """Return cached incident-scoped docs for ``collection``, or None if the
    incident cache isn't loaded for this incident."""
    from utils.incident_cache import incident_cache

    if incident_cache.incident_id != str(incident_id):
        return None
    return incident_cache.get_all(collection)


def _normalize(doc: dict[str, Any]) -> dict[str, Any]:
    """Mirror the server's ``_strip``: expose ``int_id`` as ``id``."""
    return {**doc, "id": doc.get("id") or doc.get("int_id")}


def _sort_key(value: Any) -> tuple[bool, Any]:
    """Sort ``None`` last regardless of the other values' type."""
    return (value is None, value if value is not None else "")


def _sorted_by(docs: list[dict[str, Any]], fields: tuple[tuple[str, bool], ...]) -> list[dict[str, Any]]:
    """Sort by multiple (field, descending) pairs, matching Mongo's compound sort."""
    result = list(docs)
    for field, descending in reversed(fields):
        result.sort(key=lambda d: _sort_key(d.get(field)), reverse=descending)
    return result


def _cached_doc_by_int_id(incident_id: str, collection: str, int_id: int) -> dict[str, Any] | None:
    cached = _cached_docs(incident_id, collection)
    if cached is None:
        return None
    for doc in cached:
        if doc.get("int_id") == int_id:
            return doc
    return None


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
    cached = _cached_docs(incident_id, "finance_fuel_price_profiles")
    if cached is not None:
        ordered = _sorted_by(cached, (("effective_at", True), ("int_id", True)))
        return [FuelPriceProfileRead(**_normalize(row)) for row in ordered]
    rows = _client().get(f"{_base(incident_id)}/fuel-price-profiles") or []
    return [FuelPriceProfileRead(**row) for row in rows]


def create_fuel_price_profile(incident_id: str, data: FuelPriceProfileCreate) -> FuelPriceProfileRead:
    row = _post(f"{_base(incident_id)}/fuel-price-profiles", json=_jsonable(data))
    return FuelPriceProfileRead(**row)


def get_fuel_price_profile(incident_id: str, profile_id: int) -> FuelPriceProfileRead:
    cached = _cached_doc_by_int_id(incident_id, "finance_fuel_price_profiles", profile_id)
    if cached is not None:
        return FuelPriceProfileRead(**_normalize(cached))
    row = _client().get(f"{_base(incident_id)}/fuel-price-profiles/{profile_id}")
    return FuelPriceProfileRead(**row)


def get_active_fuel_price_profile(incident_id: str) -> FuelPriceProfileRead | None:
    cached = _cached_docs(incident_id, "finance_fuel_price_profiles")
    if cached is not None:
        active = [d for d in cached if d.get("is_active")]
        ordered = _sorted_by(active, (("effective_at", True), ("int_id", True)))
        return FuelPriceProfileRead(**_normalize(ordered[0])) if ordered else None
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
    cached = _cached_docs(incident_id, "finance_forecasts")
    if cached is not None:
        ordered = _sorted_by(cached, (("created_at", True), ("int_id", True)))
        return [FinanceForecastRead(**_normalize(row)) for row in ordered]
    rows = _client().get(f"{_base(incident_id)}/forecasts") or []
    return [FinanceForecastRead(**row) for row in rows]


def create_forecast(incident_id: str, data: FinanceForecastCreate) -> FinanceForecastRead:
    row = _post(f"{_base(incident_id)}/forecasts", json=_jsonable(data))
    return FinanceForecastRead(**row)


def get_forecast(incident_id: str, forecast_id: int) -> FinanceForecastRead:
    cached = _cached_doc_by_int_id(incident_id, "finance_forecasts", forecast_id)
    if cached is not None:
        return FinanceForecastRead(**_normalize(cached))
    row = _client().get(f"{_base(incident_id)}/forecasts/{forecast_id}")
    return FinanceForecastRead(**row)


def add_fuel_forecast_line(incident_id: str, forecast_id: int, data: FuelForecastLineCreate) -> FuelForecastLineRead:
    row = _post(f"{_base(incident_id)}/forecasts/{forecast_id}/fuel-lines", json=_jsonable(data))
    return FuelForecastLineRead(**row)


def list_fuel_forecast_lines(incident_id: str, forecast_id: int) -> list[FuelForecastLineRead]:
    cached = _cached_docs(incident_id, "finance_fuel_forecast_lines")
    if cached is not None:
        filtered = [d for d in cached if d.get("forecast_id") == forecast_id]
        ordered = _sorted_by(filtered, (("int_id", False),))
        return [FuelForecastLineRead(**_normalize(row)) for row in ordered]
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
    cached = _cached_docs(incident_id, "finance_funding_sources")
    if cached is not None:
        ordered = _sorted_by(cached, (("name", False),))
        return [FundingSourceRead(**_normalize(row)) for row in ordered]
    rows = _client().get(f"{_base(incident_id)}/funding-sources") or []
    return [FundingSourceRead(**row) for row in rows]


def create_funding_source(incident_id: str, data: FundingSourceCreate) -> FundingSourceRead:
    row = _post(f"{_base(incident_id)}/funding-sources", json=_jsonable(data))
    return FundingSourceRead(**row)


def list_expenses(incident_id: str) -> list[FinanceExpenseRead]:
    cached = _cached_docs(incident_id, "finance_expenses")
    if cached is not None:
        ordered = _sorted_by(cached, (("expense_datetime", True), ("int_id", True)))
        return [FinanceExpenseRead(**_normalize(row)) for row in ordered]
    rows = _client().get(f"{_base(incident_id)}/expenses") or []
    return [FinanceExpenseRead(**row) for row in rows]


def create_expense(incident_id: str, data: FinanceExpenseCreate) -> FinanceExpenseRead:
    row = _post(f"{_base(incident_id)}/expenses", json=_jsonable(data))
    return FinanceExpenseRead(**row)


def get_expense(incident_id: str, expense_id: int) -> FinanceExpenseRead:
    cached = _cached_doc_by_int_id(incident_id, "finance_expenses", expense_id)
    if cached is not None:
        return FinanceExpenseRead(**_normalize(cached))
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
    cached = _cached_docs(incident_id, "finance_attachments")
    if cached is not None:
        filtered = [
            d for d in cached
            if d.get("record_type") == record_type and d.get("record_id") == record_id
        ]
        ordered = _sorted_by(filtered, (("uploaded_at", True), ("int_id", True)))
        return [AttachmentRead(**_normalize(row)) for row in ordered]
    rows = _client().get(
        f"{_base(incident_id)}/attachments",
        params={"record_type": record_type, "record_id": record_id},
    ) or []
    return [AttachmentRead(**row) for row in rows]


def list_approvals(incident_id: str, record_type: str, record_id: int) -> list[ApprovalRecordRead]:
    cached = _cached_docs(incident_id, "finance_approvals")
    if cached is not None:
        filtered = [
            d for d in cached
            if d.get("record_type") == record_type and d.get("record_id") == record_id
        ]
        ordered = _sorted_by(filtered, (("timestamp", True), ("int_id", True)))
        return [ApprovalRecordRead(**_normalize(row)) for row in ordered]
    rows = _client().get(
        f"{_base(incident_id)}/approvals",
        params={"record_type": record_type, "record_id": record_id},
    ) or []
    return [ApprovalRecordRead(**row) for row in rows]


def create_approval(incident_id: str, data: ApprovalRecordCreate) -> ApprovalRecordRead:
    row = _post(f"{_base(incident_id)}/approvals", json=_jsonable(data))
    return ApprovalRecordRead(**row)


def get_dashboard_snapshot(incident_id: str) -> FinanceDashboardSnapshot:
    forecasts = _cached_docs(incident_id, "finance_forecasts")
    expenses = _cached_docs(incident_id, "finance_expenses")
    if forecasts is not None and expenses is not None:
        total_forecast_cost = sum(f.get("total_estimated_cost", 0) for f in forecasts)
        total_actual_cost = sum(e.get("amount_total", 0) for e in expenses)
        fuel_forecast_cost = sum(
            f.get("total_estimated_cost", 0) for f in forecasts if f.get("category") == "Fuel"
        )
        fuel_actual_cost = sum(
            e.get("amount_total", 0) for e in expenses if e.get("category") == "Fuel"
        )
        pending_approvals = (
            sum(1 for f in forecasts if f.get("status") == "Submitted")
            + sum(1 for e in expenses if e.get("status") == "Submitted")
        )
        missing_receipts = sum(1 for e in expenses if not e.get("receipt_attached"))
        return FinanceDashboardSnapshot(
            total_forecast_cost=total_forecast_cost,
            total_actual_cost=total_actual_cost,
            fuel_forecast_cost=fuel_forecast_cost,
            fuel_actual_cost=fuel_actual_cost,
            pending_approvals=pending_approvals,
            missing_receipts=missing_receipts,
            forecast_count=len(forecasts),
            expense_count=len(expenses),
        )
    row = _client().get(f"{_base(incident_id)}/dashboard")
    return FinanceDashboardSnapshot(**row)


def get_fuel_report(incident_id: str) -> list[FuelReportRow]:
    forecasts_cached = _cached_docs(incident_id, "finance_forecasts")
    lines_cached = _cached_docs(incident_id, "finance_fuel_forecast_lines")
    expenses_cached = _cached_docs(incident_id, "finance_expenses")
    if forecasts_cached is not None and lines_cached is not None and expenses_cached is not None:
        forecasts = {f["int_id"]: f for f in forecasts_cached}
        expenses = [
            e for e in expenses_cached
            if e.get("category") == "Fuel" and e.get("linked_forecast_id") is not None
        ]

        expense_totals: dict[int, float] = {}
        for e in expenses:
            fid = e.get("linked_forecast_id")
            expense_totals[fid] = expense_totals.get(fid, 0) + e.get("amount_total", 0)

        grouped: dict[int, list[dict[str, Any]]] = {}
        for line in lines_cached:
            fid = line.get("forecast_id")
            if fid in forecasts:
                grouped.setdefault(fid, []).append(line)

        rows: list[dict[str, Any]] = []
        for fid, lines in grouped.items():
            forecast = forecasts[fid]
            resource_names = {l.get("resource_name") for l in lines}
            fuel_types = {l.get("fuel_type") for l in lines}
            estimated_gallons = sum(l.get("estimated_gallons", 0) for l in lines)
            estimated_cost = sum(l.get("estimated_cost", 0) for l in lines)
            actual_cost = expense_totals.get(fid, 0)
            rows.append({
                "forecast_name": forecast.get("forecast_name", ""),
                "resource_name": next(iter(resource_names)) if len(resource_names) == 1 else "Multiple resources",
                "fuel_type": next(iter(fuel_types)) if len(fuel_types) == 1 else "Mixed",
                "estimated_gallons": estimated_gallons,
                "estimated_cost": estimated_cost,
                "actual_cost": actual_cost,
                "variance": actual_cost - estimated_cost,
            })
        rows.sort(key=lambda r: r["forecast_name"])
        return [FuelReportRow(**row) for row in rows]

    rows = _client().get(f"{_base(incident_id)}/fuel-report") or []
    return [FuelReportRow(**row) for row in rows]


def list_pending_approvals(incident_id: str) -> list[PendingApprovalRow]:
    forecasts = _cached_docs(incident_id, "finance_forecasts")
    expenses = _cached_docs(incident_id, "finance_expenses")
    if forecasts is not None and expenses is not None:
        rows = [
            {
                "record_type": "forecast",
                "record_id": f["int_id"],
                "description": f.get("forecast_name", ""),
                "amount": f.get("total_estimated_cost", 0),
                "submitted_at": f.get("submitted_at"),
                "status": f.get("status"),
            }
            for f in forecasts if f.get("status") == "Submitted"
        ] + [
            {
                "record_type": "expense",
                "record_id": e["int_id"],
                "description": e.get("description", ""),
                "amount": e.get("amount_total", 0),
                "submitted_at": e.get("submitted_at"),
                "status": e.get("status"),
            }
            for e in expenses if e.get("status") == "Submitted"
        ]
        rows.sort(key=lambda r: r["submitted_at"] or "", reverse=True)
        return [PendingApprovalRow(**row) for row in rows]

    rows = _client().get(f"{_base(incident_id)}/pending-approvals") or []
    return [PendingApprovalRow(**row) for row in rows]


def _jsonable(data: Any, *, exclude_none: bool = False) -> dict[str, Any]:
    """Serialize a pydantic model to a JSON-safe dict (datetimes -> ISO strings)."""

    return data.model_dump(mode="json", exclude_none=exclude_none)
