"""Resolve established binding descriptors without desktop state or database access."""
from __future__ import annotations

from typing import Any

from .context import human_time


def lookup_path(data: Any, path: str) -> Any:
    value = data
    for part in path.split("."):
        if isinstance(value, dict):
            value = value.get(part)
        elif isinstance(value, list) and part.isdigit() and int(part) < len(value):
            value = value[int(part)]
        else:
            return None
    return value


def apply_transform(value: Any, transform: str) -> Any:
    if value is None:
        return None
    if transform == "upper":
        return str(value).upper()
    if transform == "lower":
        return str(value).lower()
    if transform == "freq_mhz":
        return f"{value} MHz" if str(value).strip() else ""
    if transform in {"date_short", "time_short", "datetime_short", "datetime_human"}:
        return human_time(value, transform)
    raise ValueError(f"Unsupported binding transform: {transform}")


def checkbox_value(value: Any, source: dict[str, Any]) -> str:
    if "checked_if" in source:
        expected = source["checked_if"]
        if not isinstance(expected, list):
            expected = [expected]
        checked = any(str(value).strip().lower() == str(v).strip().lower() for v in expected)
    elif isinstance(value, str):
        checked = value.strip().lower() not in {"", "0", "false", "no", "off", "none"}
    else:
        checked = bool(value)
    return str(source.get("checked_value", "/Yes") if checked else source.get("unchecked_value", "/Off"))


def resolve_source(data: dict[str, Any], source: Any) -> Any:
    """Keep the existing literal/key/first_of/join/checkbox binding language."""
    if source is None or isinstance(source, (int, float, bool)):
        return source
    if isinstance(source, str):
        return lookup_path(data, source)
    if isinstance(source, list):
        return [resolve_source(data, item) for item in source]
    if not isinstance(source, dict):
        raise ValueError("Unsupported binding source descriptor")
    if "literal" in source:
        return source["literal"]
    if "first_of" in source:
        for path in source["first_of"]:
            value = resolve_source(data, path)
            if value not in (None, ""):
                return apply_transform(value, source["transform"]) if source.get("transform") else value
        return source.get("default")
    if "join" in source:
        values = [resolve_source(data, item) for item in source["join"]]
        joined = str(source.get("separator", " ")).join(str(v) for v in values if v not in (None, ""))
        return joined or source.get("default")
    if "key" in source:
        value = lookup_path(data, source["key"])
        if value in (None, ""):
            value = source.get("default")
        if value is None:
            return None
        if source.get("checkbox"):
            return checkbox_value(value, source)
        return apply_transform(value, source["transform"]) if source.get("transform") else value
    if "default" in source:
        return source["default"]
    raise ValueError("Unrecognized binding source mapping")


def resolve_fields(mapping: dict[str, Any], data: dict[str, Any]) -> dict[str, Any]:
    """Bind explicit canonical fields; never silently overwrite a conflicting binding."""
    values: dict[str, Any] = {}
    for field in mapping["fields"]:
        source = field["source"]
        if source is None or source == "":
            continue
        name = field["pdf_field"]
        value = resolve_source(data, source)
        if name in values and values[name] != value:
            raise ValueError(f"Conflicting bindings for PDF field: {name}")
        values[name] = value
    return values


def resolve_row(group: dict[str, Any], row: dict[str, Any], number: int) -> dict[str, Any]:
    """Resolve one already-paginated repeating row using its verified field patterns."""
    if number < 1 or number > sum(group["rows_per_page"]):
        raise ValueError("Repeating row exceeds its template capacity; paginate first")
    return {
        pattern.format(n=number): lookup_path(row, path)
        for path, pattern in group["col_patterns"].items()
    }
