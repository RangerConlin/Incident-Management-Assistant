from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Tuple
import re
import urllib.request
import urllib.error
import urllib.parse

from pypdf import PdfReader, PdfWriter

from .form_catalog import FormCatalog, TemplateEntry
from .schema_scaffold import ensure_schema_for_form


INDEX_URLS = [
    "https://training.fema.gov/icsresource/icsforms.aspx",
    "https://www.fema.gov/incident-command-system",
]

FORM_IDS = [
    "ICS_201", "ICS_202", "ICS_203", "ICS_204", "ICS_205", "ICS_206", "ICS_208",
    "ICS_209", "ICS_211", "ICS_213", "ICS_213RR", "ICS_214", "ICS_215", "ICS_215A",
    "ICS_216", "ICS_217", "ICS_218",
]


PDF_DIR = Path("data/forms/pdfs")


def _http_get(url: str, *, timeout: int = 30, referer: Optional[str] = None) -> bytes:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
        ),
        "Accept": "text/html,application/pdf,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
    }
    if referer:
        headers["Referer"] = referer
    req = urllib.request.Request(url, headers=headers, method="GET")
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _fetch_text(url: str, timeout: int = 20) -> str:
    try:
        data = _http_get(url, timeout=timeout)
        try:
            return data.decode("utf-8", errors="ignore")
        except Exception:
            return data.decode(errors="ignore")
    except Exception:
        return ""


def _find_pdf_links(index_html: str) -> List[str]:
    # crude href parser for .pdf links
    links: List[str] = []
    for m in re.finditer(r"href=\"([^\"]+\.pdf)\"", index_html, re.I):
        href = m.group(1)
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            # cannot resolve without base; leave as absolute path if host present elsewhere
            pass
        links.append(href)
    return list(dict.fromkeys(links))  # dedupe preserve order


def _choose_link_for_form(form_id: str, links: List[str]) -> Optional[str]:
    # prefer links containing the numeric id, the word form, or exact match
    num = re.sub(r"[^0-9A-Za-z]", "", form_id)
    candidates = [
        l for l in links if re.search(rf"{num}\b", l, re.I) or re.search(form_id.replace('_', '[ _]'), l, re.I)
    ]
    if not candidates:
        # try any link mentioning 'ics' and the number
        n = re.sub(r"[^0-9]", "", form_id)
        candidates = [l for l in links if ("ics" in l.lower() and n in l)]
    # prefer 'fillable' or 'form' in path
    candidates.sort(key=lambda s: ("fillable" not in s.lower(), "form" not in s.lower(), len(s)))
    return candidates[0] if candidates else None


def _guess_version_from_text(text: str, fallback: str = "latest") -> str:
    # Look for patterns like: Rev. 10/2018, 2023.10, 2023-10
    for rx in (
        re.compile(r"Rev\.?\s*(\d{1,2})/(\d{4})", re.I),
        re.compile(r"(\d{4})[\.-](\d{2})"),
    ):
        m = rx.search(text)
        if m:
            if len(m.groups()) == 2 and len(m.group(1)) == 4:
                # 2023, 10
                return f"{m.group(1)}.{m.group(2)}"
            if len(m.groups()) == 2 and len(m.group(2)) == 4:
                # 10 / 2018 -> 2018.10
                return f"{m.group(2)}.{m.group(1).zfill(2)}"
    return fallback


def _trim_to_field_pages(src: Path, dst: Path) -> bool:
    """Write a copy with only pages that contain form widgets from first..last.

    Returns True if trimming occurred and output was written; otherwise False.
    """
    try:
        reader = PdfReader(str(src))
        first, last = None, None
        for i, page in enumerate(reader.pages):
            annots = page.get("/Annots")
            has_widget = False
            if annots:
                try:
                    for a in annots:  # type: ignore
                        obj = a.get_object() if hasattr(a, 'get_object') else a
                        subtype = str(obj.get("/Subtype")) if isinstance(obj, dict) else str(obj)
                        if "/Widget" in subtype:
                            has_widget = True
                            break
                except Exception:
                    pass
            if has_widget:
                if first is None:
                    first = i
                last = i
        if first is None or last is None:
            return False
        if first == 0 and last == len(reader.pages) - 1:
            return False  # nothing to trim
        writer = PdfWriter()
        for i in range(first, last + 1):
            writer.add_page(reader.pages[i])
        dst.parent.mkdir(parents=True, exist_ok=True)
        with dst.open("wb") as f:
            writer.write(f)
        return True
    except Exception:
        return False


def fetch_latest(forms: Optional[List[str]] = None, *, trim_instructions: bool = True) -> List[Tuple[str, str, str]]:
    """Fetch latest FEMA ICS PDFs for the given form IDs.

    Returns a list of (form_id, version, pdf_path_rel) entries registered in the catalog.
    """
    forms = forms or FORM_IDS
    HTML: str = ""
    for url in INDEX_URLS:
        HTML = _fetch_text(url)
        if HTML:
            break
    # If index failed to load, proceed with empty link set; caller will see no results
    # and can use manual URL or local upload workflows.
    if not HTML:
        HTML = ""

    links = _find_pdf_links(HTML) if HTML else []
    results: List[Tuple[str, str, str]] = []
    catalog = FormCatalog()
    PDF_DIR.mkdir(parents=True, exist_ok=True)

    for fid in forms:
        link = _choose_link_for_form(fid, links)
        if not link:
            continue
        try:
            # Use origin as referer to avoid 403 on some hosts
            parts = urllib.parse.urlparse(link)
            origin = f"{parts.scheme}://{parts.netloc}" if parts.scheme and parts.netloc else None
            data = _http_get(link, timeout=30, referer=origin)
        except Exception:
            continue

        # Guess version from link or inline text later
        version = _guess_version_from_text(link, fallback="latest")

        tmp = PDF_DIR / f"{fid}_download.pdf"
        tmp.write_bytes(data)

        # Better version guess: inspect first 2 pages of text
        try:
            reader = PdfReader(str(tmp))
            txt = ""
            for p in reader.pages[:2]:
                try:
                    txt += p.extract_text() or ""
                except Exception:
                    pass
            v2 = _guess_version_from_text(txt, fallback=version)
            if v2:
                version = v2
        except Exception:
            pass

        out_pdf = PDF_DIR / f"{fid}_v{version}.pdf"
        if trim_instructions and _trim_to_field_pages(tmp, out_pdf):
            pass
        else:
            out_pdf.write_bytes(tmp.read_bytes())
        tmp.unlink(missing_ok=True)

        # Ensure schema exists
        try:
            ensure_schema_for_form(fid)
        except Exception:
            pass

        # Register in catalog
        rel = str(out_pdf).replace("\\", "/")
        catalog.add_template(fid, TemplateEntry(version=version, pdf=rel, mapping=None))
        results.append((fid, version, rel))

    return results


__all__ = ["fetch_latest", "FORM_IDS"]
