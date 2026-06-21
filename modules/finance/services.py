from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text

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
from .repository import with_incident_session


def _normalize_bool(value: Any) -> bool:
    return bool(value) if value is not None else False


def _fetch_one(session, query: str, params: dict[str, Any]) -> dict[str, Any]:
    row = session.execute(text(query), params).mappings().first()
    if row is None:
        raise ValueError("Requested finance record was not found.")
    return dict(row)


def _require_forecast(session, incident_id: str, forecast_id: int) -> dict[str, Any]:
    return _fetch_one(
        session,
        """
        SELECT * FROM finance_forecasts
        WHERE id = :id AND incident_id = :incident_id
        """,
        {"id": forecast_id, "incident_id": incident_id},
    )


def _require_expense(session, incident_id: str, expense_id: int) -> dict[str, Any]:
    return _fetch_one(
        session,
        """
        SELECT * FROM finance_expenses
        WHERE id = :id AND incident_id = :incident_id
        """,
        {"id": expense_id, "incident_id": incident_id},
    )


def _require_fuel_price_profile(session, incident_id: str, profile_id: int) -> dict[str, Any]:
    return _fetch_one(
        session,
        """
        SELECT * FROM finance_fuel_price_profiles
        WHERE id = :id AND incident_id = :incident_id
        """,
        {"id": profile_id, "incident_id": incident_id},
    )


def _calc_line_totals(data: FuelForecastLineCreate) -> tuple[float, float, float]:
    total_miles = (data.estimated_miles_per_resource or 0) * data.quantity
    gallons_from_miles = total_miles / data.estimated_mpg if data.estimated_mpg else 0
    gallons_from_hours = (data.estimated_hours or 0) * (data.gallons_per_hour or 0)
    gallons = gallons_from_miles if gallons_from_miles > 0 else gallons_from_hours
    cost = gallons * data.fuel_price
    return total_miles, gallons, cost


def _refresh_forecast_totals(session, incident_id: str, forecast_id: int) -> None:
    totals = session.execute(
        text(
            """
            SELECT COALESCE(SUM(estimated_gallons), 0) AS gallons,
                   COALESCE(SUM(estimated_cost), 0) AS cost
            FROM finance_fuel_forecast_lines
            WHERE forecast_id = :forecast_id
            """
        ),
        {"forecast_id": forecast_id},
    ).mappings().one()
    session.execute(
        text(
            """
            UPDATE finance_forecasts
            SET total_estimated_gallons = :gallons,
                total_estimated_cost = :cost
            WHERE id = :forecast_id AND incident_id = :incident_id
            """
        ),
        {
            "forecast_id": forecast_id,
            "incident_id": incident_id,
            "gallons": totals["gallons"],
            "cost": totals["cost"],
        },
    )


def _record_approval(
    session,
    incident_id: str,
    record_type: str,
    record_id: int,
    action: str,
    approver_id: str | None = None,
    approver_role: str | None = None,
    comments: str | None = None,
    timestamp: datetime | None = None,
) -> None:
    session.execute(
        text(
            """
            INSERT INTO finance_approvals (
                incident_id, record_type, record_id, approver_id, approver_role, action, comments, timestamp
            )
            VALUES (
                :incident_id, :record_type, :record_id, :approver_id, :approver_role, :action, :comments, :timestamp
            )
            """
        ),
        {
            "incident_id": incident_id,
            "record_type": record_type,
            "record_id": record_id,
            "approver_id": approver_id,
            "approver_role": approver_role,
            "action": action,
            "comments": comments,
            "timestamp": timestamp or datetime.utcnow(),
        },
    )


def list_fuel_price_profiles(incident_id: str) -> list[FuelPriceProfileRead]:
    with with_incident_session(incident_id) as session:
        rows = session.execute(
            text(
                """
                SELECT * FROM finance_fuel_price_profiles
                WHERE incident_id = :incident_id
                ORDER BY effective_at DESC, id DESC
                """
            ),
            {"incident_id": incident_id},
        ).mappings().all()
        return [FuelPriceProfileRead(**{**row, "is_active": _normalize_bool(row["is_active"])}) for row in rows]


def create_fuel_price_profile(incident_id: str, data: FuelPriceProfileCreate) -> FuelPriceProfileRead:
    with with_incident_session(incident_id) as session:
        if data.is_active:
            session.execute(
                text(
                    """
                    UPDATE finance_fuel_price_profiles
                    SET is_active = 0
                    WHERE incident_id = :incident_id
                    """
                ),
                {"incident_id": incident_id},
            )
        now = datetime.utcnow()
        result = session.execute(
            text(
                """
                INSERT INTO finance_fuel_price_profiles (
                    incident_id, operational_period_id, gasoline_price, diesel_price, jet_a_price,
                    aviation_100ll_price, location_note, source_note, entered_by, entered_at,
                    effective_at, is_active
                )
                VALUES (
                    :incident_id, :operational_period_id, :gasoline_price, :diesel_price, :jet_a_price,
                    :aviation_100ll_price, :location_note, :source_note, :entered_by, :entered_at,
                    :effective_at, :is_active
                )
                """
            ),
            {
                "incident_id": incident_id,
                "entered_at": now,
                "is_active": 1 if data.is_active else 0,
                **data.model_dump(),
            },
        )
        profile_id = result.lastrowid
        session.commit()
        return get_fuel_price_profile(incident_id, profile_id)


def get_fuel_price_profile(incident_id: str, profile_id: int) -> FuelPriceProfileRead:
    with with_incident_session(incident_id) as session:
        row = _require_fuel_price_profile(session, incident_id, profile_id)
        return FuelPriceProfileRead(**{**row, "is_active": _normalize_bool(row["is_active"])})


def get_active_fuel_price_profile(incident_id: str) -> FuelPriceProfileRead | None:
    with with_incident_session(incident_id) as session:
        row = session.execute(
            text(
                """
                SELECT * FROM finance_fuel_price_profiles
                WHERE incident_id = :incident_id AND is_active = 1
                ORDER BY effective_at DESC, id DESC
                LIMIT 1
                """
            ),
            {"incident_id": incident_id},
        ).mappings().first()
        if row is None:
            return None
        return FuelPriceProfileRead(**{**row, "is_active": _normalize_bool(row["is_active"])})


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
    with with_incident_session(incident_id) as session:
        _require_fuel_price_profile(session, incident_id, profile_id)
        session.execute(
            text(
                """
                UPDATE finance_fuel_price_profiles
                SET is_active = 0
                WHERE incident_id = :incident_id
                """
            ),
            {"incident_id": incident_id},
        )
        session.execute(
            text(
                """
                UPDATE finance_fuel_price_profiles
                SET is_active = 1
                WHERE id = :id AND incident_id = :incident_id
                """
            ),
            {"id": profile_id, "incident_id": incident_id},
        )
        session.commit()


def list_forecasts(incident_id: str) -> list[FinanceForecastRead]:
    with with_incident_session(incident_id) as session:
        rows = session.execute(
            text(
                """
                SELECT * FROM finance_forecasts
                WHERE incident_id = :incident_id
                ORDER BY created_at DESC, id DESC
                """
            ),
            {"incident_id": incident_id},
        ).mappings().all()
        return [FinanceForecastRead(**row) for row in rows]


def create_forecast(incident_id: str, data: FinanceForecastCreate) -> FinanceForecastRead:
    with with_incident_session(incident_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO finance_forecasts (
                    incident_id, operational_period_id, forecast_name, forecast_type, category,
                    status, total_estimated_cost, total_estimated_gallons, created_by, created_at, notes
                )
                VALUES (
                    :incident_id, :operational_period_id, :forecast_name, :forecast_type, :category,
                    'Draft', 0, 0, :created_by, :created_at, :notes
                )
                """
            ),
            {"incident_id": incident_id, "created_at": datetime.utcnow(), **data.model_dump()},
        )
        forecast_id = result.lastrowid
        session.commit()
        return get_forecast(incident_id, forecast_id)


def get_forecast(incident_id: str, forecast_id: int) -> FinanceForecastRead:
    with with_incident_session(incident_id) as session:
        row = _require_forecast(session, incident_id, forecast_id)
        return FinanceForecastRead(**row)


def add_fuel_forecast_line(incident_id: str, forecast_id: int, data: FuelForecastLineCreate) -> FuelForecastLineRead:
    total_miles, gallons, cost = _calc_line_totals(data)
    with with_incident_session(incident_id) as session:
        _require_forecast(session, incident_id, forecast_id)
        result = session.execute(
            text(
                """
                INSERT INTO finance_fuel_forecast_lines (
                    forecast_id, resource_type, resource_id, resource_name, fuel_type, quantity,
                    estimated_miles_per_resource, estimated_total_miles, estimated_mpg,
                    estimated_hours, gallons_per_hour, fuel_price, estimated_gallons,
                    estimated_cost, linked_task_id, notes
                )
                VALUES (
                    :forecast_id, :resource_type, :resource_id, :resource_name, :fuel_type, :quantity,
                    :estimated_miles_per_resource, :estimated_total_miles, :estimated_mpg,
                    :estimated_hours, :gallons_per_hour, :fuel_price, :estimated_gallons,
                    :estimated_cost, :linked_task_id, :notes
                )
                """
            ),
            {
                "forecast_id": forecast_id,
                "estimated_total_miles": total_miles,
                "estimated_gallons": gallons,
                "estimated_cost": cost,
                **data.model_dump(),
            },
        )
        line_id = result.lastrowid
        _refresh_forecast_totals(session, incident_id, forecast_id)
        session.commit()
        row = _fetch_one(
            session,
            """
            SELECT l.*
            FROM finance_fuel_forecast_lines l
            JOIN finance_forecasts f ON f.id = l.forecast_id
            WHERE l.id = :id AND f.incident_id = :incident_id
            """,
            {"id": line_id, "incident_id": incident_id},
        )
        return FuelForecastLineRead(**row)


def list_fuel_forecast_lines(incident_id: str, forecast_id: int) -> list[FuelForecastLineRead]:
    with with_incident_session(incident_id) as session:
        _require_forecast(session, incident_id, forecast_id)
        rows = session.execute(
            text(
                """
                SELECT l.*
                FROM finance_fuel_forecast_lines l
                JOIN finance_forecasts f ON f.id = l.forecast_id
                WHERE l.forecast_id = :forecast_id AND f.incident_id = :incident_id
                ORDER BY l.id
                """
            ),
            {"forecast_id": forecast_id, "incident_id": incident_id},
        ).mappings().all()
        return [FuelForecastLineRead(**row) for row in rows]


def submit_forecast(incident_id: str, forecast_id: int, approver_role: str | None = None) -> None:
    with with_incident_session(incident_id) as session:
        _require_forecast(session, incident_id, forecast_id)
        submitted_at = datetime.utcnow()
        session.execute(
            text(
                """
                UPDATE finance_forecasts
                SET status = 'Submitted', submitted_at = :submitted_at
                WHERE id = :id AND incident_id = :incident_id
                """
            ),
            {"id": forecast_id, "incident_id": incident_id, "submitted_at": submitted_at},
        )
        _record_approval(
            session,
            incident_id,
            "forecast",
            forecast_id,
            "Submitted",
            approver_role=approver_role,
            timestamp=submitted_at,
        )
        session.commit()


def approve_forecast(
    incident_id: str,
    forecast_id: int,
    approved_by: str | None = None,
    comments: str | None = None,
) -> None:
    with with_incident_session(incident_id) as session:
        _require_forecast(session, incident_id, forecast_id)
        approved_at = datetime.utcnow()
        session.execute(
            text(
                """
                UPDATE finance_forecasts
                SET status = 'Approved', approved_by = :approved_by, approved_at = :approved_at
                WHERE id = :id AND incident_id = :incident_id
                """
            ),
            {
                "id": forecast_id,
                "incident_id": incident_id,
                "approved_by": approved_by,
                "approved_at": approved_at,
            },
        )
        _record_approval(
            session,
            incident_id,
            "forecast",
            forecast_id,
            "Approved",
            approver_id=approved_by,
            comments=comments,
            timestamp=approved_at,
        )
        session.commit()


def list_funding_sources(incident_id: str) -> list[FundingSourceRead]:
    with with_incident_session(incident_id) as session:
        rows = session.execute(
            text(
                """
                SELECT * FROM finance_funding_sources
                WHERE incident_id = :incident_id
                ORDER BY name
                """
            ),
            {"incident_id": incident_id},
        ).mappings().all()
        return [FundingSourceRead(**{**row, "is_active": _normalize_bool(row["is_active"])}) for row in rows]


def create_funding_source(incident_id: str, data: FundingSourceCreate) -> FundingSourceRead:
    with with_incident_session(incident_id) as session:
        result = session.execute(
            text(
                """
                INSERT INTO finance_funding_sources (
                    incident_id, name, code, type, agency, starting_balance,
                    current_balance, notes, is_active
                )
                VALUES (
                    :incident_id, :name, :code, :type, :agency, :starting_balance,
                    :current_balance, :notes, :is_active
                )
                """
            ),
            {"incident_id": incident_id, "is_active": 1 if data.is_active else 0, **data.model_dump()},
        )
        source_id = result.lastrowid
        session.commit()
        row = _fetch_one(
            session,
            """
            SELECT * FROM finance_funding_sources
            WHERE id = :id AND incident_id = :incident_id
            """,
            {"id": source_id, "incident_id": incident_id},
        )
        return FundingSourceRead(**{**row, "is_active": _normalize_bool(row["is_active"])})


def list_expenses(incident_id: str) -> list[FinanceExpenseRead]:
    with with_incident_session(incident_id) as session:
        rows = session.execute(
            text(
                """
                SELECT * FROM finance_expenses
                WHERE incident_id = :incident_id
                ORDER BY expense_datetime DESC, id DESC
                """
            ),
            {"incident_id": incident_id},
        ).mappings().all()
        return [FinanceExpenseRead(**{**row, "receipt_attached": _normalize_bool(row["receipt_attached"])}) for row in rows]


def create_expense(incident_id: str, data: FinanceExpenseCreate) -> FinanceExpenseRead:
    with with_incident_session(incident_id) as session:
        if data.linked_forecast_id is not None:
            _require_forecast(session, incident_id, data.linked_forecast_id)
        count = session.execute(
            text("SELECT COUNT(*) FROM finance_expenses WHERE incident_id = :incident_id"),
            {"incident_id": incident_id},
        ).scalar_one()
        expense_number = f"EXP-{count + 1:04d}"
        total = data.amount_subtotal + data.amount_tax + data.amount_tip
        result = session.execute(
            text(
                """
                INSERT INTO finance_expenses (
                    incident_id, operational_period_id, expense_number, category, subcategory, description,
                    vendor, expense_datetime, amount_subtotal, amount_tax, amount_tip, amount_total,
                    payment_method, funding_source_id, status, entered_by, entered_at, notes,
                    linked_forecast_id, receipt_attached
                )
                VALUES (
                    :incident_id, :operational_period_id, :expense_number, :category, :subcategory, :description,
                    :vendor, :expense_datetime, :amount_subtotal, :amount_tax, :amount_tip, :amount_total,
                    :payment_method, :funding_source_id, 'Draft', :entered_by, :entered_at, :notes,
                    :linked_forecast_id, :receipt_attached
                )
                """
            ),
            {
                "incident_id": incident_id,
                "expense_number": expense_number,
                "amount_total": total,
                "entered_at": datetime.utcnow(),
                "receipt_attached": 1 if data.receipt_attached else 0,
                **data.model_dump(),
            },
        )
        expense_id = result.lastrowid
        session.commit()
        return get_expense(incident_id, expense_id)


def get_expense(incident_id: str, expense_id: int) -> FinanceExpenseRead:
    with with_incident_session(incident_id) as session:
        row = _require_expense(session, incident_id, expense_id)
        return FinanceExpenseRead(**{**row, "receipt_attached": _normalize_bool(row["receipt_attached"])})


def update_expense(incident_id: str, expense_id: int, data: FinanceExpenseUpdate) -> None:
    fields = {k: v for k, v in data.model_dump(exclude_none=True).items()}
    if not fields:
        return
    if "receipt_attached" in fields:
        fields["receipt_attached"] = 1 if fields["receipt_attached"] else 0
    clauses = ", ".join(f"{field} = :{field}" for field in fields)
    with with_incident_session(incident_id) as session:
        _require_expense(session, incident_id, expense_id)
        session.execute(
            text(f"UPDATE finance_expenses SET {clauses} WHERE id = :id AND incident_id = :incident_id"),
            {"id": expense_id, "incident_id": incident_id, **fields},
        )
        session.commit()


def submit_expense(incident_id: str, expense_id: int, approver_role: str | None = None) -> None:
    with with_incident_session(incident_id) as session:
        _require_expense(session, incident_id, expense_id)
        submitted_at = datetime.utcnow()
        session.execute(
            text(
                """
                UPDATE finance_expenses
                SET status = 'Submitted', submitted_at = :submitted_at
                WHERE id = :id AND incident_id = :incident_id
                """
            ),
            {"id": expense_id, "incident_id": incident_id, "submitted_at": submitted_at},
        )
        _record_approval(
            session,
            incident_id,
            "expense",
            expense_id,
            "Submitted",
            approver_role=approver_role,
            timestamp=submitted_at,
        )
        session.commit()


def approve_expense(
    incident_id: str,
    expense_id: int,
    approved_by: str | None = None,
    comments: str | None = None,
) -> None:
    with with_incident_session(incident_id) as session:
        _require_expense(session, incident_id, expense_id)
        approved_at = datetime.utcnow()
        session.execute(
            text(
                """
                UPDATE finance_expenses
                SET status = 'Approved', approved_by = :approved_by, approved_at = :approved_at
                WHERE id = :id AND incident_id = :incident_id
                """
            ),
            {
                "id": expense_id,
                "incident_id": incident_id,
                "approved_by": approved_by,
                "approved_at": approved_at,
            },
        )
        _record_approval(
            session,
            incident_id,
            "expense",
            expense_id,
            "Approved",
            approver_id=approved_by,
            comments=comments,
            timestamp=approved_at,
        )
        session.commit()


def mark_expense_status(
    incident_id: str,
    expense_id: int,
    status: str,
    actor: str | None = None,
    comments: str | None = None,
) -> None:
    with with_incident_session(incident_id) as session:
        _require_expense(session, incident_id, expense_id)
        now = datetime.utcnow()
        extra_sets: list[str] = []
        params: dict[str, Any] = {"id": expense_id, "incident_id": incident_id, "status": status}
        if status == "Paid/Reimbursed":
            extra_sets.append("paid_at = :paid_at")
            params["paid_at"] = now
        elif status in {"Returned for Information", "Denied", "Cancelled", "Closed"}:
            extra_sets.append("approved_at = COALESCE(approved_at, :approved_at)")
            params["approved_at"] = now
        set_clause = "status = :status"
        if extra_sets:
            set_clause = f"{set_clause}, " + ", ".join(extra_sets)
        session.execute(
            text(
                f"""
                UPDATE finance_expenses
                SET {set_clause}
                WHERE id = :id AND incident_id = :incident_id
                """
            ),
            params,
        )
        _record_approval(
            session,
            incident_id,
            "expense",
            expense_id,
            status,
            approver_id=actor,
            comments=comments,
            timestamp=now,
        )
        session.commit()


def create_attachment(incident_id: str, data: AttachmentCreate) -> AttachmentRead:
    with with_incident_session(incident_id) as session:
        if data.record_type == "expense":
            _require_expense(session, incident_id, data.record_id)
        elif data.record_type == "forecast":
            _require_forecast(session, incident_id, data.record_id)
        uploaded_at = datetime.utcnow()
        result = session.execute(
            text(
                """
                INSERT INTO finance_attachments (
                    incident_id, record_type, record_id, filename, file_path, file_type,
                    attachment_type, uploaded_by, uploaded_at, notes
                )
                VALUES (
                    :incident_id, :record_type, :record_id, :filename, :file_path, :file_type,
                    :attachment_type, :uploaded_by, :uploaded_at, :notes
                )
                """
            ),
            {"incident_id": incident_id, "uploaded_at": uploaded_at, **data.model_dump()},
        )
        if data.record_type == "expense":
            session.execute(
                text(
                    """
                    UPDATE finance_expenses
                    SET receipt_attached = 1
                    WHERE id = :id AND incident_id = :incident_id
                    """
                ),
                {"id": data.record_id, "incident_id": incident_id},
            )
        attachment_id = result.lastrowid
        session.commit()
        row = _fetch_one(
            session,
            """
            SELECT * FROM finance_attachments
            WHERE id = :id AND incident_id = :incident_id
            """,
            {"id": attachment_id, "incident_id": incident_id},
        )
        return AttachmentRead(**row)


def list_attachments(incident_id: str, record_type: str, record_id: int) -> list[AttachmentRead]:
    with with_incident_session(incident_id) as session:
        rows = session.execute(
            text(
                """
                SELECT * FROM finance_attachments
                WHERE incident_id = :incident_id AND record_type = :record_type AND record_id = :record_id
                ORDER BY uploaded_at DESC, id DESC
                """
            ),
            {"incident_id": incident_id, "record_type": record_type, "record_id": record_id},
        ).mappings().all()
        return [AttachmentRead(**row) for row in rows]


def list_approvals(incident_id: str, record_type: str, record_id: int) -> list[ApprovalRecordRead]:
    with with_incident_session(incident_id) as session:
        rows = session.execute(
            text(
                """
                SELECT * FROM finance_approvals
                WHERE incident_id = :incident_id AND record_type = :record_type AND record_id = :record_id
                ORDER BY timestamp DESC, id DESC
                """
            ),
            {"incident_id": incident_id, "record_type": record_type, "record_id": record_id},
        ).mappings().all()
        return [ApprovalRecordRead(**row) for row in rows]


def create_approval(incident_id: str, data: ApprovalRecordCreate) -> ApprovalRecordRead:
    with with_incident_session(incident_id) as session:
        if data.record_type == "expense":
            _require_expense(session, incident_id, data.record_id)
        elif data.record_type == "forecast":
            _require_forecast(session, incident_id, data.record_id)
        timestamp = datetime.utcnow()
        result = session.execute(
            text(
                """
                INSERT INTO finance_approvals (
                    incident_id, record_type, record_id, approver_id, approver_role,
                    action, comments, timestamp
                )
                VALUES (
                    :incident_id, :record_type, :record_id, :approver_id, :approver_role,
                    :action, :comments, :timestamp
                )
                """
            ),
            {"incident_id": incident_id, "timestamp": timestamp, **data.model_dump()},
        )
        approval_id = result.lastrowid
        session.commit()
        row = _fetch_one(
            session,
            """
            SELECT * FROM finance_approvals
            WHERE id = :id AND incident_id = :incident_id
            """,
            {"id": approval_id, "incident_id": incident_id},
        )
        return ApprovalRecordRead(**row)


def get_dashboard_snapshot(incident_id: str) -> FinanceDashboardSnapshot:
    with with_incident_session(incident_id) as session:
        row = session.execute(
            text(
                """
                SELECT
                    COALESCE((SELECT SUM(total_estimated_cost) FROM finance_forecasts WHERE incident_id = :incident_id), 0) AS total_forecast_cost,
                    COALESCE((SELECT SUM(amount_total) FROM finance_expenses WHERE incident_id = :incident_id), 0) AS total_actual_cost,
                    COALESCE((SELECT SUM(total_estimated_cost) FROM finance_forecasts WHERE incident_id = :incident_id AND category = 'Fuel'), 0) AS fuel_forecast_cost,
                    COALESCE((SELECT SUM(amount_total) FROM finance_expenses WHERE incident_id = :incident_id AND category = 'Fuel'), 0) AS fuel_actual_cost,
                    COALESCE((SELECT COUNT(*) FROM finance_forecasts WHERE incident_id = :incident_id AND status = 'Submitted'), 0) +
                    COALESCE((SELECT COUNT(*) FROM finance_expenses WHERE incident_id = :incident_id AND status = 'Submitted'), 0) AS pending_approvals,
                    COALESCE((SELECT COUNT(*) FROM finance_expenses WHERE incident_id = :incident_id AND receipt_attached = 0), 0) AS missing_receipts,
                    COALESCE((SELECT COUNT(*) FROM finance_forecasts WHERE incident_id = :incident_id), 0) AS forecast_count,
                    COALESCE((SELECT COUNT(*) FROM finance_expenses WHERE incident_id = :incident_id), 0) AS expense_count
                """
            ),
            {"incident_id": incident_id},
        ).mappings().one()
        return FinanceDashboardSnapshot(**row)


def get_fuel_report(incident_id: str) -> list[FuelReportRow]:
    with with_incident_session(incident_id) as session:
        rows = session.execute(
            text(
                """
                WITH expense_totals AS (
                    SELECT linked_forecast_id AS forecast_id,
                           COALESCE(SUM(amount_total), 0) AS actual_cost
                    FROM finance_expenses
                    WHERE incident_id = :incident_id
                      AND category = 'Fuel'
                      AND linked_forecast_id IS NOT NULL
                    GROUP BY linked_forecast_id
                )
                SELECT
                    f.forecast_name,
                    CASE WHEN COUNT(l.id) = 1 THEN MIN(l.resource_name) ELSE 'Multiple resources' END AS resource_name,
                    CASE WHEN COUNT(DISTINCT l.fuel_type) = 1 THEN MIN(l.fuel_type) ELSE 'Mixed' END AS fuel_type,
                    COALESCE(SUM(l.estimated_gallons), 0) AS estimated_gallons,
                    COALESCE(SUM(l.estimated_cost), 0) AS estimated_cost,
                    COALESCE(et.actual_cost, 0) AS actual_cost,
                    COALESCE(et.actual_cost, 0) - COALESCE(SUM(l.estimated_cost), 0) AS variance
                FROM finance_fuel_forecast_lines l
                JOIN finance_forecasts f ON f.id = l.forecast_id
                LEFT JOIN expense_totals et ON et.forecast_id = f.id
                WHERE f.incident_id = :incident_id
                GROUP BY f.id, f.forecast_name, et.actual_cost
                ORDER BY f.forecast_name
                """
            ),
            {"incident_id": incident_id},
        ).mappings().all()
        return [FuelReportRow(**row) for row in rows]


def list_pending_approvals(incident_id: str) -> list[PendingApprovalRow]:
    with with_incident_session(incident_id) as session:
        rows = session.execute(
            text(
                """
                SELECT 'forecast' AS record_type,
                       id AS record_id,
                       forecast_name AS description,
                       total_estimated_cost AS amount,
                       submitted_at,
                       status
                FROM finance_forecasts
                WHERE incident_id = :incident_id AND status = 'Submitted'
                UNION ALL
                SELECT 'expense' AS record_type,
                       id AS record_id,
                       description,
                       amount_total AS amount,
                       submitted_at,
                       status
                FROM finance_expenses
                WHERE incident_id = :incident_id AND status = 'Submitted'
                ORDER BY submitted_at DESC
                """
            ),
            {"incident_id": incident_id},
        ).mappings().all()
        return [PendingApprovalRow(**row) for row in rows]

