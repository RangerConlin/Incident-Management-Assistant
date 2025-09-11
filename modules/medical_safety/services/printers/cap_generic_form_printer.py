"""Generic PDF printer for CAP forms using stored layout metadata."""

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from modules.medical_safety.models.cap_form_models import CapFormTemplate


def print_cap_form(template: CapFormTemplate, data: dict, out_path: str) -> None:
    c = canvas.Canvas(out_path, pagesize=letter)
    c.setFont("Helvetica", 12)
    c.drawString(72, 750, f"{template.code} - {template.title}")
    y = 730
    for key, value in data.items():
        c.drawString(72, y, f"{key}: {value}")
        y -= 18
    c.save()
