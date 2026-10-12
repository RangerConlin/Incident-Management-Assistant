"""Thumbnail generation for library documents."""

from __future__ import annotations

from pathlib import Path

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency
    Image = None

THUMB_ROOT = Path("data/library/.cache/thumbs")


def generate_thumbnail(path: Path, size: tuple[int, int] = (256, 256)) -> Path | None:
    """Generate a thumbnail for *path* if possible."""
    THUMB_ROOT.mkdir(parents=True, exist_ok=True)
    if Image is None:
        return None
    if path.suffix.lower() not in {".png", ".jpg", ".jpeg"}:
        return None
    thumb_path = THUMB_ROOT / f"{path.stem}.png"
    if thumb_path.exists():
        return thumb_path
    try:
        with Image.open(path) as img:
            img.thumbnail(size)
            img.save(thumb_path, format="PNG")
        return thumb_path
    except Exception:
        return None
