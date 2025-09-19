"""PDF rendering utilities for the resource request module."""

from __future__ import annotations

import json
from pathlib import Path

from reportlab.graphics import renderPDF
from reportlab.graphics.barcode import qr
from reportlab.graphics.shapes import Drawing
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas

from .. import get_service

OUTPUT_DIR = Path("data") / "output"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


def _training_mode_enabled() -> bool:
    settings_path = Path("settings.json")
    if settings_path.exists():
        try:
            data = json.loads(settings_path.read_text(encoding="utf-8"))
            return bool(data.get("training_mode"))
        except Exception:  # pragma: no cover - defensive against malformed files
            return False
    return False


def _draw_training_watermark(pdf: canvas.Canvas) -> None:
    if not _training_mode_enabled():
        return
    pdf.saveState()
    pdf.setFont("Helvetica-Bold", 48)
    pdf.setFillColorRGB(0.85, 0.85, 0.85)
    pdf.translate(300, 400)
    pdf.rotate(45)
    pdf.drawCentredString(0, 0, "TRAINING MODE")
    pdf.restoreState()


def _draw_qr(pdf: canvas.Canvas, data: str, x: float, y: float, size: float = 80) -> None:
    widget = qr.QrCodeWidget(data)
    bounds = widget.getBounds()
    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    scale_x = size / width
    scale_y = size / height
    drawing = Drawing(size, size, transform=[scale_x, 0, 0, scale_y, 0, 0])
    drawing.add(widget)
    renderPDF.draw(drawing, pdf, x, y)


def render_ics_213rr(request_id: str) -> Path:
    """Render an ICS-213 Resource Request PDF and return the output path."""

    service = get_service()
    record = service.get_request(request_id)
    output_path = OUTPUT_DIR / f"ICS-213RR_{request_id}.pdf"

    pdf = canvas.Canvas(str(output_path), pagesize=letter)
    _draw_training_watermark(pdf)
    pdf.setFont("Helvetica-Bold", 16)
    pdf.drawString(40, 750, "ICS-213 RR - Resource Request")
    pdf.setFont("Helvetica", 10)

    y = 720
    for label, key in [
        ("Title", "title"),
        ("Priority", "priority"),
        ("Status", "status"),
        ("Needed By", "needed_by_utc"),
        ("Delivery", "delivery_location"),
        ("Comms", "comms_requirements"),
    ]:
        value = record.get(key) or "-"
        pdf.drawString(40, y, f"{label}: {value}")
        y -= 16

    pdf.drawString(40, y, "Justification:")
    y -= 14
    justification = record.get("justification") or "No justification provided"
    for line in _wrap_text(justification, 90):
        pdf.drawString(60, y, line)
        y -= 12

    pdf.drawString(40, y, "Items:")
    y -= 14
    for item in record.get("items", []):
        pdf.drawString(
            60,
            y,
            f"- {item['quantity']} {item['unit']} {item['description']} ({item['kind']})",
        )
        y -= 12

    pdf.drawString(40, y, "Approvals:")
    y -= 14
    for approval in record.get("approvals", []):
        pdf.drawString(
            60,
            y,
            f"{approval['ts_utc']} - {approval['action']} by {approval['actor_id']}",
        )
        y -= 12
        if approval.get("note"):
            pdf.drawString(80, y, approval["note"])
            y -= 12

    _draw_qr(pdf, data=json.dumps({"request_id": request_id}), x=460, y=40)
    pdf.showPage()
    pdf.save()
    return output_path


def render_summary_sheet(request_id: str) -> Path:
    """Render a condensed summary PDF for quick reference."""

    service = get_service()
    record = service.get_request(request_id)
    output_path = OUTPUT_DIR / f"RR-Summary_{request_id}.pdf"

    pdf = canvas.Canvas(str(output_path), pagesize=letter)
    _draw_training_watermark(pdf)
    pdf.setFont("Helvetica-Bold", 14)
    pdf.drawString(40, 750, "Resource Request Summary")
    pdf.setFont("Helvetica", 10)

    pdf.drawString(40, 730, f"Request: {record['title']}")
    pdf.drawString(40, 714, f"Priority: {record['priority']} | Status: {record['status']}")
    pdf.drawString(40, 698, f"Needed By: {record.get('needed_by_utc', '-')}")

    pdf.drawString(40, 672, "Fulfillment Status:")
    y = 656
    for entry in record.get("fulfillments", []):
        pdf.drawString(60, y, f"{entry['ts_utc']} - {entry['status']} ({entry.get('note', 'No note')})")
        y -= 12

    pdf.drawString(40, y - 10, "Audit Trail (latest 5):")
    y -= 24
    for audit in record.get("audit", [])[-5:]:
        pdf.drawString(
            60,
            y,
            f"{audit['ts_utc']} - {audit['entity_type']}:{audit['field']} => {audit['new_value']}",
        )
        y -= 12

    _draw_qr(pdf, data=json.dumps({"request_id": request_id, "summary": True}), x=460, y=40)
    pdf.showPage()
    pdf.save()
    return output_path


def _wrap_text(text: str, width: int) -> list[str]:
    words = text.split()
    lines: list[str] = []
    current: list[str] = []
    for word in words:
        candidate = " ".join(current + [word]) if current else word
        if len(candidate) > width:
            lines.append(" ".join(current))
            current = [word]
        else:
            current.append(word)
    if current:
        lines.append(" ".join(current))
    return lines or [""]
