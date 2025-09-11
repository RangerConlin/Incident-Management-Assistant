"""Printing helpers for logistics reports."""

from __future__ import annotations

try:  # pragma: no cover - not executed in tests
    from PySide6.QtGui import QTextDocument
    from PySide6.QtPrintSupport import QPrinter
except Exception:  # pragma: no cover
    QTextDocument = QPrinter = object  # type: ignore


def render_html_to_pdf(html: str, output_path: str) -> None:
    """Render simple HTML to a PDF file using Qt's print support."""

    doc = QTextDocument()
    doc.setHtml(html)  # type: ignore[attr-defined]
    printer = QPrinter()  # type: ignore[call-arg]
    printer.setOutputFormat(QPrinter.PdfFormat)  # type: ignore[attr-defined]
    printer.setOutputFileName(output_path)  # type: ignore[attr-defined]
    doc.print(printer)  # type: ignore[attr-defined]
