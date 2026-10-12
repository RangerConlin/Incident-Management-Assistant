"""UI customization package entry points."""

from .repository import UICustomizationRepository
from .models import LayoutTemplate, ThemeProfile, CustomizationBundle
from . import services


def get_layout_manager_panel(main_window):
    from .panels.layout_manager_panel import get_layout_manager_panel as _impl

    return _impl(main_window)


def get_dashboard_designer_panel(main_window):
    from .panels.dashboard_designer_panel import (
        get_dashboard_designer_panel as _impl,
    )

    return _impl(main_window)


def get_theme_editor_panel(main_window):
    from .panels.theme_editor_panel import get_theme_editor_panel as _impl

    return _impl(main_window)


__all__ = [
    "UICustomizationRepository",
    "LayoutTemplate",
    "ThemeProfile",
    "CustomizationBundle",
    "services",
    "get_layout_manager_panel",
    "get_dashboard_designer_panel",
    "get_theme_editor_panel",
]
