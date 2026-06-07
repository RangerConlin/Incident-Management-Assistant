from __future__ import annotations

from typing import Any


class SummaryRenderer:
    def render(self, instance: dict[str, Any], template_version: dict[str, Any]) -> str:
        lines = [f"{instance.get('title') or 'Form'}", f"Agency: {instance.get('agency') or ''}", f"Revision: {instance.get('revision_number')}", ""]
        values = instance.get("values", {})
        for field in template_version.get("fields", []):
            key = field.get("key")
            if not key:
                continue
            label = field.get("label") or key
            value = values.get(key, {}).get("display_value") or values.get(key, {}).get("value") or ""
            lines.append(f"{label}: {value}")
        return "\n".join(lines) + "\n"
