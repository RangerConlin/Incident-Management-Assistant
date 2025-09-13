from __future__ import annotations

from io import BytesIO
from typing import Dict, Any

from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas


def render_overlay(field_values: Dict[str, Any]) -> bytes:
    """Simple overlay renderer used when no template is available.

    Draws each field on its own line. This is a minimal implementation
    intended primarily for tests and as a fallback.
    """
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    y = 750
    for key, value in field_values.items():
        c.drawString(72, y, f"{key}: {value}")
        y -= 20
        if y < 72:
            c.showPage()
            y = 750
    c.save()
    return buffer.getvalue()
