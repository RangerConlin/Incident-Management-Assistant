from datetime import datetime
from pathlib import Path

from utils import incident_storage


def generate(incident_id: str, html: str = "") -> tuple[bytes, str]:
    """Generate a PDF for ICS-206 via the forms engine."""
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        raise RuntimeError(f"Unknown incident: {incident_id}")
    forms_dir = paths.forms_exports
    forms_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    pdf_path = forms_dir / f"ICS206-{timestamp}.pdf"

    from modules.forms.api import export_form_unified

    export_form_unified("ics_206", pdf_path, context={"incident_id": incident_id})
    content = pdf_path.read_bytes()
    return content, str(pdf_path)
