from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from utils import incident_storage
from typing import Dict, List

from sqlalchemy import text
from sqlalchemy.orm import Session

BASE_DIR = Path(__file__).resolve().parent


def export_daily_cost_summary(session: Session, incident_id: str, day: str) -> Dict[str, str]:
    row = session.execute(
        text(
            "SELECT total_labor, total_equipment, total_procurement, total_other FROM daily_cost_summary WHERE incident_id=:m AND date=:d"
        ),
        {"m": incident_id, "d": day},
    ).mappings().first()
    if not row:
        row = {"total_labor": 0, "total_equipment": 0, "total_procurement": 0, "total_other": 0}

    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        raise RuntimeError(f"Unknown incident: {incident_id}")
    export_dir = paths.exports / "finance"
    export_dir.mkdir(parents=True, exist_ok=True)
    path = export_dir / f"daily_cost_{day}.csv"
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["total_labor", "total_equipment", "total_procurement", "total_other"])
        writer.writerow([row["total_labor"], row["total_equipment"], row["total_procurement"], row["total_other"]])
    return {"path": str(path), "created_at": datetime.utcnow().isoformat(timespec="seconds")}


def list_artifacts(incident_id: str) -> List[Dict[str, str]]:
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        raise RuntimeError(f"Unknown incident: {incident_id}")
    export_dir = paths.exports / "finance"
    if not export_dir.exists():
        return []
    artifacts = []
    for file in export_dir.iterdir():
        artifacts.append({"path": str(file), "created_at": datetime.fromtimestamp(file.stat().st_mtime).isoformat(timespec="seconds")})
    return artifacts
