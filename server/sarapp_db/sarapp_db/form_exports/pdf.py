"""Portable PDF filling, pagination, and lossless text continuations."""
from __future__ import annotations
from io import BytesIO
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, TextStringObject
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.utils import simpleSplit
from reportlab.pdfbase.pdfmetrics import stringWidth
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer

from .context import human_time
from .models import ExportSnapshot


def _field_name(widget: Any) -> str:
    parts = []
    current = widget
    while current:
        if current.get("/T") is not None:
            parts.insert(0, str(current["/T"]))
        parent = current.get("/Parent")
        current = parent.get_object() if parent else None
    return ".".join(parts)


def _widgets(reader: PdfReader | PdfWriter) -> dict[str, list[Any]]:
    result: dict[str, list[Any]] = {}
    for page in reader.pages:
        for reference in page.get("/Annots", []):
            widget = reference.get_object()
            if widget.get("/Subtype") == "/Widget":
                result.setdefault(_field_name(widget), []).append(widget)
    return result


def _visible_text(text: str, widget: Any, minimum_size: float = 8.0) -> tuple[str, float, bool]:
    rect = widget.get("/Rect", [0, 0, 100, 20])
    width = max(8.0, float(rect[2]) - float(rect[0]) - 5)
    height = max(8.0, float(rect[3]) - float(rect[1]) - 4)
    rotation = int(widget.get("/MK", {}).get("/R", 0)) % 180
    if rotation == 90:
        width, height = height, width
    flags = widget.get("/Ff")
    parent = widget.get("/Parent")
    while flags is None and parent:
        obj = parent.get_object()
        flags = obj.get("/Ff")
        parent = obj.get("/Parent")
    multiline = bool(int(flags or 0) & 4096)
    for size in (size for size in (10.0, 9.0, 8.0, 7.0, 6.0) if size >= minimum_size):
        lines = [line for paragraph in text.split("\n") for line in simpleSplit(paragraph or " ", "Helvetica", size, width)]
        fits_width = all(stringWidth(line, "Helvetica", size) <= width for line in lines)
        if fits_width and ((multiline and len(lines) * size * 1.15 <= height) or (not multiline and len(lines) <= 1)):
            return ("\n".join(lines) if multiline else text), size, False
    # Explicit continuation marker; the complete content goes into the annex.
    marker = "[see annex]"
    prefix = text.replace("\n", " ")
    while prefix and stringWidth(prefix + " " + marker, "Helvetica", 8) > width:
        prefix = prefix[:-1]
    visible = (prefix.rstrip() + " " + marker).strip()
    if stringWidth(visible, "Helvetica", 8) > width:
        visible = "..."
    return visible, 8.0, True


def _supplement(snapshot: ExportSnapshot, overflow: list[tuple[str, str]], label: str) -> bytes:
    stream = BytesIO()
    styles = getSampleStyleSheet()
    styles["BodyText"].fontSize = 9
    styles["BodyText"].leading = 12
    doc = SimpleDocTemplate(stream, title=label, leftMargin=40, rightMargin=40, topMargin=40, bottomMargin=40)
    story: list[Any] = [Paragraph(escape(label + " - continuation"), styles["Heading1"]),
                        Paragraph(escape(str(snapshot.incident.get("name", ""))), styles["Heading2"])]
    def paragraph(text: Any) -> Any:
        return Paragraph(escape(str(text)).replace("\n", "<br/>"), styles["BodyText"])
    if snapshot.period:
        story.append(paragraph(f"Operational period {snapshot.period.get('number', '')}: {human_time(snapshot.period.get('start_time'))} to {human_time(snapshot.period.get('end_time'))}"))
    if overflow:
        story.append(Paragraph("Full text for continued fields", styles["Heading2"]))
        for name, text in overflow:
            story.extend([Paragraph(escape(name), styles["Heading3"]), paragraph(text), Spacer(1, 8)])
    # Retain meaningful source details that do not have official form fields.
    # In particular, no signature or finance data is inferred from approval actions.
    exclude = {"_id", "incident_id", "deleted", "audit", "metadata", "task_assignment", "version"}
    def add_record(record: dict[str, Any], heading: str, level: int = 0) -> None:
        story.append(Paragraph(escape(heading), styles["Heading2" if level == 0 else "Heading3"]))
        for key, value in record.items():
            if key in exclude or value is None or value == "" or value == [] or value == {}:
                continue
            if isinstance(value, list):
                for index, item in enumerate(value, 1):
                    if isinstance(item, dict):
                        add_record(item, f"{key.replace('_', ' ').title()} {index}", level + 1)
                    else:
                        story.append(paragraph(f"{key.replace('_', ' ').title()}: {item}"))
            elif not isinstance(value, dict):
                display = human_time(value) if (key.endswith(("_at", "_utc", "_time", "_ts")) or key in {"ts", "timestamp"}) else str(value)
                story.append(paragraph(f"{key.replace('_', ' ').title()}: {display}"))
    for index, record in enumerate(snapshot.records, 1):
        add_record(record, f"Saved source record {index}")
    if not snapshot.records:
        story.append(paragraph("No matching source records were recorded for this selection."))
    def footer(canvas: Any, document: Any) -> None:
        canvas.setFont("Helvetica", 8)
        canvas.drawString(40, 22, "Continuation - " + label)
        canvas.drawRightString(document.pagesize[0] - 40, 22, str(document.page))
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
    return stream.getvalue()


def render_pdf(
    snapshot: ExportSnapshot, *, template: Path, sheets: list[dict[str, Any]],
    label: str, minimum_font_size: float = 8.0,
) -> bytes:
    merged = PdfWriter()
    overflow: list[tuple[str, str]] = []
    expected: dict[str, str] = {}
    for index, values in enumerate(sheets, 1):
        reader = PdfReader(template)
        fields = reader.get_fields() or {}
        widgets = _widgets(reader)
        unknown = set(values) - set(fields)
        if unknown:
            raise ValueError("Template fields missing: " + ", ".join(sorted(unknown)))
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)
        filled: dict[str, Any] = {}
        for name, value in values.items():
            if value is None or value == "":
                continue
            if fields[name].get("/FT") == "/Btn":
                on_values = []
                for widget in widgets.get(name, []):
                    on_values.extend(str(key) for key in widget.get("/AP", {}).get("/N", {}) if str(key) != "/Off")
                on_values = sorted(set(on_values))
                if not on_values:
                    raise ValueError(f"Checkbox has no on-state: {name}")
                if isinstance(value, bool):
                    if value and len(on_values) != 1:
                        raise ValueError(f"A radio group requires an explicit export state: {name}")
                    visible = on_values[0] if value else "/Off"
                else:
                    visible = str(value)
                if visible not in ["/Off", *on_values]:
                    raise ValueError(f"Unknown checkbox/radio export state: {name}")
                filled[name] = visible
            else:
                text = str(value)
                candidates = widgets.get(name, [])
                if not candidates:
                    raise ValueError(f"Mapped field has no page widget: {name}")
                visible, size, continued = _visible_text(text, candidates[0], minimum_font_size)
                if continued:
                    overflow.append((name, text))
                filled[name] = (visible, "/Helvetica", size)
            expected[f"sheet_{index}.{name}"] = visible
        # Set canonical parent values before generating widget appearances.
        def stamp(references: Any, prefix: str = "") -> None:
            for reference in references:
                node = reference.get_object()
                local = str(node.get("/T", ""))
                name = ".".join(part for part in [prefix, local] if part)
                if name in filled:
                    value = filled[name]
                    if node.get("/FT") == "/Btn":
                        node[NameObject("/V")] = NameObject(str(value))
                    else:
                        node[NameObject("/V")] = TextStringObject(value[0] if isinstance(value, tuple) else str(value))
                stamp(node.get("/Kids", []), name)
        stamp(writer.root_object["/AcroForm"].get("/Fields", []))
        writer.update_page_form_field_values(None, filled, auto_regenerate=False)
        buffer = BytesIO()
        writer.write(buffer)
        part = PdfReader(BytesIO(buffer.getvalue()))
        part.add_form_topname(f"sheet_{index}")
        merged.append(part, import_outline=False)
    merged.append(PdfReader(BytesIO(_supplement(snapshot, overflow, label))), import_outline=False)
    output = BytesIO()
    merged.write(output)
    result = output.getvalue()
    # Check the written canonical field tree rather than trusting appearance alone.
    written = PdfReader(BytesIO(result))
    actual = written.get_fields() or {}
    for name, value in expected.items():
        if name not in actual or str(actual[name].get("/V", "")) != value:
            raise ValueError(f"PDF field value did not round-trip: {name}")
    return result
