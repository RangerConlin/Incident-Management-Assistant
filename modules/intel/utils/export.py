"""Export helpers for intel reports and forms."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QPageLayout, QPageSize, QTextDocument, QPdfWriter


def export_html_to_pdf(html: str, pdf_path: Path) -> None:
    """Render ``html`` to ``pdf_path`` using Qt's PDF writer."""
    writer = QPdfWriter(str(pdf_path))
    writer.setPageSize(QPageSize(QPageSize.A4))
    writer.setPageMargins(QPageLayout.Margins(12, 12, 12, 12))
    doc = QTextDocument()
    doc.setHtml(html)
    doc.print_(writer)
