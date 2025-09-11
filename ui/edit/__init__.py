"""QtWidgets-based editors replacing previous QML dialogs.

This package provides a common :class:`BaseEditDialog` along with specific
entity editors such as :class:`RolesEditor`.  The editors are intentionally
light-weight so they can be invoked directly from the main window without
blocking other parts of the UI.
"""

from .base_dialog import BaseEditDialog  # re-export

__all__ = ["BaseEditDialog"]
