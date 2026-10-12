"""Optional OCR helpers for the form creator module."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class OCRConfig:
    """Configuration flagging whether OCR support is enabled."""

    enabled: bool = False
    tessdata_path: Path | None = None


class OCRService:
    """Very small facade around an optional OCR backend."""

    def __init__(self, config: OCRConfig | None = None):
        self.config = config or OCRConfig()

    def suggest_fields(self, image_path: Path) -> list[dict[str, Any]]:
        """Return suggested field bounding boxes for ``image_path``.

        The default implementation simply returns an empty list.  It exists to
        provide a well defined hook should the desktop build bundle Tesseract in
        the future.  Keeping the API synchronous avoids threading issues in the
        UI layer.
        """

        if not self.config.enabled:
            return []
        raise RuntimeError(
            "OCR support is disabled in this build. Provide a custom OCRService "
            "with enabled=True and an engine implementation."
        )
