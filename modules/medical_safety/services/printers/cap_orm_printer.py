"""Convenience wrapper for printing CAP ORM worksheets."""

from modules.medical_safety.models.cap_form_models import CapFormTemplate
from modules.medical_safety.services.printers.cap_generic_form_printer import (
    print_cap_form,
)


def print_cap_orm(template: CapFormTemplate, data: dict, out_path: str) -> None:
    """Currently just delegates to :func:`print_cap_form`."""
    print_cap_form(template, data, out_path)
