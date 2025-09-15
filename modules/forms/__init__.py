"""Forms subsystem.

Historically this package only exposed :func:`render_form` for converting
structured data into PDFs.  The deterministic form export pipeline introduces
additional helpers such as :class:`FormRegistry`, :class:`FormSession` and the
high level :func:`export_form` utility.  The legacy API remains available while
new components are exported for newer code paths and tests.
"""

from .render import render_form  # legacy
from .form_registry import FormRegistry
from .session import FormSession
from .export import export_form
from .api import export_form_unified

__all__ = [
    "render_form",  # legacy
    "FormRegistry",
    "FormSession",
    "export_form",
    "export_form_unified",
]
