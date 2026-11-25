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


def export_estimates_report(incident_id: str) -> Dict[str, str]:
    rows = services.list_estimates(incident_id)

    export_dir = _export_dir_for_incident(incident_id)
    path = export_dir / "estimates_report.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "id", "description", "category", "task_id", "original_amount",
            "satisfied_amount", "remaining_amount", "status", "closed", "closed_reason",
        ])
        for row in rows:
            writer.writerow([
                row.id, row.description, row.category, row.task_id or "", row.original_amount,
                row.satisfied_amount, row.remaining_amount, row.status, row.closed, row.closed_reason or "",
            ])
    return {"path": str(path), "created_at": datetime.utcnow().isoformat(timespec="seconds")}


def export_incident_cost_summary(incident_id: str) -> Dict[str, str]:
    summary = services.get_budget(incident_id)

    export_dir = _export_dir_for_incident(incident_id)
    path = export_dir / "incident_cost_summary.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow([
            "incident_id", "total_budget", "open_estimated_cost", "open_committed_cost",
            "actual_cost", "projected_incident_cost", "remaining_budget", "projected_budget_variance",
        ])
        writer.writerow([
            incident_id, summary.total_budget, summary.open_estimated_cost, summary.open_committed_cost,
            summary.actual_cost, summary.projected_incident_cost, summary.remaining_budget, summary.projected_budget_variance,
        ])
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

