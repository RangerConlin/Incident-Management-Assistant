from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Dict, List, Optional


@dataclass(slots=True)
class LayoutTemplate:
    """Metadata describing a saved ADS perspective and dashboard preset."""

    id: str
    name: str
    perspective_name: str
    description: str = ""
    ads_state: str = ""
    dashboard_widgets: List[str] = field(default_factory=list)
    is_default: bool = field(default=False, init=False, repr=False, compare=False)

    def to_dict(self) -> Dict[str, object]:
        data = asdict(self)
        data.pop("is_default", None)
        return data

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "LayoutTemplate":
        layout = cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            perspective_name=str(data.get("perspective_name", "")),
            description=str(data.get("description", "")),
            ads_state=str(data.get("ads_state", "")),
            dashboard_widgets=list(data.get("dashboard_widgets", []) or []),
        )
        layout.is_default = bool(data.get("is_default", False))
        return layout


@dataclass(slots=True)
class ThemeProfile:
    """Custom theme palette overrides."""

    id: str
    name: str
    base_theme: str
    description: str = ""
    tokens: Dict[str, str] = field(default_factory=dict)
    is_default: bool = field(default=False, init=False, repr=False, compare=False)

    def to_dict(self) -> Dict[str, object]:
        return {
            "id": self.id,
            "name": self.name,
            "base_theme": self.base_theme,
            "description": self.description,
            "tokens": dict(self.tokens),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "ThemeProfile":
        profile = cls(
            id=str(data.get("id", "")),
            name=str(data.get("name", "")),
            base_theme=str(data.get("base_theme", "light")),
            description=str(data.get("description", "")),
            tokens=dict(data.get("tokens", {}) or {}),
        )
        profile.is_default = bool(data.get("is_default", False))
        return profile


@dataclass(slots=True)
class CustomizationBundle:
    """Serializable export of customization metadata."""

    layouts: List[LayoutTemplate] = field(default_factory=list)
    themes: List[ThemeProfile] = field(default_factory=list)
    active_layout_id: Optional[str] = None
    active_theme_id: Optional[str] = None

    def to_dict(self) -> Dict[str, object]:
        return {
            "layouts": [layout.to_dict() for layout in self.layouts],
            "themes": [theme.to_dict() for theme in self.themes],
            "active_layout_id": self.active_layout_id,
            "active_theme_id": self.active_theme_id,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, object]) -> "CustomizationBundle":
        layouts = [LayoutTemplate.from_dict(entry) for entry in data.get("layouts", [])]
        themes = [ThemeProfile.from_dict(entry) for entry in data.get("themes", [])]
        return cls(
            layouts=layouts,
            themes=themes,
            active_layout_id=data.get("active_layout_id"),
            active_theme_id=data.get("active_theme_id"),
        )
