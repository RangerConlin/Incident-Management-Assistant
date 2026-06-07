from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time
from typing import Any


@dataclass(slots=True)
class ValidationResult:
    field_key: str | None
    severity: str
    message: str
    blocking: bool = True


class ValidationService:
    def validate_fields(self, fields: list[dict[str, Any]], values: dict[str, Any], *, status: str = "draft") -> list[ValidationResult]:
        results: list[ValidationResult] = []
        if status == "finalized":
            results.append(ValidationResult(None, "info", "finalized forms are read-only", False))
        for field in fields:
            key = field.get("key")
            value = values.get(key, {}).get("value") if isinstance(values.get(key), dict) else values.get(key)
            if field.get("required") and value in (None, "", []):
                results.append(ValidationResult(key, "error", "required value is empty", True))
                continue
            if value in (None, ""):
                continue
            field_type = field.get("field_type", "text")
            if not self._valid_type(field_type, value):
                results.append(ValidationResult(key, "error", f"value does not match {field_type}", True))
            options = field.get("options") or []
            if options and field_type in {"select", "multi_select"}:
                chosen = value if isinstance(value, list) else [value]
                allowed = {o.get("value", o) if isinstance(o, dict) else o for o in options}
                if any(item not in allowed for item in chosen):
                    results.append(ValidationResult(key, "error", "value is not an available option", True))
            for rule in field.get("validation_rules") or []:
                results.extend(self._check_rule(key, value, rule))
        return results

    def _valid_type(self, field_type: str, value: Any) -> bool:
        if field_type in {"text", "multiline_text", "signature", "attachment_reference", "calculated", "hidden"}:
            return True
        if field_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if field_type == "number":
            return isinstance(value, (int, float)) and not isinstance(value, bool)
        if field_type in {"checkbox", "boolean"}:
            return isinstance(value, bool)
        if field_type in {"select", "date", "time", "datetime"}:
            return isinstance(value, str) or isinstance(value, (date, time, datetime))
        if field_type in {"multi_select", "table", "repeater"}:
            return isinstance(value, list)
        return True

    def _check_rule(self, key: str | None, value: Any, rule: dict[str, Any]) -> list[ValidationResult]:
        results: list[ValidationResult] = []
        rtype = rule.get("rule_type") or rule.get("type")
        limit = rule.get("value")
        message = rule.get("message") or "validation rule failed"
        if rtype == "min_length" and len(str(value)) < int(limit):
            results.append(ValidationResult(key, rule.get("severity", "error"), message, bool(rule.get("blocking", True))))
        if rtype == "max_length" and len(str(value)) > int(limit):
            results.append(ValidationResult(key, rule.get("severity", "error"), message, bool(rule.get("blocking", True))))
        if rtype == "min" and float(value) < float(limit):
            results.append(ValidationResult(key, rule.get("severity", "error"), message, bool(rule.get("blocking", True))))
        if rtype == "max" and float(value) > float(limit):
            results.append(ValidationResult(key, rule.get("severity", "error"), message, bool(rule.get("blocking", True))))
        if rtype == "min_rows" and isinstance(value, list) and len(value) < int(limit):
            results.append(ValidationResult(key, rule.get("severity", "error"), message, bool(rule.get("blocking", True))))
        if rtype == "max_rows" and isinstance(value, list) and len(value) > int(limit):
            results.append(ValidationResult(key, rule.get("severity", "error"), message, bool(rule.get("blocking", True))))
        return results
