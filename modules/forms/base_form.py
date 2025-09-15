"""Base form normalization utilities for ICS forms.

This module defines a lightweight mapping system used to convert the
field names from vendor supplied fillable PDF forms into a canonical
schema understood by the application.  The classes are intentionally
small and free of any GUI or I/O logic so that they may be reused in
multiple contexts (unit tests, back‑end services, etc.).

An in‑memory registry keeps track of available form classes and allows
lookups by their ``FORM_CLASS`` string.  New subclasses should register
themselves using the :func:`register_form_class` decorator.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Iterable, Mapping, MutableMapping
from typing import Type, Set

__all__ = [
    "BaseForm",
    "FormClassNotFound",
    "register_form_class",
    "registry_form_class_for",
    "ICS201Form",
    "extract_pdf_fields",
    "ingest_canonical",
]


class FormClassNotFound(KeyError):
    """Raised when a form class is not registered."""


@dataclass(slots=True)
class BaseForm:
    """Base class for all form mapping helpers.

    Subclasses specify a ``FORM_CLASS`` identifier, a mapping from PDF field
    names to canonical keys and optional field formatters.  ``normalize_pdf_fields``
    applies the mapping and returns a dictionary using the canonical keys
    expected by the application.
    """

    FORM_CLASS: str = ""
    DEFAULT_VERSION: str | None = None
    FIELD_MAP: Dict[str, str] = field(default_factory=dict)
    FORMATTERS: Dict[str, Callable[[Any], Any]] = field(default_factory=dict)

    def normalize_pdf_fields(self, raw: Mapping[str, Any]) -> Dict[str, Any]:
        """Normalize fields extracted from a PDF.

        Parameters
        ----------
        raw:
            Mapping of raw PDF field names to their values.

        Returns
        -------
        dict
            Canonical key/value pairs.
        """

        canonical: MutableMapping[str, Any] = {}
        for pdf_key, canonical_key in self.FIELD_MAP.items():
            if pdf_key not in raw:
                continue
            value = raw[pdf_key]
            formatter = self.FORMATTERS.get(canonical_key)
            if formatter is not None:
                try:
                    value = formatter(value)
                except Exception:
                    # Formatter errors should not abort normalization; the raw
                    # value is used as a best effort.
                    pass
            canonical[canonical_key] = value
        return dict(canonical)

    @classmethod
    def schema_keys(cls) -> Set[str]:
        """Return the set of canonical keys this form produces."""

        return set(cls.FIELD_MAP.values())


_FORM_CLASS_REGISTRY: Dict[str, Type[BaseForm]] = {}


def register_form_class(cls: Type[BaseForm]) -> Type[BaseForm]:
    """Class decorator to register :class:`BaseForm` subclasses.

    The class' ``FORM_CLASS`` attribute is used as the registry key.
    """

    if not cls.FORM_CLASS:
        raise ValueError("FORM_CLASS must be defined for form classes")
    _FORM_CLASS_REGISTRY[cls.FORM_CLASS] = cls
    return cls


def registry_form_class_for(class_name: str) -> Type[BaseForm]:
    """Return the registered form class for ``class_name``.

    Parameters
    ----------
    class_name:
        The canonical form class identifier (e.g. ``"ICS201"``).
    """

    try:
        return _FORM_CLASS_REGISTRY[class_name]
    except KeyError as exc:  # pragma: no cover - thin wrapper
        raise FormClassNotFound(class_name) from exc


@register_form_class
class ICS201Form(BaseForm):
    """Example implementation for the ICS 201 form."""

    FORM_CLASS = "ICS201"
    DEFAULT_VERSION = "2025.09"
    FIELD_MAP = {
        # Vendor PDF field name -> canonical key used by the application.
        "Incident Name": "incident_name",
        "Date": "operational_period_date",
        "Time": "operational_period_time",
        "Map/Sketch": "map_sketch",
    }
    FORMATTERS = {
        "operational_period_date": lambda v: str(v).strip(),
        "operational_period_time": lambda v: str(v).strip(),
    }


# ---------------------------------------------------------------------------
# The following helpers are placeholders used in documentation examples. They
# are intentionally tiny and contain no real implementation.
# ---------------------------------------------------------------------------

def extract_pdf_fields(file_path: str | bytes) -> Dict[str, Any]:
    """Placeholder that pretends to extract fields from a PDF template."""

    return {}


def ingest_canonical(data: Mapping[str, Any]) -> None:
    """Placeholder that pretends to ingest canonical form data."""

    _ = data


if __name__ == "__main__":  # pragma: no cover - smoke test
    mapper = ICS201Form()
    example = {"Incident Name": "Test", "Date": "2025-01-01"}
    print(mapper.normalize_pdf_fields(example))
    print("Schema keys:", ICS201Form.schema_keys())
