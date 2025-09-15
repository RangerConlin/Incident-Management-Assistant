from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
import re

from pypdf import PdfReader


ICS_PATTERNS = [
    (re.compile(r"\bICS\s*201\b", re.I), "ICS_201"),
    (re.compile(r"\bICS\s*202\b", re.I), "ICS_202"),
    (re.compile(r"\bICS\s*203\b", re.I), "ICS_203"),
    (re.compile(r"\bICS\s*204\b", re.I), "ICS_204"),
    (re.compile(r"\bICS\s*205\b", re.I), "ICS_205"),
    (re.compile(r"\bICS\s*206\b", re.I), "ICS_206"),
    (re.compile(r"\bICS\s*208\b", re.I), "ICS_208"),
    (re.compile(r"\bICS\s*209\b", re.I), "ICS_209"),
    (re.compile(r"\bICS\s*211\b", re.I), "ICS_211"),
    (re.compile(r"\bICS\s*213\s*RR\b", re.I), "ICS_213RR"),
    (re.compile(r"\bICS\s*213\b", re.I), "ICS_213"),
    (re.compile(r"\bICS\s*214\b", re.I), "ICS_214"),
    (re.compile(r"\bICS\s*215A\b", re.I), "ICS_215A"),
    (re.compile(r"\bICS\s*215\b", re.I), "ICS_215"),
    (re.compile(r"\bICS\s*216\b", re.I), "ICS_216"),
    (re.compile(r"\bICS\s*217\b", re.I), "ICS_217"),
    (re.compile(r"\bICS\s*218\b", re.I), "ICS_218"),
    (re.compile(r"\bCAP\s*F\s*109\b", re.I), "CAPF_109"),
    (re.compile(r"\bSAR\s*104\b", re.I), "SAR_104"),
]


def _read_text(pdf_path: Path, pages: int = 2) -> str:
    try:
        reader = PdfReader(str(pdf_path))
        buf = []
        for i, page in enumerate(reader.pages[:pages]):
            try:
                buf.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(buf)
    except Exception:
        return ""


def guess_form_id_and_version(pdf_path: Path) -> Tuple[Optional[str], Optional[str]]:
    """Heuristically guess form ID and version from text and filename.

    Version guesses look for patterns like vYYYY.MM, YYYY-MM, or YY.MM in filename or text.
    """
    text = _read_text(pdf_path)
    name = pdf_path.name

    # ID by text
    for rx, fid in ICS_PATTERNS:
        if rx.search(text) or rx.search(name):
            form_id = fid
            break
    else:
        form_id = None

    # Version
    ver = None
    for rx in (
        re.compile(r"v(\d{4}[\.-]?\d{2})", re.I),
        re.compile(r"(\d{4}[\.-]\d{2})"),
        re.compile(r"(\d{2}[\.-]\d{2})"),
    ):
        m = rx.search(name) or rx.search(text)
        if m:
            ver = m.group(1).replace(".", ".").replace("-", ".")
            break

    return form_id, ver


__all__ = ["guess_form_id_and_version"]

