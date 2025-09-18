"""Utilities for converting PDFs and images to raster backgrounds."""
from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QGuiApplication, QImage, QPainter

try:  # QtPdf is optional on some installs.
    from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions
except ModuleNotFoundError:  # pragma: no cover - optional dependency
    QPdfDocument = None  # type: ignore[assignment]
    QPdfDocumentRenderOptions = None  # type: ignore[assignment]


class RasterizerError(RuntimeError):
    """Raised when rasterisation fails."""


@dataclass(slots=True)
class Rasterizer:
    """Convert templates to raster images.

    The class is intentionally dependency injectable.  During tests or in
    constrained environments a fake implementation can be provided.  By
    default the implementation relies on ``PySide6.QtPdf`` for PDF
    rendering and ``QImage`` for image handling.
    """

    dpi: int = 150

    def _ensure_app(self) -> None:
        """Ensure a ``QGuiApplication`` instance exists."""

        if QGuiApplication.instance() is None:
            QGuiApplication(sys.argv or ["forms_creator_rasterizer"])

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def rasterize_pdf(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        """Rasterize ``pdf_path`` into PNG images stored in ``output_dir``."""

        if QPdfDocument is None:
            raise RasterizerError(
                "QtPdf is not available. Install the optional PySide6-QtPdf "
                "package to enable PDF rasterisation."
            )

        pdf_path = pdf_path.expanduser().resolve()
        if not pdf_path.exists():
            raise RasterizerError(f"PDF file not found: {pdf_path}")

        self._ensure_app()
        document = QPdfDocument()
        status = document.load(str(pdf_path))
        if status != QPdfDocument.Status.Ready:
            raise RasterizerError(f"Failed to load PDF {pdf_path} (status={status})")

        page_count = document.pageCount()
        if page_count <= 0:
            raise RasterizerError(f"PDF {pdf_path} has no pages")

        output_dir.mkdir(parents=True, exist_ok=True)
        render_options = QPdfDocumentRenderOptions() if QPdfDocumentRenderOptions else None

        result: list[Path] = []
        scale = self.dpi / 72.0  # PDF point size is 72 DPI
        for page_number in range(page_count):
            size = document.pagePointSize(page_number)
            pixel_size = QSize(int(size.width() * scale), int(size.height() * scale))
            if pixel_size.width() <= 0 or pixel_size.height() <= 0:
                raise RasterizerError("Encountered invalid page dimensions during rasterisation")

            image = QImage(pixel_size, QImage.Format.Format_ARGB32)
            image.fill(Qt.white)

            painter = QPainter(image)
            if render_options is not None:
                document.render(page_number, painter, render_options)
            else:  # pragma: no cover - compatibility path
                document.render(page_number, painter)
            painter.end()

            filename = output_dir / f"background_page_{page_number + 1:03d}.png"
            if not image.save(str(filename)):
                raise RasterizerError(f"Failed to write rasterized page to {filename}")
            result.append(filename)

        return result

    def rasterize_images(self, image_paths: Iterable[Path], output_dir: Path) -> list[Path]:
        """Copy or convert image files into the output directory."""

        self._ensure_app()
        output_dir.mkdir(parents=True, exist_ok=True)
        result: list[Path] = []
        for index, path in enumerate(image_paths, start=1):
            path = path.expanduser().resolve()
            if not path.exists():
                raise RasterizerError(f"Image file not found: {path}")
            image = QImage(str(path))
            if image.isNull():
                raise RasterizerError(f"Failed to load image: {path}")
            filename = output_dir / f"background_page_{index:03d}.png"
            if not image.save(str(filename)):
                raise RasterizerError(f"Failed to save rasterized image: {filename}")
            result.append(filename)
        return result

