# NOTE: Module code lives under /modules/logistics (not /backend).

"""ICS 213-RR form export via the forms engine."""

from pathlib import Path

from utils import incident_storage

from .models import LogisticsResourceRequest
from .repository import with_incident_session


def generate_pdf(incident_id: str, request_id: int) -> tuple[str, bytes]:
    """Generate a PDF for the given ICS-213RR resource request."""
    with with_incident_session(incident_id) as session:
        req = session.get(LogisticsResourceRequest, request_id)

    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        raise RuntimeError(f"Unknown incident: {incident_id}")
    forms_dir = paths.forms_exports
    forms_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = forms_dir / f"ics213rr_{request_id}.pdf"

    values = {}
    if req is not None:
        values = {k: v for k, v in vars(req).items() if not k.startswith("_")}

    from modules.forms.api import export_form_unified

    export_form_unified(
        "ics_213rr",
        pdf_path,
        values=values,
        context={"incident_id": incident_id},
    )
    data = pdf_path.read_bytes()
    return str(pdf_path), data
