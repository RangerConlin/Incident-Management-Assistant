"""Utilities for extracting fillable form fields from PDF documents.

The form creator can pre-populate a newly imported template with the fields
defined in an AcroForm enabled PDF.  This module is intentionally Qt-free so
that it can be exercised from tests or command line tooling without requiring
Qt to be initialised.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
try:  # pragma: no cover - optional dependency guard
    from pypdf import PdfReader
    from pypdf.generic import (
        ArrayObject,
        BooleanObject,
        DictionaryObject,
        FloatObject,
        IndirectObject,
        NameObject,
        NumberObject,
        TextStringObject,
    )
except Exception as exc:  # pragma: no cover - import-time feedback
    PdfReader = None  # type: ignore[assignment]

    class _DummyIndirect:  # pragma: no cover - simple stand-in
        def get_object(self):
            raise RuntimeError("pypdf is required for PDF field extraction")

    ArrayObject = list  # type: ignore[assignment]
    BooleanObject = int  # type: ignore[assignment]
    DictionaryObject = dict  # type: ignore[assignment]
    FloatObject = float  # type: ignore[assignment]
    IndirectObject = _DummyIndirect  # type: ignore[assignment]
    NameObject = str  # type: ignore[assignment]
    NumberObject = float  # type: ignore[assignment]
    TextStringObject = str  # type: ignore[assignment]

    _PDF_IMPORT_ERROR = exc
else:  # pragma: no cover - keeping the symbol for linting tools
    _PDF_IMPORT_ERROR = None

from pypdf.constants import FieldFlag


# Field specific flags as defined by the PDF 1.7 specification.
TEXT_FLAG_MULTILINE = 1 << 12
BUTTON_FLAG_RADIO = 1 << 15
BUTTON_FLAG_PUSHBUTTON = 1 << 16

CHOICE_FLAG_EDIT = 1 << 18
CHOICE_FLAG_MULTI_SELECT = 1 << 20


class PDFFieldExtractionError(RuntimeError):
    """Raised when fillable fields cannot be extracted from a PDF."""


@dataclass(slots=True)
class DetectedPDFField:
    """Represents a single field encountered within a PDF document."""

    name: str
    page_index: int  # zero-based page index
    rect: tuple[float, float, float, float]
    page_width: float
    page_height: float
    template_type: str
    required: bool
    default_value: str | None
    options: list[str] | None = None
    choice_editable: bool = False
    choice_multi_select: bool = False
    export_value: str | None = None
    flags: int = 0


class PDFFormFieldExtractor:
    """High level helper that extracts AcroForm fields from a PDF."""

    def extract(self, pdf_path: Path) -> list[DetectedPDFField]:
        """Return detected fields for ``pdf_path``.

        Parameters
        ----------
        pdf_path:
            Path to the PDF document to inspect.
        """

        if PdfReader is None:  # pragma: no cover - optional dependency guard
            raise PDFFieldExtractionError(
                "pypdf is not available. Install the 'pypdf' package to enable "
                "fillable PDF import.",
            ) from _PDF_IMPORT_ERROR

        try:
            reader = PdfReader(str(pdf_path))
        except Exception as exc:  # pragma: no cover - passthrough for UI display
            raise PDFFieldExtractionError(f"Unable to read PDF: {exc}") from exc

        detected: list[DetectedPDFField] = []
        for page_index, page in enumerate(reader.pages):
            try:
                page_width = float(page.mediabox.width)
                page_height = float(page.mediabox.height)
            except Exception:  # pragma: no cover - defensive fallback
                page_width = float(page.mediabox.right - page.mediabox.left)
                page_height = float(page.mediabox.top - page.mediabox.bottom)

            annotations = page.get("/Annots")
            if not annotations:
                continue

            for annot_ref in annotations:  # type: ignore[assignment]
                annot = _get_dictionary(annot_ref)
                if annot is None:
                    continue
                if _normalise_name(annot.get("/Subtype")) != "Widget":
                    continue

                rect = _extract_rect(annot.get("/Rect"))
                if rect is None:
                    continue

                field_dict = annot
                field_type = _normalise_name(_resolve_inherited(field_dict, "/FT"))
                if not field_type:
                    continue

                flags = int(_resolve_inherited(field_dict, "/Ff") or 0)
                template_type = _map_template_type(field_type, flags)
                if template_type is None:
                    continue

                name_value = _resolve_inherited(field_dict, "/T")
                field_name = _normalise_text(name_value) or ""

                required = bool(flags & FieldFlag.REQUIRED)
                default_raw = _resolve_inherited(field_dict, "/V")
                default_value = _normalise_text(default_raw)

                options: list[str] | None = None
                editable = False
                multi_select = False
                export_value: str | None = None

                if template_type == "dropdown":
                    options_raw = _resolve_inherited(field_dict, "/Opt")
                    options = _normalise_options(options_raw)
                    editable = bool(flags & CHOICE_FLAG_EDIT)
                    multi_select = bool(flags & CHOICE_FLAG_MULTI_SELECT)
                elif template_type in {"checkbox", "radio"}:
                    export_value = _normalise_text(annot.get("/AS"))
                    if not default_value and export_value and export_value != "Off":
                        default_value = export_value

                detected.append(
                    DetectedPDFField(
                        name=field_name,
                        page_index=page_index,
                        rect=rect,
                        page_width=page_width,
                        page_height=page_height,
                        template_type=template_type,
                        required=required,
                        default_value=default_value,
                        options=options,
                        choice_editable=editable,
                        choice_multi_select=multi_select,
                        export_value=export_value,
                        flags=flags,
                    )
                )
        return detected


# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------


def _get_dictionary(value: object) -> DictionaryObject | None:
    """Return a resolved :class:`DictionaryObject` if possible."""

    if value is None:
        return None
    if isinstance(value, DictionaryObject):
        return value
    if isinstance(value, IndirectObject):
        try:
            resolved = value.get_object()
        except Exception:  # pragma: no cover - PDF quirks
            return None
        if isinstance(resolved, DictionaryObject):
            return resolved
    return None


def _resolve_inherited(field_dict: DictionaryObject, key: str):
    """Resolve a field attribute, walking up the parent chain if needed."""

    current: DictionaryObject | None = field_dict
    visited: set[int] = set()
    while current is not None:
        if key in current:
            return current[key]
        parent = current.get("/Parent")
        if parent is None:
            break
        if isinstance(parent, IndirectObject):
            obj_id = (parent.idnum << 16) | parent.generation
            if obj_id in visited:
                break
            visited.add(obj_id)
            current = _get_dictionary(parent)
        elif isinstance(parent, DictionaryObject):
            obj_id = id(parent)
            if obj_id in visited:
                break
            visited.add(obj_id)
            current = parent
        else:
            break
    return None


def _extract_rect(value: object) -> tuple[float, float, float, float] | None:
    """Convert the PDF ``/Rect`` entry into numeric coordinates."""

    if not isinstance(value, (ArrayObject, list, tuple)) or len(value) < 4:
        return None
    try:
        llx, lly, urx, ury = (
            float(value[0]),
            float(value[1]),
            float(value[2]),
            float(value[3]),
        )
    except Exception:
        return None
    min_x = min(llx, urx)
    max_x = max(llx, urx)
    min_y = min(lly, ury)
    max_y = max(lly, ury)
    if max_x - min_x <= 0 or max_y - min_y <= 0:
        return None
    return (min_x, min_y, max_x, max_y)


def _map_template_type(pdf_field_type: str, flags: int) -> str | None:
    """Map PDF field types/flags to template field identifiers."""

    if pdf_field_type == "Tx":
        return "multiline" if (flags & TEXT_FLAG_MULTILINE) else "text"
    if pdf_field_type == "Btn":
        if flags & BUTTON_FLAG_PUSHBUTTON:
            return None
        if flags & BUTTON_FLAG_RADIO:
            return "radio"
        return "checkbox"
    if pdf_field_type == "Ch":
        return "dropdown"
    if pdf_field_type == "Sig":
        return "signature"
    return None


def _normalise_name(value: object) -> str:
    """Return a name token without a leading slash."""

    if isinstance(value, NameObject):
        text = str(value)
    else:
        text = str(value) if value is not None else ""
    if text.startswith("/"):
        return text[1:]
    return text


def _normalise_text(value: object) -> str | None:
    """Convert a PDF object to a human readable string if possible."""

    if value is None:
        return None
    if isinstance(value, TextStringObject):
        return str(value)
    if isinstance(value, NameObject):
        text = str(value)
        return text[1:] if text.startswith("/") else text
    if isinstance(value, BooleanObject):
        return "true" if bool(value) else "false"
    if isinstance(value, (NumberObject, FloatObject)):
        # Preserve integer vs float formatting sensibly.
        number = float(value)
        if number.is_integer():
            return str(int(number))
        return f"{number:.2f}".rstrip("0").rstrip(".")
    if isinstance(value, ArrayObject):
        parts = [_normalise_text(v) for v in value]
        return ", ".join(p for p in parts if p) or None
    try:
        return str(value)
    except Exception:  # pragma: no cover - defensive
        return None


def _normalise_options(value: object) -> list[str] | None:
    """Return a list of option strings for choice fields."""

    if value is None:
        return None
    if not isinstance(value, (ArrayObject, list, tuple)):
        normalised = _normalise_text(value)
        return [normalised] if normalised else None

    options: list[str] = []
    for entry in value:  # type: ignore[assignment]
        normalised = _normalise_text(entry)
        if normalised:
            # Entries can be provided as "export, display" pairs; keep the
            # export token by taking the first component when a comma separated
            # value is encountered.
            if "," in normalised and isinstance(entry, ArrayObject):
                first = _normalise_text(entry[0])
                if first:
                    options.append(first)
                    continue
            options.append(normalised)
    return options or None

