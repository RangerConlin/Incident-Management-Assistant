"""SARApp Forms Creator — primary form authoring and binding management tool.

HubWindow (ui/HubWindow.py) is the active entry point: catalog browser,
version matrix, and graphical binding editor (MapperWindow / NewBindingDialog).
Accessible via Developer → Forms Creator.
"""

from .services.templates import FormService

__all__ = ["FormService"]
