from __future__ import annotations

from datetime import date
from sqlalchemy import text
from sqlalchemy.orm import Session


def resolve_labor_cost(
    session: Session,
    labor_rate_id: int,
    work_date: date,
    hours: float,
    overtime_hours: float = 0.0,
) -> float:
    row = session.execute(
        text(
            """
            SELECT rate_per_hour, overtime_mult FROM labor_rates
            WHERE id=:id AND :d >= effective_from AND (effective_to IS NULL OR :d <= effective_to)
            """
        ),
        {"id": labor_rate_id, "d": work_date},
    ).mappings().first()
    if not row:
        return 0.0
    return row["rate_per_hour"] * hours + row["rate_per_hour"] * row["overtime_mult"] * overtime_hours


def resolve_equipment_cost(
    session: Session,
    equipment_rate_id: int,
    work_date: date,
    hours: float,
) -> float:
    row = session.execute(
        text(
            """
            SELECT rate_per_hour FROM equipment_rates
            WHERE id=:id AND :d >= effective_from AND (effective_to IS NULL OR :d <= effective_to)
            """
        ),
        {"id": equipment_rate_id, "d": work_date},
    ).mappings().first()
    if not row:
        return 0.0
    return row["rate_per_hour"] * hours
