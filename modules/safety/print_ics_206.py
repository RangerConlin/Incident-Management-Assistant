import os
from datetime import datetime
from pathlib import Path

from utils import incident_storage
from typing import Tuple


def generate(incident_id: str, html: str) -> Tuple[bytes, str]:
    """Generate a PDF from HTML for ICS-206. Stub implementation."""
    paths = incident_storage.resolve_incident_paths_by_identifier(incident_id)
    if paths is None:
        raise RuntimeError(f"Unknown incident: {incident_id}")
    forms_dir = paths.forms_exports
    forms_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    pdf_path = forms_dir / f"ICS206-{timestamp}.pdf"
    content = b"%PDF-1.4\n% Stub PDF for ICS-206\n"
    with open(pdf_path, "wb") as f:
        f.write(content)
    return content, str(pdf_path)
