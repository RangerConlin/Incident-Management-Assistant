"""Printing helpers for Logistics module."""
from __future__ import annotations

from pathlib import Path

from PySide6 import QtGui, QtPrintSupport, QtWidgets


def print_widget(widget: QtWidgets.QWidget) -> None:
    """Show the standard print dialog and print the widget."""
    printer = QtPrintSupport.QPrinter()
    dialog = QtPrintSupport.QPrintDialog(printer, widget)
    if dialog.exec() == QtWidgets.QDialog.Accepted:
        painter = QtGui.QPainter(printer)
        widget.render(painter)
        painter.end()


def export_pdf(widget: QtWidgets.QWidget, path: Path) -> None:
    """Export the widget to a PDF file."""
    printer = QtPrintSupport.QPrinter()
    printer.setOutputFormat(QtPrintSupport.QPrinter.OutputFormat.PdfFormat)
    printer.setOutputFileName(str(path))
    painter = QtGui.QPainter(printer)
    widget.render(painter)
    painter.end()
