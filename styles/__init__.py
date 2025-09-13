"""Style system package providing theme palettes and framework adapters."""

from .styles import (
    THEME_NAME,
    StyleBus,
    style_bus,
    get_palette,
    apply_app_palette,
    set_theme,
    subscribe_theme,
    team_status_colors,
    task_status_colors,
    TEAM_TYPE_COLORS,
)

__all__ = [
    'THEME_NAME',
    'StyleBus',
    'style_bus',
    'get_palette',
    'apply_app_palette',
    'set_theme',
    'subscribe_theme',
    'team_status_colors',
    'task_status_colors',
    'TEAM_TYPE_COLORS',
]
