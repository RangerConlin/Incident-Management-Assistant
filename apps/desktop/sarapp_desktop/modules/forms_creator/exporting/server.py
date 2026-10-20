"""Desktop download boundary for forms rendered by the shared API server."""
from __future__ import annotations

from pathlib import Path
import os
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from utils.api_client import api_client


def download_ics203(
    incident_id: str, operational_period_id: int, output_path: Path,
    *, prepared_by: str = "",
    form_set_id: str = "fema",
    prepared_by_position: str = "",
) -> Path:
    if not incident_id or operational_period_id <= 0:
        raise ValueError("An incident and operational period are required")
    content = api_client.post_pdf(
        f"/api/incidents/{quote(incident_id, safe='')}/form-exports",
        json={"form_id": "ics_203", "operational_period_id": operational_period_id,
              "prepared_by": prepared_by, "form_set_id": form_set_id,
              "prepared_by_position": prepared_by_position},
    )
    temporary: Path | None = None
    try:
        with NamedTemporaryFile(dir=output_path.parent, suffix=".pdf.tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, output_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output_path
