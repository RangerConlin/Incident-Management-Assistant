"""Register existing server exports; new domains provide their own builders/mappers."""
from __future__ import annotations

from .context import load_snapshot
from .mapping import build_sheets
from .models import ExportSnapshot, FormDefinition, ResolvedTemplate, TemplateSpec
from .organization import build_203_sheets
from .registry import ExportRegistry


def map_saved_records(snapshot: ExportSnapshot, template: ResolvedTemplate) -> list[dict]:
    return build_sheets(snapshot)


def map_organization(snapshot: ExportSnapshot, template: ResolvedTemplate) -> list[dict]:
    if template.mapping is None:
        raise ValueError("ICS 203 requires its registered form mapping")
    return build_203_sheets(snapshot, template.mapping)


def default_registry() -> ExportRegistry:
    registry = ExportRegistry()
    registry.register(FormDefinition(
        form_id="ics_203", label="ICS 203 - Organization Assignment List",
        source="organization", default_set="fema",
        templates=(TemplateSpec("fema", "ics_203.pdf", "ics_203.json"),
                   TemplateSpec("ics_canada", "ics_203_ics_canada.pdf", "ics_203_ics_canada.json"),
                   TemplateSpec("uscg", "ics_203_uscg.pdf", "ics_203_uscg.json")),
        builder=load_snapshot, mapper=map_organization, period_required=True,
        allow_source=False, minimum_font_size=6.0,
    ))
    existing = (
        ("ics_202", "Incident Objectives", "objectives", "fema"),
        ("ics_204", "Assignment List", "work_assignment", "fema"),
        ("ics_209", "Incident Status Summary", "sitrep", "ics_canada"),
        ("ics_211", "Check-In List", "checkin", "fema"),
        ("ics_213rr", "Resource Request", "resource_request", "fema"),
        ("ics_215", "Operational Planning Worksheet", "work_assignment", "ics_canada"),
        ("ics_215a", "Safety Analysis", "work_assignment", "fema"),
        ("ics_230", "Meeting Schedule", "meetings", "fema"),
    )
    for form_id, title, source, form_set in existing:
        publisher = "FEMA" if form_set == "fema" else "ICS Canada"
        label = f"{form_id.replace('_', ' ').upper()} - {title} ({publisher})"
        registry.register(FormDefinition(
            form_id=form_id, label=label, source=source, default_set=form_set,
            templates=(TemplateSpec(form_set, f"{form_id}.pdf"),),
            builder=load_snapshot, mapper=map_saved_records,
            source_required=source in {"work_assignment", "resource_request", "sitrep"},
        ))
    return registry
