"""ICS 218 - Support Vehicle/Equipment report generation."""
from __future__ import annotations

from PySide6 import QtGui, QtPrintSupport

from ..models.services import LogisticsService


def _build_html(service: LogisticsService) -> str:
    vehicles = service.vehicle_repo.list()
    equipment = service.equipment_repo.list()
    aircraft = service.aircraft_repo.list()
    rows = "".join(
        f"<tr><td>{v.name}</td><td>{v.type}</td><td>{v.callsign}</td><td>{v.assigned_team_id or ''}</td><td>{v.status}</td></tr>"
        for v in vehicles
    )
    rows += "".join(
        f"<tr><td>{e.name}</td><td>{e.type}</td><td>{e.serial}</td><td>{e.assigned_team_id or ''}</td><td>{e.status}</td></tr>"
        for e in equipment
    )
    rows += "".join(
        f"<tr><td>{a.tail}</td><td>{a.type}</td><td>{a.callsign}</td><td>{a.assigned_team_id or ''}</td><td>{a.status}</td></tr>"
        for a in aircraft
    )
    return f"""
    <h2>ICS 218 - Support Vehicle/Equipment</h2>
    <table border='1' cellspacing='0' cellpadding='2'>
        <tr><th>Name/Tail</th><th>Type</th><th>Callsign/Serial</th><th>Team</th><th>Status</th></tr>
        {rows}
    </table>
    """


def print_report(service: LogisticsService) -> None:
    doc = QtGui.QTextDocument()
    doc.setHtml(_build_html(service))
    printer = QtPrintSupport.QPrinter()
    dialog = QtPrintSupport.QPrintDialog(printer)
    if dialog.exec() == QtPrintSupport.QPrintDialog.Accepted:
        doc.print(printer)
