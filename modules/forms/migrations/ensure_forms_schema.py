from __future__ import annotations

from pathlib import Path

from modules.forms.repositories import IncidentFormsRepository, MasterFormsRepository


def ensure_forms_schema(master_db_path: Path | str = Path("data") / "master.db", incident_id: str | None = None, incident_db_path: Path | str | None = None) -> None:
    MasterFormsRepository(master_db_path).ensure_schema()
    if incident_id:
        IncidentFormsRepository(incident_id, incident_db_path).ensure_schema()
