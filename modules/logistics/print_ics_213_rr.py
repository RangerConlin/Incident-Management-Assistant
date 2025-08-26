# AUTO-GENERATED: Logistics module for Incident Management Assistant
# NOTE: Module code lives under /modules/logistics (not /backend).

"""Stub for printing ICS 213-RR forms."""

from pathlib import Path

from .models import LogisticsResourceRequest
from .repository import with_incident_session


def generate_pdf(incident_id: str, request_id: int) -> tuple[str, bytes]:
    """Generate a placeholder PDF for the given request."""
    with with_incident_session(incident_id) as session:
        session.get(LogisticsResourceRequest, request_id)
    forms_dir = Path("data") / "incidents" / incident_id / "forms"
    forms_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = forms_dir / f"ics213rr_{request_id}.pdf"
    data = b"PDF PLACEHOLDER"
    pdf_path.write_bytes(data)
    return str(pdf_path), data
