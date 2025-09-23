"""CSV exporter for communications log entries."""

from __future__ import annotations

import csv
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from ..models import CommsLogEntry


COLUMNS: Sequence[str] = (
    "Timestamp UTC",
    "Timestamp Local",
    "Direction",
    "Priority",
    "Channel",
    "Frequency",
    "Band",
    "Mode",
    "From",
    "To",
    "Message",
    "Action Taken",
    "Follow Up",
    "Disposition",
    "Operator",
    "Team",
    "Task",
    "Vehicle",
    "Personnel",
    "Attachments",
    "Geotag Lat",
    "Geotag Lon",
    "Notification",
    "Status Update",
)


def _entry_row(entry: CommsLogEntry) -> List[str]:
    attachments = "; ".join(entry.attachments)
    return [
        entry.ts_utc,
        entry.ts_local,
        entry.direction,
        entry.priority,
        entry.resource_label,
        entry.frequency,
        entry.band,
        entry.mode,
        entry.from_unit,
        entry.to_unit,
        entry.message,
        entry.action_taken,
        "Yes" if entry.follow_up_required else "No",
        entry.disposition,
        entry.operator_user_id or "",
        str(entry.team_id or ""),
        str(entry.task_id or ""),
        str(entry.vehicle_id or ""),
        str(entry.personnel_id or ""),
        attachments,
        "" if entry.geotag_lat is None else f"{entry.geotag_lat:.6f}",
        "" if entry.geotag_lon is None else f"{entry.geotag_lon:.6f}",
        entry.notification_level or "",
        "Yes" if entry.is_status_update else "No",
    ]


def export_entries(entries: Iterable[CommsLogEntry], path: Path, metadata: Dict[str, object]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["Communications Traffic Log Export"])
        writer.writerow([f"Incident: {metadata.get('incident', '')}"])
        if metadata.get("operational_period"):
            writer.writerow([f"Operational Period: {metadata['operational_period']}"])
        if metadata.get("time_zone"):
            writer.writerow([f"Time Zone: {metadata['time_zone']}"])
        if metadata.get("generated_at"):
            writer.writerow([f"Generated: {metadata['generated_at']}"])
        writer.writerow([])
        writer.writerow(list(COLUMNS))
        for entry in entries:
            writer.writerow(_entry_row(entry))
    return path


__all__ = ["export_entries", "COLUMNS"]
