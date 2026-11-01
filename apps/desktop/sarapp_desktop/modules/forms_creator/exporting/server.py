"""Desktop download boundary for forms rendered by the shared API server."""
from __future__ import annotations

from pathlib import Path
import os
from tempfile import NamedTemporaryFile
from urllib.parse import quote

from utils.api_client import api_client


def download_form(
    incident_id: str,
    form_id: str,
    output_path: Path,
    *,
    source_id: str | int | None = None,
    operational_period_id: int | None = None,
    prepared_by: str = "",
    form_set_id: str | None = None,
    prepared_by_position: str = "",
) -> Path:
    if not incident_id or not form_id:
        raise ValueError("An incident and form are required")
    body = {
        "form_id": form_id,
        "source_id": None if source_id in (None, "") else str(source_id),
        "operational_period_id": operational_period_id,
        "prepared_by": prepared_by,
        "form_set_id": form_set_id,
        "prepared_by_position": prepared_by_position,
    }
    content = api_client.post_pdf(
        f"/api/incidents/{quote(incident_id, safe='')}/form-exports",
        json=body,
    )
    temporary: Path | None = None
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(dir=output_path.parent, suffix=".pdf.tmp", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(content)
        os.replace(temporary, output_path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output_path
