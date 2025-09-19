"""PDF to PNG rasterisation helpers."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


DEFAULT_DPI = 200


class RasterizerError(RuntimeError):
    """Raised when rasterisation fails or is unavailable."""


class RasterizeEngine(Protocol):
    """Protocol describing a rasterisation backend."""

    def __call__(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        ...


@dataclass(slots=True)
class Rasterizer:
    """Dependency injectable PDF rasteriser.

    The rasteriser will attempt to auto-discover a working backend the first
    time it is used. Deployments that ship QtPdf or pypdfium2 will therefore
    function without additional wiring. When neither backend is available, a
    descriptive :class:`RasterizerError` is raised so the UI can guide the user
    through enabling PDF support.
    """

    engine: RasterizeEngine | None = None
    dpi: int = DEFAULT_DPI

    def rasterize_pdf(self, pdf_path: Path, output_dir: Path) -> list[Path]:
        """Convert ``pdf_path`` into PNG images under ``output_dir``."""

        engine = self.engine
        debug_messages: list[str] = []
        if engine is None:
            engine, debug_messages = _autodetect_engine(self.dpi)
            if engine is not None:
                # Cache the discovered engine for future calls.
                self.engine = engine

        if engine is None:
            hints = "\n".join(f" - {msg}" for msg in debug_messages)
            hint_block = f"\n{hints}\n" if hints else "\n"
            raise RasterizerError(
                "No PDF rasterisation backend is available." +
                hint_block +
                "Install the QtPdf components for PySide6 or `pypdfium2` and "
                "restart the Form Creator, or inject a custom engine via "
                "Rasterizer(engine=...).",
            )

        output_dir.mkdir(parents=True, exist_ok=True)
        return engine(pdf_path, output_dir)


def _autodetect_engine(dpi: int) -> tuple[RasterizeEngine | None, list[str]]:
    """Try to locate a usable PDF rasterisation backend."""

    debug_messages: list[str] = []
    for builder in (_build_qtpdf_engine, _build_pypdfium2_engine):
        engine, debug = builder(dpi)
        if engine is not None:
            return engine, debug_messages
        if debug:
            debug_messages.append(debug)
    return None, debug_messages


def _build_qtpdf_engine(dpi: int) -> tuple[RasterizeEngine | None, str | None]:
    """Return a QtPdf-backed rasterisation engine if available."""

    try:  # pragma: no cover - optional dependency import
        from PySide6.QtCore import QSize
        from PySide6.QtGui import QImage
        from PySide6.QtPdf import QPdfDocument, QPdfDocumentRenderOptions
    except Exception as exc:  # pragma: no cover - QtPdf missing
        return None, f"QtPdf unavailable: {exc}"

    def engine(pdf_path: Path, output_dir: Path) -> list[Path]:
        document = QPdfDocument()
        error = document.load(str(pdf_path))
        if error != QPdfDocument.Error.None_:
            document.close()
            raise RasterizerError(
                f"QtPdf failed to load {pdf_path.name}: {error.name}",
            )

        page_count = document.pageCount()
        if page_count <= 0:
            document.close()
            raise RasterizerError(f"PDF has no pages: {pdf_path}")

        scale = dpi / 72.0  # points per inch
        render_opts = QPdfDocumentRenderOptions()
        render_opts.setRenderFlags(
            QPdfDocumentRenderOptions.RenderFlag.OptimizedForLcd
        )

        output_paths: list[Path] = []
        try:
            for index in range(page_count):
                size_pt = document.pagePointSize(index)
                if size_pt.isEmpty():
                    continue
                width = max(1, int(round(size_pt.width() * scale)))
                height = max(1, int(round(size_pt.height() * scale)))
                image_size = QSize(width, height)
                image: QImage = document.render(index, image_size, render_opts)
                if image.isNull():
                    raise RasterizerError(
                        f"QtPdf could not render page {index + 1} of {pdf_path.name}",
                    )

                image = image.convertToFormat(QImage.Format_RGBA8888)
                output_path = output_dir / f"background_page_{index + 1:03d}.png"
                if not image.save(str(output_path), "PNG"):
                    raise RasterizerError(
                        f"Failed to save rasterised page {index + 1} for {pdf_path.name}",
                    )
                output_paths.append(output_path)
        finally:
            document.close()

        if not output_paths:
            raise RasterizerError(f"QtPdf did not render any pages for {pdf_path.name}")

        return output_paths

    return engine, None


def _build_pypdfium2_engine(dpi: int) -> tuple[RasterizeEngine | None, str | None]:
    """Return a pypdfium2-backed rasterisation engine if available."""

    try:  # pragma: no cover - optional dependency import
        import pypdfium2 as pdfium
    except Exception as exc:  # pragma: no cover - dependency missing
        return None, f"pypdfium2 unavailable: {exc}"

    def engine(pdf_path: Path, output_dir: Path) -> list[Path]:
        document = pdfium.PdfDocument(str(pdf_path))
        page_indices = list(range(len(document)))
        if not page_indices:
            document.close()
            raise RasterizerError(f"PDF has no pages: {pdf_path}")

        scale = dpi / 72.0
        bitmap_iter = document.render_to(
            pdfium.BitmapConv.pil_image,
            page_indices=page_indices,
            scale=scale,
        )

        output_paths: list[Path] = []
        try:
            for page_index, pil_image in zip(page_indices, bitmap_iter):
                output_path = output_dir / f"background_page_{page_index + 1:03d}.png"
                pil_image.save(output_path, format="PNG")
                output_paths.append(output_path)
        finally:
            document.close()

        if not output_paths:
            raise RasterizerError(f"pypdfium2 did not render any pages for {pdf_path.name}")

        return output_paths

    return engine, None
