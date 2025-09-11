"""ICS 211 Check-In List report generation."""
from __future__ import annotations

from PySide6 import QtGui, QtPrintSupport

from ..models.services import LogisticsService


def _build_html(service: LogisticsService) -> str:
    rows = "".join(
        f"<tr><td>{p.callsign}</td><td>{p.first_name} {p.last_name}</td><td>{p.role}</td><td>{p.team_id or ''}</td><td>{p.checkin_status}</td><td>{p.status}</td></tr>"
        for p in service.list_personnel()
    )
    return f"""
    <h2>ICS 211 - Incident Check-In List</h2>
    <table border='1' cellspacing='0' cellpadding='2'>
        <tr><th>Callsign</th><th>Name</th><th>Role</th><th>Team</th><th>Check-In</th><th>Status</th></tr>
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
