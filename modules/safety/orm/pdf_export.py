"""PDF generation utilities for the Safety Risk Manager hazard register."""

from __future__ import annotations

from io import BytesIO
from typing import Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import Hazard


def build_pdf(*, hazards: Sequence[Hazard], incident_name: str | None = None) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        title="Safety Risk Register",
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    header_style = styles["Heading2"]

    elements = []
    title = "Safety Risk Register"
    if incident_name:
        title = f"{incident_name}: {title}"
    elements.append(Paragraph(title, header_style))
    elements.append(Spacer(1, 12))

    table_header = ["#", "Title", "Category", "Initial SPE", "Residual SPE", "Control Measure"]
    table_data = [table_header]
    for idx, hazard in enumerate(hazards, start=1):
        initial = f"{hazard.spe_initial.score} ({hazard.spe_initial.band})" if hazard.spe_initial else "—"
        residual = f"{hazard.spe_residual.score} ({hazard.spe_residual.band})" if hazard.spe_residual else "—"
        table_data.append(
            [
                str(idx),
                hazard.title,
                hazard.category or "",
                initial,
                residual,
                hazard.control_measure or "",
            ]
        )

    table = Table(table_data, repeatRows=1)
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(table)

    doc.build(elements)
    return buffer.getvalue()
