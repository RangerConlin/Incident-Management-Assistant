from __future__ import annotations

import textwrap
from dataclasses import asdict, is_dataclass
from typing import Any

from modules.forms_creator.exporting.builders.generic import _active_incident_id, _output_path
from modules.forms_creator.exporting.models import ExportRequest, PreparedExport
from modules.forms_creator.exporting.registry import ExportRegistry
from modules.forms_creator.exporting.service import utcnow_seconds
from modules.intel.repositories.intel_items_repo import IntelItemsRepository


def intel_form_key(form_id: str) -> str:
    return f"intel:{_normalize_form_id(form_id)}"


def intel_form_label(form_id: str) -> str:
    normalized = _normalize_form_id(form_id)
    prefix, _, suffix = normalized.partition("_")
    if prefix == "sar":
        return f"SAR {suffix.upper()}"
    return normalized.upper().replace("_", " ")


def _normalize_form_id(form_id: str) -> str:
    text = str(form_id or "").strip().lower().replace("-", "_").replace(" ", "_")
    compact = text.replace("_", "")
    if compact.startswith("sar") and not text.startswith("sar_"):
        return f"sar_{compact[3:]}"
    return text


def _as_dict(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if is_dataclass(value):
        return asdict(value)
    raw = getattr(value, "__dict__", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _pdf_text(value: object) -> str:
    return (
        str(value or "")
        .replace("\u2014", "-")
        .replace("\u2013", "-")
        .replace("\u2018", "'")
        .replace("\u2019", "'")
        .replace("\u201c", '"')
        .replace("\u201d", '"')
    )


def _latest_observation(observations: list[Any]) -> dict[str, Any]:
    rows = [_as_dict(obs) for obs in observations or []]
    if not rows:
        return {}
    return max(rows, key=lambda row: str(row.get("observed_at") or ""))


def _text_lines(value: object, *, width: int, count: int) -> list[str]:
    text = _pdf_text(value).strip()
    if not text:
        return [""] * count
    lines: list[str] = []
    for paragraph in text.splitlines():
        paragraph = paragraph.strip()
        if not paragraph:
            lines.append("")
            continue
        lines.extend(textwrap.wrap(paragraph, width=width, break_long_words=False, replace_whitespace=False))
    return (lines + [""] * count)[:count]


def _text_block(value: object, *, width: int, count: int) -> str:
    return "\n".join(_text_lines(value, width=width, count=count)).rstrip()


def _compact_join(parts: list[object]) -> str:
    values: list[str] = []
    seen: set[str] = set()
    for part in parts:
        text = _pdf_text(part).strip()
        if not text or text in seen:
            continue
        seen.add(text)
        values.append(text)
    return " - ".join(values)


def _datetime_display(value: object) -> str:
    text = _pdf_text(value).strip()
    if not text:
        return ""
    try:
        from utils.timefmt import abbreviate_tz_name, to_datetime

        dt = to_datetime(text)
        if dt is None:
            return text
        tz_abbr = abbreviate_tz_name(dt.tzname() or "")
        return f"{dt.strftime('%m/%d/%y %H:%M')} {tz_abbr}".strip()
    except Exception:
        return text


def _description_text(item_data: dict[str, Any], observations: list[Any]) -> str:
    initial = _compact_join([item_data.get("title"), item_data.get("notes")])
    observation_parts: list[str] = []
    for observation in sorted(
        (_as_dict(obs) for obs in observations or []),
        key=lambda row: str(row.get("observed_at") or ""),
    ):
        observed_at = _datetime_display(observation.get("observed_at"))
        body = _compact_join([observation.get("summary"), observation.get("detailed_notes")])
        if not body:
            continue
        prefix = f"Observation {observed_at}: " if observed_at else "Observation: "
        observation_parts.append(prefix + body)
    if initial and observation_parts:
        return initial + "\n\n" + "\n".join(observation_parts)
    if observation_parts:
        return "\n".join(observation_parts)
    return initial


def _merge_dicts(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    result = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _merge_dicts(result[key], value)
        else:
            result[key] = value
    return result


def _confidence_flags(confidence: object) -> dict[str, bool]:
    text = str(confidence or "").strip().lower()
    return {
        "very_likely_good": text == "confirmed",
        "probably_good": text == "probable",
        "may_be_good": text == "possible",
        "probably_not_good": text == "unlikely",
        "very_likely_not_good": text == "ruled out",
        "dont_know": text in {"", "unconfirmed", "unknown"},
    }


def _clue_display_number(item_data: dict[str, Any], clue_items: list[Any]) -> str:
    for key in ("clue_number", "display_number", "item_number", "number"):
        raw = item_data.get(key)
        if isinstance(raw, int):
            return f"C-{raw:03d}"
        text = _pdf_text(raw).strip()
        if text:
            return text

    target_id = str(item_data.get("id") or item_data.get("_id") or "")
    clue_rows = [_as_dict(row) for row in clue_items or []]
    clue_rows.sort(key=lambda row: (str(row.get("created_at") or ""), str(row.get("id") or row.get("_id") or "")))
    for index, row in enumerate(clue_rows, start=1):
        row_id = str(row.get("id") or row.get("_id") or "")
        if row_id == target_id:
            return f"C-{index:03d}"
    return "C-UNK"


def _clue_export_context(item: Any, clue_items: list[Any] | None = None) -> dict[str, Any]:
    item_data = _as_dict(item)
    observations = item_data.get("observations") or []
    observation = _latest_observation(observations)
    found_at = observation.get("observed_at") or item_data.get("created_at") or item_data.get("updated_at") or ""
    description = _description_text(item_data, observations)
    location = _pdf_text(observation.get("location_text") or item_data.get("location_text") or "")
    found_by = _pdf_text(observation.get("source_team") or "")
    located_by = _pdf_text(observation.get("observer") or item_data.get("created_by") or "")
    urgent = bool(item_data.get("urgent_response_needed"))

    sar_135 = {
        "clue_id": _clue_display_number(item_data, clue_items or []),
        "report_timestamp": found_at,
        "found_time": found_at,
        "found_by": found_by,
        "located_by": located_by,
        "description": description,
        "description_display": _text_block(description, width=68, count=6),
        "description_lines": _text_lines(description, width=68, count=6),
        "location": location,
        "location_display": _text_block(location, width=72, count=5),
        "location_lines": _text_lines(location, width=72, count=5),
        "urgent_response_needed": urgent,
        "information_only": not urgent,
        "response_due_time": "",
        "action": {
            "collect": False,
            "mark_and_leave": False,
            "disregard": False,
            "other": False,
            "other_text": "",
        },
        "confidence": _confidence_flags(item_data.get("confidence")),
        "segment_probabilities": {
            "completed_by_plans": "",
            "virtually_certain": "",
            "very_strong_in": "",
            "strong_in": "",
            "better_than_even_in": "",
            "no_information": "",
            "better_than_even_not_in": "",
            "strong_not_in": "",
            "very_strong_not_in": "",
            "list_segments": "",
            "prepared_by": "",
        },
        "route_to": {
            "plans": False,
            "investigations": False,
            "debriefing": False,
            "attach_to_clue": False,
            "other": False,
            "other_text": "",
        },
    }
    clue_row = {
        "clue_id": sar_135["clue_id"],
        "found_time": sar_135["found_time"],
        "found_by": sar_135["found_by"],
        "located_by": sar_135["located_by"],
        "description": sar_135["description"],
        "location": sar_135["location"],
    }
    return {
        "sar_135": sar_135,
        "clue": clue_row,
        "clues": [clue_row],
        "intel_item": item_data,
    }


class Sar135ClueFormBuilder:
    """Prepares a SAR 135 clue report export for one canonical Intel clue item."""

    form_id = "sar_135"
    form_set_id = "sar"

    def build(self, request: ExportRequest) -> PreparedExport:
        if request.target_id in (None, ""):
            raise ValueError("sar_135 export requires target_id (an intel clue item id)")

        incident_id = _active_incident_id(request)
        repo = IntelItemsRepository(incident_id)
        item = repo.get(str(request.target_id))
        if item is None:
            raise ValueError(f"Intel clue item not found: {request.target_id}")
        item_data = _as_dict(item)
        if str(item_data.get("item_type") or "").lower() != "clue":
            raise ValueError(f"SAR 135 requires an Intel item with item_type='Clue': {request.target_id}")
        clue_items = repo.list(item_type="Clue", include_deleted=True)

        generated_at = utcnow_seconds()
        extra_data = _clue_export_context(item, clue_items)
        manual = request.options.get("extra_data")
        if isinstance(manual, dict):
            extra_data = _merge_dicts(extra_data, manual)

        export_data: dict[str, Any] = {
            "form_id": self.form_id,
            "form_label": intel_form_label(self.form_id),
            "target_type": request.target_type or "intel_item",
            "target_id": request.target_id,
            "builder_level": self.form_id,
            "data_domain": "intel_clue",
        }
        existing_export_data = extra_data.get("export")
        if isinstance(existing_export_data, dict):
            export_data = {**existing_export_data, **export_data}
        extra_data["export"] = export_data

        return PreparedExport(
            form_id=self.form_id,
            output_path=_output_path(self.form_id, request, generated_at),
            incident_id=incident_id,
            form_set_id=request.form_set_id or self.form_set_id,
            extra_data=extra_data,
            metadata={
                "generated_at": generated_at,
                "form_label": intel_form_label(self.form_id),
                "builder_level": self.form_id,
                "data_domain": "intel_clue",
                "target_type": request.target_type or "intel_item",
                "target_id": request.target_id,
            },
        )


def register_intel_builders(registry: ExportRegistry) -> None:
    builder = Sar135ClueFormBuilder()
    registry.register(intel_form_key("sar_135"), builder)
    registry.register("sar_135", builder)
    registry.register(intel_form_label("sar_135"), builder)
