"""Simple PDF printer for ICS 215A safety analysis."""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from modules.medical_safety.models.safety_models import ICS215AItem


def print_ics215a(items: list[ICS215AItem], out_path: str) -> None:
    """Render a minimal table of hazards."""
    c = canvas.Canvas(out_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 750, "ICS 215A Safety Analysis")
    y = 730
    for item in items:
        c.drawString(72, y, f"{item.hazard_description} -> {item.mitigation or ''}")
        y -= 18
    c.save()
