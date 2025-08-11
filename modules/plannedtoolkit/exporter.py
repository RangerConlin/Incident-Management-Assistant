from __future__ import annotations

import datetime as dt
from pathlib import Path
from zipfile import ZipFile

from reportlab.pdfgen import canvas

from . import planned_models as models
from .models import schemas
from .repository import with_event_session


def export_iap(event_id: str, request: schemas.IapBuildRequest) -> models.ExportArtifact:
    exports_dir = Path("data/missions") / event_id / "exports"
    exports_dir.mkdir(parents=True, exist_ok=True)
    ts = int(dt.datetime.utcnow().timestamp())
    pdf_path = exports_dir / f"iap_{ts}.pdf"
    c = canvas.Canvas(str(pdf_path))
    c.drawString(100, 750, "IAP Packet Placeholder")
    c.save()

    zip_path = exports_dir / f"iap_{ts}.zip"
    with ZipFile(zip_path, "w") as z:
        z.write(pdf_path, pdf_path.name)

    with with_event_session(event_id) as session:
        artifact = models.ExportArtifact(
            op_number=request.op_numbers[0] if request.op_numbers else None,
            type="iap",
            file_path=str(zip_path),
            created_at=dt.datetime.utcnow(),
        )
        session.add(artifact)
        session.flush()
        return artifact
