"""ICS 203 wrapper for incident-organization widgets."""
from pathlib import Path

from modules.forms_creator.exporting import ExportRequest, ExportResult, default_export_service
from utils.settingsmanager import SettingsManager


def generate_ics203(
    *, incident_id: str, operational_period_id: int, output_path: Path,
    form_set_id: str, prepared_by: str = "",
) -> ExportResult:
    settings = SettingsManager()
    return default_export_service().export(ExportRequest(
        form_key="ics_203", incident_id=incident_id, form_set_id=form_set_id,
        options={"operational_period_id": operational_period_id,
                 "output_path": output_path, "prepared_by": prepared_by or settings.get("user_name", ""),
                 "prepared_by_position": settings.get("user_position", "")},
    ))
