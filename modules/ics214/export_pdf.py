"""PDF generation utilities for ICS-214 exports."""
from __future__ import annotations

from typing import List, Dict
from reportlab.pdfgen import canvas


def render_pdf(entries: List[Dict], file_path: str) -> None:
    c = canvas.Canvas(file_path)
    y = 800
    c.setFont("Helvetica", 12)
    for e in entries:
        c.drawString(20, y, f"{e['timestamp_utc']} - {e['text']}")
        y -= 20
        if y < 40:
            c.showPage()
            y = 800
    c.save()
