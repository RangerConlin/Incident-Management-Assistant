"""Minimal ICS 218 Support Vehicle/Equipment report."""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

from ..models.dto import Equipment, Vehicle, Aircraft
from ..utils.printing import render_html_to_pdf


def create_pdf(equipment: Iterable[Equipment], vehicles: Iterable[Vehicle], aircraft: Iterable[Aircraft], output_path: str | Path) -> None:
    rows = []
    for e in equipment:
        rows.append(f"<tr><td>Equipment</td><td>{e.name}</td><td>{e.type}</td><td>{e.status.value}</td></tr>")
    for v in vehicles:
        rows.append(f"<tr><td>Vehicle</td><td>{v.name}</td><td>{v.type}</td><td>{v.status.value}</td></tr>")
    for a in aircraft:
        rows.append(f"<tr><td>Aircraft</td><td>{a.tail}</td><td>{a.type}</td><td>{a.status.value}</td></tr>")
    html = "<html><body><h1>ICS 218 Support Vehicle/Equipment</h1><table border='1'>" + "".join(rows) + "</table></body></html>"
    render_html_to_pdf(html, str(output_path))
