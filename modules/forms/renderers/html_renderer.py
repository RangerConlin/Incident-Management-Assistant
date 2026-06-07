from __future__ import annotations

from html import escape
from typing import Any


class HtmlRenderer:
    def render(self, instance: dict[str, Any], template_version: dict[str, Any]) -> str:
        rows = []
        values = instance.get("values", {})
        for field in template_version.get("fields", []):
            key = field.get("key")
            if not key:
                continue
            value = values.get(key, {}).get("display_value") or values.get(key, {}).get("value") or ""
            rows.append(f"<tr><th>{escape(field.get('label') or key)}</th><td>{escape(str(value))}</td></tr>")
        return "<html><body><table>" + "".join(rows) + "</table></body></html>"
