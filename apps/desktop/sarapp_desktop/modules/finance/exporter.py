from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path
from typing import Dict, List

from utils import incident_storage

from . import services

BASE_DIR = Path(__file__).resolve().parent


def _export_dir_for_incident(incident_id: str) -> Path:
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        raise RuntimeError(f"Unknown incident: {incident_id}")
    export_dir = paths.exports / "finance"
    export_dir.mkdir(parents=True, exist_ok=True)
    return export_dir


def export_fuel_report(incident_id: str) -> Dict[str, str]:
    rows = services.get_fuel_report(incident_id)

    export_dir = _export_dir_for_incident(incident_id)
    path = export_dir / "fuel_report.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["forecast_name", "estimated_gallons", "estimated_cost", "actual_cost", "variance"])
        for row in rows:
            writer.writerow(
                [
                    row.forecast_name,
                    row.estimated_gallons,
                    row.estimated_cost,
                    row.actual_cost,
                    row.variance,
                ]
            )
    return {"path": str(path), "created_at": datetime.utcnow().isoformat(timespec="seconds")}


def export_incident_cost_summary(incident_id: str) -> Dict[str, str]:
    snapshot = services.get_dashboard_snapshot(incident_id)
    variance = snapshot.total_actual_cost - snapshot.total_forecast_cost

    export_dir = _export_dir_for_incident(incident_id)
    path = export_dir / "incident_cost_summary.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["incident_id", "total_forecast", "total_actual", "variance"])
        writer.writerow([incident_id, snapshot.total_forecast_cost, snapshot.total_actual_cost, variance])
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

