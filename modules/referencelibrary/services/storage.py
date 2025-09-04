"""Filesystem helpers for storing library documents."""

from __future__ import annotations

import hashlib
import shutil
from pathlib import Path
from typing import Tuple

LIBRARY_ROOT = Path("data/library")


def _hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def store_file(src: Path) -> Tuple[Path, str]:
    """Copy *src* into the library, returning the destination path and hash.

    If a file with the same hash already exists, that path is returned and the
    source is not copied again.
    """
    LIBRARY_ROOT.mkdir(parents=True, exist_ok=True)
    file_hash = _hash_file(src)
    dest = LIBRARY_ROOT / src.name
    if dest.exists():
        existing_hash = _hash_file(dest)
        if existing_hash == file_hash:
            return dest, file_hash
        dest = LIBRARY_ROOT / f"{file_hash}{src.suffix}"
    if not dest.exists():
        shutil.copy2(src, dest)
    return dest, file_hash
