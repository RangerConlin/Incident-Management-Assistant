from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Dict, List, Optional
from uuid import uuid4

from .models import LayoutTemplate, ThemeProfile, CustomizationBundle


DEFAULT_STORAGE = Path(os.getenv("UICUSTOMIZATION_STORAGE", "settings/ui_customization.json"))


class UICustomizationRepository:
    """Lightweight persistence layer for saved layouts and theme profiles."""

    def __init__(self, storage_path: Path | str | None = None):
        self._path = Path(storage_path or DEFAULT_STORAGE)
        if not self._path.parent.exists():
            self._path.parent.mkdir(parents=True, exist_ok=True)
        self._data: Dict[str, object] = {}
        self._load()

    # ------------------------------------------------------------------
    # Internal helpers
    def _load(self) -> None:
        if self._path.exists():
            try:
                self._data = json.loads(self._path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                self._data = {}
        if not isinstance(self._data, dict):
            self._data = {}
        self._data.setdefault("layouts", [])
        self._data.setdefault("themes", [])
        self._data.setdefault("active_layout_id", None)
        self._data.setdefault("active_theme_id", None)

    def _save(self) -> None:
        payload = json.dumps(self._data, indent=2, sort_keys=True)
        self._path.write_text(payload, encoding="utf-8")

    def _layout_index(self, layout_id: str) -> Optional[int]:
        layouts = self._data.get("layouts", [])
        for idx, entry in enumerate(layouts):
            if str(entry.get("id")) == layout_id:
                return idx
        return None

    def _theme_index(self, theme_id: str) -> Optional[int]:
        themes = self._data.get("themes", [])
        for idx, entry in enumerate(themes):
            if str(entry.get("id")) == theme_id:
                return idx
        return None

    # ------------------------------------------------------------------
    # Layout templates
    def list_layouts(self) -> List[LayoutTemplate]:
        layouts = []
        active_id = self._data.get("active_layout_id")
        for entry in self._data.get("layouts", []):
            layout = LayoutTemplate.from_dict(entry)
            if layout.ads_state is None:
                layout.ads_state = ""  # type: ignore[attr-defined]
            layouts.append(layout)
        layouts.sort(key=lambda l: l.name.lower())
        for layout in layouts:
            if layout.id == active_id:
                # annotate via attribute for convenience
                setattr(layout, "is_default", True)
        return layouts

    def get_layout(self, layout_id: str) -> Optional[LayoutTemplate]:
        idx = self._layout_index(layout_id)
        if idx is None:
            return None
        entry = self._data["layouts"][idx]
        layout = LayoutTemplate.from_dict(entry)
        if layout.ads_state is None:
            layout.ads_state = ""  # type: ignore[attr-defined]
        return layout

    def upsert_layout(self, layout: LayoutTemplate) -> LayoutTemplate:
        if not layout.id:
            layout = LayoutTemplate(
                id=uuid4().hex,
                name=layout.name,
                perspective_name=layout.perspective_name or f"custom_layout_{uuid4().hex}",
                description=layout.description,
                ads_state=layout.ads_state,
                dashboard_widgets=list(layout.dashboard_widgets),
            )
        idx = self._layout_index(layout.id)
        entry = layout.to_dict()
        if idx is None:
            self._data.setdefault("layouts", []).append(entry)
        else:
            self._data["layouts"][idx] = entry
        self._save()
        return layout

    def delete_layout(self, layout_id: str) -> None:
        idx = self._layout_index(layout_id)
        if idx is None:
            return
        layouts: List[Dict[str, object]] = self._data.get("layouts", [])
        layouts.pop(idx)
        if self._data.get("active_layout_id") == layout_id:
            self._data["active_layout_id"] = None
        self._save()

    def set_active_layout(self, layout_id: Optional[str]) -> None:
        if layout_id is not None and self._layout_index(layout_id) is None:
            raise ValueError("Layout not found")
        self._data["active_layout_id"] = layout_id
        self._save()

    def active_layout_id(self) -> Optional[str]:
        layout_id = self._data.get("active_layout_id")
        return str(layout_id) if layout_id else None

    # ------------------------------------------------------------------
    # Theme profiles
    def list_themes(self) -> List[ThemeProfile]:
        items = []
        active_id = self._data.get("active_theme_id")
        for entry in self._data.get("themes", []):
            theme = ThemeProfile.from_dict(entry)
            items.append(theme)
        items.sort(key=lambda t: t.name.lower())
        for theme in items:
            if theme.id == active_id:
                setattr(theme, "is_default", True)
        return items

    def get_theme(self, theme_id: str) -> Optional[ThemeProfile]:
        idx = self._theme_index(theme_id)
        if idx is None:
            return None
        entry = self._data["themes"][idx]
        return ThemeProfile.from_dict(entry)

    def upsert_theme(self, theme: ThemeProfile) -> ThemeProfile:
        if not theme.id:
            theme = ThemeProfile(
                id=uuid4().hex,
                name=theme.name,
                base_theme=theme.base_theme,
                description=theme.description,
                tokens=dict(theme.tokens),
            )
        idx = self._theme_index(theme.id)
        entry = theme.to_dict()
        if idx is None:
            self._data.setdefault("themes", []).append(entry)
        else:
            self._data["themes"][idx] = entry
        self._save()
        return theme

    def delete_theme(self, theme_id: str) -> None:
        idx = self._theme_index(theme_id)
        if idx is None:
            return
        themes: List[Dict[str, object]] = self._data.get("themes", [])
        themes.pop(idx)
        if self._data.get("active_theme_id") == theme_id:
            self._data["active_theme_id"] = None
        self._save()

    def set_active_theme(self, theme_id: Optional[str]) -> None:
        if theme_id is not None and self._theme_index(theme_id) is None:
            raise ValueError("Theme not found")
        self._data["active_theme_id"] = theme_id
        self._save()

    def active_theme_id(self) -> Optional[str]:
        theme_id = self._data.get("active_theme_id")
        return str(theme_id) if theme_id else None

    # ------------------------------------------------------------------
    # Export/import helpers
    def export_bundle(self) -> CustomizationBundle:
        bundle = CustomizationBundle(
            layouts=[LayoutTemplate.from_dict(entry) for entry in self._data.get("layouts", [])],
            themes=[ThemeProfile.from_dict(entry) for entry in self._data.get("themes", [])],
            active_layout_id=self.active_layout_id(),
            active_theme_id=self.active_theme_id(),
        )
        return bundle

    def import_bundle(self, bundle: CustomizationBundle, *, replace: bool = False) -> None:
        if replace:
            self._data["layouts"] = []
            self._data["themes"] = []
            self._data["active_layout_id"] = None
            self._data["active_theme_id"] = None

        existing_layouts = {entry.get("id"): entry for entry in self._data.get("layouts", [])}
        layout_id_map: Dict[str, str] = {}
        for layout in bundle.layouts:
            entry = layout.to_dict()
            original_id = layout.id
            new_id = original_id
            if original_id in existing_layouts and not replace:
                # generate a new id to avoid clobbering existing entry
                new_id = uuid4().hex
                entry["id"] = new_id
                entry["perspective_name"] = layout.perspective_name or f"custom_layout_{new_id}"
            layout_id_map[str(original_id)] = str(new_id)
            self._data.setdefault("layouts", []).append(entry)

        existing_themes = {entry.get("id"): entry for entry in self._data.get("themes", [])}
        theme_id_map: Dict[str, str] = {}
        for theme in bundle.themes:
            entry = theme.to_dict()
            original_id = theme.id
            new_id = original_id
            if original_id in existing_themes and not replace:
                new_id = uuid4().hex
                entry["id"] = new_id
            theme_id_map[str(original_id)] = str(new_id)
            self._data.setdefault("themes", []).append(entry)

        if bundle.active_layout_id:
            resolved_layout = layout_id_map.get(str(bundle.active_layout_id), bundle.active_layout_id)
            self._data["active_layout_id"] = resolved_layout
        if bundle.active_theme_id:
            resolved_theme = theme_id_map.get(str(bundle.active_theme_id), bundle.active_theme_id)
            self._data["active_theme_id"] = resolved_theme
        self._save()
