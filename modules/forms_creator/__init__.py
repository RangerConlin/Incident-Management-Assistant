"""SARApp Form Creator package.

Unified Forms Engine is now the preferred service layer; this package remains
available for older authoring tools during migration.
"""

from .services.templates import FormService

__all__ = ["FormService"]
