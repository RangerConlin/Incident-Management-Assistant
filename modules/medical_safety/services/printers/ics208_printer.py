"""Simple PDF printer for ICS 208 forms."""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from modules.medical_safety.models.safety_models import ICS208


def print_ics208(record: ICS208, out_path: str) -> None:
    """Render a very small PDF containing the safety message."""
    c = canvas.Canvas(out_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 750, f"ICS 208 Safety Message: {record.title}")
    text = c.beginText(72, 730)
    for line in record.message.splitlines():
        text.textLine(line)
    c.drawText(text)
    c.save()
