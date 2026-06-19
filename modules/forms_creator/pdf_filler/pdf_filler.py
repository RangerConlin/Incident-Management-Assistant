"""PDF form filling utilities for ICS form exports."""

from __future__ import annotations

import io
import json
import textwrap
from datetime import datetime
from pathlib import Path
from typing import Any

from pypdf import PdfReader, PdfWriter
from pypdf.constants import FieldDictionaryAttributes
from pypdf.generic import DictionaryObject, TextStringObject


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
        form_row_groups: list[dict] | None = None,
    ) -> list[str]:
        """Fill ``input_pdf`` with resolved values and write the result to ``output_pdf``.

        ``form_row_groups`` is the row_groups list from the form catalog entry
        (the form-level definition of what repeats — data_key, chars_per_row,
        column definitions).  The mapping's row_groups supply the version-specific
        PDF field patterns and row counts.  When a mapping row_group carries a
        ``ref`` that matches a form_row_group ``id``, they are merged: the form
        definition supplies the data source and wrap behavior; the mapping supplies
        the field name patterns.  Mappings without a ``ref`` continue to work
        as before (all config inline).
        """
        input_path = Path(input_pdf)
        output_path = Path(output_pdf)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        reader = PdfReader(str(input_path))
        writer = PdfWriter()
        writer.clone_document_from_reader(reader)
        warnings: list[str] = []
        field_values: dict[str, Any] = {}
        available_fields = set((reader.get_fields() or {}).keys())

        # --- Regular fields --------------------------------------------------
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
                if default_value is not None:
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

        # --- Row groups ------------------------------------------------------
        row_groups = self.mapping.get("row_groups", [])
        mapping_dir = self.mapping_path.parent
        # continuation_field_values accumulates fields from all continuation
        # pages; they are written in a single pass after all pages are appended.
        continuation_field_values: dict[str, Any] = {}

        for rg in row_groups:
            rg_warnings = self._fill_row_group(
                rg=rg,
                data=data,
                writer=writer,
                page0_field_values=field_values,
                cont_field_values=continuation_field_values,
                mapping_dir=mapping_dir,
                strict=strict,
                form_row_groups=form_row_groups or [],
                template_path=input_path,
            )
            warnings.extend(rg_warnings)

        # --- Write all fields in one pass (page 1 + continuation) -----------
        all_field_values = {**field_values, **continuation_field_values}
        if all_field_values:
            writer.set_need_appearances_writer(True)
            writer.update_page_form_field_values(list(writer.pages), all_field_values, auto_regenerate=True)

        with output_path.open("wb") as handle:
            writer.write(handle)

        return warnings

    # ------------------------------------------------------------------
    # Row group helpers
    # ------------------------------------------------------------------

    def _fill_row_group(
        self,
        rg: dict[str, Any],
        data: dict[str, Any],
        writer: PdfWriter,
        page0_field_values: dict[str, Any],
        cont_field_values: dict[str, Any],
        mapping_dir: Path,
        strict: bool,
        form_row_groups: list[dict] | None = None,
        template_path: Path | None = None,
    ) -> list[str]:
        """Process a single row_group entry.  Returns accumulated warnings.

        If ``rg`` contains a ``ref`` key and a matching entry exists in
        ``form_row_groups``, the form-level definition supplies ``data_key``,
        ``chars_per_row``, and column definitions.  Field patterns in ``rg``
        may then use ``"column": "<id>"`` instead of ``"source_key"``/``"role"``
        to reference the shared column definitions.

        Overflow modes (set via ``"overflow_mode"`` in the mapping row_group):

        - ``"continuation"`` (default): overflow rows go to a separate template
          file named by ``continuation_template``.  The continuation page uses
          ``continuation_fields`` patterns.  The first continuation page is
          appended as-is; subsequent pages clone it with ``_p{n}`` suffixes to
          avoid AcroForm name collisions.

        - ``"repeat"``: overflow rows clone the main template page.  Field names
          from the same ``fields`` definitions are reused, with ``_p{n}`` suffixes
          appended to avoid collisions.  No ``continuation_template`` needed.

        - ``"truncate"``: rows beyond ``rows_per_page[0]`` are silently dropped.
          Use for fields with a natural hard limit (objectives lists, comment
          boxes) where spilling to a new page is not appropriate.
        """
        warnings: list[str] = []

        # --- col_patterns path (mapper-driven arrays) ---
        col_patterns = rg.get("col_patterns")
        if col_patterns:
            return self._fill_col_patterns_group(
                rg, data, page0_field_values, warnings
            )

        # Resolve form-level row group definition if ref is provided
        ref = rg.get("ref")
        form_rg: dict[str, Any] = {}
        col_map: dict[str, dict] = {}
        if ref and form_row_groups:
            form_rg = next((r for r in form_row_groups if r.get("id") == ref), {})
            col_map = {c["id"]: c for c in form_rg.get("columns", [])}

        data_key = form_rg.get("data_key") or rg.get("data_key", "entries")
        chars_per_row: int = int(form_rg.get("chars_per_row") or rg.get("chars_per_row", 85))
        rows_per_page: list[int] = rg.get("rows_per_page", [24, 36])
        p1_capacity: int = rows_per_page[0] if rows_per_page else 24
        cont_capacity: int = rows_per_page[1] if len(rows_per_page) > 1 else p1_capacity

        # Raw entries from data
        raw_entries: list[dict[str, Any]] = data.get(data_key) or []

        # Expand each entry into (timestamp, text) display rows
        display_rows: list[tuple[str, str]] = []
        for item in raw_entries:
            ts: str = str(item.get("timestamp_display") or "")
            text: str = str(item.get("text") or "")
            if not text:
                display_rows.append((ts, ""))
                continue
            chunks = textwrap.wrap(text, width=chars_per_row) or [text]
            for i, chunk in enumerate(chunks):
                display_rows.append((ts if i == 0 else "", chunk))

        # Compute total page count upfront so page_number bindings are accurate
        overflow_mode_preview: str = rg.get("overflow_mode", "").lower()
        if not overflow_mode_preview:
            has_cont = rg.get("continuation_template") or rg.get("continuation_page") is not None
            overflow_mode_preview = "continuation" if has_cont else "truncate"
        if overflow_mode_preview == "truncate" or len(display_rows) <= p1_capacity:
            total_pages = 1
        else:
            import math
            total_pages = 1 + math.ceil((len(display_rows) - p1_capacity) / cont_capacity)

        # Fill page 1 page-number header fields
        page1_header: dict[str, Any] = rg.get("page1_header_fields", {})
        for raw_field_name, source_desc in page1_header.items():
            value = self._resolve_computed(source_desc, page_number=1, total_pages=total_pages, data=data)
            if value is not None:
                page0_field_values[raw_field_name] = str(value)

        # --- Page 1 rows (into shared field_values dict) ---
        page1_rows = display_rows[:p1_capacity]
        fields_p1: list[dict[str, Any]] = rg.get("fields", [])
        for row_idx_0, (ts, txt) in enumerate(page1_rows):
            n = row_idx_0 + 1  # 1-based within page
            for fdef in fields_p1:
                if not self._row_in_range(n, fdef):
                    continue
                field_name = self._resolve_field_name(fdef, n)
                if not field_name:
                    continue
                role, src_key = self._resolve_column(fdef, col_map)
                value = ts if role == "timestamp" else txt
                page0_field_values[field_name] = value

        # --- Overflow rows need continuation pages ---
        overflow_rows = display_rows[p1_capacity:]
        if not overflow_rows:
            return warnings

        overflow_mode: str = rg.get("overflow_mode", "").lower()

        # Infer overflow_mode from presence of continuation_template if not explicit
        if not overflow_mode:
            overflow_mode = "continuation" if rg.get("continuation_template") else "truncate"

        # --- truncate: silently drop overflow ---
        if overflow_mode == "truncate":
            return warnings

        # --- repeat: clone the main template page for each overflow block ---
        if overflow_mode == "repeat":
            if template_path is None or not template_path.exists():
                warnings.append("overflow_mode='repeat' requires template_path to be set")
                return warnings
            repeat_reader = PdfReader(str(template_path))
            repeat_fields: list[dict[str, Any]] = rg.get("fields", [])
            repeat_header_fields: dict[str, Any] = rg.get("continuation_header_fields", {})
            page_num = 2
            offset = 0
            while offset < len(overflow_rows):
                block = overflow_rows[offset: offset + cont_capacity]
                offset += cont_capacity
                suffix = f"_p{page_num}"
                self._append_cloned_continuation(repeat_reader, writer, suffix)
                for raw_field_name, source_desc in repeat_header_fields.items():
                    value = self._resolve_computed(source_desc, page_number=page_num,
                                                   total_pages=total_pages, data=data)
                    if value is not None:
                        cont_field_values[raw_field_name + suffix] = str(value)
                for row_idx_0, (ts, txt) in enumerate(block):
                    n = row_idx_0 + 1
                    for fdef in repeat_fields:
                        if not self._row_in_range(n, fdef):
                            continue
                        base_name = self._resolve_field_name(fdef, n)
                        if not base_name:
                            continue
                        role, _ = self._resolve_column(fdef, col_map)
                        cont_field_values[base_name + suffix] = ts if role == "timestamp" else txt
                page_num += 1
            return warnings

        # --- continuation: separate file or page-within-template ---
        cont_page_idx: int | None = None  # 0-based page index in template
        cont_template_path: Path | None = None

        raw_cont_page = rg.get("continuation_page")
        if raw_cont_page is not None:
            # Use a specific page from the main template PDF
            if template_path is None or not template_path.exists():
                warnings.append("continuation_page requires template_path to be set")
                return warnings
            cont_page_idx = int(raw_cont_page) - 1  # convert to 0-based
        else:
            cont_template_rel: str = rg.get("continuation_template", "")
            if not cont_template_rel:
                warnings.append(
                    "row_group has overflow rows but no continuation_template "
                    "or continuation_page specified"
                )
                return warnings
            cont_template_path = mapping_dir / cont_template_rel
            if not cont_template_path.exists():
                warnings.append(f"Continuation template not found: {cont_template_path}")
                return warnings

        def _make_cont_reader() -> PdfReader | None:
            if cont_page_idx is not None:
                main_reader = PdfReader(str(template_path))
                if cont_page_idx >= len(main_reader.pages):
                    warnings.append(
                        f"continuation_page {cont_page_idx + 1} out of range "
                        f"(template has {len(main_reader.pages)} pages)"
                    )
                    return None
                buf = io.BytesIO()
                pw = PdfWriter()
                pw.add_page(main_reader.pages[cont_page_idx])
                pw.write(buf)
                buf.seek(0)
                return PdfReader(buf)
            return PdfReader(str(cont_template_path))

        cont_fields: list[dict[str, Any]] = rg.get("continuation_fields", [])
        cont_header_fields: dict[str, Any] = rg.get("continuation_header_fields", {})

        # Process overflow in blocks of cont_capacity per continuation page
        page_num = 2  # page 1 is the main template
        offset = 0
        while offset < len(overflow_rows):
            block = overflow_rows[offset: offset + cont_capacity]
            offset += cont_capacity

            cont_reader = _make_cont_reader()
            if cont_reader is None:
                return warnings

            if page_num == 2:
                # Append the continuation page as-is (first overflow page)
                writer.append(cont_reader)
                cont_suffix = ""
            else:
                # Clone the continuation page, renaming fields with _p{page_num}
                cont_suffix = f"_p{page_num}"
                self._append_cloned_continuation(cont_reader, writer, cont_suffix)

            # Fill header fields
            for raw_field_name, source_desc in cont_header_fields.items():
                field_name = raw_field_name + cont_suffix
                value = self._resolve_computed(source_desc, page_number=page_num,
                                               total_pages=total_pages, data=data)
                if value is not None:
                    cont_field_values[field_name] = str(value)

            # Fill activity rows
            for row_idx_0, (ts, txt) in enumerate(block):
                n = row_idx_0 + 1  # 1-based within this continuation page
                for fdef in cont_fields:
                    if not self._row_in_range(n, fdef):
                        continue
                    base_name = self._resolve_field_name(fdef, n)
                    if not base_name:
                        continue
                    role, _ = self._resolve_column(fdef, col_map)
                    cont_field_values[base_name + cont_suffix] = ts if role == "timestamp" else txt

            page_num += 1

        return warnings

    def _fill_col_patterns_group(
        self,
        rg: dict[str, Any],
        data: dict[str, Any],
        field_values: dict[str, Any],
        warnings: list[str],
    ) -> list[str]:
        """Fill PDF fields driven by col_patterns (mapper-assigned arrays)."""
        import re as _re

        data_key: str = rg.get("data_key", rg.get("ref", ""))
        col_patterns: dict[str, str] = rg.get("col_patterns", {})
        col_checkboxes: set[str] = set(rg.get("col_checkboxes", []))
        rows_per_page: list[int] = rg.get("rows_per_page", [1])
        max_rows: int = rows_per_page[0] if rows_per_page else 1
        row_offset: int = rg.get("row_offset", 0)

        rows: list[dict[str, Any]] = data.get(data_key) or []

        for row_idx, row in enumerate(rows[row_offset:row_offset + max_rows]):
            n = row_offset + row_idx + 1  # 1-based, accounting for offset
            for col_id, pattern in col_patterns.items():
                if not pattern:
                    continue
                field_name = _re.sub(r"\{n\}", str(n), pattern, flags=_re.IGNORECASE)
                value = row.get(col_id)
                if col_id in col_checkboxes:
                    field_values[field_name] = "X" if value else ""
                else:
                    field_values[field_name] = "" if value is None else str(value)

        return warnings

    @staticmethod
    def _resolve_column(fdef: dict[str, Any], col_map: dict[str, dict]) -> tuple[str, str]:
        """Return (role, source_key) for a field pattern definition.

        If the fdef has a ``column`` key, look up role and source_key from
        col_map (the form-level column definitions).  Otherwise fall back to
        inline ``role`` and ``source_key`` keys for backward compatibility.
        """
        col_id = fdef.get("column")
        if col_id and col_map:
            col_def = col_map.get(col_id, {})
            return col_def.get("role", ""), col_def.get("source_key", col_id)
        return fdef.get("role", ""), fdef.get("source_key", "text")

    @staticmethod
    def _resolve_computed(
        source_desc: Any,
        page_number: int,
        total_pages: int,
        data: dict[str, Any],
    ) -> Any:
        """Resolve a header field source that may be a computed value, a key path,
        or a legacy plain-dict with a ``"key"`` entry.

        Computed sources:
        - ``{"computed": "page_number"}``  → current page number (int)
        - ``{"computed": "total_pages"}``  → total pages in this group (int)
        - ``{"computed": "page_of_total"}`` → e.g. "2 of 4"

        All other sources fall back to key-path lookup so that existing
        ``{"key": "incident.name"}`` entries in continuation_header_fields
        continue to work unchanged.
        """
        if not isinstance(source_desc, dict):
            return None
        computed = source_desc.get("computed")
        if computed == "page_number":
            return page_number
        if computed == "total_pages":
            return total_pages
        if computed == "page_of_total":
            return f"{page_number} of {total_pages}"
        # Legacy / regular key-path
        key_path = source_desc.get("key", "")
        if key_path:
            return PDFFiller._lookup_path(data, key_path)
        return None

    @staticmethod
    def _resolve_field_name(fdef: dict[str, Any], n: int) -> str:
        """Return the PDF field name for row ``n`` from a field definition.

        Supports two formats:
        - Explicit: ``{"pdf_field": "Text37"}`` → returns "Text37" as-is
        - Pattern: ``{"pdf_field_pattern": "DateTimeRow{n}"}`` → substitutes n
        """
        explicit = fdef.get("pdf_field")
        if explicit:
            return str(explicit)
        pattern = fdef.get("pdf_field_pattern", "")
        return pattern.replace("{n}", str(n))

    @staticmethod
    def _row_in_range(n: int, fdef: dict[str, Any]) -> bool:
        """Return True if row index ``n`` (1-based) falls within the fdef range.

        Supports two formats:
        - Pattern range: ``{"from_row": 1, "to_row": 15, "pdf_field_pattern": "..."}``
        - Explicit single row: ``{"row": 1, "pdf_field": "Text37"}``
        """
        explicit_row = fdef.get("row")
        if explicit_row is not None:
            return n == int(explicit_row)
        from_row = fdef.get("from_row")
        to_row = fdef.get("to_row")
        if from_row is not None and n < int(from_row):
            return False
        if to_row is not None and n > int(to_row):
            return False
        return True

    @staticmethod
    def _append_cloned_continuation(
        reader: PdfReader,
        writer: PdfWriter,
        suffix: str,
    ) -> None:
        """Append reader's pages to writer, renaming widget annotation /T values
        by appending ``suffix`` to avoid AcroForm field name collisions."""
        # Write reader to an in-memory buffer, then reload so we have an
        # independent copy whose annotations we can mutate safely.
        buf = io.BytesIO()
        tmp_writer = PdfWriter()
        tmp_writer.clone_document_from_reader(reader)
        tmp_writer.write(buf)
        buf.seek(0)
        cloned_reader = PdfReader(buf)

        # Rename every widget annotation /T on every page
        for page in cloned_reader.pages:
            annots = page.get("/Annots")
            if not annots:
                continue
            for annot_ref in annots:
                annot = annot_ref.get_object()
                if str(annot.get("/Subtype", "")) != "/Widget":
                    continue
                t_val = annot.get("/T")
                if t_val is None:
                    continue
                new_name = str(t_val) + suffix
                annot["/T"] = TextStringObject(new_name)

        writer.append(cloned_reader)

    # ------------------------------------------------------------------
    # Preview / introspection
    # ------------------------------------------------------------------

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
            "description": f"Mapping scaffold for {pdf_path.name}",
            "fields": [
                {"pdf_field": field["name"], "source": ""}
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

        if "first_of" in source:
            for path in source["first_of"]:
                value = self._lookup_path(data, str(path))
                if value not in (None, ""):
                    return value
            return source.get("default")

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
