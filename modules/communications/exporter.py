"""ICS-205/205A export helpers."""

import csv
from pathlib import Path
from sqlmodel import Session, select

from .repository import get_incident_engine
from .models.comms_models import ChannelAssignment


def export_ics205(incident_id: str, output_dir: Path) -> Path:
    """Export channel assignments to a CSV file (stub for ICS-205)."""
    engine = get_incident_engine(incident_id)
    with Session(engine) as session:
        assignments = session.exec(select(ChannelAssignment)).all()
    output_dir.mkdir(parents=True, exist_ok=True)
    path = output_dir / f"{incident_id}_ICS205.csv"
    with path.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["Team", "Channel ID"])
        for a in assignments:
            writer.writerow([a.team, a.channel_id])
    return path


def export_ics205a(incident_id: str, output_dir: Path) -> Path:
    """Stub for ICS-205A export; currently mirrors :func:`export_ics205`."""
    return export_ics205(incident_id, output_dir)
