"""Metadata extraction for library documents."""

from __future__ import annotations

from pathlib import Path
from . import thumbnails
from ..models.reference_models import Metadata


def extract_metadata(path: Path) -> Metadata:
    """Return basic metadata for *path*. Currently extracts size and extension."""
    size = path.stat().st_size
    ext = path.suffix.lower()
    # Generate thumbnail asynchronously? For now do synchronously
    try:
        thumbnails.generate_thumbnail(path)
    except Exception:
        pass
    return Metadata(size=size, extension=ext)
