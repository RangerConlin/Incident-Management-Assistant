"""Bridge layer exposing safety services with incident context."""

from __future__ import annotations

from pathlib import Path

from utils.state import AppState
from modules.medical_safety.services.safety_service import SafetyService
from modules.medical_safety.services.cap_forms_service import CapFormsService
from modules.medical_safety.safety_permissions import can_edit_safety

safety_service = SafetyService()
capforms_service = CapFormsService()


def get_incident_db_path() -> str:
    """Return the active incident database path."""
    inc = AppState.get_active_incident()
    if not inc:
        raise RuntimeError("No active incident selected")
    return f"data/incidents/{inc}.db"


def ensure_tables() -> None:
    """Ensure all required tables exist for the active incident."""
    db_path = get_incident_db_path()
    Path(db_path).parent.mkdir(parents=True, exist_ok=True)
    safety_service.ensure_incident_tables(db_path)
    capforms_service.ensure_incident_tables(db_path)
