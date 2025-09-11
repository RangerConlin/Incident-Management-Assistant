"""Minimal ICS 211 Check-In List report generation."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..models.dto import Personnel
from ..utils.printing import render_html_to_pdf


TEMPLATE = """<html><body><h1>ICS 211 Check-In List</h1><table border='1' cellspacing='0' cellpadding='2'>
<tr><th>Callsign</th><th>Name</th><th>Role</th><th>Team</th><th>Phone</th><th>Status</th></tr>
{rows}
</table></body></html>"""


def create_pdf(personnel: Iterable[Personnel], output_path: str | Path) -> None:
    rows = []
    for p in personnel:
        rows.append(
            f"<tr><td>{p.callsign}</td><td>{p.first_name} {p.last_name}</td><td>{p.role}</td><td>{p.team_id or ''}</td><td>{p.phone}</td><td>{p.status.value}</td></tr>"
        )
    html = TEMPLATE.format(rows="\n".join(rows))
    render_html_to_pdf(html, str(output_path))
