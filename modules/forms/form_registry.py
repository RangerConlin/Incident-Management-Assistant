"""Runtime form template registry.

The registry provides a single source of truth mapping ``form_id`` and
``form_class`` values to concrete template files on disk.  It is used by
``SARApp`` when creating documents so the UI can locate the correct
PDF/DOCX template and the appropriate :class:`~modules.forms.base_form.BaseForm`
subclass for field normalization.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, Iterator, List, Mapping
from typing import MutableMapping, Sequence
import json
import os
import difflib
from packaging.version import Version, InvalidVersion

from .base_form import BaseForm, registry_form_class_for

__all__ = [
    "FormTemplate",
    "TemplateNotFound",
    "load_registry",
    "save_registry",
    "register_template",
    "get_template",
    "list_templates",
    "resolve_for_creation",
    "reload_if_dev",
    "registry_stats",
    "search",
]

# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class FormTemplate:
    """Metadata describing a single template file."""

    form_id: str
    title: str
    class_name: str
    version: str
    format: str
    file_path: Path | None
    jurisdiction: str | None = None
    tags: list[str] = field(default_factory=list)
    related: list[str] = field(default_factory=list)
    deprecated: bool = False

    def to_json(self) -> Dict[str, Any]:
        data = asdict(self)
        if self.file_path is not None:
            data["file_path"] = str(self.file_path).replace(os.sep, "/")
        return data


class TemplateNotFound(LookupError):
    """Raised when a template cannot be located."""


# ---------------------------------------------------------------------------
# Internal state
# ---------------------------------------------------------------------------

ROOT = Path(__file__).resolve().parents[2]
DEFAULT_JSON = ROOT / "data" / "templates" / "form_templates.json"

_REGISTRY: Dict[str, List[FormTemplate]] = {}
_BY_CLASS: Dict[str, List[FormTemplate]] = {}
_REGISTRY_PATH: Path | None = None
_REGISTRY_MTIME: float | None = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sort_key(t: FormTemplate) -> Any:
    try:
        return Version(t.version)
    except InvalidVersion:
        return t.version


def _ensure_sorted(l: List[FormTemplate]) -> None:
    l.sort(key=_sort_key, reverse=True)


def _json_path(json_path: Path | None) -> Path:
    if json_path is not None:
        return json_path
    env = os.getenv("FORM_TEMPLATES_PATH")
    if env:
        p = Path(env)
        if not p.is_absolute():
            p = ROOT / p
        return p
    return DEFAULT_JSON


# Seed data used when the JSON file does not yet exist.
_SEED_DATA: List[Dict[str, Any]] = [
    {
        "form_id": "ics_201",
        "title": "ICS 201 — Incident Briefing",
        "class_name": "ICS201",
        "version": "2025.09",
        "format": "pdf",
        "file_path": "templates/ics/ics201_2025.09.pdf",
        "jurisdiction": "federal",
        "tags": ["planning", "command"],
        "related": ["ics_202"],
        "deprecated": False,
    },
    {
        "form_id": "ics_201",
        "title": "ICS 201 — Incident Briefing",
        "class_name": "ICS201",
        "version": "2025.05",
        "format": "pdf",
        "file_path": "templates/ics/ics201_2025.05.pdf",
        "jurisdiction": "federal",
        "tags": ["planning", "command"],
        "related": ["ics_202"],
        "deprecated": False,
    },
    {
        "form_id": "ics_205",
        "title": "ICS 205 — Communications Plan",
        "class_name": "ICS205",
        "version": "2025.04",
        "format": "pdf",
        "file_path": "templates/ics/ics205_2025.04.pdf",
        "jurisdiction": "federal",
        "tags": ["communications"],
        "related": [],
        "deprecated": False,
    },
    {
        "form_id": "cap_104",
        "title": "CAPF 104 — Mission Flight Plan",
        "class_name": "CAP104",
        "version": "2024.01",
        "format": "pdf",
        "file_path": "templates/cap/capf104_2024.01.pdf",
        "jurisdiction": "cap",
        "tags": ["aviation"],
        "related": [],
        "deprecated": False,
    },
    {
        "form_id": "state_id_ics_214",
        "title": "ICS 214 — Activity Log (Idaho)",
        "class_name": "ICS214",
        "version": "2023.11",
        "format": "docx",
        "file_path": "templates/state/id/ics214_2023.11.docx",
        "jurisdiction": "state:ID",
        "tags": ["operations"],
        "related": [],
        "deprecated": False,
    },
    {
        "form_id": "mission_brief",
        "title": "Mission Brief",
        "class_name": "MissionBrief",
        "version": "1",
        "format": "internal",
        "file_path": "",
        "jurisdiction": None,
        "tags": ["internal"],
        "related": [],
        "deprecated": False,
    },
]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def load_registry(json_path: Path | None = None) -> None:
    """Load the registry from ``json_path``.

    If the file does not exist it will be created with a default set of
    templates.  The data is normalised and stored in the module level
    registries for fast lookup.
    """

    global _REGISTRY_PATH, _REGISTRY_MTIME
    path = _json_path(json_path)
    _REGISTRY_PATH = path

    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf8") as fh:
            json.dump(_SEED_DATA, fh, indent=2, sort_keys=True)
        # Ensure placeholder files exist for seeded entries
        for item in _SEED_DATA:
            p = item.get("file_path")
            if item["format"] in {"pdf", "docx"} and p:
                (ROOT / p).parent.mkdir(parents=True, exist_ok=True)
                (ROOT / p).touch()

    with path.open("r", encoding="utf8") as fh:
        data = json.load(fh)

    _REGISTRY.clear()
    _BY_CLASS.clear()

    for item in data:
        pstr = item.get("file_path")
        if item.get("format") in {"pdf", "docx"} and pstr:
            p = (ROOT / pstr).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.touch(exist_ok=True)
        ft = FormTemplate(
            form_id=item["form_id"],
            title=item["title"],
            class_name=item["class_name"],
            version=item["version"],
            format=item["format"],
            file_path=(ROOT / pstr).resolve() if pstr else None,
            jurisdiction=item.get("jurisdiction"),
            tags=list(item.get("tags", [])),
            related=list(item.get("related", [])),
            deprecated=bool(item.get("deprecated", False)),
        )
        register_template(ft, allow_replace=True)

    _REGISTRY_MTIME = path.stat().st_mtime


def save_registry(json_path: Path | None = None) -> None:
    """Persist the current registry to ``json_path``."""

    path = _json_path(json_path)
    all_items: List[FormTemplate] = [t for lst in _REGISTRY.values() for t in lst]
    all_items.sort(key=lambda t: (t.form_id, _sort_key(t)))
    serialised = [t.to_json() for t in all_items]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf8") as fh:
        json.dump(serialised, fh, indent=2, sort_keys=True)
    global _REGISTRY_MTIME
    _REGISTRY_MTIME = path.stat().st_mtime


def register_template(t: FormTemplate, allow_replace: bool = False) -> None:
    """Add ``t`` to the in-memory registry."""

    if not t.form_id or not t.class_name or not t.version:
        raise ValueError("form_id, class_name and version are required")
    if t.format not in {"pdf", "docx", "internal"}:
        raise ValueError(f"Unsupported format: {t.format}")
    if t.format in {"pdf", "docx"}:
        if not t.file_path:
            raise ValueError("file_path required for pdf/docx templates")
        if not Path(t.file_path).exists():
            raise FileNotFoundError(str(t.file_path))
    key = t.form_id
    lst = _REGISTRY.setdefault(key, [])
    existing = next((x for x in lst if x.version == t.version), None)
    if existing and not allow_replace:
        raise ValueError(f"Template {t.form_id!r} version {t.version!r} already registered")
    if existing:
        lst.remove(existing)
    lst.append(t)
    _ensure_sorted(lst)

    cl = _BY_CLASS.setdefault(t.class_name, [])
    cl_existing = next((x for x in cl if x.form_id == t.form_id and x.version == t.version), None)
    if cl_existing:
        cl.remove(cl_existing)
    cl.append(t)
    _ensure_sorted(cl)


def _filter_templates(
    candidates: Iterable[FormTemplate],
    *,
    version: str | None,
    jurisdiction: str | None,
    include_deprecated: bool,
) -> List[FormTemplate]:
    lst = [t for t in candidates if include_deprecated or not t.deprecated]
    if version:
        lst = [t for t in lst if t.version == version]
    if jurisdiction:
        exact = [t for t in lst if t.jurisdiction == jurisdiction]
        if exact:
            lst = exact
        else:
            generic = [t for t in lst if not t.jurisdiction]
            lst = generic
    return lst


def get_template(
    *,
    form_id: str | None = None,
    class_name: str | None = None,
    version: str | None = None,
    jurisdiction: str | None = None,
    include_deprecated: bool = False,
) -> FormTemplate:
    """Retrieve a template using the lookup precedence rules."""

    candidates: List[FormTemplate] = []

    if form_id and version:
        candidates = _REGISTRY.get(form_id, [])
    elif form_id:
        candidates = _REGISTRY.get(form_id, [])
    elif class_name and version:
        candidates = _BY_CLASS.get(class_name, [])
    elif class_name:
        candidates = _BY_CLASS.get(class_name, [])
    else:
        raise ValueError("Either form_id or class_name must be provided")

    filtered = _filter_templates(
        candidates,
        version=version if form_id else (version if class_name and version else None),
        jurisdiction=jurisdiction,
        include_deprecated=include_deprecated,
    )

    if not filtered:
        keys = set(_REGISTRY) | set(_BY_CLASS)
        msg = f"No template found for form_id={form_id!r} class_name={class_name!r}"
        close = difflib.get_close_matches(form_id or class_name or "", list(keys), n=3)
        if close:
            msg += f". Close matches: {', '.join(close)}"
        raise TemplateNotFound(msg)

    _ensure_sorted(filtered)
    return filtered[0]


def list_templates(
    *,
    class_name: str | None = None,
    jurisdiction: str | None = None,
    include_deprecated: bool = False,
) -> List[FormTemplate]:
    """Return a list of templates filtered by the provided criteria."""

    if class_name:
        candidates = list(_BY_CLASS.get(class_name, []))
    else:
        candidates = [t for lst in _REGISTRY.values() for t in lst]
    return _filter_templates(
        candidates,
        version=None,
        jurisdiction=jurisdiction,
        include_deprecated=include_deprecated,
    )


def resolve_for_creation(
    form_class: str,
    preferred_form_id: str | None = None,
    version: str | None = None,
    jurisdiction: str | None = None,
) -> FormTemplate:
    """Convenience wrapper used by UI when creating a document."""

    if preferred_form_id:
        return get_template(
            form_id=preferred_form_id,
            version=version,
            jurisdiction=jurisdiction,
        )
    return get_template(
        class_name=form_class,
        version=version,
        jurisdiction=jurisdiction,
    )


def reload_if_dev() -> None:
    """Reload the registry if ``DEV_MODE`` is enabled and the file changed."""

    if not os.getenv("DEV_MODE"):
        return
    if _REGISTRY_PATH is None:
        return
    try:
        mtime = _REGISTRY_PATH.stat().st_mtime
    except OSError:
        return
    global _REGISTRY_MTIME
    if _REGISTRY_MTIME and mtime > _REGISTRY_MTIME:
        load_registry(_REGISTRY_PATH)


def registry_stats() -> Dict[str, int]:
    """Return counts by class name and jurisdiction."""

    stats: Dict[str, int] = {}
    for class_name, items in _BY_CLASS.items():
        stats[f"class:{class_name}"] = len(items)
    juris: MutableMapping[str, int] = {}
    for items in _REGISTRY.values():
        for t in items:
            key = t.jurisdiction or "generic"
            juris[key] = juris.get(key, 0) + 1
    stats.update({f"jurisdiction:{k}": v for k, v in juris.items()})
    return stats


def search(query: str) -> List[FormTemplate]:
    """Fuzzy search templates by id, title or tags."""

    hay = [t for lst in _REGISTRY.values() for t in lst]
    keys = {t.form_id: t for t in hay}
    for t in hay:
        keys[t.title] = t
        for tag in t.tags:
            keys[f"tag:{tag}"] = t
    matches = difflib.get_close_matches(query, list(keys), n=5, cutoff=0.3)
    return [keys[m] for m in matches]


# Integration example -------------------------------------------------------

__doc__ += """

Example
-------

>>> from modules.forms.form_registry import resolve_for_creation
>>> from modules.forms.base_form import BaseForm, registry_form_class_for, extract_pdf_fields, ingest_canonical
>>> t = resolve_for_creation(form_class="ICS201", jurisdiction="federal")
>>> t.form_id
'ics_201'
>>> FormCls = registry_form_class_for(t.class_name)
>>> mapper = FormCls()
>>> canonical = mapper.normalize_pdf_fields(extract_pdf_fields(t.file_path))
>>> ingest_canonical(canonical)
"""


if __name__ == "__main__":  # pragma: no cover - smoke test
    load_registry()
    print("Registry stats:", registry_stats())
    try:
        t = resolve_for_creation(form_class="ICS201", jurisdiction="federal")
        print("Resolved:", t)
    except TemplateNotFound as exc:
        print("Lookup failed:", exc)
