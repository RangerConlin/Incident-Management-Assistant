"""PDF generation utilities for CAP ORM forms."""

from __future__ import annotations

from io import BytesIO
from typing import Sequence

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

from .models import ORMForm, ORMHazard


def _watermark(canvas_obj: canvas.Canvas, doc, *, highest: str) -> None:
    canvas_obj.saveState()
    canvas_obj.setFillColorRGB(0.8, 0.1, 0.1, alpha=0.25)
    canvas_obj.setFont("Helvetica-Bold", 48)
    canvas_obj.translate(300, 400)
    canvas_obj.rotate(45)
    canvas_obj.drawCentredString(0, 0, "NOT APPROVED — PENDING MITIGATION")
    canvas_obj.drawCentredString(0, -60, f"Highest Residual Risk: {highest}")
    canvas_obj.restoreState()


def build_pdf(
    *,
    form: ORMForm,
    hazards: Sequence[ORMHazard],
    incident_name: str | None = None,
) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        title=f"CAPF160_OP{form.op_period}",
        leftMargin=36,
        rightMargin=36,
        topMargin=54,
        bottomMargin=36,
    )
    styles = getSampleStyleSheet()
    header_style = styles["Heading2"]
    body_style = styles["BodyText"]

    elements = []

    title = f"CAP Operational Risk Management — OP {form.op_period}"
    if incident_name:
        title = f"{incident_name}: {title}"
    elements.append(Paragraph(title, header_style))
    elements.append(Spacer(1, 12))

    meta_lines = [
        f"Activity: {form.activity or '—'}",
        f"Prepared By ID: {form.prepared_by_id or '—'}",
        f"Date: {form.date_iso or '—'}",
        f"Status: {form.status.title()}",
        f"Highest Residual Risk: {form.highest_residual_risk}",
    ]
    for line in meta_lines:
        elements.append(Paragraph(line, body_style))
    elements.append(Spacer(1, 18))

    table_header = [
        "#",
        "Sub-Activity",
        "Hazard / Outcome",
        "Initial",
        "Control(s)",
        "Residual",
        "How",
        "Who",
    ]
    table_data = [table_header]
    for idx, hazard in enumerate(hazards, start=1):
        table_data.append(
            [
                str(idx),
                hazard.sub_activity,
                hazard.hazard_outcome,
                hazard.initial_risk,
                hazard.control_text,
                hazard.residual_risk,
                hazard.implement_how or "",
                hazard.implement_who or "",
            ]
        )

    table = Table(table_data, repeatRows=1)
    table_style = TableStyle(
        [
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.grey),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("ALIGN", (0, 0), (0, -1), "CENTER"),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ]
    )
    table.setStyle(table_style)
    elements.append(table)

    watermark = None
    if form.approval_blocked:
        watermark = lambda canv, doc: _watermark(  # noqa: E731
            canv, doc, highest=form.highest_residual_risk
        )

    doc.build(
        elements,
        onFirstPage=watermark,
        onLaterPages=watermark,
    )
    return buffer.getvalue()
