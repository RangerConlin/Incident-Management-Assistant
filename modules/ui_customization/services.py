from __future__ import annotations

import base64
from dataclasses import replace
from typing import Iterable, Optional

from PySide6.QtCore import QSettings, QByteArray

from .models import LayoutTemplate, ThemeProfile
from .repository import UICustomizationRepository


def _extract_state_from_settings(settings: QSettings, perspective_name: str) -> Optional[str]:
    settings.beginGroup("Perspectives")
    try:
        size_value = settings.value("size", 0)
        try:
            size = int(size_value)
        except (TypeError, ValueError):
            size = 0
        for idx in range(1, size + 1):
            name = settings.value(f"{idx}\\Name")
            if str(name) == perspective_name:
                raw = settings.value(f"{idx}\\State")
                if isinstance(raw, QByteArray):
                    return base64.b64encode(bytes(raw)).decode("ascii")
                if isinstance(raw, (bytes, bytearray)):
                    return base64.b64encode(bytes(raw)).decode("ascii")
                if raw is None:
                    return None
                return base64.b64encode(str(raw).encode("utf-8")).decode("ascii")
    finally:
        settings.endGroup()
    return None


def capture_layout_state(dock_manager, perspective_file: str, perspective_name: str) -> Optional[str]:
    """Persist the current perspective state and return an encoded snapshot."""

    settings = QSettings(perspective_file, QSettings.IniFormat)
    try:
        try:
            dock_manager.removePerspective(perspective_name)
        except Exception:
            pass
        dock_manager.addPerspective(perspective_name)
        dock_manager.savePerspectives(settings)
        settings.sync()
        return _extract_state_from_settings(settings, perspective_name)
    finally:
        del settings


def apply_layout_state(dock_manager, perspective_file: str, perspective_name: str, encoded_state: str) -> bool:
    """Apply an encoded layout state to the dock manager."""

    if not encoded_state:
        return False

    raw = base64.b64decode(encoded_state.encode("ascii"))
    settings = QSettings(perspective_file, QSettings.IniFormat)
    try:
        settings.beginGroup("Perspectives")
        size_value = settings.value("size", 0)
        try:
            size = int(size_value)
        except (TypeError, ValueError):
            size = 0
        target_idx: Optional[int] = None
        for idx in range(1, size + 1):
            if str(settings.value(f"{idx}\\Name")) == perspective_name:
                target_idx = idx
                break
        if target_idx is None:
            target_idx = size + 1
        settings.setValue("size", max(size, target_idx))
        settings.setValue(f"{target_idx}\\Name", perspective_name)
        settings.setValue(f"{target_idx}\\State", QByteArray(raw))
        settings.endGroup()
        settings.sync()
        try:
            dock_manager.removePerspective(perspective_name)
        except Exception:
            pass
        dock_manager.loadPerspectives(settings)
        rv = dock_manager.openPerspective(perspective_name)
        return bool(rv) if rv is not None else True
    finally:
        del settings


def register_dashboard_widgets(repo: UICustomizationRepository, layout_id: str, widgets: Iterable[str]) -> LayoutTemplate:
    layout = repo.get_layout(layout_id)
    if not layout:
        raise ValueError("Layout not found")
    updated = replace(layout, dashboard_widgets=list(widgets))
    return repo.upsert_layout(updated)


def apply_theme_profile(theme: ThemeProfile, theme_manager, settings_bridge=None) -> None:
    """Register and activate a custom theme profile."""

    if not theme_manager:
        return

    try:
        register = getattr(theme_manager, "register_custom_theme")
        apply_custom = getattr(theme_manager, "apply_custom_theme")
    except AttributeError:
        return

    register(theme.id, theme.tokens, base_theme=theme.base_theme)
    apply_custom(theme.id)
    if settings_bridge is not None and hasattr(settings_bridge, "setSetting"):
        settings_bridge.setSetting("themeName", f"custom:{theme.id}")


def ensure_active_theme(repo: UICustomizationRepository, theme_manager, settings_bridge=None) -> None:
    theme_id = repo.active_theme_id()
    if not theme_id:
        return
    theme = repo.get_theme(theme_id)
    if not theme:
        return
    apply_theme_profile(theme, theme_manager, settings_bridge)


def ensure_active_layout(repo: UICustomizationRepository, dock_manager, perspective_file: str) -> bool:
    layout_id = repo.active_layout_id()
    if not layout_id:
        return False
    layout = repo.get_layout(layout_id)
    if not layout or not layout.ads_state:
        return False
    return apply_layout_state(dock_manager, perspective_file, layout.perspective_name, layout.ads_state)
