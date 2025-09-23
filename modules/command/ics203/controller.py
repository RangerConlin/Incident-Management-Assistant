from __future__ import annotations

"""Controller coordinating persistence for the ICS-203 panel."""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import List, Sequence

from .models import (
    Assignment,
    ICS203Repository,
    MasterPersonnelRepository,
    OrgUnit,
    Position,
    ensure_incident_schema,
    render_template,
    seed_units_and_positions,
)

SeedItem = tuple[str, OrgUnit | Position]


class ICS203Controller:
    """High level operations for the ICS-203 organization module."""

    def __init__(self, incident_id: str) -> None:
        self.incident_id = str(incident_id)
        ensure_incident_schema(self.incident_id)
        self.repo = ICS203Repository(self.incident_id)
        self.master_repo = MasterPersonnelRepository()

    # ------------------------------------------------------------------
    def load_units(self) -> List[OrgUnit]:
        return self.repo.list_units()

    def load_positions(self) -> List[Position]:
        return self.repo.list_all_positions()

    def list_assignments(self, position_id: int) -> List[Assignment]:
        return self.repo.list_assignments(position_id)

    # ------------------------------------------------------------------
    def add_unit(self, values: dict[str, object]) -> int:
        unit = OrgUnit(
            id=None,
            incident_id=self.incident_id,
            unit_type=str(values.get("unit_type", "Command")),
            name=str(values.get("name", "")).strip(),
            parent_unit_id=values.get("parent_unit_id") if values.get("parent_unit_id") else None,
            sort_order=int(values.get("sort_order", 0)),
        )
        return self.repo.upsert_unit(unit)

    def add_position(self, values: dict[str, object]) -> int:
        unit_id = values.get("unit_id")
        if unit_id in ("", None):
            unit_id = None
        else:
            unit_id = int(unit_id)
        position = Position(
            id=None,
            incident_id=self.incident_id,
            title=str(values.get("title", "")).strip(),
            unit_id=unit_id,
            sort_order=int(values.get("sort_order", 0)),
        )
        return self.repo.upsert_position(position)

    def add_assignment(self, position_id: int, values: dict[str, object | None]) -> int:
        person_id = values.get("person_id")
        parsed_person_id: int | None
        if isinstance(person_id, int):
            parsed_person_id = person_id
        else:
            try:
                parsed_person_id = int(str(person_id)) if person_id not in (None, "") else None
            except (TypeError, ValueError):
                parsed_person_id = None
        assignment = Assignment(
            id=None,
            incident_id=self.incident_id,
            position_id=position_id,
            person_id=parsed_person_id,
            display_name=str(values.get("display_name", "")) or None,
            callsign=values.get("callsign"),
            phone=values.get("phone"),
            agency=values.get("agency"),
            start_utc=None,
            end_utc=None,
            notes=None,
        )
        return self.repo.upsert_assignment(assignment)

    # ------------------------------------------------------------------
    def seed_defaults(self) -> None:
        self.repo.apply_batch(seed_units_and_positions(self.incident_id))

    def apply_template(self, template_name: str) -> None:
        items = render_template(template_name, self.incident_id)
        if items:
            self.repo.apply_batch(items)

    def apply_items(self, items: Sequence[SeedItem]) -> None:
        self.repo.apply_batch(items)

    # ------------------------------------------------------------------
    def export_snapshot(self) -> Path:
        export_dir = _incident_export_dir(self.incident_id)
        export_dir.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
        path = export_dir / f"ICS203_{timestamp}.tsv"
        units = {unit.id: unit for unit in self.load_units()}
        positions = self.load_positions()
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle, delimiter="\t")
            writer.writerow(
                [
                    "Unit Type",
                    "Unit Name",
                    "Position",
                    "Name",
                    "Callsign",
                    "Phone",
                    "Agency",
                    "Start",
                    "End",
                    "Notes",
                ]
            )
            for position in positions:
                unit = units.get(position.unit_id) if position.unit_id else None
                assignments = self.repo.list_assignments(position.id)
                if not assignments:
                    writer.writerow(
                        [
                            unit.unit_type if unit else "Command",
                            unit.name if unit else "",
                            position.title,
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                            "",
                        ]
                    )
                    continue
                for assignment in assignments:
                    writer.writerow(
                        [
                            unit.unit_type if unit else "Command",
                            unit.name if unit else "",
                            position.title,
                            assignment.display_name or "",
                            assignment.callsign or "",
                            assignment.phone or "",
                            assignment.agency or "",
                            assignment.start_utc or "",
                            assignment.end_utc or "",
                            assignment.notes or "",
                        ]
                    )
        return path


def _incident_export_dir(incident_id: str) -> Path:
    base = Path(os.environ.get("CHECKIN_DATA_DIR", "data"))
    return base / "incidents" / str(incident_id) / "exports"
