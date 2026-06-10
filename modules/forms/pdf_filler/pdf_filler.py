"""PDF form filling utilities for ICS form exports."""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.constants import FieldDictionaryAttributes
from pypdf.generic import DictionaryObject


_PATCH_APPLIED = False


def _apply_pypdf_patch() -> None:
    """Normalize pypdf choice field option values across supported templates."""
    global _PATCH_APPLIED
    if _PATCH_APPLIED:
        return

    original = DictionaryObject.get_inherited

    def patched(self: DictionaryObject, key: Any, default: Any = None) -> Any:
        result = original(self, key, default)
        if key == FieldDictionaryAttributes.Opt:
            if isinstance(result, list) and all(isinstance(v, list) and len(v) == 2 for v in result):
                result = [row[0] for row in result]
        return result

    DictionaryObject.get_inherited = patched
    _PATCH_APPLIED = True


class PDFFiller:
    """Fill PDF AcroForm templates from incident data using JSON mappings."""

    def __init__(self, mapping_path: str | Path) -> None:
        """Load and validate a JSON mapping configuration."""
        self.mapping_path = Path(mapping_path)
        with self.mapping_path.open("r", encoding="utf-8") as handle:
            self.mapping = json.load(handle)
        self.fields = self.mapping.get("fields", [])
        if not isinstance(self.fields, list):
            raise ValueError("Mapping config must contain a 'fields' list")
        _apply_pypdf_patch()

    def fill(
        self,
        data: dict[str, Any],
        input_pdf: str | Path,
        output_pdf: str | Path,
        strict: bool = False,
    ) -> list[str]:
        """Fill ``input_pdf`` with resolved values and write the result to ``output_pdf``."""
        input_path = Path(input_pdf)
        output_path = Path(output_pdf)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        reader = PdfReader(str(input_path))
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)
        warnings: list[str] = []
        field_values: dict[str, Any] = {}
        available_fields = set((reader.get_fields() or {}).keys())

        for field in self.fields:
            if not isinstance(field, dict):
                warnings.append("Skipped invalid mapping entry that is not an object")
                continue

            pdf_field = field.get("pdf_field") or field.get("field") or field.get("name")
            if not pdf_field:
                warnings.append("Skipped mapping entry missing a pdf_field")
                continue

            try:
                value = self._resolve_value(data, field.get("source"))
            except Exception as exc:
                message = f"Failed to resolve '{pdf_field}': {exc}"
                if strict:
                    raise ValueError(message) from exc
                warnings.append(message)
                continue

            if value in (None, ""):
                default_value = field.get("default")
                if default_value not in (None, ""):
                    value = default_value

            if value is None:
                message = f"No value resolved for '{pdf_field}'"
                if strict:
                    raise ValueError(message)
                warnings.append(message)
                continue

            if pdf_field not in available_fields:
                message = f"PDF field '{pdf_field}' not found in template"
                if strict:
                    raise ValueError(message)
                warnings.append(message)

            field_values[pdf_field] = value

        if field_values:
            writer.set_need_appearances_writer(True)
            writer.update_page_form_field_values(list(writer.pages), field_values, auto_regenerate=True)

        with output_path.open("wb") as handle:
            writer.write(handle)

        return warnings

    def preview_rows(self, data: dict[str, Any]) -> list[dict[str, str]]:
        """Resolve current mapping values into preview rows for the UI."""
        rows: list[dict[str, str]] = []
        for field in self.fields:
            if not isinstance(field, dict):
                continue
            pdf_field = str(field.get("pdf_field") or field.get("field") or field.get("name") or "")
            source = field.get("source")
            try:
                resolved = self._resolve_value(data, source)
            except Exception as exc:
                resolved = f"<error: {exc}>"
            rows.append(
                {
                    "pdf_field": pdf_field,
                    "source": self._source_to_text(source),
                    "resolved": "" if resolved is None else str(resolved),
                }
            )
        return rows

    @staticmethod
    def inspect_pdf_fields(pdf_path: str | Path) -> list[dict[str, Any]]:
        """Return metadata for all fillable fields discovered in a PDF template."""
        _apply_pypdf_patch()
        reader = PdfReader(str(pdf_path))
        fields = reader.get_fields() or {}
        page_numbers = PDFFiller._field_page_numbers(reader)
        results: list[dict[str, Any]] = []

        for name, field in fields.items():
            kind = PDFFiller._field_type(field)
            entry: dict[str, Any] = {
                "name": name,
                "type": kind,
                "page": page_numbers.get(name),
            }

            if kind == "choice":
                options = field.get(FieldDictionaryAttributes.Opt) or field.get("/Opt") or []
                entry["options"] = [str(option) for option in options]
            elif kind == "radio":
                options = PDFFiller._radio_options(field)
                if options:
                    entry["options"] = options

            results.append(entry)

        results.sort(key=lambda item: ((item.get("page") or 0), item["name"]))
        return results

    @staticmethod
    def generate_mapping_scaffold(
        pdf_path: str | Path,
        output_path: str | Path | None = None,
    ) -> dict[str, Any]:
        """Create a starter mapping scaffold from a PDF's fillable fields."""
        pdf_path = Path(pdf_path)
        fields = PDFFiller.inspect_pdf_fields(pdf_path)
        scaffold = {
            "_comment": "Replace source values with real incident data paths; PDF field IDs must match the template exactly.",
            "description": f"Starter mapping scaffold for {pdf_path.name}",
            "fields": [
                {
                    "pdf_field": field["name"],
                    "source": {"literal": ""},
                    "field_type": field["type"],
                }
                for field in fields
            ],
        }
        if output_path is not None:
            target = Path(output_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            with target.open("w", encoding="utf-8") as handle:
                json.dump(scaffold, handle, indent=2)
        return scaffold

    def _resolve_value(self, data: dict[str, Any], source: Any) -> Any:
        """Resolve a mapping source descriptor against the supplied incident data."""
        if source is None:
            return None
        if isinstance(source, str):
            return self._lookup_path(data, source)
        if isinstance(source, (int, float, bool)):
            return source
        if isinstance(source, list):
            return [self._resolve_value(data, item) for item in source]
        if not isinstance(source, dict):
            raise TypeError(f"Unsupported source descriptor: {source!r}")

        if "literal" in source:
            return source["literal"]

        if "join" in source:
            separator = str(source.get("separator", " "))
            parts = []
            for item in source.get("join", []):
                resolved = self._resolve_value(data, item)
                if resolved not in (None, ""):
                    parts.append(str(resolved))
            joined = separator.join(parts)
            if joined:
                return joined
            return source.get("default")

        if "key" in source:
            value = self._lookup_path(data, str(source["key"]))
            if value in (None, ""):
                value = source.get("default")
            if value is None:
                return None
            if source.get("checkbox"):
                return self._checkbox_value(value, source)
            transform = source.get("transform")
            if transform:
                value = self._apply_transform(value, str(transform))
            return value

        if "default" in source:
            return source["default"]

        raise ValueError(f"Unrecognized source mapping: {source!r}")

    @staticmethod
    def _source_to_text(source: Any) -> str:
        if source is None:
            return ""
        if isinstance(source, str):
            return source
        try:
            return json.dumps(source, ensure_ascii=False)
        except TypeError:
            return str(source)

    @staticmethod
    def _lookup_path(data: Any, path: str) -> Any:
        current = data
        for segment in path.split("."):
            if isinstance(current, list):
                if not segment.isdigit():
                    return None
                index = int(segment)
                if index >= len(current):
                    return None
                current = current[index]
                continue
            if isinstance(current, dict):
                if segment not in current:
                    return None
                current = current[segment]
                continue
            return None
        return current

    @staticmethod
    def _apply_transform(value: Any, transform: str) -> Any:
        if value is None:
            return None
        if transform == "upper":
            return str(value).upper()
        if transform == "lower":
            return str(value).lower()

        if transform == "date_short":
            text = str(value).strip()
            if not text:
                return ""
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            parsed = datetime.fromisoformat(text)
            return parsed.strftime("%m/%d/%Y")
        if transform == "time_short":
            text = str(value).strip()
            if not text:
                return ""
            iso = text
            if iso.endswith("Z"):
                iso = iso[:-1] + "+00:00"
            try:
                dt = datetime.fromisoformat(iso)
                return dt.strftime("%H%M")
            except Exception:
                digits = ''.join(ch for ch in text if ch.isdigit())
                if len(digits) == 3:
                    digits = "0" + digits
                if len(digits) == 4:
                    return digits
                return text
        if transform == "datetime_short":
            text = str(value).strip()
            if not text:
                return ""
            if text.endswith("Z"):
                text = text[:-1] + "+00:00"
            dt = datetime.fromisoformat(text)
            return dt.strftime("%m/%d/%Y %H:%M")
        raise ValueError(f"Unsupported transform '{transform}'")


    @staticmethod
    def _checkbox_value(value: Any, source: dict[str, Any]) -> str:
        true_value = str(source.get("checked_value", "/Yes"))
        false_value = str(source.get("unchecked_value", "/Off"))
        if isinstance(value, str):
            normalized = value.strip().lower()
            truthy = normalized not in {"", "0", "false", "no", "off", "none"}
        else:
            truthy = bool(value)
        return true_value if truthy else false_value

    @staticmethod
    def _field_page_numbers(reader: PdfReader) -> dict[str, int]:
        pages: dict[str, int] = {}
        for index, page in enumerate(reader.pages, start=1):
            annotations = page.get("/Annots") or []
            for annotation_ref in annotations:
                annotation = annotation_ref.get_object()
                name = annotation.get("/T")
                if name:
                    pages.setdefault(str(name), index)
                parent = annotation.get("/Parent")
                if parent is not None:
                    parent_obj = parent.get_object()
                    parent_name = parent_obj.get("/T")
                    if parent_name:
                        pages.setdefault(str(parent_name), index)
        return pages

    @staticmethod
    def _field_type(field: Any) -> str:
        field_type = field.get("/FT")
        if field_type == "/Tx":
            return "text"
        if field_type == "/Ch":
            return "choice"
        if field_type == "/Btn":
            if field.get("/Kids"):
                return "radio"
            return "checkbox"
        return "unknown"

    @staticmethod
    def _radio_options(field: Any) -> list[str]:
        options: list[str] = []
        for kid_ref in field.get("/Kids") or []:
            kid = kid_ref.get_object()
            appearance = kid.get("/AP")
            if appearance is None:
                continue
            normal = appearance.get("/N") if hasattr(appearance, "get") else None
            if normal is None:
                continue
            keys = [str(key) for key in normal.keys() if str(key) != "/Off"]
            options.extend(keys)
        return sorted(set(options))
