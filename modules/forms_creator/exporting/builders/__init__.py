from __future__ import annotations

from modules.forms_creator.exporting.registry import ExportRegistry

from .communications import register_communications_builders
from .generic import register_generic_builders
from .ics import register_ics_builders
from .intel import register_intel_builders
from .medical import register_medical_builders
from .task_assignments import register_task_assignment_builders
from .work_assignments import register_work_assignment_builders


def default_registry() -> ExportRegistry:
    registry = ExportRegistry()
    register_generic_builders(registry)
    register_ics_builders(registry)
    # Registered after the generic ICS builders so its ics_205-specific
    # builder (live channel plan + per-op-period special instructions)
    # overrides the generic passthrough entry registered above.
    register_communications_builders(registry)
    # Registered after the generic ICS builders so the ICS-206 medical-plan
    # builder can scope medical sections to the selected operational period.
    register_medical_builders(registry)
    # Registered after the generic SAR builders so SAR 135's clue-scoped
    # builder overrides the generic passthrough entry registered above.
    register_intel_builders(registry)
    register_task_assignment_builders(registry)
    register_work_assignment_builders(registry)
    return registry


__all__ = [
    "default_registry",
    "register_communications_builders",
    "register_generic_builders",
    "register_ics_builders",
    "register_intel_builders",
    "register_medical_builders",
    "register_task_assignment_builders",
    "register_work_assignment_builders",
]
