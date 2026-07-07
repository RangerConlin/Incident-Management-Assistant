"""Release preview generation service."""
from __future__ import annotations

from html import escape
from typing import Any

from modules.public_information.models.records import utc_now


def apply_merge_fields(text: str, message: dict[str, Any], template: dict[str, Any] | None = None) -> str:
    template = template or {}
    fields = {
        "{incident_name}": message.get("related_incident_id", ""),
        "{incident_number}": message.get("related_incident_id", ""),
        "{operational_period}": message.get("related_operational_period_id", ""),
        "{release_datetime}": message.get("published_at") or message.get("updated_at") or utc_now(),
        "{prepared_by}": message.get("created_by", ""),
        "{approved_by}": message.get("approved_by", ""),
        "{pio_contact_name}": "",
        "{pio_contact_phone}": "",
        "{agency_name}": template.get("agency_name", ""),
        "{release_title}": message.get("title", ""),
        "{release_subtitle}": message.get("subtitle", ""),
        "{release_body}": message.get("body", ""),
        "{next_update_time}": message.get("next_update_statement", ""),
        "{boilerplate}": message.get("boilerplate", ""),
        "{public_summary}": message.get("body", "")[:500],
    }
    rendered = text or ""
    for key, value in fields.items():
        rendered = rendered.replace(key, str(value or ""))
    return rendered


def build_release_html(message: dict[str, Any] | None, template: dict[str, Any] | None = None) -> str:
    message = message or {}
    template = template or {}
    header = apply_merge_fields(template.get("header_text", ""), message, template)
    footer = apply_merge_fields(template.get("footer_text", ""), message, template)
    contact = apply_merge_fields(template.get("contact_block", ""), message, template)
    parts = [
        "<article>",
        f"<h3>{escape(template.get('agency_name', '') or '')}</h3>" if template.get("agency_name") else "",
        f"<pre>{escape(header)}</pre>" if header else "",
        f"<p><strong>{escape(template.get('release_label', '') or message.get('type', ''))}</strong></p>",
        f"<h1>{escape(message.get('title', ''))}</h1>",
        f"<h2>{escape(message.get('subtitle', ''))}</h2>" if message.get("subtitle") else "",
        f"<p><strong>{escape(message.get('dateline', ''))}</strong></p>" if message.get("dateline") else "",
        f"<div>{escape(message.get('body', '')).replace(chr(10), '<br>')}</div>",
        f"<p><strong>Next Update:</strong> {escape(message.get('next_update_statement', ''))}</p>" if message.get("next_update_statement") else "",
        f"<pre>{escape(message.get('boilerplate', ''))}</pre>" if message.get("boilerplate") else "",
        f"<pre>{escape(contact)}</pre>" if contact else "",
        f"<pre>{escape(footer)}</pre>" if footer else "",
        f"<p><em>{escape(template.get('default_footer_disclaimer', '') or '')}</em></p>" if template.get("default_footer_disclaimer") else "",
        "</article>",
    ]
    return "\n".join(part for part in parts if part)
