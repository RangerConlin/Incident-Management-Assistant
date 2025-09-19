"""PDF to PNG rasterisation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


class RasterizerError(RuntimeError):
    """Raised when rasterisation fails or is unavailable."""


class RasterizeEngine(Protocol):
    """Protocol describing a rasterisation backend."""

    def __call__(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        ...


@dataclass(slots=True)
class Rasterizer:
    """Dependency injectable PDF rasteriser.

    The default configuration intentionally does not provide a concrete engine
    because QtPdf/Poppler bindings may not be available in all deployments.  UI
    callers should catch :class:`RasterizerError` and present a friendly message
    with steps to enable a rasterisation backend.
    """

    engine: RasterizeEngine | None = None

    def rasterize_pdf(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        """Convert ``pdf_path`` into PNG images under ``output_dir``."""

        if self.engine is None:
            raise RasterizerError(
                "No PDF rasterisation backend configured. Install QtPdf or poppler "
                "and pass an engine callable to Rasterizer(engine=...)."
            )
        output_dir.mkdir(parents=True, exist_ok=True)
        return self.engine(pdf_path, output_dir)
