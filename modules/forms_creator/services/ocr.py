"""Optional OCR helper stubs used by the Forms Creator."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable


ENABLE_OCR = False


@dataclass(slots=True)
class OCRSuggestion:
    """Represents a suggested field detected on a page image."""

    page: int
    rect: tuple[float, float, float, float]
    confidence: float
    label: str | None = None


class OCRService:
    """Lightweight placeholder for future OCR integration."""

    def __init__(self, *, enabled: bool | None = None) -> None:
        self.enabled = ENABLE_OCR if enabled is None else enabled

    def suggest(self, image_paths: Iterable[Path]) -> list[OCRSuggestion]:
        """Return OCR suggestions.

        The current implementation is intentionally a stub.  It preserves
        the public API expected by the UI but simply returns an empty list
        when OCR is disabled.  Future iterations can integrate with
        Tesseract or Windows OCR APIs by augmenting this class.
        """

        if not self.enabled:
            return []
        # Placeholder for future OCR logic.  A real implementation would
        # invoke Tesseract (or another OCR engine), parse the resulting
        # bounding boxes and yield :class:`OCRSuggestion` instances.
        return []


__all__ = ["ENABLE_OCR", "OCRService", "OCRSuggestion"]

