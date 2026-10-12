"""Minimal PDF exporter for communications log entries."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from textwrap import wrap
from typing import Dict, Iterable, List

from ..models import CommsLogEntry


def _escape_pdf_text(text: str) -> str:
    return text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _wrap_entry_lines(entry: CommsLogEntry) -> List[str]:
    base = f"{entry.ts_local} | {entry.priority[:3]} | {entry.resource_label} | {entry.from_unit} -> {entry.to_unit}"
    lines = [base]
    for field_label, field_value in (
        ("Message", entry.message),
        ("Action", entry.action_taken),
    ):
        if field_value:
            wrapped = wrap(field_value, 88) or [field_value]
            for idx, segment in enumerate(wrapped):
                prefix = f"  {field_label}: " if idx == 0 else " " * 11
                lines.append(prefix + segment)
    if entry.follow_up_required:
        lines.append("  Follow Up Required")
    if entry.is_status_update:
        lines.append("  Status Update Flagged")
    if entry.notification_level:
        lines.append(f"  Notification Level: {entry.notification_level}")
    if entry.attachments:
        lines.append("  Attachments: " + ", ".join(entry.attachments))
    return lines


def _compose_text(entries: Iterable[CommsLogEntry], metadata: Dict[str, object]) -> List[str]:
    lines: List[str] = []
    lines.append("Communications Traffic Log Export")
    incident_label = metadata.get("incident") or ""
    lines.append(f"Incident: {incident_label}")
    if metadata.get("operational_period"):
        lines.append(f"Operational Period: {metadata['operational_period']}")
    if metadata.get("time_zone"):
        lines.append(f"Time Zone: {metadata['time_zone']}")
    generated = metadata.get("generated_at") or datetime.utcnow().isoformat(timespec="seconds")
    lines.append(f"Generated: {generated}")
    lines.append("")
    for entry in entries:
        lines.extend(_wrap_entry_lines(entry))
        lines.append("")
    return lines


def _build_pdf_bytes(lines: List[str]) -> bytes:
    content_lines = ["BT", "/F1 10 Tf", "50 770 Td"]
    first_line = True
    for line in lines:
        safe = _escape_pdf_text(line)
        if first_line:
            content_lines.append(f"({safe}) Tj")
            first_line = False
        else:
            content_lines.append("T*")
            content_lines.append(f"({safe}) Tj")
    content_lines.append("ET")
    content_stream = "\n".join(content_lines).encode("latin-1", "ignore")

    objects: List[bytes] = []
    objects.append(b"1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj\n")
    objects.append(b"2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj\n")
    objects.append(
        b"3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
        b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj\n"
    )
    content_obj = (
        f"4 0 obj << /Length {len(content_stream)} >> stream\n".encode("ascii")
        + content_stream
        + b"\nendstream\nendobj\n"
    )
    objects.append(content_obj)
    objects.append(b"5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj\n")

    header = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]
    body = bytearray()
    offset = len(header)
    for obj in objects:
        offsets.append(offset)
        body.extend(obj)
        offset += len(obj)

    xref_entries = [b"0000000000 65535 f \n"]
    for off in offsets[1:]:
        xref_entries.append(f"{off:010d} 00000 n \n".encode("ascii"))
    xref = b"xref\n0 %d\n" % (len(offsets)) + b"".join(xref_entries)
    trailer = (
        b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF\n"
        % (len(offsets), len(header) + len(body))
    )
    return header + body + xref + trailer


def export_entries(entries: Iterable[CommsLogEntry], path: Path, metadata: Dict[str, object]) -> Path:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = _compose_text(entries, metadata)
    pdf_bytes = _build_pdf_bytes(lines)
    path.write_bytes(pdf_bytes)
    return path


__all__ = ["export_entries"]
