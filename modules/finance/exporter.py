from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

from utils import incident_storage

BASE_DIR = Path(__file__).resolve().parent


def _export_dir_for_incident(incident_id: str) -> Path:
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        raise RuntimeError(f"Unknown incident: {incident_id}")
    export_dir = paths.exports / "finance"
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def export_fuel_report(session: Session, incident_id: str) -> Dict[str, str]:
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

    export_dir = _export_dir_for_incident(incident_id)
    path = export_dir / "fuel_report.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["forecast_name", "estimated_gallons", "estimated_cost", "actual_cost", "variance"])
        for row in rows:
            writer.writerow(
                [
                    row["forecast_name"],
                    row["estimated_gallons"],
                    row["estimated_cost"],
                    row["actual_cost"],
                    row["variance"],
                ]
            )
    return {"path": str(path), "created_at": datetime.utcnow().isoformat(timespec="seconds")}


def export_incident_cost_summary(session: Session, incident_id: str) -> Dict[str, str]:
    row = session.execute(
        text(
            """
            SELECT
                COALESCE((SELECT SUM(total_estimated_cost) FROM finance_forecasts WHERE incident_id = :incident_id), 0) AS total_forecast,
                COALESCE((SELECT SUM(amount_total) FROM finance_expenses WHERE incident_id = :incident_id), 0) AS total_actual
            """
        ),
        {"incident_id": incident_id},
    ).mappings().one()
    variance = row["total_actual"] - row["total_forecast"]

    export_dir = _export_dir_for_incident(incident_id)
    path = export_dir / "incident_cost_summary.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["incident_id", "total_forecast", "total_actual", "variance"])
        writer.writerow([incident_id, row["total_forecast"], row["total_actual"], variance])
    return {"path": str(path), "created_at": datetime.utcnow().isoformat(timespec="seconds")}


def list_artifacts(incident_id: str) -> List[Dict[str, str]]:
    export_dir = _export_dir_for_incident(incident_id)
    artifacts = []
    for file in export_dir.iterdir():
        if file.is_file():
            artifacts.append(
                {"path": str(file), "created_at": datetime.fromtimestamp(file.stat().st_mtime).isoformat(timespec="seconds")}
            )
    return sorted(artifacts, key=lambda item: item["created_at"], reverse=True)

