import os
from datetime import datetime
from pathlib import Path
from typing import Tuple


def generate(mission_id: str, html: str) -> Tuple[bytes, str]:
    """Generate a PDF from HTML for ICS-206. Stub implementation."""
    forms_dir = Path("data/missions") / mission_id / "forms"
    forms_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    pdf_path = forms_dir / f"ICS206-{timestamp}.pdf"
    content = b"%PDF-1.4\n% Stub PDF for ICS-206\n"
    with open(pdf_path, "wb") as f:
        f.write(content)
    return content, str(pdf_path)
